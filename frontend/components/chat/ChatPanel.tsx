'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  createEditTask,
  downloadFile,
  streamUserMessage,
  uploadFile,
} from '@/lib/api';
import type { EditTaskRequest, UserStreamEvent, UserStreamMessage } from '@/types/api';
import type { Message } from '@/types/chat';
import type { ModelType } from '@/components/forms/ModelSelector';
import type { ConversationDraftFile, ConversationFormDraft } from '@/stores/chatStore';
import { tenderTypeDisplayNameMap } from './tenderFormRegistry';
import { resolveGngkFormType } from '@/lib/gngkFormType';

interface ChatPanelProps {
  className?: string;
}

const missingInsertionAnchorMessage = '请先补全当前页面的插入锚点';

function collectNormalChatContext(messages: Message[]): UserStreamMessage[] {
  const candidates: Array<{ message: Message; content: string }> = [];

  for (const message of messages) {
    if (message.metadata?.messageKind) {
      continue;
    }
    if (message.metadata?.chatKind && message.metadata.chatKind !== 'normal') {
      continue;
    }
    if (message.type !== 'user' && (message.type !== 'ai' || message.status !== 'completed')) {
      continue;
    }

    const content = typeof message.content === 'string' ? message.content.trim() : '';
    if (!content) {
      continue;
    }

    candidates.push({ message, content });
  }

  return candidates.slice(-6).map<UserStreamMessage>(({ message, content }) => ({
    role: message.type === 'user' ? 'user' : 'assistant',
    content,
  }));
}

function collectUserRouteContext(messages: Message[], latestPrompt: string): UserStreamMessage[] {
  const history = collectNormalChatContext(messages).slice(-5);
  return [...history, { role: 'user' as const, content: latestPrompt }];
}

function getConversationMessagesById(conversationId: string): Message[] {
  const state = useChatStore.getState();
  return state.conversations.find((item) => item.id === conversationId)?.messages || [];
}

function toConversationDraftFile(uploadedFile: {
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time?: string;
}): ConversationDraftFile {
  return {
    id: `edit-${Date.now()}`,
    file_path: uploadedFile.file_path,
    file_name: uploadedFile.file_name,
    original_name: uploadedFile.original_name,
    size: uploadedFile.size,
    upload_time: uploadedFile.upload_time || new Date().toISOString(),
  };
}

function resolveEditFormType(
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null
): EditTaskRequest['form_type'] | null {
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

function getEditContextMessage(
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null
): string | null {
  if (!draft?.edit_file) {
    return '请先上传一个 Word 文档';
  }

  if (draft.tender_lx !== 0 && draft.tender_lx !== 1 && draft.tender_lx !== 2) {
    return '请先补全当前页面的货物/工程/服务类型';
  }

  if (draft.fund_lx !== 0 && draft.fund_lx !== 1) {
    return '请先补全当前页面的资金性质';
  }

  const insertionConfig = draft.insertion_config;
  if (
    !insertionConfig ||
    !insertionConfig.before_text?.trim() ||
    !insertionConfig.after_text?.trim()
  ) {
    return missingInsertionAnchorMessage;
  }

  if (!resolveEditFormType(tenderType, draft)) {
    return '当前页面缺少可识别的 edit 上下文';
  }

  return null;
}

function buildEditTaskRequest(
  conversationId: string,
  tenderType: 'xjcg' | 'gngk' | 'gjgk',
  draft: ConversationFormDraft | null,
  model: ModelType,
  prompt: string
): { request?: EditTaskRequest; error?: string } {
  const normalizedPrompt = prompt.trim();
  if (!normalizedPrompt) {
    return { error: '请输入修改要求' };
  }

  const contextMessage = getEditContextMessage(tenderType, draft);
  if (contextMessage) {
    return { error: contextMessage };
  }

  const formType = resolveEditFormType(tenderType, draft);
  if (!formType || !draft?.edit_file || draft.tender_lx === undefined || draft.fund_lx === undefined) {
    return { error: '当前页面缺少可识别的 edit 上下文' };
  }

  return {
    request: {
      conversation_id: conversationId,
      form_type: formType,
      model,
      edit_prompt: normalizedPrompt,
      file_path: draft.edit_file.file_path,
      insertion_config: draft.insertion_config,
      tender_lx: draft.tender_lx,
      fund_source_lx: draft.fund_lx,
      tender_data_snapshot: draft.tender_data || undefined,
    },
  };
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
    taskSummaries,
  } =
    useChatStore();
  const streams = useChatStreamStore((state) => state.streams);
  const normalChatAbortRef = useRef<Record<string, AbortController>>({});
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [isUploadingEditFile, setIsUploadingEditFile] = useState(false);
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
  const inputMode = conversationDraft?.input_mode || 'normal';
  const editFile = conversationDraft?.edit_file || null;
  const currentEditFileSize = conversationDraft?.edit_file?.size || 0;
  const isEditMode = inputMode === 'edit' || !!editFile;
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
          typeof node === 'string' && typeof round === 'number' ? `${node}:${round}` : null;
        const stepSnapshot = stepKey ? stream.agentSteps?.[stepKey] : undefined;
        if (message.status === 'generating' && stepSnapshot && !stepSnapshot.isComplete) {
          return {
            ...message,
            content: stepSnapshot.content,
            metadata: {
              ...(message.metadata || {}),
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
  const isComposerBusy = isBusy || isUploadingEditFile;
  const isRewriteQueueStage =
    !!conversation &&
    currentTaskStatus === 'queued' &&
    typeof waitingCount === 'number' &&
    waitingCount > 0 &&
    conversationDraft?.pending_rewrite_task_id === currentTaskId;
  const isEditQueueStage =
    !!conversation &&
    currentTaskStatus === 'queued' &&
    typeof waitingCount === 'number' &&
    waitingCount > 0 &&
    conversationDraft?.pending_edit_task_id === currentTaskId;
  const isTaskQueueStage = isRewriteQueueStage || isEditQueueStage;

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

  const handleEditFileSelect = useCallback(
    async (file: File) => {
      if (!conversation || isBusy) {
        return;
      }

      setComposerNotice(null);
      setIsUploadingEditFile(true);
      try {
        const uploadedFile = await uploadFile(file, 'origin_tender');
        updateConversationDraft(conversation.id, {
          input_mode: 'edit',
          edit_file: toConversationDraftFile({
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
        setIsUploadingEditFile(false);
      }
    },
    [conversation, isBusy, updateConversationDraft]
  );

  const handleEditFileRemove = useCallback(() => {
    if (!conversation || isBusy) {
      return;
    }
    setComposerNotice(null);
    updateConversationDraft(conversation.id, {
      input_mode: 'normal',
      edit_file: undefined,
    });
  }, [conversation, isBusy, updateConversationDraft]);

  const sendUserMessage = useCallback(
    async (
      prompt: string,
      options: {
        appendUserMessage?: boolean;
        modelOverride?: ModelType;
        reuseAiMessageId?: string;
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
      const baseAiMetadata = {
        chatKind: 'normal' as const,
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
            chatKind: 'normal',
          },
        });
      }

      let aiMessageId = options.reuseAiMessageId;
      let aiMessagePrepared = false;
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
      const contextMessages = appendUserMessage
        ? collectUserRouteContext(existingMessages, prompt)
        : collectNormalChatContext(getConversationMessagesById(conversationId));

      const controller = new AbortController();
      normalChatAbortRef.current[conversationId] = controller;
      setNormalChatActive(conversationId, true);

      let accumulatedText = '';
      let streamFinished = false;
      let activeRoute: 'reply' | 'rewrite' | null = null;
      let rewritePlaceholderMessageId: string | undefined;
      let rewriteTaskAccepted = false;

      const cleanupRewritePlaceholder = () => {
        if (!rewritePlaceholderMessageId || rewriteTaskAccepted) {
          return;
        }
        deleteMessage(conversationId, rewritePlaceholderMessageId);
        rewritePlaceholderMessageId = undefined;
      };

      try {
        const handleStreamEvent = (event: UserStreamEvent) => {
          if (event.event === 'route') {
            activeRoute = event.data.route;
            if (event.data.route === 'rewrite' && userMessageId) {
              updateMessage(conversationId, userMessageId, {
                metadata: {
                  chatKind: 'rewrite',
                },
              });
            }
            if (event.data.route === 'rewrite' && !rewritePlaceholderMessageId) {
              rewritePlaceholderMessageId = addMessage(conversationId, {
                type: 'ai',
                content: '正在创建修改重写任务',
                status: 'completed',
                metadata: {
                  chatKind: 'rewrite',
                },
              });
            }
            return;
          }

          if (event.event === 'task_accepted') {
            rewriteTaskAccepted = true;
            if (userMessageId) {
              updateMessage(conversationId, userMessageId, {
                metadata: {
                  chatKind: 'rewrite',
                },
              });
            }
            startTask(
              conversation.id,
              event.data.task_id,
              {
                task_kind: event.data.task_kind,
                status: event.data.status || 'queued',
                queue_position: event.data.queue_position,
                waiting_count: event.data.waiting_count,
              },
              rewritePlaceholderMessageId
                ? { logMessageId: rewritePlaceholderMessageId }
                : undefined
            );
            updateConversationDraft(conversation.id, {
              chat_input: '',
              pending_rewrite_prompt: prompt,
              pending_rewrite_task_id: event.data.task_id,
            });
            streamFinished = true;
            return;
          }

          if (event.event === 'chunk') {
            if (!activeRoute) {
              activeRoute = 'reply';
            }
            if (activeRoute === 'rewrite') {
              return;
            }
            const ensuredAiMessageId = ensureAiMessage();
            accumulatedText += event.data.content || '';
            updateMessage(conversationId, ensuredAiMessageId, {
              content: accumulatedText,
              status: 'generating',
            });
            return;
          }

          if (event.event === 'done') {
            if (!activeRoute) {
              activeRoute = 'reply';
            }
            if (activeRoute === 'rewrite') {
              streamFinished = true;
              return;
            }
            const ensuredAiMessageId = ensureAiMessage();
            const finalText = event.data.content || accumulatedText;
            accumulatedText = finalText;
            updateMessage(conversationId, ensuredAiMessageId, {
              content: finalText,
              status: 'completed',
              error: undefined,
            });
            streamFinished = true;
            return;
          }

          if (event.event === 'error') {
            if (activeRoute === 'rewrite') {
              cleanupRewritePlaceholder();
            }
            const errorMessage = event.data.message || '聊天失败';
            const shouldBindToReplyBubble = activeRoute !== 'rewrite' || !!options.reuseAiMessageId;
            if (shouldBindToReplyBubble) {
              const ensuredAiMessageId = ensureAiMessage();
              updateMessage(conversationId, ensuredAiMessageId, {
                content: accumulatedText,
                status: 'error',
                error: errorMessage,
              });
            }
            if (activeRoute === 'rewrite' || !aiMessagePrepared) {
              addMessage(conversationId, {
                type: 'system',
                content: errorMessage,
                status: 'completed',
              });
            }
            streamFinished = true;
          }
        };

        await streamUserMessage(
          {
            conversation_id: conversationId,
            model: modelForRequest,
            messages: contextMessages,
          },
          {
            signal: controller.signal,
            onEvent: handleStreamEvent,
          }
        );

        if (!streamFinished) {
          if (activeRoute !== 'rewrite' && aiMessagePrepared && aiMessageId) {
            updateMessage(conversationId, aiMessageId, {
              content: accumulatedText,
              status: 'completed',
              error: undefined,
            });
          }
        }
      } catch (error) {
        if (activeRoute === 'rewrite') {
          cleanupRewritePlaceholder();
        }
        const isAbort =
          error instanceof DOMException
            ? error.name === 'AbortError'
            : error instanceof Error && error.name === 'AbortError';

        if (isAbort) {
          if (aiMessagePrepared && aiMessageId) {
            updateMessage(conversationId, aiMessageId, {
              content: accumulatedText,
              status: 'cancelled',
            });
          }
        } else {
          const message = error instanceof ApiError ? error.message : '聊天失败，请稍后重试';
          if (aiMessagePrepared && aiMessageId) {
            updateMessage(conversationId, aiMessageId, {
              content: accumulatedText,
              status: 'error',
              error: message,
            });
          }
          if (!aiMessagePrepared) {
            addMessage(conversationId, {
              type: 'system',
              content: message,
              status: 'completed',
            });
          }
        }
      } finally {
        if (activeRoute === 'rewrite') {
          cleanupRewritePlaceholder();
        }
        delete normalChatAbortRef.current[conversationId];
        setNormalChatActive(conversationId, false);
      }
    },
    [
      addMessage,
      conversation,
      deleteMessage,
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

      if (isEditMode) {
        const { request, error } = buildEditTaskRequest(
          conversation.id,
          conversation.tenderType,
          conversationDraft,
          selectedModel,
          content
        );
        if (!request) {
          setComposerNotice(error || '当前页面缺少可识别的 edit 上下文');
          return false;
        }

        addMessage(conversation.id, {
          type: 'user',
          content,
          status: 'sent',
          metadata: {
            chatKind: 'edit',
          },
        });
        const placeholderMessageId = addMessage(conversation.id, {
          type: 'ai',
          content: '正在创建文件修改任务',
          status: 'completed',
          metadata: {
            chatKind: 'edit',
          },
        });

        setComposerNotice(null);
        updateConversationDraft(conversation.id, { chat_input: '' });

        void (async () => {
          try {
            const result = await createEditTask(request);
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
            updateConversationDraft(conversation.id, {
              pending_edit_prompt: content,
              pending_edit_task_id: result.task_id,
            });
          } catch (error) {
            deleteMessage(conversation.id, placeholderMessageId);
            const message =
              error instanceof ApiError ? error.message : '创建文件修改任务失败，请稍后重试';
            setComposerNotice(message);
            addMessage(conversation.id, {
              type: 'system',
              content: message,
              status: 'completed',
            });
          }
        })();

        return true;
      }

      void sendUserMessage(content, {
        appendUserMessage: true,
      });
      updateConversationDraft(conversation.id, { chat_input: '' });
      return true;
    },
    [
      addMessage,
      conversation,
      conversationDraft,
      deleteMessage,
      isEditMode,
      isBusy,
      selectedModel,
      sendUserMessage,
      startTask,
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

      if (retryPrompt) {
        void sendUserMessage(retryPrompt, {
          appendUserMessage: false,
          modelOverride: retryModel,
          reuseAiMessageId: message.id,
        });
        return;
      }
    },
    [conversation, isBusy, selectedModel, sendUserMessage]
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
      } else if (isEditQueueStage) {
        const refillPrompt = conversationDraft?.pending_edit_prompt || '';
        updateConversationDraft(conversation.id, {
          chat_input: refillPrompt,
          pending_edit_prompt: undefined,
          pending_edit_task_id: undefined,
        });
      }
    } catch {
      // noop
    }
  }, [
    conversation,
    conversationDraft?.pending_edit_prompt,
    conversationDraft?.pending_rewrite_prompt,
    currentTaskId,
    isEditQueueStage,
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
    if (composerNotice !== missingInsertionAnchorMessage || !conversation) {
      return;
    }

    if (!isEditMode) {
      setComposerNotice(null);
      return;
    }

    if (!getEditContextMessage(conversation.tenderType, conversationDraft)) {
      setComposerNotice(null);
    }
  }, [composerNotice, conversation, conversationDraft, isEditMode]);

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

    updateConversationDraft(conversation.id, {
      pending_rewrite_task_id: undefined,
      pending_rewrite_prompt: undefined,
    });
  }, [
    conversation,
    conversationDraft?.pending_rewrite_task_id,
    taskSummaries,
    updateConversationDraft,
  ]);

  useEffect(() => {
    if (!conversation) {
      return;
    }
    const pendingTaskId = conversationDraft?.pending_edit_task_id;
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
      updateConversationDraft(conversation.id, {
        pending_edit_task_id: undefined,
        pending_edit_prompt: undefined,
        input_mode: 'edit',
        edit_file: {
          id: `edit-result-${pendingTaskId}`,
          file_path: latestOutputFile,
          file_name: latestOutputFileName,
          original_name: latestOutputFileName,
          size: currentEditFileSize,
          upload_time: new Date().toISOString(),
        },
      });
      return;
    }

    updateConversationDraft(conversation.id, {
      chat_input:
        conversationDraft?.chat_input ||
        conversationDraft?.pending_edit_prompt ||
        '',
      pending_edit_task_id: undefined,
      pending_edit_prompt: undefined,
    });
  }, [
    conversation,
    conversationDraft?.chat_input,
    conversationDraft?.pending_edit_prompt,
    conversationDraft?.pending_edit_task_id,
    currentEditFileSize,
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
                {isEditQueueStage ? '文件修改任务排队中' : '修改任务排队中'}
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
        inputMode={isEditMode ? 'edit' : 'normal'}
        editFile={editFile}
        onEditFileSelect={handleEditFileSelect}
        onEditFileRemove={handleEditFileRemove}
        noticeMessage={composerNotice}
        placeholder={
          isBusy
            ? '回复生成中，请稍候...'
            : isEditMode
              ? '输入修改要求，系统将只修改当前锚点区正文...'
              : '输入文字并发送即可对话...'
        }
      />
    </div>
  );
}

export default ChatPanel;
