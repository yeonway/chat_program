import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/api_models.dart';
import '../services/messenger_session.dart';
import '../widgets/auth_avatar.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<MessengerSession>().loadConversations();
    });
  }

  Future<void> _openSearch() async {
    final session = context.read<MessengerSession>();
    final queryController = TextEditingController();
    List<UserPublic> results = [];
    bool loading = false;
    Timer? debounce;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            Future<void> runSearch(String query) async {
              debounce?.cancel();
              debounce = Timer(const Duration(milliseconds: 260), () async {
                final q = query.trim();
                if (q.length < 2) {
                  setModalState(() {
                    results = [];
                    loading = false;
                  });
                  return;
                }
                setModalState(() => loading = true);
                final found = await session.searchUsers(q);
                if (!ctx.mounted) return;
                setModalState(() {
                  results = found;
                  loading = false;
                });
              });
            }

            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: 16 + MediaQuery.viewInsetsOf(ctx).bottom,
              ),
              child: SizedBox(
                height: 520,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Start a new conversation',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: queryController,
                      decoration: const InputDecoration(
                        hintText: 'Search by username or display name',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onChanged: runSearch,
                    ),
                    const SizedBox(height: 12),
                    Expanded(
                      child: loading
                          ? const Center(child: CircularProgressIndicator())
                          : results.isEmpty
                          ? const Center(
                              child: Text(
                                'Type at least 2 characters to search users',
                              ),
                            )
                          : ListView.separated(
                              itemCount: results.length,
                              separatorBuilder: (_, __) =>
                                  const Divider(height: 1),
                              itemBuilder: (_, i) {
                                final u = results[i];
                                return ListTile(
                                  leading: AuthAvatar(
                                    avatarUrl: u.avatarUrl,
                                    accessToken: session.accessToken,
                                  ),
                                  title: Text(u.nickname),
                                  subtitle: Text('@${u.username}'),
                                  onTap: () async {
                                    final id = await session.createOrGetDirect(
                                      u.id,
                                    );
                                    if (!ctx.mounted) return;
                                    Navigator.pop(ctx);
                                    await session.loadConversations();
                                    if (!mounted) return;
                                    context.push('/chat/$id');
                                  },
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
    debounce?.cancel();
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<MessengerSession>();
    final me = session.me;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          me == null ? 'Messenger' : 'Hi, ${me['nickname'] ?? 'there'}',
        ),
        actions: [
          IconButton(
            tooltip: 'Profile',
            icon: const Icon(Icons.person_outline),
            onPressed: () => context.push('/profile'),
          ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
            onPressed: () => session.logout(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: session.loadConversations,
        child: session.conversations.isEmpty
            ? ListView(
                children: [
                  SizedBox(
                    height: MediaQuery.of(context).size.height * 0.6,
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.forum_outlined,
                            size: 56,
                            color: Theme.of(
                              context,
                            ).colorScheme.primary.withValues(alpha: 0.6),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            'No conversations yet',
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 6),
                          const Text('Tap the search button to start chatting'),
                        ],
                      ),
                    ),
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(12, 6, 12, 90),
                itemCount: session.conversations.length,
                separatorBuilder: (_, __) => const SizedBox(height: 6),
                itemBuilder: (_, i) {
                  final c = session.conversations[i];
                  final other = c.otherUser;
                  final online = other?.online == true;
                  final title = other?.nickname ?? 'Conversation #${c.id}';
                  final subtitle = c.lastMessage?.body.trim().isNotEmpty == true
                      ? c.lastMessage!.body
                      : (c.lastMessage?.fileId != null
                            ? 'Sent an attachment'
                            : 'No messages yet');
                  return Card(
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 4,
                      ),
                      leading: Stack(
                        children: [
                          AuthAvatar(
                            avatarUrl: other?.avatarUrl,
                            accessToken: session.accessToken,
                          ),
                          if (online)
                            Positioned(
                              right: 0,
                              bottom: 0,
                              child: Container(
                                width: 12,
                                height: 12,
                                decoration: BoxDecoration(
                                  color: const Color(0xFF16A34A),
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: Colors.white,
                                    width: 2,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                      title: Row(
                        children: [
                          Expanded(
                            child: Text(
                              title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          if (c.unreadCount > 0)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 3,
                              ),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.primary,
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                c.unreadCount > 99 ? '99+' : '${c.unreadCount}',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                        ],
                      ),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      onTap: () => context.push('/chat/${c.id}'),
                    ),
                  );
                },
              ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openSearch,
        icon: const Icon(Icons.search),
        label: const Text('New Chat'),
      ),
    );
  }
}
