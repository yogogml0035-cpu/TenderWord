'use client';

import React, { useState, useCallback } from 'react';
import { Loader2, X } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { XjcgTenderForm } from '../forms/XjcgTenderForm';
import { GngkTenderForm } from '../forms/GngkTenderForm';
import { cancelTask, createGenerateTask } from '@/lib/api';
import { useChatSSE } from '@/hooks/useChatSSE';

interface FormPanelProps {
  className?: string;
}

export function FormPanel({ className = '' }: FormPanelProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [currentMessageId, setCurrentMessageId] = useState<string | null>(null);
  
  const {
    getCurrentConversation,
    activeTaskIds,
    concurrentTaskWarning,
    dismissConcurrentWarning,
    cancelTask: cancelChatTask,
    startTask,
  } = useChatStore();

  const conversation = getCurrentConversation();
  const hasActiveTask = activeTaskIds.length > 0;

  // Use SSE for current task
  useChatSSE({
    taskId: currentTaskId,
    conversationId: conversation?.id || null,
    messageId: currentMessageId,
    onComplete: () => {
      setCurrentTaskId(null);
      setCurrentMessageId(null);
      setIsSubmitting(false);
    },
    onError: (error) => {
      console.error('Task failed:', error);
      setCurrentTaskId(null);
      setCurrentMessageId(null);
      setIsSubmitting(false);
    },
  });

  const handleCancelTask = async () => {
    if (conversation?.currentTaskId) {
      try {
        await cancelTask(conversation.currentTaskId);
        cancelChatTask(conversation.currentTaskId);
      } catch (error) {
        console.error('Cancel task failed:', error);
      }
    }
  };

  const handleSubmit = useCallback(async (formData: { tenderNo: string; templateFile?: File; paramFiles: File[]; model: string }) => {
    if (!conversation) return;

    try {
      setIsSubmitting(true);

      // Create the generation task
      // TODO: This API structure needs to be updated to match GenerateRequest type
      const result = await createGenerateTask({
        tender_no: formData.tenderNo,
        tender_type: conversation.tenderType,
        template_file: formData.templateFile?.name,
        param_files: formData.paramFiles?.map((f) => f.name) || [],
        model: formData.model as 'deepseek' | 'qwen' | 'doubao',
      } as any);

      // Start task in store (creates message)
      const messageId = startTask(conversation.id, result.task_id);
      // Track current task for SSE
      setCurrentTaskId(result.task_id);
      setCurrentMessageId(messageId);
    } catch (error) {
      console.error('Failed to create task:', error);
      setIsSubmitting(false);
      alert('创建任务失败，请重试');
    }
  }, [conversation, startTask]);

  // Empty state when no conversation
  if (!conversation) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-gradient-to-br from-slate-50 to-gray-100 p-8 ${className}`}>
        <div className="text-center max-w-sm">
          {/* Animated Document Icon */}
          <div className="relative mb-8">
            <div className="absolute inset-0 bg-indigo-100 rounded-full animate-pulse opacity-50" />
            <div className="relative bg-white rounded-full p-6 shadow-lg border border-indigo-100">
              <svg
                className="w-16 h-16 text-indigo-500"
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
          <h3 className="text-2xl font-semibold text-gray-800 mb-3 tracking-tight">
            选择招标类型
          </h3>
          <p className="text-gray-500 mb-6 leading-relaxed">
            请先选择招标类型，填写相关信息后生成文档
          </p>

          {/* Tips */}
          <div className="bg-white/70 backdrop-blur-sm rounded p-4 border border-gray-200 shadow-sm">
            <p className="text-sm text-gray-600 mb-3 font-medium flex items-center gap-2">
              <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              支持以下招标类型：
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex items-center justify-center w-6 h-6 rounded bg-indigo-100 text-indigo-600 text-xs font-semibold">询</span>
                <span>询价采购 (XJCG)</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span className="flex items-center justify-center w-6 h-6 rounded bg-indigo-100 text-indigo-600 text-xs font-semibold">公</span>
                <span>国内公开招标 (GNGK)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white shadow-sm ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="font-medium text-gray-900">招标信息</h2>
          <p className="text-xs text-gray-500">
            {conversation.tenderType === 'xjcg' ? '询价采购' : '国内公开'}
          </p>
        </div>
        
        {hasActiveTask && (
          <button
            onClick={handleCancelTask}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 bg-red-50 rounded hover:bg-red-100 transition-colors duration-200 shadow-sm"
          >
            <X className="w-4 h-4" />
            取消生成
          </button>
        )}
      </div>

      {/* Concurrent Task Warning */}
      {concurrentTaskWarning && (
        <div className="mx-4 mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded shadow-sm animate-fade-in-up">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-yellow-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <p className="text-sm text-yellow-800">当前有其他任务在运行，将排队等待</p>
              <button
                onClick={dismissConcurrentWarning}
                className="text-xs text-yellow-600 hover:text-yellow-800 mt-1 transition-colors duration-200"
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
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting || hasActiveTask}
          />
        ) : (
          <GngkTenderForm
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting || hasActiveTask}
          />
        )}
      </div>

      {/* Loading Overlay */}
      {hasActiveTask && (
        <div className="absolute inset-0 bg-white/80 flex items-center justify-center z-10 animate-fade-in-up">
          <div className="text-center p-6 rounded shadow-lg border border-gray-200 bg-white">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-2" />
            <p className="text-sm text-gray-600">正在生成招标文档...</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default FormPanel;
