/// 빌드 시: flutter run --dart-define=API_BASE=http://10.0.2.2:8000 (Android 에뮬레이터 → 호스트)
class ApiConfig {
  ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://127.0.0.1:8000',
  );

  /// WebSocket URL (인증은 연결 후 첫 메시지 `{"type":"auth","token":"..."}`).
  static Uri wsUri() {
    final u = Uri.parse(baseUrl);
    final scheme = u.scheme == 'https' ? 'wss' : 'ws';
    return Uri(
      scheme: scheme,
      host: u.host,
      port: u.hasPort ? u.port : null,
      path: '/ws',
    );
  }

  /// REST 경로를 전체 URL로 (이미지 등)
  static String resolveUrl(String? pathOrUrl) {
    if (pathOrUrl == null || pathOrUrl.isEmpty) return '';
    if (pathOrUrl.startsWith('http')) return pathOrUrl;
    final base = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final p = pathOrUrl.startsWith('/') ? pathOrUrl : '/$pathOrUrl';
    return '$base$p';
  }

  static String bearer(String accessToken) => 'Bearer $accessToken';
}
