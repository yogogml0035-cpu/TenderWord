'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useHydrated } from '@/hooks/useHydrated';
import { useCurrentConversationTaskStatus } from '@/hooks/useCurrentConversationTaskStatus';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import {
  ApiError,
  cancelTask,
  createCommentSupplementTask,
  downloadFile,
  streamAgentRun,
  uploadFile,
} from '@/lib/api';
import type {
  AgentRunContextSnapshot,
  AgentRunEvent,
  AgentSkill,
} from '@/types/api';
import type { AgentThinkingCardState, ChatMessageKind, Message } from '@/types/chat';
import type { ModelType } from '@/components/forms/ModelSelector';
import type { ConversationDraftFile, ConversationFormDraft } from '@/stores/chatStore';
import { tenderTypeDisplayNameMap } from './tenderFormRegistry';
import { resolveGngkFormType } from '@/lib/gngkFormType';
import {
  applyAgentThinkingEvent,
  finalizeCancelledAgentThinkingState,
} from '@/lib/agentThinking';

interface ChatPanelProps {
  className?: string;
}

type RewriteFormType = NonNullable<AgentRunContextSnapshot['rewrite_context']>['form_type'];

function isSyntheticAgentRunTaskId(taskId: string): boolean {
  return taskId.startsWith('fake-');
}

function hasRewriteContext(messages: Message[]): boolean {
  for (const message of messages) {
    if (message.metadata?.messageKind !== 'task-download') {
      continue;
    }
    if (message.status !== 'completed') {
      continue;
    }
    if (typeof message.metadata?.outputFile !== 'string' || !message.metadata.outputFile.trim()) {
      continue;
    }
    return true;
  }

  return false;
}

function getConversationMessagesById(conversationId: string): Message[] {
  const state = useChatStore.getState();
  return state.conversations.find((item) => item.id === conversationId)?.messages || [];
}

function isAgentSkill(value: unknown): value is AgentSkill {
  return value === 'rewrite';
}

function normalizeSelectedSkills(skills: AgentSkill[] | undefined | null): AgentSkill[] {
  if (!Array.isArray(skills)) {
    return [];
  }
  return skills.filter(isAgentSkill).slice(0, 1);
}

function getSelectedSkillChatKind(skills: AgentSkill[]): ChatMessageKind {
  const selectedSkill = skills[0];
  if (selectedSkill === 'rewrite') {
    return selectedSkill;
  }
  return 'normal';
}

function buildAgentRunRewriteContext(
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null,
  selectedSkills: AgentSkill[]
): AgentRunContextSnapshot['rewrite_context'] {
  const shouldIncludeRewriteContext =
    selectedSkills.includes('rewrite') || !!draft?.rewrite_file;
  if (!shouldIncludeRewriteContext) {
    return undefined;
  }

  const rewriteContext: NonNullable<AgentRunContextSnapshot['rewrite_context']> = {};
  const formType = resolveRewriteFormType(tenderType, draft);
  if (formType) {
    rewriteContext.form_type = formType;
  }

  if (draft?.insertion_config) {
    rewriteContext.insertion_config = {
      before_text: draft.insertion_config.before_text,
      after_text: draft.insertion_config.after_text,
    };
  }

  if (draft?.tender_lx === 0 || draft?.tender_lx === 1 || draft?.tender_lx === 2) {
    rewriteContext.tender_lx = draft.tender_lx;
  }

  if (draft?.fund_lx === 0 || draft?.fund_lx === 1) {
    rewriteContext.fund_source_lx = draft.fund_lx;
  }

  if (draft?.tender_data) {
    rewriteContext.tender_data_snapshot = draft.tender_data;
  }

  return rewriteContext;
}

function buildAgentRunContextSnapshot(
  messages: Message[],
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null,
  selectedSkills: AgentSkill[]
): AgentRunContextSnapshot {
  const rewriteContext = buildAgentRunRewriteContext(tenderType, draft, selectedSkills);

  return {
    rewrite_available: hasRewriteContext(messages),
    uploaded_files: draft?.rewrite_file
      ? [
          {
            file_path: draft.rewrite_file.file_path,
            file_name: draft.rewrite_file.original_name || draft.rewrite_file.file_name,
          },
        ]
      : [],
    ...(rewriteContext ? { rewrite_context: rewriteContext } : {}),
  };
}

function toConversationDraftFile(uploadedFile: {
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time?: string;
}): ConversationDraftFile {
  return {
    id: `rewrite-${Date.now()}`,
    file_path: uploadedFile.file_path,
    file_name: uploadedFile.file_name,
    original_name: uploadedFile.original_name,
    size: uploadedFile.size,
    upload_time: uploadedFile.upload_time || new Date().toISOString(),
  };
}

function resolveRewriteFormType(
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null
): RewriteFormType | null {
  const tenderLx = draft?.tender_lx;
  const fundSourceLx = draft?.fund_lx;

  if (tenderType === 'xjcg') {
    return 'xjcg_tender';
  }

  if (tenderType === 'gjgk') {
    return 'gjgk_tender';
  }

  if ((tenderLx !== 0 && tenderLx !== 1 && tenderLx !== 2) || (fundSourceLx !== 0 && fundSourceLx !== 1)) {
    return null;
  }

  return resolveGngkFormType({
    tender_lx: tenderLx,
    fund_lx: fundSourceLx,
    ifzgcg: draft?.tender_data?.ifzgcg,
  });
}

export function ChatPanel({ className = '' }: ChatPanelProps) {
  const mounted = useHydrated();
  const {
    getCurrentConversation,
    getConversationDraft,
    updateConversationDraft,
    addMessage,
    updateMessage,
    deleteMessage,
    findTaskMessageGroup,
    startTask,
    ensureTaskLogMessage,
    ensureTaskContentMessage,
    detachTaskTracking,
    taskSummaries,
  } =
    useChatStore();
  const streams = useChatStreamStore((state) => state.streams);
  const normalChatAbortRef = useRef<Record<string, AbortController>>({});
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [isUploadingRewriteFile, setIsUploadingRewriteFile] = useState(false);
  const [activeNormalConversations, setActiveNormalConversations] = useState<Record<string, boolean>>(
    {}
  );

  const conversation = getCurrentConversation();
  const conversationDraft = getConversationDraft(conversation?.id || null);
  const {
    currentTaskId,
    currentTaskStatus,
    waitingCount,
    isCurrentTaskQueued,
    isCurrentTaskRunning,
    runningTaskProgress,
  } = useCurrentConversationTaskStatus();
  const isCurrentTaskStarting =
    isCurrentTaskQueued && (!waitingCount || Number.isNaN(Number(waitingCount)) || waitingCount <= 0);
  const selectedModel: ModelType = conversationDraft?.model || 'deepseek';
  const inputValue = conversationDraft?.chat_input || '';
  const rewriteFile = conversationDraft?.rewrite_file || null;
  const selectedSkills: AgentSkill[] = useMemo(
    () => (rewriteFile ? ['rewrite'] : normalizeSelectedSkills(conversationDraft?.selected_skills)),
    [conversationDraft?.selected_skills, rewriteFile]
  );
  const currentRewriteFileSize = conversationDraft?.rewrite_file?.size || 0;
  const isRewriteFileMode = !!rewriteFile;
  const messages = conversation?.messages || [];
  const mergedMessages: Message[] = messages.map((message) => {
    if (!message.taskId) {
      return message;
    }

    const stream = streams[message.taskId];
    if (!stream) {
      return message;
    }

    const kind = message.metadata?.messageKind;
    if (kind === 'task-download' || kind === 'agent-step') {
      if (kind === 'agent-step') {
        const node = message.metadata?.agentStepNode;
        const round = message.metadata?.agentStepRound;
        const stepKey =
          message.metadata?.agentStepKey ||
          (message.metadata?.contentAgent || node === 'content_agent'
            ? 'content_agent'
            : typeof node === 'string' && typeof round === 'number'
              ? `${node}:${round}`
              : null);
        const stepSnapshot = stepKey ? stream.agentSteps?.[stepKey] : undefined;
        if (message.status === 'generating' && stepSnapshot && !stepSnapshot.isComplete) {
          return {
            ...message,
            content: stepSnapshot.content,
            metadata: {
              ...(message.metadata || {}),
              ...(stepSnapshot.contentAgent ? { contentAgent: stepSnapshot.contentAgent } : {}),
              ...(stepSnapshot.commentAgent ? { commentAgent: stepSnapshot.commentAgent } : {}),
            },
          };
        }
      }
      return message;
    }

    const mergedMetadata = {
      ...(message.metadata || {}),
      ...(kind === 'task-log' ? { logs: stream.logs } : {}),
      progressPercent: stream.progressPercent,
      progressText: stream.progressText,
      currentNode: stream.currentNode,
      currentNodeDisplay: stream.currentNodeDisplay,
      lastEventId: stream.lastEventId,
    };

    if (kind === 'task-content') {
      return {
        ...message,
        content: stream.aiText,
        metadata: mergedMetadata,
      };
    }

    if (kind === 'task-log') {
      return {
        ...message,
        metadata: mergedMetadata,
      };
    }

    return {
      ...message,
      content: stream.aiText,
      metadata: mergedMetadata,
    };
  });
  const isNormalStreamActive = !!(conversation && activeNormalConversations[conversation.id]);
  const isTaskBusy = isCurrentTaskQueued || isCurrentTaskRunning;
  const isBusy = isTaskBusy || isNormalStreamActive;
  const isComposerBusy = isBusy || isUploadingRewriteFile;
  const isRewriteQueueStage =
    !!conversation &&
    currentTaskStatus === 'queued' &&
    typeof waitingCount === 'number' &&
    waitingCount > 0 &&
    conversationDraft?.pending_rewrite_task_id === currentTaskId;
  const isTaskQueueStage = isRewriteQueueStage;

  const updateInputValue = useCallback(
    (nextValue: string) => {
      if (!conversation) {
        return;
      }
      if (composerNotice) {
        setComposerNotice(null);
      }
      updateConversationDraft(conversation.id, { chat_input: nextValue });
    },
    [composerNotice, conversation, updateConversationDraft]
  );

  const setNormalChatActive = useCallback((conversationId: string, active: boolean) => {
    setActiveNormalConversations((state) => {
      if (active) {
        return { ...state, [conversationId]: true };
      }
      return Object.fromEntries(Object.entries(state).filter(([id]) => id !== conversationId));
    });
  }, []);

  const handleRewriteFileSelect = useCallback(
    async (file: File) => {
      if (!conversation || isBusy) {
        return;
      }

      setComposerNotice(null);
      setIsUploadingRewriteFile(true);
      try {
        const uploadedFile = await uploadFile(file, 'rewrite_source');
        updateConversationDraft(conversation.id, {
          selected_skills: ['rewrite'],
          rewrite_file: toConversationDraftFile({
            file_path: uploadedFile.file_path,
            file_name: uploadedFile.file_name,
            original_name: uploadedFile.original_name,
            size: file.size,
            upload_time: uploadedFile.upload_time,
          }),
        });
      } catch (error) {
        setComposerNotice(error instanceof ApiError ? error.message : '文件上传失败，请重试');
      } finally {
        setIsUploadingRewriteFile(false);
      }
    },
    [conversation, isBusy, updateConversationDraft]
  );

  const handleRewriteFileRemove = useCallback(() => {
    if (!conversation || isBusy) {
      return;
    }
    setComposerNotice(null);
    updateConversationDraft(conversation.id, {
      rewrite_file: undefined,
      selected_skills: undefined,
    });
  }, [conversation, isBusy, updateConversationDraft]);

  const updateSelectedSkills = useCallback(
    (nextSkills: AgentSkill[]) => {
      if (!conversation) {
        return;
      }
      if (composerNotice) {
        setComposerNotice(null);
      }
      updateConversationDraft(conversation.id, {
        selected_skills: nextSkills.length > 0 ? nextSkills : undefined,
      });
    },
    [composerNotice, conversation, updateConversationDraft]
  );

  const sendAgentRunMessage = useCallback(
    async (
      prompt: string,
      options: {
        appendUserMessage?: boolean;
        modelOverride?: ModelType;
        reuseAiMessageId?: string;
        selectedSkillsOverride?: AgentSkill[];
      } = {}
    ) => {
      if (!conversation) {
        return;
      }
      const conversationId = conversation.id;
      if (normalChatAbortRef.current[conversationId]) {
        return;
      }
      if (isTaskBusy) {
        return;
      }

      const appendUserMessage = options.appendUserMessage ?? true;
      const modelForRequest = options.modelOverride || selectedModel;
      const existingMessages = getConversationMessagesById(conversationId);
      const draftForRequest = useChatStore.getState().getConversationDraft(conversationId);
      const selectedSkillsForRequest = normalizeSelectedSkills(
        options.selectedSkillsOverride ??
          (draftForRequest?.rewrite_file ? ['rewrite'] : draftForRequest?.selected_skills)
      );
      const selectedSkillChatKind = getSelectedSkillChatKind(selectedSkillsForRequest);
      const contextSnapshot = buildAgentRunContextSnapshot(
        existingMessages,
        conversation.tenderType,
        draftForRequest,
        selectedSkillsForRequest
      );
      const baseAiMetadata = {
        chatKind: selectedSkillChatKind,
        chatPrompt: prompt,
        chatModel: modelForRequest,
      };
      let userMessageId: string | undefined;

      if (appendUserMessage) {
        userMessageId = addMessage(conversationId, {
          type: 'user',
          content: prompt,
          status: 'sent',
          metadata: {
            chatKind: selectedSkillChatKind,
          },
        });
      }

      let aiMessageId = options.reuseAiMessageId;
      let aiMessagePrepared = false;
      let thinkingMessageId: string | undefined;
      let thinkingCardState: AgentThinkingCardState | null = null;
      let shouldRenderThinkingCard = selectedSkillsForRequest.length === 0;
      const clearThinkingMessage = () => {
        if (thinkingMessageId) {
          deleteMessage(conversationId, thinkingMessageId);
          thinkingMessageId = undefined;
        }
        thinkingCardState = null;
      };
      const suppressThinkingCardForSkill = (skill?: AgentSkill) => {
        if (skill === 'rewrite') {
          shouldRenderThinkingCard = false;
          clearThinkingMessage();
        }
      };
      const ensureAiMessage = (): string => {
        if (aiMessagePrepared && aiMessageId) {
          return aiMessageId;
        }
        if (aiMessageId) {
          updateMessage(conversationId, aiMessageId, {
            content: '',
            status: 'generating',
            error: undefined,
            metadata: baseAiMetadata,
          });
          aiMessagePrepared = true;
          return aiMessageId;
        }
        aiMessageId = addMessage(conversationId, {
          type: 'ai',
          content: '',
          status: 'generating',
          metadata: baseAiMetadata,
        });
        aiMessagePrepared = true;
        return aiMessageId;
      };
      const upsertThinkingMessage = (
        event: AgentRunEvent,
        status: Message['status'] = 'generating'
      ) => {
        if (!shouldRenderThinkingCard) {
          return;
        }
        const nextThinkingState = applyAgentThinkingEvent(thinkingCardState, event);
        if (!nextThinkingState) {
          return;
        }

        thinkingCardState = nextThinkingState;
        const errorMessage =
          status === 'error'
            ? nextThinkingState.stages.find((stage) => stage.key === 'retry')?.summary ||
              '任务助手请求失败'
            : undefined;

        if (!thinkingMessageId) {
          thinkingMessageId = addMessage(conversationId, {
            type: 'ai',
            content: '',
            status,
            ...(errorMessage ? { error: errorMessage } : {}),
            metadata: {
              agentThinking: nextThinkingState,
            },
          });
          return;
        }

        updateMessage(conversationId, thinkingMessageId, {
          content: '',
          status,
          error: errorMessage,
          metadata: {
            agentThinking: nextThinkingState,
          },
        });
      };

      const controller = new AbortController();
      normalChatAbortRef.current[conversationId] = controller;
      setNormalChatActive(conversationId, true);

      let streamFinished = false;
      let taskAccepted = false;
      let latestRunId: string | undefined;

      const syncUserChatKind = (chatKind: ChatMessageKind) => {
        if (!userMessageId || chatKind === 'normal' || chatKind === 'task-notice') {
          return;
        }
        updateMessage(conversationId, userMessageId, {
          metadata: {
            chatKind,
          },
        });
      };

      try {
        const handleStreamEvent = (event: AgentRunEvent) => {
          latestRunId = event.data.run_id;

          if (event.event === 'run_started') {
            suppressThinkingCardForSkill(event.data.selected_skills[0]);
            upsertThinkingMessage(event, 'generating');
            return;
          }

          if (event.event === 'task_accepted') {
            taskAccepted = true;
            const isSyntheticTask = isSyntheticAgentRunTaskId(event.data.task_id);
            const acceptedChatKind: ChatMessageKind =
              event.data.task_kind === 'rewrite' ? 'rewrite' : 'normal';
            syncUserChatKind(acceptedChatKind);
            shouldRenderThinkingCard = false;
            clearThinkingMessage();
            startTask(
              conversationId,
              event.data.task_id,
              {
                task_kind: event.data.task_kind,
                status: event.data.status || 'queued',
                queue_position: event.data.queue_position,
                waiting_count: event.data.waiting_count,
              }
            );
            ensureTaskLogMessage(event.data.task_id, { status: 'generating' });
            if (event.data.task_kind !== 'rewrite') {
              ensureTaskContentMessage(event.data.task_id, { status: 'generating' });
            }
            if (!isSyntheticTask && event.data.task_kind === 'rewrite') {
              updateConversationDraft(conversationId, {
                chat_input: '',
                pending_rewrite_prompt: prompt,
                pending_rewrite_task_id: event.data.task_id,
              });
            }
            if (isSyntheticTask) {
              detachTaskTracking(event.data.task_id);
            }
            return;
          }

          if (event.event === 'thinking_stage') {
            suppressThinkingCardForSkill(event.data.selected_skill);
            if (event.data.selected_skill === 'rewrite') {
              syncUserChatKind('rewrite');
            }
            upsertThinkingMessage(event, 'generating');
            return;
          }

          if (event.event === 'tool_call') {
            upsertThinkingMessage(event, 'generating');
            return;
          }

          if (event.event === 'needs_input') {
            if (event.data.selected_skill === 'rewrite') {
              syncUserChatKind('rewrite');
            }
            upsertThinkingMessage(event, 'completed');
            const ensuredAiMessageId = ensureAiMessage();
            updateMessage(conversationId, ensuredAiMessageId, {
              content: event.data.message,
              status: 'completed',
              error: undefined,
            });
            streamFinished = true;
            return;
          }

          if (event.event === 'done') {
            if (taskAccepted) {
              streamFinished = true;
              return;
            }
            if (event.data.selected_skill === 'rewrite') {
              syncUserChatKind('rewrite');
            }
            upsertThinkingMessage(event, 'completed');
            const ensuredAiMessageId = ensureAiMessage();
            updateMessage(conversationId, ensuredAiMessageId, {
              content: event.data.message,
              status: 'completed',
              error: undefined,
            });
            streamFinished = true;
            return;
          }

          if (event.event === 'error') {
            upsertThinkingMessage(event, 'error');
            const errorMessage = event.data.message || '任务助手请求失败';
            const ensuredAiMessageId = ensureAiMessage();
            updateMessage(conversationId, ensuredAiMessageId, {
              content: errorMessage,
              status: 'error',
              error: errorMessage,
            });
            streamFinished = true;
          }
        };

        await streamAgentRun(
          {
            conversation_id: conversationId,
            message: prompt,
            model: modelForRequest,
            selected_skills: selectedSkillsForRequest,
            context_snapshot: contextSnapshot,
          },
          {
            signal: controller.signal,
            onEvent: handleStreamEvent,
          }
        );

        if (!streamFinished && taskAccepted) {
          streamFinished = true;
        }

        if (!streamFinished) {
          const incompleteMessage = '任务助手流未返回完成事件，请重试';
          const currentThinkingState = thinkingCardState as AgentThinkingCardState | null;
          if (thinkingMessageId && currentThinkingState) {
            const finalizedThinkingState =
              applyAgentThinkingEvent(currentThinkingState, {
                event: 'error',
                data: {
                  run_id: latestRunId || currentThinkingState.runId || 'unknown-run',
                  code: 'AGENT_RUN_STREAM_INCOMPLETE',
                  message: incompleteMessage,
                },
              }) || currentThinkingState;
            thinkingCardState = finalizedThinkingState;
            updateMessage(conversationId, thinkingMessageId, {
              content: '',
              status: 'error',
              error: incompleteMessage,
              metadata: {
                agentThinking: finalizedThinkingState,
              },
            });
          } else {
            const ensuredAiMessageId = ensureAiMessage();
            updateMessage(conversationId, ensuredAiMessageId, {
              content: incompleteMessage,
              status: 'error',
              error: incompleteMessage,
            });
          }
          streamFinished = true;
        }
      } catch (error) {
        const isAbort =
          error instanceof DOMException
            ? error.name === 'AbortError'
            : error instanceof Error && error.name === 'AbortError';

        if (isAbort) {
          if (thinkingMessageId && thinkingCardState) {
            thinkingCardState = finalizeCancelledAgentThinkingState(thinkingCardState);
            updateMessage(conversationId, thinkingMessageId, {
              content: '',
              status: 'cancelled',
              metadata: {
                agentThinking: thinkingCardState,
              },
            });
          }
          if (aiMessagePrepared && aiMessageId) {
            updateMessage(conversationId, aiMessageId, {
              content: '',
              status: 'cancelled',
            });
          }
        } else if (!taskAccepted) {
          const message = error instanceof ApiError ? error.message : '任务助手请求失败，请稍后重试';
          const ensuredAiMessageId = ensureAiMessage();
          updateMessage(conversationId, ensuredAiMessageId, {
            content: message,
            status: 'error',
            error: message,
          });
        }
      } finally {
        delete normalChatAbortRef.current[conversationId];
        setNormalChatActive(conversationId, false);
      }
    },
    [
      addMessage,
      conversation,
      deleteMessage,
      ensureTaskContentMessage,
      ensureTaskLogMessage,
      detachTaskTracking,
      isTaskBusy,
      selectedModel,
      setNormalChatActive,
      startTask,
      updateConversationDraft,
      updateMessage,
    ]
  );

  const handleSendMessage = useCallback(
    (content: string): boolean => {
      if (!conversation || isBusy) {
        return false;
      }

      const selectedSkillsForRequest: AgentSkill[] =
        selectedSkills.length > 0 ? selectedSkills : isRewriteFileMode ? ['rewrite'] : [];

      void sendAgentRunMessage(content, {
        appendUserMessage: true,
        selectedSkillsOverride: selectedSkillsForRequest,
      });
      updateConversationDraft(conversation.id, {
        chat_input: '',
        selected_skills: undefined,
      });
      return true;
    },
    [
      conversation,
      isRewriteFileMode,
      isBusy,
      selectedSkills,
      sendAgentRunMessage,
      updateConversationDraft,
    ]
  );

  const handleModelChange = (model: ModelType) => {
    if (!conversation) {
      return;
    }

    if (composerNotice) {
      setComposerNotice(null);
    }
    updateConversationDraft(conversation.id, { model });
  };

  const handleRetry = useCallback(
    (message: Message) => {
      if (!conversation || isBusy) {
        return;
      }

      const retryPrompt =
        typeof message.metadata?.chatPrompt === 'string' ? message.metadata.chatPrompt : '';
      const retryModel =
        message.metadata?.chatModel === 'deepseek' ||
        message.metadata?.chatModel === 'qwen' ||
        message.metadata?.chatModel === 'doubao'
          ? message.metadata.chatModel
          : selectedModel;
      const retrySelectedSkills =
        message.metadata?.chatKind === 'rewrite'
          ? [message.metadata.chatKind]
          : [];

      if (retryPrompt) {
        void sendAgentRunMessage(retryPrompt, {
          appendUserMessage: false,
          modelOverride: retryModel,
          reuseAiMessageId: message.id,
          selectedSkillsOverride: retrySelectedSkills,
        });
        return;
      }
    },
    [conversation, isBusy, selectedModel, sendAgentRunMessage]
  );

  const handleDownload = async (filePath: string, fileName?: string) => {
    try {
      const blob = await downloadFile(filePath, fileName);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName || filePath.split('/').pop() || 'download';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      alert('下载失败，请重试');
    }
  };

  const handleCommentSupplement = useCallback(
    (message: Message) => {
      if (!conversation || isBusy) {
        return;
      }
      const outputFile =
        typeof message.metadata?.outputFile === 'string' ? message.metadata.outputFile : '';
      if (!outputFile || message.metadata?.taskKind !== 'generate') {
        return;
      }

      const placeholderMessageId = addMessage(conversation.id, {
        type: 'ai',
        content: '正在创建补充批注任务',
        status: 'completed',
        metadata: {
          chatKind: 'task-notice',
        },
      });

      setComposerNotice(null);

      void (async () => {
        try {
          const result = await createCommentSupplementTask({
            conversation_id: conversation.id,
            source_file: outputFile,
            model: selectedModel,
          });
          startTask(
            conversation.id,
            result.task_id,
            {
              task_kind: result.task_kind,
              status: result.status || 'queued',
              queue_position: result.queue_position,
              waiting_count: result.waiting_count,
            },
            { logMessageId: placeholderMessageId }
          );
        } catch (error) {
          deleteMessage(conversation.id, placeholderMessageId);
          const errorMessage =
            error instanceof ApiError ? error.message : '创建补充批注任务失败，请稍后重试';
          setComposerNotice(errorMessage);
          addMessage(conversation.id, {
            type: 'system',
            content: errorMessage,
            status: 'completed',
          });
        }
      })();
    },
    [addMessage, conversation, deleteMessage, isBusy, selectedModel, startTask]
  );

  const handleStopAction = useCallback(async () => {
    if (!conversation) {
      return;
    }

    if (isNormalStreamActive) {
      normalChatAbortRef.current[conversation.id]?.abort();
      return;
    }

    if (!currentTaskId) {
      return;
    }

    try {
      await cancelTask(currentTaskId);

      if (isRewriteQueueStage) {
        const refillPrompt = conversationDraft?.pending_rewrite_prompt || '';
        updateConversationDraft(conversation.id, {
          chat_input: refillPrompt,
          pending_rewrite_prompt: undefined,
          pending_rewrite_task_id: undefined,
        });
      }
    } catch {
      // noop
    }
  }, [
    conversation,
    conversationDraft?.pending_rewrite_prompt,
    currentTaskId,
    isNormalStreamActive,
    isRewriteQueueStage,
    updateConversationDraft,
  ]);

  useEffect(
    () => () => {
      const controllers = Object.values(normalChatAbortRef.current);
      for (const controller of controllers) {
        controller.abort();
      }
      normalChatAbortRef.current = {};
    },
    []
  );

  useEffect(() => {
    if (!conversation) {
      return;
    }
    const pendingTaskId = conversationDraft?.pending_rewrite_task_id;
    if (!pendingTaskId) {
      return;
    }

    const pendingSummary = taskSummaries[pendingTaskId];
    const pendingStatus = pendingSummary?.status;
    const stillActive =
      conversation.currentTaskId === pendingTaskId ||
      pendingStatus === 'queued' ||
      pendingStatus === 'running';
    if (stillActive) {
      return;
    }

    const taskGroup = findTaskMessageGroup(pendingTaskId);
    const latestOutputFile =
      typeof taskGroup?.downloadMessage?.metadata?.outputFile === 'string'
        ? taskGroup.downloadMessage.metadata.outputFile
        : '';
    const latestOutputFileName =
      typeof taskGroup?.downloadMessage?.metadata?.fileName === 'string'
        ? taskGroup.downloadMessage.metadata.fileName
        : latestOutputFile.split(/[\\/]/).pop() || '';
    const terminalStatus =
      taskGroup?.downloadMessage?.status ||
      taskGroup?.contentMessage?.status ||
      taskGroup?.logMessage?.status;

    if (terminalStatus === 'completed' && latestOutputFile) {
      const updates: Partial<ConversationFormDraft> = {
        pending_rewrite_task_id: undefined,
        pending_rewrite_prompt: undefined,
      };
      if (conversationDraft?.rewrite_file) {
        updates.rewrite_file = {
          id: `rewrite-result-${pendingTaskId}`,
          file_path: latestOutputFile,
          file_name: latestOutputFileName,
          original_name: latestOutputFileName,
          size: currentRewriteFileSize,
          upload_time: new Date().toISOString(),
        };
      }
      updateConversationDraft(conversation.id, updates);
      return;
    }

    updateConversationDraft(conversation.id, {
      chat_input:
        conversationDraft?.chat_input ||
        conversationDraft?.pending_rewrite_prompt ||
        '',
      pending_rewrite_task_id: undefined,
      pending_rewrite_prompt: undefined,
    });
  }, [
    conversation,
    conversationDraft?.chat_input,
    conversationDraft?.pending_rewrite_prompt,
    conversationDraft?.pending_rewrite_task_id,
    conversationDraft?.rewrite_file,
    currentRewriteFileSize,
    findTaskMessageGroup,
    taskSummaries,
    updateConversationDraft,
  ]);

  const queueProgressLabel = runningTaskProgress
    ? `${Math.round(runningTaskProgress.progress_percent)}%`
    : '等待中';
  const queueProgressSummary = runningTaskProgress
    ? `全局执行进度：${runningTaskProgress.completed_count}/${runningTaskProgress.total_nodes}`
    : '全局执行进度获取中...';
  const queueProgressBarPercent = runningTaskProgress
    ? Math.max(8, Math.round(runningTaskProgress.progress_percent))
    : 12;

  // Empty state when no conversation selected or during hydration
  if (!mounted || !conversation) {
    return (
      <div
        className={`flex h-full min-h-0 flex-col bg-gradient-to-br from-slate-50 to-gray-100 ${className}`}
      >
        <div className="flex flex-1 items-center justify-center p-8">
          <div className="max-w-md text-center">
            {/* Animated Icon Container */}
            <div className="relative mb-8 inline-block">
              <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-50" />
              <div className="relative rounded-full border border-blue-100 bg-white p-6 shadow-lg">
                <svg
                  className="h-16 w-16 text-blue-500"
                  width={64}
                  height={64}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
            </div>

            {/* Welcome Text */}
            <h3 className="mb-3 text-2xl font-semibold tracking-tight text-gray-800">
              欢迎使用体验
            </h3>
            <p className="mb-6 leading-relaxed text-gray-500">
              智能招标文档生成助手，让文档创建更高效
            </p>
            <div className="rounded-xl border border-gray-200/50 bg-white/70 p-4 shadow-sm backdrop-blur-sm">
              <p className="mb-3 text-sm font-medium text-gray-600">开始新对话：</p>
              <div className="space-y-2">
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-600">
                    1
                  </span>
                  <span>在左侧选择招标类型</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-600">
                    2
                  </span>
                  <span>填写招标信息并上传文件</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-600">
                    3
                  </span>
                  <span>AI 自动生成招标文档</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex h-full min-h-0 flex-col bg-white shadow-sm ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <div>
          <h2 className="font-medium text-gray-900">{conversation.title}</h2>
          <p className="text-xs text-gray-500">
            {tenderTypeDisplayNameMap[conversation.tenderType]}
          </p>
        </div>
        <div className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-400">
          {mergedMessages.length} 条消息
        </div>
      </div>

      {/* Message List */}
      <div className="relative flex-1 overflow-hidden">
        <MessageList
          messages={mergedMessages}
          onDownload={handleDownload}
          onCommentSupplement={handleCommentSupplement}
          onRetry={handleRetry}
          interactionDisabled={isTaskQueueStage}
          commentSupplementDisabled={isBusy}
          emptyState={
            isCurrentTaskQueued || isCurrentTaskStarting ? <div className="h-full" /> : undefined
          }
        />

        {isTaskQueueStage && (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center p-6">
            <div className="absolute inset-0 bg-slate-900/6 shadow-inner backdrop-blur-[1px]" />
            <div className="relative w-full max-w-md rounded-3xl border border-amber-300/90 bg-white/95 p-6 shadow-xl shadow-amber-100/70">
              <div className="mb-3 inline-flex rounded-full border border-amber-200/80 bg-amber-50 px-3 py-1 text-xs font-semibold tracking-[0.18em] text-amber-700">
                排队等待
              </div>
              <h3 className="text-xl font-semibold tracking-tight text-slate-900">
                修改任务排队中
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                前方等待 {waitingCount} 个任务（含当前执行任务），轮到后将自动进入日志流。
              </p>
              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{queueProgressSummary}</span>
                  <span>{queueProgressLabel}</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-200/80">
                  <div
                    className="h-full rounded-full bg-amber-500/90 transition-[width] duration-500"
                    style={{ width: `${Math.max(0, Math.min(100, queueProgressBarPercent))}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput
        value={inputValue}
        onValueChange={updateInputValue}
        onSend={handleSendMessage}
        onCancel={handleStopAction}
        selectedModel={selectedModel}
        onModelChange={handleModelChange}
        actionMode={isBusy ? 'cancel' : 'send'}
        loading={isComposerBusy}
        rewriteFile={rewriteFile}
        onRewriteFileSelect={handleRewriteFileSelect}
        onRewriteFileRemove={handleRewriteFileRemove}
        selectedSkills={selectedSkills}
        onSelectedSkillsChange={updateSelectedSkills}
        noticeMessage={composerNotice}
        placeholder={
          isBusy
            ? '回复生成中，请稍候...'
            : isRewriteFileMode
              ? '输入重写要求，系统将重写当前锚点区正文...'
              : '输入文字并发送即可对话...'
        }
      />
    </div>
  );
}

export default ChatPanel;
