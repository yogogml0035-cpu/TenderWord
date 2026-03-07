'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, CheckCircle2, Copy, Loader2, RefreshCw, XCircle } from 'lucide-react';
import type { Message } from '@/types/chat';

interface TaskContentMessageProps {
  message: Message;
  onRetry?: () => void;
  maxHeight?: number;
}

async function copyPlainText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'absolute';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

function getStatusIcon(status: Message['status']) {
  switch (status) {
    case 'generating':
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'error':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'cancelled':
      return <XCircle className="h-4 w-4 text-gray-400" />;
    default:
      return null;
  }
}

function getStatusLabel(status: Message['status']) {
  switch (status) {
    case 'generating':
      return '生成中...';
    case 'completed':
      return '已完成';
    case 'error':
      return '生成失败';
    case 'cancelled':
      return '已取消';
    default:
      return 'AI 内容';
  }
}

function getBorderColor(status: Message['status']) {
  switch (status) {
    case 'generating':
      return 'border-blue-500';
    case 'completed':
      return 'border-green-500';
    case 'error':
      return 'border-red-500';
    case 'cancelled':
      return 'border-gray-300';
    default:
      return 'border-gray-200';
  }
}

export function TaskContentMessage({
  message,
  onRetry,
  maxHeight = 320,
}: TaskContentMessageProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const content = typeof message.content === 'string' ? message.content : '';
  const progressText = message.metadata?.progressText;
  const progressPercent = message.metadata?.progressPercent;

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    setStickToBottom(atBottom);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickToBottom) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [content, stickToBottom]);

  const handleCopyContent = useCallback(() => {
    void copyPlainText(content);
  }, [content]);

  return (
    <div className={`overflow-hidden rounded border bg-white shadow-sm ${getBorderColor(message.status)}`}>
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">AI 生成内容</span>
          <div className="ml-1 flex items-center gap-1.5 text-xs text-gray-500">
            {getStatusIcon(message.status)}
            <span>{getStatusLabel(message.status)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {message.status === 'error' && onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 rounded bg-blue-50 px-2.5 py-1 text-xs text-blue-600 transition-colors duration-200 hover:bg-blue-100"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              重试
            </button>
          )}
          <button
            type="button"
            aria-label="复制AI内容"
            title="复制AI内容"
            onClick={handleCopyContent}
            disabled={!content}
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {(typeof progressText === 'string' || typeof progressPercent === 'number') && (
        <div className="border-b border-gray-100 bg-gray-50/60 px-4 py-1.5 text-xs text-gray-500">
          {typeof progressText === 'string' ? progressText : '处理中'}
          {typeof progressPercent === 'number' ? ` (${Math.round(progressPercent)}%)` : ''}
        </div>
      )}

      {message.error && (
        <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          {message.error}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="overflow-x-hidden overflow-y-auto p-3"
        style={{ maxHeight }}
      >
        {content ? (
          <pre className="min-w-0 break-all whitespace-pre-wrap font-mono text-sm text-gray-700">
            {content}
          </pre>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <div className="relative mb-3">
              <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-30" />
              <div className="relative rounded-full bg-white p-2 shadow-sm">
                <Bot className="h-5 w-5 text-blue-400" />
              </div>
            </div>
            <span className="text-xs">等待生成...</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default TaskContentMessage;
