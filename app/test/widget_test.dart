import 'package:flutter_test/flutter_test.dart';

import 'package:app/main.dart';
import 'package:app/services/messenger_session.dart';

void main() {
  testWidgets('앱이 빌드된다', (WidgetTester tester) async {
    final session = MessengerSession();
    // 테스트에서는 네트워크/저장소 부트스트랩 생략 (미로그인 상태)
    await tester.pumpWidget(MessengerApp(session: session));
    await tester.pump();
    expect(find.text('로그인'), findsWidgets);
  });
}
