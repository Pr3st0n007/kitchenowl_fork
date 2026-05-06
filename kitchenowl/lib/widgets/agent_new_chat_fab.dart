import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:kitchenowl/cubits/agent_chat_list_cubit.dart';
import 'package:kitchenowl/cubits/household_cubit.dart';

/// Floating action button shown on the agent chat list page.
/// Tapping it creates a new chat and navigates to it.
class AgentNewChatFab extends StatelessWidget {
  const AgentNewChatFab({super.key});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      heroTag: 'agentNewChat',
      onPressed: () => _createChat(context),
      child: const Icon(Icons.add_comment_outlined),
    );
  }

  Future<void> _createChat(BuildContext context) async {
    final household =
        context.read<HouseholdCubit>().state.household;
    final cubit = context.read<AgentChatListCubit>();
    final chatId = await cubit.createChat();
    if (chatId == null || !context.mounted) return;
    context.push(
      '/household/${household.id}/agent/$chatId',
      extra: household,
    );
  }
}
