import 'package:flutter/material.dart';
import 'package:kitchenowl/models/agent_chat.dart';
import 'package:kitchenowl/models/household.dart';

/// Displays the result of a single agent tool call in a compact card.
class AgentToolCallCard extends StatelessWidget {
  final AgentMessage message;
  final Household household;

  /// The parsed input arguments for this call, keyed by argument name.
  /// Sourced from the preceding assistant message's tool_calls JSON.
  final Map<String, dynamic>? arguments;

  const AgentToolCallCard({
    super.key,
    required this.message,
    required this.household,
    this.arguments,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final toolName = message.toolName ?? 'tool';
    final content = (message.content ?? '').trim();

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 2),
      color: theme.colorScheme.surfaceContainerHighest,
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  Icons.build_outlined,
                  size: 14,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    toolName,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            if (content.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                content,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
