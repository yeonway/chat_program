// FastAPI snake_case JSON과 매핑되는 단순 모델 (직렬화는 수동).

class UserPublic {
  UserPublic({
    required this.id,
    required this.username,
    required this.nickname,
    required this.statusMessage,
    this.avatarUrl,
    this.lastSeenAt,
    this.online,
  });

  final int id;
  final String username;
  final String nickname;
  final String statusMessage;
  final String? avatarUrl;
  final String? lastSeenAt;

  /// WebSocket presence로만 갱신 (REST에는 없음)
  bool? online;

  factory UserPublic.fromJson(Map<String, dynamic> j) => UserPublic(
    id: j['id'] as int,
    username: j['username'] as String,
    nickname: j['nickname'] as String,
    statusMessage: (j['status_message'] as String?) ?? '',
    avatarUrl: j['avatar_url'] as String?,
    lastSeenAt: j['last_seen_at'] as String?,
  );

  UserPublic copyWith({bool? online}) => UserPublic(
    id: id,
    username: username,
    nickname: nickname,
    statusMessage: statusMessage,
    avatarUrl: avatarUrl,
    lastSeenAt: lastSeenAt,
    online: online ?? this.online,
  );
}

class MessageDto {
  MessageDto({
    required this.id,
    required this.conversationId,
    required this.senderId,
    required this.body,
    this.fileId,
    required this.createdAt,
    this.editedAt,
    this.deletedAt,
    this.readByMe = false,
    this.readByPeer = false,
  });

  final int id;
  final int conversationId;
  final int senderId;
  final String body;
  final int? fileId;
  final String createdAt;
  final String? editedAt;
  final String? deletedAt;
  final bool readByMe;
  final bool readByPeer;

  factory MessageDto.fromJson(Map<String, dynamic> j) => MessageDto(
    id: j['id'] as int,
    conversationId: j['conversation_id'] as int,
    senderId: j['sender_id'] as int,
    body: (j['body'] as String?) ?? '',
    fileId: j['file_id'] as int?,
    createdAt: j['created_at'] as String,
    editedAt: j['edited_at'] as String?,
    deletedAt: j['deleted_at'] as String?,
    readByMe: j['read_by_me'] as bool? ?? false,
    readByPeer: j['read_by_peer'] as bool? ?? false,
  );
}

class ConversationItem {
  ConversationItem({
    required this.id,
    required this.type,
    this.otherUser,
    this.lastMessage,
    this.unreadCount = 0,
  });

  final int id;
  final String type;
  UserPublic? otherUser;
  MessageDto? lastMessage;
  int unreadCount;

  factory ConversationItem.fromJson(Map<String, dynamic> j) => ConversationItem(
    id: j['id'] as int,
    type: j['type'] as String,
    otherUser: j['other_user'] != null
        ? UserPublic.fromJson(Map<String, dynamic>.from(j['other_user'] as Map))
        : null,
    lastMessage: j['last_message'] != null
        ? MessageDto.fromJson(
            Map<String, dynamic>.from(j['last_message'] as Map),
          )
        : null,
    unreadCount: j['unread_count'] as int? ?? 0,
  );
}
