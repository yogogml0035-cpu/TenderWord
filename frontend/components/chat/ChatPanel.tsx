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
  downloadFile,
  streamUserMessage,
} from '@/lib/api';
import type { UserStreamEvent, UserStreamMessage } from '@/types/api';
import type { Message } from '@/types/chat';
import type { ModelType } from '@/components/forms/ModelSelector';

interface ChatPanelProps {
  className?: string;
}

function collectNormalChatContext(messages: Message[]): UserStreamMessage[] {
  const candidates = messages.filter((message) => {
    if (message.metadata?.messageKind) {
      return false;
    }
    if (message.metadata?.chatKind && message.metadata.chatKind !== 'normal') {
      return false;
    }
    if (message.type === 'user') {
      return true;
    }
    if (message.type === 'ai') {
      return message.status === 'completed';
    }
    return false;
  });

  return candidates.slice(-6).map<UserStreamMessage>((message) => ({
    role: message.type === 'user' ? 'user' : 'assistant',
    content: typeof message.content === 'string' ? message.content : '',
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

export function ChatPanel({ className = '' }: ChatPanelProps) {
  const mounted = useHydrated();
  const {
    getCurrentConversation,
    getConversationDraft,
    updateConversationDraft,
    addMessage,
    updateMessage,
    deleteMessage,
    startTask,
    taskSummaries,
  } =
    useChatStore();
  const streams = useChatStreamStore((state) => state.streams);
  const normalChatAbortRef = useRef<Record<string, AbortController>>({});
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
    if (kind === 'task-download') {
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
  const isRewriteQueueStage =
    !!conversation &&
    currentTaskStatus === 'queued' &&
    typeof waitingCount === 'number' &&
    waitingCount > 0 &&
    conversationDraft?.pending_rewrite_task_id === currentTaskId;

  const updateInputValue = useCallback(
    (nextValue: string) => {
      if (!conversation) {
        return;
      }
      updateConversationDraft(conversation.id, { chat_input: nextValue });
    },
    [conversation, updateConversationDraft]
  );

  const setNormalChatActive = useCallback((conversationId: string, active: boolean) => {
    setActiveNormalConversations((state) => {
      if (active) {
        return { ...state, [conversationId]: true };
      }
      return Object.fromEntries(Object.entries(state).filter(([id]) => id !== conversationId));
    });
  }, []);

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
    async (content: string) => {
      if (!conversation || isBusy) {
        return;
      }

      await sendUserMessage(content, {
        appendUserMessage: true,
      });
      updateConversationDraft(conversation.id, { chat_input: '' });
    },
    [
      conversation,
      isBusy,
      sendUserMessage,
      updateConversationDraft,
    ]
  );

  const handleModelChange = (model: ModelType) => {
    if (!conversation) {
      return;
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
            {conversation.tenderType === 'xjcg' ? '询价采购' : '国内公开'}
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
          onRetry={handleRetry}
          interactionDisabled={isRewriteQueueStage}
          emptyState={isCurrentTaskQueued || isCurrentTaskStarting ? <div className="h-full" /> : undefined}
        />

        {isRewriteQueueStage && (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center p-6">
            <div className="absolute inset-0 bg-slate-900/6 shadow-inner backdrop-blur-[1px]" />
            <div className="relative w-full max-w-md rounded-3xl border border-amber-300/90 bg-white/95 p-6 shadow-xl shadow-amber-100/70">
              <div className="mb-3 inline-flex rounded-full border border-amber-200/80 bg-amber-50 px-3 py-1 text-xs font-semibold tracking-[0.18em] text-amber-700">
                排队等待
              </div>
              <h3 className="text-xl font-semibold tracking-tight text-slate-900">修改任务排队中</h3>
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
        loading={isBusy}
        placeholder={isBusy ? '回复生成中，请稍候...' : '输入文字并发送即可对话...'}
      />
    </div>
  );
}

export default ChatPanel;
