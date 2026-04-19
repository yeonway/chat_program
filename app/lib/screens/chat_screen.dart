import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/api_models.dart';
import '../services/messenger_session.dart';
import '../widgets/auth_avatar.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.conversationId});

  final int conversationId;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _text = TextEditingController();
  final _scrollController = ScrollController();
  List<MessageDto> _messages = [];
  bool _loading = true;
  bool _sending = false;
  StreamSubscription<Map<String, dynamic>>? _sub;
  double? _uploadProgress;

  int get _myId =>
      (context.read<MessengerSession>().me?['id'] as num?)?.toInt() ?? -1;

  @override
  void initState() {
    super.initState();
    _load();
    _sub = context.read<MessengerSession>().wsEvents.stream.listen(_onWs);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _text.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onWs(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    if (type == 'message.new') {
      final payload = Map<String, dynamic>.from(data['payload'] as Map);
      final cid = (payload['conversation_id'] as num?)?.toInt();
      if (cid != widget.conversationId) return;
      final msg = MessageDto.fromJson(payload);
      if (!mounted) return;
      setState(() {
        if (!_messages.any((m) => m.id == msg.id)) {
          _messages.add(msg);
        }
      });
      _scrollToBottom();
      _tryMarkRead();
      context.read<MessengerSession>().loadConversations();
    }
    if (type == 'message.read') {
      final p = data['payload'] as Map<String, dynamic>?;
      final cid = (p?['conversation_id'] as num?)?.toInt();
      if (cid != widget.conversationId) return;
      _load(silent: true);
    }
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) setState(() => _loading = true);
    try {
      final list = await context.read<MessengerSession>().fetchMessages(
        widget.conversationId,
      );
      if (!mounted) return;
      setState(() => _messages = list);
      _scrollToBottom();
      await _tryMarkRead();
    } finally {
      if (!silent && mounted) setState(() => _loading = false);
    }
  }

  Future<void> _tryMarkRead() async {
    if (_messages.isEmpty) return;
    final lastId = _messages.last.id;
    try {
      await context.read<MessengerSession>().markRead(
        widget.conversationId,
        lastId,
      );
    } catch (_) {}
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send() async {
    final t = _text.text.trim();
    if (t.isEmpty || _sending) return;
    setState(() => _sending = true);
    _text.clear();
    final session = context.read<MessengerSession>();
    try {
      final msg = await session.sendTextMessage(widget.conversationId, t);
      if (!mounted) return;
      setState(() => _messages.add(msg));
      _scrollToBottom();
      await session.loadConversations();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Failed to send: $e')));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _pickAndUpload() async {
    final session = context.read<MessengerSession>();
    final pick = await FilePicker.platform.pickFiles(
      withData: false,
      type: FileType.custom,
      allowedExtensions: MessengerSession.allowedUploadExtensions,
    );
    if (pick == null || pick.files.single.path == null) return;
    final path = pick.files.single.path!;
    final file = File(path);
    setState(() => _uploadProgress = 0);
    try {
      final fid = await session.uploadFileChunked(
        file,
        onProgress: (p) => setState(() => _uploadProgress = p),
      );
      final caption = pick.files.single.name;
      final msg = await session.sendTextMessage(
        widget.conversationId,
        caption,
        fileId: fid,
      );
      if (!mounted) return;
      setState(() {
        _messages.add(msg);
        _uploadProgress = null;
      });
      _scrollToBottom();
      await session.loadConversations();
    } catch (e) {
      if (!mounted) return;
      setState(() => _uploadProgress = null);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(_uploadErrorMessage(e))));
    }
  }

  String _uploadErrorMessage(Object e) {
    if (e is DioException) {
      final data = e.response?.data;
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return 'Upload failed: $detail';
        }
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map && first['msg'] is String) {
            return 'Upload failed: ${first['msg']}';
          }
        }
      }
      if (e.message != null && e.message!.trim().isNotEmpty) {
        return 'Upload failed: ${e.message}';
      }
    }
    return 'Upload failed. Please try another file.';
  }

  String _formatTime(String iso) {
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return '';
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<MessengerSession>();
    final match = session.conversations
        .where((c) => c.id == widget.conversationId)
        .toList();
    final other = match.isEmpty ? null : match.first.otherUser;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            AuthAvatar(
              avatarUrl: other?.avatarUrl,
              accessToken: session.accessToken,
              radius: 18,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(other?.nickname ?? 'Conversation'),
                  Text(
                    other?.online == true ? 'Online' : 'Offline',
                    style: TextStyle(
                      fontSize: 12,
                      color: other?.online == true
                          ? const Color(0xFF16A34A)
                          : Colors.black54,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_uploadProgress != null)
            LinearProgressIndicator(value: _uploadProgress),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                ? Center(
                    child: Text(
                      'No messages yet.\nSay hello first.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  )
                : ListView.separated(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
                    itemCount: _messages.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 4),
                    itemBuilder: (_, i) {
                      final m = _messages[i];
                      final mine = m.senderId == _myId;
                      final bubbleColor = mine
                          ? Theme.of(context).colorScheme.primaryContainer
                          : Theme.of(
                              context,
                            ).colorScheme.surfaceContainerHighest;
                      return Align(
                        alignment: mine
                            ? Alignment.centerRight
                            : Alignment.centerLeft,
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 480),
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: bubbleColor,
                              borderRadius: BorderRadius.only(
                                topLeft: const Radius.circular(14),
                                topRight: const Radius.circular(14),
                                bottomLeft: Radius.circular(mine ? 14 : 4),
                                bottomRight: Radius.circular(mine ? 4 : 14),
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 8,
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (m.fileId != null)
                                    Text(
                                      'Attachment #${m.fileId}: ${session.fileDownloadUrl(m.fileId!)}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(
                                            color: Theme.of(
                                              context,
                                            ).colorScheme.primary,
                                            fontWeight: FontWeight.w600,
                                          ),
                                    ),
                                  if (m.body.isNotEmpty) ...[
                                    if (m.fileId != null)
                                      const SizedBox(height: 5),
                                    Text(m.body),
                                  ],
                                  const SizedBox(height: 4),
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        _formatTime(m.createdAt),
                                        style: Theme.of(
                                          context,
                                        ).textTheme.labelSmall,
                                      ),
                                      if (mine) ...[
                                        const SizedBox(width: 8),
                                        Text(
                                          m.readByPeer ? 'Read' : 'Sent',
                                          style: Theme.of(context)
                                              .textTheme
                                              .labelSmall
                                              ?.copyWith(
                                                fontWeight: FontWeight.w700,
                                              ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          SafeArea(
            top: false,
            minimum: const EdgeInsets.fromLTRB(10, 8, 10, 10),
            child: Row(
              children: [
                IconButton(
                  tooltip: 'Attach file',
                  icon: const Icon(Icons.attach_file),
                  onPressed: _pickAndUpload,
                ),
                Expanded(
                  child: TextField(
                    controller: _text,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: const InputDecoration(
                      hintText: 'Write a message',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _sending ? null : _send,
                  style: FilledButton.styleFrom(minimumSize: const Size(0, 44)),
                  child: _sending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.send_rounded),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
