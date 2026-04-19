import 'package:flutter/material.dart';

import '../config/api_config.dart';

/// 아바타 URL은 상대 경로일 수 있음. 인증이 필요한 경우 Bearer 전달.
class AuthAvatar extends StatelessWidget {
  const AuthAvatar({
    super.key,
    this.avatarUrl,
    this.accessToken,
    this.radius = 20,
  });

  final String? avatarUrl;
  final String? accessToken;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final url = ApiConfig.resolveUrl(avatarUrl);
    final fallback = CircleAvatar(
      radius: radius,
      backgroundColor: Theme.of(
        context,
      ).colorScheme.primary.withValues(alpha: 0.12),
      child: Icon(
        Icons.person,
        size: radius * 1.1,
        color: Theme.of(context).colorScheme.primary,
      ),
    );
    if (url.isEmpty) {
      return fallback;
    }
    final headers = <String, String>{};
    if (accessToken != null && accessToken!.isNotEmpty) {
      headers['Authorization'] = ApiConfig.bearer(accessToken!);
    }
    final size = radius * 2;
    return ClipOval(
      child: Image.network(
        url,
        headers: headers.isEmpty ? null : headers,
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => fallback,
      ),
    );
  }
}
