import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/messenger_session.dart';
import '../widgets/auth_avatar.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final TextEditingController _nick;
  late final TextEditingController _status;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final me = context.read<MessengerSession>().me;
    _nick = TextEditingController(text: me?['nickname'] as String? ?? '');
    _status = TextEditingController(
      text: me?['status_message'] as String? ?? '',
    );
  }

  @override
  void dispose() {
    _nick.dispose();
    _status.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await context.read<MessengerSession>().updateProfile(
        nickname: _nick.text.trim(),
        statusMessage: _status.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Profile updated')));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pickAvatar() async {
    final r = await FilePicker.platform.pickFiles(
      withData: false,
      type: FileType.image,
    );
    if (r == null || r.files.single.path == null) return;
    try {
      if (!mounted) return;
      await context.read<MessengerSession>().uploadAvatar(
        File(r.files.single.path!),
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Avatar updated')));
        setState(() {});
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Avatar update failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<MessengerSession>();
    final me = session.me;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  AuthAvatar(
                    avatarUrl: me?['avatar_url'] as String?,
                    accessToken: session.accessToken,
                    radius: 34,
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          me?['nickname'] as String? ?? '',
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 2),
                        Text('@${me?['username'] ?? ''}'),
                        Text(me?['email'] as String? ?? ''),
                      ],
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _pickAvatar,
                    icon: const Icon(Icons.photo_camera_outlined),
                    label: const Text('Avatar'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Public profile',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _nick,
                    maxLength: 50,
                    decoration: const InputDecoration(
                      labelText: 'Display name',
                      prefixIcon: Icon(Icons.badge_outlined),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _status,
                    maxLines: 3,
                    maxLength: 160,
                    decoration: const InputDecoration(
                      labelText: 'Status message',
                      prefixIcon: Icon(Icons.notes_outlined),
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: _saving ? null : _save,
                    child: _saving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Save changes'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
