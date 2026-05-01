import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:kitchenowl/models/agent_chat.dart';
import 'package:kitchenowl/models/agent_undo.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/services/api/api_service.dart';

class AgentChatState extends Equatable {
  final bool loading;
  final bool sending;
  final AgentChat? chat;
  final List<AgentMessage> messages;
  final String? error;
  final int? lastCreatedRecipeId;
  final List<AgentRecipeCard> cards;
  final List<int> attachedRecipeIds;
  final List<int> attachedItemIds;
  // Display names for the attachment chips. Kept in parallel to the id
  // lists so the composer can render "Pasta" instead of "#581". Missing
  // entries fall back to the id.
  final Map<int, String> attachedRecipeNames;
  final Map<int, String> attachedItemNames;

  const AgentChatState({
    this.loading = false,
    this.sending = false,
    this.chat,
    this.messages = const [],
    this.error,
    this.lastCreatedRecipeId,
    this.cards = const [],
    this.attachedRecipeIds = const [],
    this.attachedItemIds = const [],
    this.attachedRecipeNames = const {},
    this.attachedItemNames = const {},
  });

  AgentChatState copyWith({
    bool? loading,
    bool? sending,
    AgentChat? chat,
    List<AgentMessage>? messages,
    String? error,
    int? lastCreatedRecipeId,
    List<AgentRecipeCard>? cards,
    List<int>? attachedRecipeIds,
    List<int>? attachedItemIds,
    Map<int, String>? attachedRecipeNames,
    Map<int, String>? attachedItemNames,
    bool clearError = false,
    bool clearRecipe = false,
    bool clearAttachments = false,
  }) =>
      AgentChatState(
        loading: loading ?? this.loading,
        sending: sending ?? this.sending,
        chat: chat ?? this.chat,
        messages: messages ?? this.messages,
        error: clearError ? null : (error ?? this.error),
        lastCreatedRecipeId:
            clearRecipe ? null : (lastCreatedRecipeId ?? this.lastCreatedRecipeId),
        cards: cards ?? this.cards,
        attachedRecipeIds: clearAttachments
            ? const []
            : (attachedRecipeIds ?? this.attachedRecipeIds),
        attachedItemIds: clearAttachments
            ? const []
            : (attachedItemIds ?? this.attachedItemIds),
        attachedRecipeNames: clearAttachments
            ? const {}
            : (attachedRecipeNames ?? this.attachedRecipeNames),
        attachedItemNames: clearAttachments
            ? const {}
            : (attachedItemNames ?? this.attachedItemNames),
      );

  @override
  List<Object?> get props => [
        loading,
        sending,
        chat,
        messages,
        error,
        lastCreatedRecipeId,
        cards,
        attachedRecipeIds,
        attachedItemIds,
        attachedRecipeNames,
        attachedItemNames,
      ];
}

class AgentChatCubit extends Cubit<AgentChatState> {
  final Household household;
  final int chatId;

  AgentChatCubit(this.household, this.chatId) : super(const AgentChatState()) {
    refresh();
  }

  Future<void> refresh() async {
    emit(state.copyWith(loading: true, clearError: true));
    final chat = await ApiService.getInstance().getAgentChat(household, chatId);
    if (chat == null) {
      emit(state.copyWith(loading: false, error: 'load_failed'));
      return;
    }
    emit(AgentChatState(
      loading: false,
      chat: chat,
      messages: chat.messages,
      cards: chat.cards,
      attachedRecipeIds: state.attachedRecipeIds,
      attachedItemIds: state.attachedItemIds,
    ));
  }

  void addAttachedRecipe(int recipeId, {String? name}) {
    if (state.attachedRecipeIds.contains(recipeId)) return;
    final names = Map<int, String>.from(state.attachedRecipeNames);
    if (name != null && name.isNotEmpty) names[recipeId] = name;
    emit(state.copyWith(
      attachedRecipeIds: [...state.attachedRecipeIds, recipeId],
      attachedRecipeNames: names,
    ));
  }

  void removeAttachedRecipe(int recipeId) {
    final names = Map<int, String>.from(state.attachedRecipeNames)
      ..remove(recipeId);
    emit(state.copyWith(
      attachedRecipeIds:
          state.attachedRecipeIds.where((id) => id != recipeId).toList(),
      attachedRecipeNames: names,
    ));
  }

  void addAttachedItem(int itemId, {String? name}) {
    if (state.attachedItemIds.contains(itemId)) return;
    final names = Map<int, String>.from(state.attachedItemNames);
    if (name != null && name.isNotEmpty) names[itemId] = name;
    emit(state.copyWith(
      attachedItemIds: [...state.attachedItemIds, itemId],
      attachedItemNames: names,
    ));
  }

  void removeAttachedItem(int itemId) {
    final names = Map<int, String>.from(state.attachedItemNames)
      ..remove(itemId);
    emit(state.copyWith(
      attachedItemIds:
          state.attachedItemIds.where((id) => id != itemId).toList(),
      attachedItemNames: names,
    ));
  }

  Future<void> closeCard(int cardId) async {
    // Optimistically remove the card.
    final remaining =
        state.cards.where((c) => c.id != cardId).toList(growable: false);
    emit(state.copyWith(cards: remaining));
    final ok = await ApiService.getInstance()
        .closeAgentChatCard(household, chatId, cardId);
    if (!ok) {
      // Roll back on failure by re-fetching.
      await reloadCards();
    }
  }

  Future<void> reloadCards() async {
    final cards =
        await ApiService.getInstance().getAgentChatCards(household, chatId);
    if (cards == null) return;
    emit(state.copyWith(cards: cards));
  }

  /// Attach an existing household recipe to this chat as a card.
  Future<bool> attachExistingRecipeAsCard(int recipeId,
      {String? groupLabel}) async {
    final card = await ApiService.getInstance().attachAgentChatRecipeCard(
      household,
      chatId,
      recipeId,
      groupLabel: groupLabel,
    );
    if (card == null) return false;
    // Replace if already present (id-match), else append.
    final next = state.cards.where((c) => c.id != card.id).toList()
      ..add(card);
    emit(state.copyWith(cards: next));
    return true;
  }

  /// Update a card's group label. Pass an empty string or null to clear.
  Future<void> setCardGroup(int cardId, String? groupLabel) async {
    final clean = (groupLabel ?? '').trim();
    final updated = await ApiService.getInstance().updateAgentChatCard(
      household,
      chatId,
      cardId,
      groupLabel: clean,
    );
    if (updated == null) return;
    final next = state.cards
        .map((c) => c.id == cardId ? updated : c)
        .toList(growable: false);
    emit(state.copyWith(cards: next));
  }

  Future<void> sendMessage(String content) async {
    if (state.sending) return;
    final trimmed = content.trim();
    if (trimmed.isEmpty) return;

    final attachedRecipeIds = List<int>.from(state.attachedRecipeIds);
    final attachedItemIds = List<int>.from(state.attachedItemIds);

    // Optimistically append the user message so the UI reacts instantly.
    final optimistic = AgentMessage(
      role: AgentMessageRole.user,
      content: trimmed,
      attachments: AgentMessageAttachments(
        recipeIds: attachedRecipeIds,
        itemIds: attachedItemIds,
      ),
    );
    emit(state.copyWith(
      sending: true,
      messages: [...state.messages, optimistic],
      clearError: true,
      clearRecipe: true,
      clearAttachments: true,
    ));

    final response = await ApiService.getInstance().postAgentMessage(
      household,
      chatId,
      trimmed,
      attachedRecipeIds: attachedRecipeIds.isEmpty ? null : attachedRecipeIds,
      attachedItemIds: attachedItemIds.isEmpty ? null : attachedItemIds,
    );
    if (response == null) {
      // Roll back the optimistic message and report the error.
      final rolledBack = state.messages.toList()..removeLast();
      emit(state.copyWith(
        sending: false,
        messages: rolledBack,
        error: 'send_failed',
        attachedRecipeIds: attachedRecipeIds,
        attachedItemIds: attachedItemIds,
      ));
      return;
    }

    // Replace the optimistic user message with the persisted ones returned
    // by the backend (which now include the assistant + tool messages).
    final without = state.messages.toList()..removeLast();
    final combined = [...without, ...response.messages];
    emit(state.copyWith(
      sending: false,
      chat: response.chat,
      messages: combined,
      lastCreatedRecipeId: response.createdRecipeId,
    ));
    // Refresh open cards in case the agent created or closed any.
    await reloadCards();
  }

  void clearRecipeNotification() {
    emit(state.copyWith(clearRecipe: true));
  }

  /// Manually rename the chat. Pass an empty string to clear the title.
  Future<bool> rename(String title) async {
    final res = await ApiService.getInstance()
        .renameAgentChat(household, chatId, title);
    if (res == null) return false;
    emit(state.copyWith(chat: res));
    return true;
  }

  /// Retry the most recent failed user message. No-op if no error / no msg.
  Future<void> retryLastUserMessage() async {
    if (state.error == null) return;
    final lastUser = state.messages.lastWhere(
      (m) => m.role == AgentMessageRole.user,
      orElse: () => const AgentMessage(role: AgentMessageRole.user),
    );
    final content = lastUser.content;
    if (content == null || content.isEmpty) return;
    // Drop the failed-user message before resending so we don't duplicate.
    final pruned = state.messages.toList()..remove(lastUser);
    emit(state.copyWith(messages: pruned, clearError: true));
    await sendMessage(content);
  }

  // ----------------------------------------------- rewind / edit / regenerate

  /// Fetch the conflict-aware preview for rewinding to / editing [messageId].
  Future<AgentRewindPreview?> previewRewind(int messageId) =>
      ApiService.getInstance()
          .previewRewindAgentMessage(household, chatId, messageId);

  Future<AgentRewindPreview?> previewEdit(int messageId) =>
      ApiService.getInstance()
          .previewEditAgentMessage(household, chatId, messageId);

  Future<AgentRewindPreview?> previewRegenerate(int messageId) =>
      ApiService.getInstance()
          .previewRegenerateAgentMessage(household, chatId, messageId);

  /// Confirm a rewind. Returns the skipped-ops list so the UI can surface
  /// any conflicts; the cubit's own state is updated with the new messages.
  Future<List<AgentUndoSkipped>?> confirmRewind(
    int messageId, {
    List<int>? skipUndoMessageIds,
  }) async {
    final res = await ApiService.getInstance().confirmRewindAgentMessage(
      household,
      chatId,
      messageId,
      skipUndoMessageIds: skipUndoMessageIds,
    );
    if (res == null) {
      emit(state.copyWith(error: 'rewind_failed'));
      return null;
    }
    emit(state.copyWith(
      chat: res.chat,
      messages: res.messages,
      clearError: true,
      clearRecipe: true,
    ));
    return res.skipped;
  }

  /// Confirm an edit. Backend rewinds + replaces the user-message text but
  /// does NOT auto-rerun the agent; surface the new content and let the user
  /// re-send manually if desired.
  Future<List<AgentUndoSkipped>?> confirmEdit(
    int messageId,
    String newContent, {
    List<int>? skipUndoMessageIds,
  }) async {
    final res = await ApiService.getInstance().confirmEditAgentMessage(
      household,
      chatId,
      messageId,
      newContent,
      skipUndoMessageIds: skipUndoMessageIds,
    );
    if (res == null) {
      emit(state.copyWith(error: 'edit_failed'));
      return null;
    }
    emit(state.copyWith(
      chat: res.chat,
      messages: res.messages,
      clearError: true,
      clearRecipe: true,
    ));
    return res.skipped;
  }

  /// Confirm regenerate: server returns only the new tail, so we replace the
  /// stale tail (everything from the regenerated assistant turn onwards).
  Future<List<AgentUndoSkipped>?> confirmRegenerate(
    int messageId, {
    List<int>? skipUndoMessageIds,
  }) async {
    emit(state.copyWith(sending: true, clearError: true, clearRecipe: true));
    final res = await ApiService.getInstance().confirmRegenerateAgentMessage(
      household,
      chatId,
      messageId,
      skipUndoMessageIds: skipUndoMessageIds,
    );
    if (res == null) {
      emit(state.copyWith(sending: false, error: 'regenerate_failed'));
      return null;
    }
    // The regenerate response is partial -- refresh from the server to get a
    // consistent message list rather than trying to splice client-side.
    await refresh();
    emit(state.copyWith(sending: false));
    return res.skipped;
  }
}
