'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Copy, FileText, Loader2, XCircle } from 'lucide-react';
import type { LogEntry, Message } from '@/types/chat';

interface TaskLogMessageProps {
  message: Message;
  maxHeight?: number;
  disabled?: boolean;
}

function formatLogTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
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

function getStatusLabel(message: Message) {
  if (message.status === 'error' && message.metadata?.localTaskReason === 'backend_restart') {
    return '日志结束（已中断）';
  }

  const status = message.status;
  switch (status) {
    case 'generating':
      return '日志收集中...';
    case 'completed':
      return '日志完成';
    case 'error':
      return '日志结束（失败）';
    case 'cancelled':
      return '日志结束（已取消）';
    default:
      return '日志';
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

function normalizeLogs(logs: unknown): LogEntry[] {
  if (!Array.isArray(logs)) {
    return [];
  }

  return logs.filter((item): item is LogEntry => {
    return (
      typeof item === 'object' &&
      item !== null &&
      typeof (item as LogEntry).id === 'string' &&
      typeof (item as LogEntry).message === 'string' &&
      typeof (item as LogEntry).timestamp === 'number'
    );
  });
}

function LogEntryItem({ log }: { log: LogEntry }) {
  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'text-red-600 bg-red-50';
      case 'warn':
        return 'text-yellow-600 bg-yellow-50';
      case 'debug':
        return 'text-gray-500 bg-gray-50';
      default:
        return 'text-blue-600 bg-blue-50';
    }
  };

  return (
    <div className="flex min-w-0 items-start gap-2 text-xs">
      <span className="shrink-0 text-gray-400">{formatLogTime(log.timestamp)}</span>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${getLevelColor(log.level)}`}>
        {log.level.toUpperCase()}
      </span>
      <span className="min-w-0 break-all whitespace-pre-wrap text-gray-700">{log.message}</span>
    </div>
  );
}

export function TaskLogMessage({
  message,
  maxHeight = 260,
  disabled = false,
}: TaskLogMessageProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);

  const logs = normalizeLogs(message.metadata?.logs);
  const progressText = message.metadata?.progressText;
  const progressPercent = message.metadata?.progressPercent;
  const isRewriteTask = message.metadata?.taskKind === 'rewrite';

  const copyText = useMemo(
    () =>
      logs
        .map((log) => `${formatLogTime(log.timestamp)} [${log.level.toUpperCase()}] ${log.message}`)
        .join('\n'),
    [logs]
  );

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
  }, [logs.length, stickToBottom]);

  const handleCopyLogs = useCallback(() => {
    if (disabled) {
      return;
    }
    void copyPlainText(copyText);
  }, [copyText, disabled]);

  return (
    <div className={`overflow-hidden rounded border bg-white shadow-sm ${getBorderColor(message.status)}`}>
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">
            {isRewriteTask ? '修改进度' : '进度日志'}
          </span>
          <div className="ml-1 flex items-center gap-1.5 text-xs text-gray-500">
            {getStatusIcon(message.status)}
            <span>{getStatusLabel(message)}</span>
          </div>
        </div>
        <button
          type="button"
          aria-label="复制进度日志"
          title="复制进度日志"
          onClick={handleCopyLogs}
          disabled={!copyText || disabled}
          className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Copy className="h-3.5 w-3.5" />
        </button>
      </div>

      {(typeof progressText === 'string' || typeof progressPercent === 'number') && (
        <div className="border-b border-gray-100 bg-gray-50/60 px-4 py-1.5 text-xs text-gray-500">
          {typeof progressText === 'string' ? progressText : '处理中'}
          {typeof progressPercent === 'number' ? ` (${Math.round(progressPercent)}%)` : ''}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="space-y-2 overflow-x-hidden overflow-y-auto p-3"
        style={{ maxHeight }}
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <div className="relative mb-3">
              <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-30" />
              <div className="relative rounded-full bg-white p-2 shadow-sm">
                <FileText className="h-5 w-5 text-blue-400" />
              </div>
            </div>
            <span className="text-xs">等待日志...</span>
          </div>
        ) : (
          logs.map((log) => <LogEntryItem key={log.id} log={log} />)
        )}
      </div>
    </div>
  );
}

export default TaskLogMessage;
