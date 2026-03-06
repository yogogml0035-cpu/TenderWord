'use client';

import React, { useState, useCallback } from 'react';
import { Loader2, X } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import { useHydrated } from '@/hooks/useHydrated';
import { XjcgTenderForm, type XjcgTenderFormData } from '../forms/XjcgTenderForm';
import { GngkTenderForm, type GngkTenderFormData } from '../forms/GngkTenderForm';
import { cancelTask, createGenerateTask, getTaskStatus } from '@/lib/api';
import { useChatSSE } from '@/hooks/useChatSSE';
import { useTaskHeartbeat } from '@/hooks/useTaskHeartbeat';
import { convertGngkFormToApiRequest, convertXjcgFormToApiRequest } from '@/lib/formDataConverter';
import { inferTenderNoFromConversationTitle } from '@/lib/chat-utils';
import type { TenderData } from '@/types/api';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
interface FormPanelProps {
  className?: string;
  /** Initial tender data from URL params (auto-fetched) */
  initialTenderData?: TenderData | null;
}

export function FormPanel({ className = '', initialTenderData }: FormPanelProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const mounted = useHydrated();
  const {
    getCurrentConversation,
    concurrentTaskWarning,
    dismissConcurrentWarning,
    cancelTask: cancelChatTask,
    completeTask: completeChatTask,
    failTask: failChatTask,
    startTask,
    hasActiveTasks,
  } = useChatStore();
  const conversation = getCurrentConversation();
  const inferredTenderNo = conversation
    ? inferTenderNoFromConversationTitle(conversation.title)
    : null;
  const hasActiveTask = hasActiveTasks();
  const currentGeneratingMessage =
    [...(conversation?.messages || [])]
      .reverse()
      .find((msg) => msg.status === 'generating' && typeof msg.taskId === 'string') || null;
  const effectiveTaskId = currentGeneratingMessage?.taskId || null;
  const hasCancelableCurrentTask = !!effectiveTaskId;

  // Use SSE for current task
  useChatSSE({
    taskId: effectiveTaskId,
    conversationId: conversation?.id || null,
    messageId: currentGeneratingMessage?.id || null,
    onComplete: () => {
      setIsSubmitting(false);
    },
    onError: (error) => {
      console.error('Task failed:', error);
      setIsSubmitting(false);
    },
  });
  useTaskHeartbeat(effectiveTaskId);

  const handleCancelTask = async () => {
    const taskIdToCancel = effectiveTaskId;
    if (taskIdToCancel) {
      try {
        const cancelResult = await cancelTask(taskIdToCancel);

        if (cancelResult.noop) {
          // 后端已结束（completed/failed/cancelled），前端需要主动同步状态，避免一直 generating
          try {
            const task = await getTaskStatus(taskIdToCancel);
            const status = task.status;
            const finalContent = useChatStreamStore.getState().streams[taskIdToCancel]?.content;

            if (status === 'completed') {
              let outputFile: string | undefined;
              let fileName: string | undefined;
              if (typeof task.result === 'string') {
                outputFile = task.result !== 'success' ? task.result : undefined;
              } else if (isRecord(task.result)) {
                const outputFileValue = task.result.output_file;
                const fileNameValue = task.result.file_name;
                outputFile = typeof outputFileValue === 'string' ? outputFileValue : undefined;
                fileName = typeof fileNameValue === 'string' ? fileNameValue : undefined;
              }
              if (!fileName && typeof outputFile === 'string') {
                fileName = outputFile.split(/[\\/]/).pop();
              }
              completeChatTask(taskIdToCancel, outputFile, fileName, finalContent);
            } else if (status === 'failed') {
              const errorMessage = typeof task.error === 'string' ? task.error : '生成失败';
              failChatTask(taskIdToCancel, errorMessage, finalContent);
            } else if (status === 'cancelled') {
              cancelChatTask(taskIdToCancel, finalContent);
            } else {
              cancelChatTask(taskIdToCancel, finalContent);
            }
          } catch {
            cancelChatTask(
              taskIdToCancel,
              useChatStreamStore.getState().streams[taskIdToCancel]?.content
            );
          }
        } else {
          cancelChatTask(
            taskIdToCancel,
            useChatStreamStore.getState().streams[taskIdToCancel]?.content
          );
        }

        useChatStreamStore.getState().clearStream(taskIdToCancel);
        useChatTaskSessionStore.getState().removeSession(taskIdToCancel);

        setIsSubmitting(false);
      } catch (error) {
        console.error('Cancel task failed:', error);
      }
    }
  };

  const handleSubmit = useCallback(
    async (formData: XjcgTenderFormData | GngkTenderFormData) => {
      if (!conversation) return;

      try {
        setIsSubmitting(true);

        const request =
          conversation.tenderType === 'xjcg'
            ? convertXjcgFormToApiRequest(formData as XjcgTenderFormData)
            : convertGngkFormToApiRequest(formData as GngkTenderFormData);

        const result = await createGenerateTask(request);
        startTask(conversation.id, result.task_id);
        useChatTaskSessionStore.getState().upsertSession(result.task_id);
        useChatStreamStore.getState().replaceStream(result.task_id);
        setIsSubmitting(false);
      } catch (error) {
        console.error('Failed to create task:', error);
        setIsSubmitting(false);
        alert('创建任务失败，请重试');
      }
    },
    [conversation, startTask]
  );

  // Empty state when no conversation or during hydration
  if (!mounted || !conversation) {
    return (
      <div
        className={`flex h-full flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-gray-100 p-8 ${className}`}
      >
        <div className="max-w-sm text-center">
          {/* Animated Document Icon */}
          <div className="relative mb-8">
            <div className="absolute inset-0 animate-pulse rounded-full bg-indigo-100 opacity-50" />
            <div className="relative rounded-full border border-indigo-100 bg-white p-6 shadow-lg">
              <svg
                className="h-16 w-16 text-indigo-500"
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
          </div>

          {/* Title */}
          <h3 className="mb-3 text-2xl font-semibold tracking-tight text-gray-800">选择招标类型</h3>
          <p className="mb-6 leading-relaxed text-gray-500">
            请先选择招标类型，填写相关信息后生成文档
          </p>

          {/* Tips */}
          <div className="rounded border border-gray-200 bg-white/70 p-4 shadow-sm backdrop-blur-sm">
            <p className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-600">
              <svg
                className="h-4 w-4 text-amber-500"
                width={16}
                height={16}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              支持以下招标类型：
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-xs font-semibold text-indigo-600">
                  询
                </span>
                <span>询价采购 (XJCG)</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-xs font-semibold text-indigo-600">
                  公
                </span>
                <span>国内公开招标 (GNGK)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative flex h-full flex-col bg-white shadow-sm ${className}`}>
      {/* Header */}
      <div className="relative z-20 flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <div>
          <h2 className="font-medium text-gray-900">招标信息</h2>
          <p className="text-xs text-gray-500">
            {conversation.tenderType === 'xjcg' ? '询价采购' : '国内公开'}
          </p>
        </div>

        {hasCancelableCurrentTask && (
          <button
            onClick={handleCancelTask}
            className="flex items-center gap-1 rounded bg-red-50 px-3 py-1.5 text-sm text-red-600 shadow-sm transition-colors duration-200 hover:bg-red-100"
          >
            <X className="h-4 w-4" />
            取消生成
          </button>
        )}
      </div>

      {/* Concurrent Task Warning */}
      {concurrentTaskWarning && (
        <div className="animate-fade-in-up mx-4 mt-4 rounded border border-yellow-200 bg-yellow-50 p-3 shadow-sm">
          <div className="flex items-start gap-2">
            <svg
              className="mt-0.5 h-5 w-5 text-yellow-500"
              width={20}
              height={20}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm text-yellow-800">当前有其他任务在运行，将排队等待</p>
              <button
                onClick={dismissConcurrentWarning}
                className="mt-1 text-xs text-yellow-600 transition-colors duration-200 hover:text-yellow-800"
              >
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Form Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {conversation.tenderType === 'xjcg' ? (
          <XjcgTenderForm
            key={conversation.id}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting || hasActiveTask}
            initialTenderNo={inferredTenderNo ?? undefined}
            initialTenderData={initialTenderData ?? undefined}
          />
        ) : (
          <GngkTenderForm
            key={conversation.id}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting || hasActiveTask}
            initialTenderNo={inferredTenderNo ?? undefined}
            initialTenderData={initialTenderData ?? undefined}
          />
        )}
      </div>

      {/* Loading Overlay */}
      {hasActiveTask && (
        <div className="animate-fade-in-up absolute inset-0 z-10 flex items-center justify-center bg-white/80">
          <div className="rounded border border-gray-200 bg-white p-6 text-center shadow-lg">
            <Loader2 className="mx-auto mb-2 h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">正在生成招标文档...</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default FormPanel;
