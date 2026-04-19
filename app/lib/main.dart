import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'screens/chat_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/register_screen.dart';
import 'services/messenger_session.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final session = MessengerSession();
  await session.bootstrap();
  runApp(MessengerApp(session: session));
}

class MessengerApp extends StatefulWidget {
  const MessengerApp({super.key, required this.session});

  final MessengerSession session;

  @override
  State<MessengerApp> createState() => _MessengerAppState();
}

class _MessengerAppState extends State<MessengerApp> {
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _router = GoRouter(
      initialLocation: widget.session.isLoggedIn ? '/' : '/login',
      refreshListenable: widget.session,
      redirect: (context, state) {
        final loggedIn = widget.session.isLoggedIn;
        final loc = state.uri.path;
        if (!loggedIn && loc != '/login' && loc != '/register') {
          return '/login';
        }
        if (loggedIn && (loc == '/login' || loc == '/register')) {
          return '/';
        }
        return null;
      },
      routes: [
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
        GoRoute(
          path: '/',
          builder: (_, __) => const HomeScreen(),
          routes: [
            GoRoute(
              path: 'chat/:cid',
              builder: (c, s) {
                final id = int.tryParse(s.pathParameters['cid'] ?? '') ?? 0;
                return ChatScreen(conversationId: id);
              },
            ),
            GoRoute(path: 'profile', builder: (_, __) => const ProfileScreen()),
          ],
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: widget.session,
      child: MaterialApp.router(
        title: 'Messenger',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        routerConfig: _router,
      ),
    );
  }
}
