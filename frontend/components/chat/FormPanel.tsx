'use client';

import React, { useState, useCallback, useRef } from 'react';
import { Loader2 } from 'lucide-react';
import { useChatStore, type ConversationFormDraft } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import { useHydrated } from '@/hooks/useHydrated';
import { cancelTask, createGenerateTask, getTaskStatus } from '@/lib/api';
import { useChatSSE } from '@/hooks/useChatSSE';
import { useTaskHeartbeat } from '@/hooks/useTaskHeartbeat';
import { useCurrentConversationTaskStatus } from '@/hooks/useCurrentConversationTaskStatus';
import { inferTenderNoFromConversationTitle } from '@/lib/chat-utils';
import type { TenderData } from '@/types/api';
import {
  tenderFormComponentMap,
  tenderFormConverterMap,
  tenderTypeDisplayNameMap,
  type TenderFormData,
} from './tenderFormRegistry';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}

function parseProgressFraction(progressText: string | null): {
  completed: number;
  total: number;
} | null {
  if (!progressText) {
    return null;
  }

  const match = progressText.match(/(\d+)\s*\/\s*(\d+)/);
  if (!match) {
    return null;
  }

  const completed = Number.parseInt(match[1], 10);
  const total = Number.parseInt(match[2], 10);
  if (!Number.isFinite(completed) || !Number.isFinite(total) || total <= 0) {
    return null;
  }

  return { completed, total };
}

type TaskStatusTone = 'blue' | 'amber';

const taskStatusThemes: Record<
  TaskStatusTone,
  {
    card: string;
    iconFrame: string;
    iconAccent: string;
    badge: string;
    progressBar: string;
    footerDot: string;
  }
> = {
  blue: {
    card: 'border-blue-400/90 shadow-blue-100/80',
    iconFrame: 'border-blue-200/80 text-blue-700 shadow-blue-100/80',
    iconAccent: 'bg-blue-100/80',
    badge: 'border-blue-200/80 bg-blue-50 text-blue-700',
    progressBar: 'bg-blue-500/90',
    footerDot: 'bg-blue-500 shadow-[0_0_0_4px_rgba(59,130,246,0.14)]',
  },
  amber: {
    card: 'border-amber-300/90 shadow-amber-100/80',
    iconFrame: 'border-amber-200/80 text-amber-700 shadow-amber-100/80',
    iconAccent: 'bg-amber-100/75',
    badge: 'border-amber-200/80 bg-amber-50 text-amber-700',
    progressBar: 'bg-amber-500/90',
    footerDot: 'bg-amber-400 shadow-[0_0_0_4px_rgba(251,191,36,0.18)]',
  },
};

interface TaskStatusCardProps {
  tone: TaskStatusTone;
  label: string;
  title: string;
  detail: string;
  progressSummary: string;
  progressLabel: string;
  progressBarPercent: number;
  footer: string;
  icon: React.ReactNode;
  className?: string;
  testId?: string;
}

function TaskStatusCard({
  tone,
  label,
  title,
  detail,
  progressSummary,
  progressLabel,
  progressBarPercent,
  footer,
  icon,
  className = '',
  testId,
}: TaskStatusCardProps) {
  const theme = taskStatusThemes[tone];

  return (
    <div
      data-testid={testId}
      className={`relative w-full overflow-hidden rounded-[28px] border bg-white/90 p-6 shadow-xl backdrop-blur-sm ${theme.card} ${className}`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`relative mt-1 flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border bg-white shadow-sm ${theme.iconFrame}`}
        >
          <span className={`absolute inset-0 rounded-2xl ${theme.iconAccent}`} />
          <div className="relative">{icon}</div>
        </div>

        <div className="min-w-0 flex-1">
          <span
            className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold tracking-[0.18em] shadow-sm ${theme.badge}`}
          >
            {label}
          </span>
          <h3 className="mt-3 text-xl font-semibold tracking-tight text-slate-900">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between gap-3 text-xs font-medium text-slate-500">
          <span>{progressSummary}</span>
          <span>{progressLabel}</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-slate-200/80">
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${theme.progressBar}`}
            style={{ width: `${Math.max(0, Math.min(100, progressBarPercent))}%` }}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
        <span className={`h-2 w-2 rounded-full ${theme.footerDot}`} />
        <span>{footer}</span>
      </div>
    </div>
  );
}

interface FormPanelProps {
  className?: string;
  /** Initial tender data from URL params (auto-fetched) */
  initialTenderData?: TenderData | null;
}

export function FormPanel({ className = '', initialTenderData }: FormPanelProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [headerControlsTarget, setHeaderControlsTarget] = useState<HTMLDivElement | null>(null);
  const submitLockRef = useRef(false);
  const mounted = useHydrated();
  const {
    addMessage,
    getCurrentConversation,
    cancelTask: cancelChatTask,
    completeTask: completeChatTask,
    deleteMessage,
    discardStaleTask,
    failTask: failChatTask,
    startTask,
    upsertTaskSummary,
    getConversationDraft,
    updateConversationDraft,
    activeTaskIds,
  } = useChatStore();
  const {
    currentTaskId: effectiveTaskId,
    currentTaskSummary,
    currentTaskStatus,
    waitingCount,
    isCurrentTaskQueued,
    isCurrentTaskRunning,
    runningTaskProgress,
  } = useCurrentConversationTaskStatus();
  const conversation = getCurrentConversation();
  const conversationDraft = getConversationDraft(conversation?.id || null);
  const inferredTenderNo = conversation
    ? inferTenderNoFromConversationTitle(conversation.title)
    : null;
  const conversationBusy =
    typeof effectiveTaskId === 'string' &&
    currentTaskStatus !== 'completed' &&
    currentTaskStatus !== 'failed' &&
    currentTaskStatus !== 'cancelled';
  const hasCancelableCurrentTask = Boolean(effectiveTaskId && conversationBusy);
  const formIsBusy = isSubmitting || conversationBusy;
  const syncingTerminalTasksRef = useRef<Set<string>>(new Set());
  const heartbeatTaskIds =
    activeTaskIds.length > 0
      ? activeTaskIds
      : conversationBusy && effectiveTaskId
        ? [effectiveTaskId]
        : null;

  const syncTaskTerminalState = useCallback(
    async (taskId: string, fallbackStatus?: 'cancelled' | 'failed') => {
      const state = useChatStore.getState();
      const hasTrackedTask =
        state.activeTaskIds.includes(taskId) ||
        state.conversations.some((item) => item.currentTaskId === taskId) ||
        !!state.taskSummaries[taskId] ||
        !!state.findTaskMessageGroup(taskId);
      if (!hasTrackedTask) {
        return;
      }

      if (syncingTerminalTasksRef.current.has(taskId)) {
        return;
      }
      syncingTerminalTasksRef.current.add(taskId);

      let settled = false;
      const stream = useChatStreamStore.getState().streams[taskId];
      const finalContent = stream
        ? {
            logs: stream.logs,
            aiText: stream.aiText,
            aiComplete: stream.aiComplete,
          }
        : undefined;

      try {
        const task = await getTaskStatus(taskId);
        const status = task.status;

        if (status === 'completed') {
          let outputFile: string | undefined;
          let fileName: string | undefined;
          let styleWriteback:
            | import('@/types/api').StyleWritebackSummary
            | undefined;

          if (typeof task.result === 'string') {
            outputFile = task.result !== 'success' ? task.result : undefined;
          } else if (isRecord(task.result)) {
            const outputFileValue = task.result.output_file;
            const fileNameValue = task.result.file_name;
            const styleWritebackValue = task.result.style_writeback;
            outputFile = typeof outputFileValue === 'string' ? outputFileValue : undefined;
            fileName = typeof fileNameValue === 'string' ? fileNameValue : undefined;
            styleWriteback =
              typeof styleWritebackValue === 'object' && styleWritebackValue !== null
                ? (styleWritebackValue as import('@/types/api').StyleWritebackSummary)
                : undefined;
          }

          if (!fileName && typeof outputFile === 'string') {
            fileName = outputFile.split(/[\\/]/).pop();
          }

          completeChatTask(taskId, outputFile, fileName, finalContent, styleWriteback);
          settled = true;
        } else if (status === 'failed') {
          const errorMessage = typeof task.error === 'string' ? task.error : '生成失败';
          failChatTask(taskId, errorMessage, finalContent);
          settled = true;
        } else if (status === 'cancelled') {
          cancelChatTask(taskId, finalContent);
          settled = true;
        }
      } catch {
        if (fallbackStatus === 'failed') {
          failChatTask(taskId, '生成失败', finalContent);
          settled = true;
        } else if (fallbackStatus === 'cancelled') {
          cancelChatTask(taskId, finalContent);
          settled = true;
        }
      } finally {
        syncingTerminalTasksRef.current.delete(taskId);
        if (settled) {
          useChatStreamStore.getState().clearStream(taskId);
          useChatTaskSessionStore.getState().removeSession(taskId);
          setIsSubmitting(false);
        }
      }
    },
    [cancelChatTask, completeChatTask, failChatTask]
  );

  // Use SSE for current task
  useChatSSE({
    taskId: effectiveTaskId,
    taskStatus: currentTaskStatus,
    conversationId: conversation?.id || null,
    onComplete: () => {
      setIsSubmitting(false);
    },
    onError: (error) => {
      console.error('Task failed:', error);
      setIsSubmitting(false);
    },
  });
  useTaskHeartbeat(heartbeatTaskIds, {
    onMissingTask: (taskId) => {
      discardStaleTask(taskId);
      setIsSubmitting(false);
    },
    onTerminalState: (taskId, status) => {
      if (status === 'cancelled' || status === 'failed') {
        void syncTaskTerminalState(taskId, status);
        return;
      }
      void syncTaskTerminalState(taskId);
    },
  });

  const handleCancelTask = async () => {
    const taskIdToCancel = effectiveTaskId;
    if (taskIdToCancel) {
      try {
        const cancelResult = await cancelTask(taskIdToCancel);

        if (cancelResult.noop) {
          // 后端已结束（completed/failed/cancelled），前端主动同步终态，避免一直 generating
          await syncTaskTerminalState(taskIdToCancel, 'cancelled');
        } else {
          const stream = useChatStreamStore.getState().streams[taskIdToCancel];
          cancelChatTask(
            taskIdToCancel,
            stream
              ? {
                  logs: stream.logs,
                  aiText: stream.aiText,
                  aiComplete: stream.aiComplete,
                }
              : undefined
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
    async (formData: TenderFormData) => {
      if (!conversation) return;
      if (submitLockRef.current || useChatStore.getState().currentConversationIsBusy()) {
        return;
      }

      let placeholderMessageId: string | null = null;
      try {
        submitLockRef.current = true;
        setIsSubmitting(true);
        placeholderMessageId = addMessage(conversation.id, {
          type: 'ai',
          content: '正在创建生成招标文件任务',
          status: 'completed',
          metadata: {
            chatKind: 'task-notice',
          },
        });
        const request = {
          ...tenderFormConverterMap[conversation.tenderType](formData),
          conversation_id: conversation.id,
        };

        const result = await createGenerateTask(request);
        startTask(
          conversation.id,
          result.task_id,
          {
            task_kind: result.task_kind,
            status: result.status || 'queued',
            queue_position: result.queue_position,
            waiting_count: result.waiting_count,
          },
          placeholderMessageId ? { logMessageId: placeholderMessageId } : undefined
        );

        // 任务创建后立即补拉一次，拿到排队摘要（waiting_count / queue_position 等）
        try {
          const task = await getTaskStatus(result.task_id);
          upsertTaskSummary(result.task_id, {
            task_kind: task.task_kind,
            status: task.status,
            queue_position: task.queue_position,
            waiting_count: task.waiting_count,
            progress_percent: task.progress.progress_percent,
            progress_text: task.progress.progress_text || '',
            current_node: task.progress.current_node || '',
            current_node_display:
              task.progress.current_node_display || task.progress.current_node || '',
          });
        } catch {
          // 摘要补拉失败不阻断提交流程
        }

        setIsSubmitting(false);
      } catch (error) {
        if (placeholderMessageId) {
          deleteMessage(conversation.id, placeholderMessageId);
        }
        console.error('Failed to create task:', error);
        setIsSubmitting(false);
        alert('创建任务失败，请重试');
      } finally {
        submitLockRef.current = false;
      }
    },
    [addMessage, conversation, deleteMessage, startTask, upsertTaskSummary]
  );

  const handleDraftChange = useCallback(
    (updates: Partial<ConversationFormDraft>) => {
      if (!conversation) {
        return;
      }
      updateConversationDraft(conversation.id, updates);
    },
    [conversation, updateConversationDraft]
  );

  const runningProgressText = runningTaskProgress
    ? `${runningTaskProgress.completed_count}/${runningTaskProgress.total_nodes}（${Math.round(
        runningTaskProgress.progress_percent
      )}%）`
    : null;
  const hasQueueAhead =
    isCurrentTaskQueued && typeof waitingCount === 'number' ? waitingCount > 0 : false;
  const isCurrentTaskStarting = isCurrentTaskQueued && !hasQueueAhead;
  const waitingCountText = typeof waitingCount === 'number' ? `${waitingCount}` : '...';
  const runningProgressNote =
    (typeof currentTaskSummary?.progress_text === 'string'
      ? currentTaskSummary.progress_text.trim()
      : '') || null;
  const runningProgressFraction = parseProgressFraction(runningProgressNote);
  const runningProgressPercent = runningTaskProgress
    ? Math.max(0, Math.min(100, Math.round(runningTaskProgress.progress_percent)))
    : typeof currentTaskSummary?.progress_percent === 'number'
      ? Math.max(0, Math.min(100, Math.round(currentTaskSummary.progress_percent)))
      : runningProgressFraction
        ? Math.max(
            0,
            Math.min(
              100,
              Math.round((runningProgressFraction.completed / runningProgressFraction.total) * 100)
            )
          )
        : 0;
  const runningOverlayPercent =
    runningProgressPercent > 0 ? Math.max(runningProgressPercent, 8) : 18;
  const runningCurrentNodeDisplay =
    typeof currentTaskSummary?.current_node_display === 'string'
      ? currentTaskSummary.current_node_display.trim()
      : '';
  const currentTaskKind = currentTaskSummary?.task_kind || 'generate';
  const isRewriteTask = currentTaskKind === 'rewrite';
  const isEditTask = currentTaskKind === 'edit';
  const taskActionLabel = isEditTask ? '文件修改' : isRewriteTask ? '修改' : '生成';
  const runningStepSummary = isCurrentTaskStarting
    ? `系统正在建立${taskActionLabel}任务与进度流`
    : runningTaskProgress
      ? `已完成 ${runningTaskProgress.completed_count}/${runningTaskProgress.total_nodes} 个步骤`
      : runningProgressFraction
        ? `已完成 ${runningProgressFraction.completed}/${runningProgressFraction.total} 个步骤`
        : `系统正在启动${taskActionLabel}流程`;
  const runningStatusDetail =
    runningCurrentNodeDisplay ||
    (isCurrentTaskStarting
      ? '当前没有前置任务，系统正在获取执行权并初始化 Word 与进度流。'
      : isEditTask
        ? '系统正在提取当前锚点区正文、生成修改结果并写回文档，请稍候，不建议关闭当前页面。'
        : isRewriteTask
        ? '系统正在选择目标版本、重写内容并写回文档，请稍候，不建议关闭当前页面。'
        : '系统正在整理章节、参数与格式，请稍候，不建议关闭当前页面。');
  const runningStatusTitle = isCurrentTaskStarting
    ? `正在启动${taskActionLabel}流程...`
    : isEditTask
      ? '正在修改上传文档...'
      : isRewriteTask
      ? '正在修改文档...'
      : '正在生成招标文档...';
  const runningStatusLabel = isCurrentTaskStarting
    ? '准备执行中'
    : isEditTask
      ? '文件修改中'
      : isRewriteTask
      ? '修改处理中'
      : '文档生成中';
  const runningProgressLabel = runningTaskProgress
    ? `${runningProgressPercent}%`
    : runningProgressNote || (isCurrentTaskStarting ? '启动中' : '处理中');
  const queueProgressSummary = runningProgressText
    ? `当前执行任务进度：${runningProgressText}`
    : '当前暂无执行任务，即将开始下一任务';
  const queueProgressLabel = runningProgressText ? `${runningProgressPercent}%` : '等待中';
  const statusOverlayCard = hasQueueAhead
    ? {
        backdropTestId: 'queue-overlay-backdrop',
        cardTestId: 'queue-status-card',
        tone: 'amber' as const,
        label: '排队等待',
        title: '任务排队中',
        detail: `前方等待${waitingCountText}个任务（含当前执行任务）`,
        progressSummary: queueProgressSummary,
        progressLabel: queueProgressLabel,
        progressBarPercent: runningProgressPercent,
        footer: `轮到当前任务后将自动开始${taskActionLabel}，无需重复提交。`,
        icon: (
          <svg
            className="h-7 w-7"
            width={28}
            height={28}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        ),
      }
    : isCurrentTaskRunning || isCurrentTaskStarting
      ? {
          backdropTestId: 'running-overlay-backdrop',
          cardTestId: 'running-status-card',
          tone: 'blue' as const,
          label: runningStatusLabel,
          title: runningStatusTitle,
          detail: runningStatusDetail,
          progressSummary: runningStepSummary,
          progressLabel: runningProgressLabel,
          progressBarPercent: runningOverlayPercent,
          footer: `${taskActionLabel}过程中可使用底部“取消任务”终止流程`,
          icon: <Loader2 className="h-7 w-7 animate-spin" />,
        }
      : null;

  // Empty state when no conversation or during hydration
  if (!mounted || !conversation) {
    return (
      <div
        className={`flex h-full min-h-0 flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-gray-100 p-8 ${className}`}
      >
        <div className="max-w-sm text-center">
          {/* Animated Document Icon */}
          <div className="relative mb-8 inline-flex">
            <div className="absolute inset-0 animate-pulse rounded-full bg-indigo-100 opacity-50" />
            <div className="relative flex h-28 w-28 items-center justify-center rounded-full border border-indigo-100 bg-white shadow-lg">
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
                <span>询价采购</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-xs font-semibold text-indigo-600">
                  公
                </span>
                <span>国内公开</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-xs font-semibold text-indigo-600">
                  国
                </span>
                <span>国际公开</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const TenderFormComponent = tenderFormComponentMap[conversation.tenderType];
  const tenderTypeDisplayName = tenderTypeDisplayNameMap[conversation.tenderType];

  return (
    <div
      aria-busy={formIsBusy}
      className={`relative flex h-full min-h-0 flex-col bg-white shadow-sm ${className}`}
    >
      {/* Header */}
      <div className="relative z-20 border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h2 className="text-[28px] font-semibold tracking-[-0.04em] text-slate-900">
            {tenderTypeDisplayName}
          </h2>
          <div
            ref={setHeaderControlsTarget}
            className="flex min-w-0 flex-wrap items-center justify-start lg:flex-1 lg:justify-end"
          />
        </div>
      </div>

      {/* Form Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <TenderFormComponent
          key={conversation.id}
          onSubmit={handleSubmit}
          headerTitle={tenderTypeDisplayName}
          headerControlsTarget={headerControlsTarget}
          isSubmitting={formIsBusy}
          canCancel={hasCancelableCurrentTask}
          onCancel={handleCancelTask}
          initialTenderNo={conversationDraft?.tender_no || inferredTenderNo || undefined}
          initialTenderData={conversationDraft?.tender_data || initialTenderData || undefined}
          initialDraft={conversationDraft}
          onDraftChange={handleDraftChange}
        />
      </div>

      {statusOverlayCard && (
        <div
          role="status"
          aria-live="polite"
          className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center p-4"
        >
          <div
            data-testid={statusOverlayCard.backdropTestId}
            className="absolute inset-0 bg-slate-900/4 backdrop-blur-[0.5px]"
          />

          <TaskStatusCard
            testId={statusOverlayCard.cardTestId}
            tone={statusOverlayCard.tone}
            label={statusOverlayCard.label}
            title={statusOverlayCard.title}
            detail={statusOverlayCard.detail}
            progressSummary={statusOverlayCard.progressSummary}
            progressLabel={statusOverlayCard.progressLabel}
            progressBarPercent={statusOverlayCard.progressBarPercent}
            footer={statusOverlayCard.footer}
            className="relative mx-auto max-w-[calc(48rem-12px)]"
            icon={statusOverlayCard.icon}
          />
        </div>
      )}
    </div>
  );
}

export default FormPanel;
