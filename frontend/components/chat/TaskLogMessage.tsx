'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Copy, FileText, Loader2, XCircle } from 'lucide-react';
import type { LogEntry, Message } from '@/types/chat';

interface TaskLogMessageProps {
  message: Message;
  maxHeight?: number;
  disabled?: boolean;
}

const VISIBLE_LOG_LIMIT = 80;

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

type StyleWritebackLogStatus = 'success' | 'skip' | 'failure';

function parseStyleWritebackLogMessage(message: string): {
  status: StyleWritebackLogStatus;
  badgeLabel: string;
  badgeClassName: string;
  textClassName: string;
  detail: string;
} | null {
  const match = message.match(/^(.*?：)?样式回填(成功|跳过|失败)\[(\d+\/\d+)\]\s*(.*)$/);
  if (!match) {
    return null;
  }

  const [, rawStepLabel, rawStatus, rawProgress, rawDetail] = match;
  const stepLabel = rawStepLabel?.replace(/：$/, '').trim();
  const detail = [stepLabel, `[${rawProgress}] ${rawDetail}`.trim()].filter(Boolean).join(' ');

  switch (rawStatus) {
    case '成功':
      return {
        status: 'success',
        badgeLabel: '回填成功',
        badgeClassName: 'text-green-700 bg-green-50',
        textClassName: 'text-green-800',
        detail,
      };
    case '跳过':
      return {
        status: 'skip',
        badgeLabel: '回填跳过',
        badgeClassName: 'text-amber-700 bg-amber-50',
        textClassName: 'text-amber-800',
        detail,
      };
    case '失败':
      return {
        status: 'failure',
        badgeLabel: '回填失败',
        badgeClassName: 'text-red-700 bg-red-50',
        textClassName: 'text-red-800',
        detail,
      };
    default:
      return null;
  }
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

  const styleWritebackLog = parseStyleWritebackLogMessage(log.message);
  const badgeLabel = styleWritebackLog?.badgeLabel ?? log.level.toUpperCase();
  const badgeClassName = styleWritebackLog?.badgeClassName ?? getLevelColor(log.level);
  const textClassName = styleWritebackLog?.textClassName ?? 'text-gray-700';
  const messageText = styleWritebackLog?.detail ?? log.message;

  return (
    <div className="flex min-w-0 items-start gap-2 text-xs">
      <span className="shrink-0 text-gray-400">{formatLogTime(log.timestamp)}</span>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClassName}`}>
        {badgeLabel}
      </span>
      <span className={`min-w-0 break-all whitespace-pre-wrap ${textClassName}`}>
        {messageText}
      </span>
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
  const [expanded, setExpanded] = useState(message.status !== 'generating');

  const logs = normalizeLogs(message.metadata?.logs);
  const visibleLogs = logs.length > VISIBLE_LOG_LIMIT ? logs.slice(-VISIBLE_LOG_LIMIT) : logs;
  const latestLog = logs[logs.length - 1];
  const latestVisibleLogId = visibleLogs[visibleLogs.length - 1]?.id || '';
  const progressText = message.metadata?.progressText;
  const progressPercent = message.metadata?.progressPercent;
  const isRewriteTask = message.metadata?.taskKind === 'rewrite';

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
    if (!expanded || !el || !stickToBottom) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [expanded, latestVisibleLogId, stickToBottom]);

  const handleCopyLogs = useCallback(() => {
    if (disabled) {
      return;
    }
    const copyText = logs
      .map((log) => `${formatLogTime(log.timestamp)} [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n');
    void copyPlainText(copyText);
  }, [disabled, logs]);

  const toggleExpanded = useCallback(() => {
    setExpanded((current) => !current);
  }, []);

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
        <div className="flex items-center gap-2">
          {logs.length > 0 && (
            <span className="rounded bg-white px-2 py-0.5 text-xs text-gray-400">
              {logs.length} 条
            </span>
          )}
          <button
            type="button"
            aria-label={expanded ? '收起进度日志' : '展开进度日志'}
            title={expanded ? '收起进度日志' : '展开进度日志'}
            onClick={toggleExpanded}
            disabled={disabled}
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            aria-label="复制进度日志"
            title="复制进度日志"
            onClick={handleCopyLogs}
            disabled={logs.length === 0 || disabled}
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

      {!expanded && latestLog && (
        <div className="border-t border-gray-100 bg-white px-4 py-2 text-xs text-gray-500">
          <span className="mr-2 text-gray-400">最新</span>
          <span className="block truncate break-all">{latestLog.message}</span>
        </div>
      )}

      {expanded && (
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
            <>
              {logs.length > visibleLogs.length && (
                <div className="rounded bg-gray-50 px-2 py-1 text-center text-xs text-gray-400">
                  最近 {visibleLogs.length} / 共 {logs.length} 条
                </div>
              )}
              {visibleLogs.map((log) => <LogEntryItem key={log.id} log={log} />)}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default TaskLogMessage;
