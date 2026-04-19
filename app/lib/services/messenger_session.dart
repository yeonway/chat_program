import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:mime/mime.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/api_config.dart';
import '../models/api_models.dart';

/// 인증, REST, WebSocket, 청크 업로드를 묶은 세션 (Provider로 제공).
class MessengerSession extends ChangeNotifier {
  static const List<String> allowedUploadExtensions = <String>[
    'pdf',
    'zip',
    'png',
    'jpg',
    'jpeg',
    'gif',
    'webp',
    'txt',
    'mp4',
    'mp3',
    'doc',
    'docx',
  ];

  MessengerSession() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final t = accessToken;
          if (t != null && t.isNotEmpty) {
            options.headers['Authorization'] = ApiConfig.bearer(t);
          }
          handler.next(options);
        },
        onError: (err, handler) async {
          if (err.response?.statusCode == 401 &&
              refreshToken != null &&
              err.requestOptions.extra['retried'] != true) {
            final ok = await _refreshTokens();
            if (ok) {
              final ro = err.requestOptions;
              ro.extra['retried'] = true;
              ro.headers['Authorization'] = ApiConfig.bearer(accessToken!);
              try {
                final res = await _dio.fetch(ro);
                handler.resolve(res);
                return;
              } catch (e) {
                if (e is DioException) {
                  handler.next(e);
                  return;
                }
              }
            }
            await logout();
          }
          handler.next(err);
        },
      ),
    );
  }

  late final Dio _dio;
  final FlutterSecureStorage _secure = const FlutterSecureStorage();

  String? accessToken;
  String? refreshToken;
  Map<String, dynamic>? me;
  List<ConversationItem> conversations = [];
  WebSocketChannel? _ws;
  StreamSubscription<dynamic>? _wsSub;
  Timer? _pingTimer;
  bool _refreshing = false;
  bool _wsAuthed = false;

  /// 채팅 화면에서 실시간으로 붙일 메시지 스트림 (conversationId → 콜크는 ChatScreen에서)
  final StreamController<Map<String, dynamic>> wsEvents =
      StreamController<Map<String, dynamic>>.broadcast();

  bool get isLoggedIn => accessToken != null && accessToken!.isNotEmpty;

  Future<void> bootstrap() async {
    accessToken = await _secure.read(key: 'access');
    refreshToken = await _secure.read(key: 'refresh');
    notifyListeners();
    if (isLoggedIn) {
      await loadMe();
      await loadConversations();
      await connectWebSocket();
    }
  }

  Future<void> _persistTokens() async {
    if (accessToken != null) {
      await _secure.write(key: 'access', value: accessToken);
    } else {
      await _secure.delete(key: 'access');
    }
    if (refreshToken != null) {
      await _secure.write(key: 'refresh', value: refreshToken);
    } else {
      await _secure.delete(key: 'refresh');
    }
  }

  Future<bool> _refreshTokens() async {
    if (_refreshing || refreshToken == null) return false;
    _refreshing = true;
    try {
      final res = await Dio(BaseOptions(baseUrl: ApiConfig.baseUrl))
          .post<Map<String, dynamic>>(
            '/auth/refresh',
            data: {'refresh_token': refreshToken},
          );
      accessToken = res.data?['access_token'] as String?;
      refreshToken = res.data?['refresh_token'] as String?;
      await _persistTokens();
      return accessToken != null;
    } catch (_) {
      return false;
    } finally {
      _refreshing = false;
    }
  }

  Future<void> login(String login, String password) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {'login': login, 'password': password},
    );
    accessToken = res.data?['access_token'] as String?;
    refreshToken = res.data?['refresh_token'] as String?;
    await _persistTokens();
    await loadMe();
    await loadConversations();
    await connectWebSocket();
    notifyListeners();
  }

  Future<void> register({
    required String email,
    required String username,
    required String password,
    required String nickname,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/auth/register',
      data: {
        'email': email,
        'username': username,
        'password': password,
        'nickname': nickname,
      },
    );
    accessToken = res.data?['access_token'] as String?;
    refreshToken = res.data?['refresh_token'] as String?;
    await _persistTokens();
    await loadMe();
    await loadConversations();
    await connectWebSocket();
    notifyListeners();
  }

  Future<void> logout() async {
    final rt = refreshToken;
    try {
      if (rt != null) {
        await Dio(
          BaseOptions(baseUrl: ApiConfig.baseUrl),
        ).post('/auth/logout', data: {'refresh_token': rt});
      }
    } catch (_) {}
    await disconnectWebSocket();
    accessToken = null;
    refreshToken = null;
    me = null;
    conversations = [];
    await _persistTokens();
    notifyListeners();
  }

  Future<void> loadMe() async {
    if (!isLoggedIn) return;
    final res = await _dio.get<Map<String, dynamic>>('/users/me');
    me = res.data;
    notifyListeners();
  }

  Future<void> loadConversations() async {
    if (!isLoggedIn) return;
    final res = await _dio.get<List<dynamic>>('/conversations');
    final list = res.data ?? [];
    conversations = list
        .map(
          (e) => ConversationItem.fromJson(Map<String, dynamic>.from(e as Map)),
        )
        .toList();
    _applyPresenceToConversations();
    notifyListeners();
  }

  void _applyPresenceToConversations() {
    for (final c in conversations) {
      final o = c.otherUser;
      if (o == null) continue;
      final on = _online[o.id];
      if (on != null) c.otherUser = o.copyWith(online: on);
    }
  }

  final Map<int, bool> _online = {};

  Future<void> connectWebSocket() async {
    await disconnectWebSocket();
    final t = accessToken;
    if (t == null) return;
    _wsAuthed = false;
    try {
      final uri = ApiConfig.wsUri();
      _ws = WebSocketChannel.connect(uri);
      _wsSub = _ws!.stream.listen(
        (event) {
          if (event is String) {
            final map = jsonDecode(event) as Map<String, dynamic>;
            final type = map['type'] as String?;
            if (!_wsAuthed) {
              if (type == 'auth.ok') {
                _wsAuthed = true;
                _startWsPing();
                return;
              }
              if (type == 'auth.error') {
                disconnectWebSocket();
                return;
              }
              return;
            }
            _onWsJson(map);
          }
        },
        onError: (_) {},
        onDone: () {},
      );
      _ws!.sink.add(jsonEncode({'type': 'auth', 'token': t}));
    } catch (_) {}
  }

  void _startWsPing() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 45), (_) {
      final ch = _ws;
      if (ch == null || !_wsAuthed) return;
      try {
        ch.sink.add(jsonEncode({'type': 'ping'}));
      } catch (_) {}
    });
  }

  Future<void> disconnectWebSocket() async {
    _wsAuthed = false;
    _pingTimer?.cancel();
    _pingTimer = null;
    await _wsSub?.cancel();
    _wsSub = null;
    await _ws?.sink.close();
    _ws = null;
  }

  void _onWsJson(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    if (type == 'presence.update') {
      final uid = (data['user_id'] as num?)?.toInt();
      final online = data['online'] as bool?;
      if (uid != null && online != null) {
        _online[uid] = online;
        for (final c in conversations) {
          if (c.otherUser?.id == uid) {
            c.otherUser = c.otherUser!.copyWith(online: online);
          }
        }
        notifyListeners();
      }
    }
    wsEvents.add(data);
  }

  Future<List<UserPublic>> searchUsers(String q) async {
    if (q.trim().length < 2) return [];
    final res = await _dio.get<List<dynamic>>(
      '/users/search',
      queryParameters: {'q': q.trim()},
    );
    return (res.data ?? [])
        .map((e) => UserPublic.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<int> createOrGetDirect(int otherUserId) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/conversations/direct',
      data: {'other_user_id': otherUserId},
    );
    return res.data!['id'] as int;
  }

  Future<List<MessageDto>> fetchMessages(
    int conversationId, {
    int? beforeId,
  }) async {
    final res = await _dio.get<List<dynamic>>(
      '/conversations/$conversationId/messages',
      queryParameters: {
        if (beforeId != null) 'before_id': beforeId,
        'limit': 80,
      },
    );
    return (res.data ?? [])
        .map((e) => MessageDto.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<MessageDto> sendTextMessage(
    int conversationId,
    String body, {
    int? fileId,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/conversations/$conversationId/messages',
      data: {'body': body, if (fileId != null) 'file_id': fileId},
    );
    return MessageDto.fromJson(Map<String, dynamic>.from(res.data!));
  }

  Future<void> markRead(int conversationId, int upToMessageId) async {
    await _dio.post(
      '/conversations/$conversationId/read',
      data: {'up_to_message_id': upToMessageId},
    );
    await loadConversations();
  }

  /// 청크 업로드 후 file_id 반환. [onProgress]는 0.0~1.0
  Future<int> uploadFileChunked(
    File file, {
    void Function(double progress)? onProgress,
  }) async {
    final name = file.path.split(Platform.pathSeparator).last;
    final bytes = await file.readAsBytes();
    final mime = lookupMimeType(name) ?? 'application/octet-stream';
    final init = await _dio.post<Map<String, dynamic>>(
      '/files/upload/init',
      data: {'filename': name, 'size': bytes.length, 'mime_type': mime},
    );
    final fileId = init.data!['file_id'] as int;
    final chunkSize = init.data!['chunk_size'] as int;
    final expected = init.data!['expected_chunks'] as int;
    for (var i = 0; i < expected; i++) {
      final start = i * chunkSize;
      final end = min(start + chunkSize, bytes.length);
      final slice = bytes.sublist(start, end);
      await _dio.put(
        '/files/upload/$fileId/chunk',
        queryParameters: {'index': i},
        data: slice,
        options: Options(
          headers: {'Content-Type': 'application/octet-stream'},
          contentType: 'application/octet-stream',
        ),
      );
      onProgress?.call((i + 1) / expected);
    }
    await _dio.post('/files/upload/$fileId/complete');
    return fileId;
  }

  String fileDownloadUrl(int fileId) => '${ApiConfig.baseUrl}/files/$fileId';

  Future<void> updateProfile({String? nickname, String? statusMessage}) async {
    await _dio.patch(
      '/users/me',
      data: {
        if (nickname != null) 'nickname': nickname,
        if (statusMessage != null) 'status_message': statusMessage,
      },
    );
    await loadMe();
    notifyListeners();
  }

  /// 프로필 이미지 (multipart). 서버가 `/users/avatar/{filename}` 경로를 반환합니다.
  Future<void> uploadAvatar(File file) async {
    final name = file.path.split(Platform.pathSeparator).last;
    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: name),
    });
    await _dio.post('/users/me/avatar', data: form);
    await loadMe();
    notifyListeners();
  }

  @override
  void dispose() {
    disconnectWebSocket();
    wsEvents.close();
    super.dispose();
  }
}
