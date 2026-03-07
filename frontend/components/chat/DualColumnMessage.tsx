'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  FileText,
  Bot,
  Loader2,
  CheckCircle2,
  XCircle,
  Download,
  RefreshCw,
  Copy,
} from 'lucide-react';
import type { Message, LogEntry } from '@/types/chat';
import { isDualColumnContent } from '@/types/chat';

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

interface DualColumnMessageProps {
  message: Message;
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: () => void;
  maxHeight?: number;
}

export function DualColumnMessage({
  message,
  onDownload,
  onRetry,
  maxHeight = 400,
}: DualColumnMessageProps) {
  const leftScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const [leftStickToBottom, setLeftStickToBottom] = useState(true);
  const [rightStickToBottom, setRightStickToBottom] = useState(true);

  const content = message.content;
  const dualContent = isDualColumnContent(content) ? content : null;

  const logs = dualContent?.logs || [];
  const aiContent = dualContent?.aiContent?.text || '';
  const logsCopyText = logs
    .map((log) => `${formatLogTime(log.timestamp)} [${log.level.toUpperCase()}] ${log.message}`)
    .join('\n');

  const handleLeftScroll = useCallback(() => {
    const el = leftScrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    setLeftStickToBottom(atBottom);
  }, []);

  const handleRightScroll = useCallback(() => {
    const el = rightScrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    setRightStickToBottom(atBottom);
  }, []);

  useEffect(() => {
    const el = leftScrollRef.current;
    if (!el || !leftStickToBottom) return;
    el.scrollTop = el.scrollHeight;
  }, [logs.length, leftStickToBottom]);

  useEffect(() => {
    const el = rightScrollRef.current;
    if (!el || !rightStickToBottom) return;
    el.scrollTop = el.scrollHeight;
  }, [aiContent, rightStickToBottom]);

  const getStatusIcon = () => {
    switch (message.status) {
      case 'generating':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getBorderColor = () => {
    switch (message.status) {
      case 'error':
        return 'border-red-500';
      case 'completed':
        return 'border-green-500';
      case 'generating':
        return 'border-blue-500';
      default:
        return 'border-gray-200';
    }
  };

  const handleDownload = () => {
    if (message.metadata?.outputFile && onDownload) {
      onDownload(message.metadata.outputFile, message.metadata.fileName);
    }
  };

  const handleCopyLogs = useCallback(() => {
    void copyPlainText(logsCopyText);
  }, [logsCopyText]);

  const handleCopyAiContent = useCallback(() => {
    void copyPlainText(aiContent);
  }, [aiContent]);

  return (
    <div className={`rounded border ${getBorderColor()} overflow-hidden bg-white shadow-sm`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-3">
          {message.status === 'completed' && message.metadata?.outputFile && (
            <button
              onClick={handleDownload}
              className="flex items-center gap-1 rounded bg-blue-500 px-3 py-1 text-sm text-white shadow-sm transition-colors duration-200 hover:bg-blue-600"
            >
              <Download className="h-4 w-4" />
              下载文件
            </button>
          )}

          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm font-medium text-gray-700">
              {message.status === 'generating' && '生成中...'}
              {message.status === 'completed' && '已完成'}
              {message.status === 'error' && '生成失败'}
              {message.status === 'cancelled' && '已取消'}
            </span>
          </div>
        </div>

        {message.status === 'error' && onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 rounded bg-blue-50 px-3 py-1.5 text-sm text-blue-600 transition-colors duration-200 hover:bg-blue-100"
          >
            <RefreshCw className="h-4 w-4" />
            重新生成
          </button>
        )}
      </div>

      {/* Error Message */}
      {message.error && (
        <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          {message.error}
        </div>
      )}

      {/* Dual Column Content */}
      <div className="flex min-w-0" style={{ maxHeight: `${maxHeight}px` }}>
        {/* Left Column - Logs */}
        <div className="flex min-w-0 w-1/2 flex-col border-r border-gray-200">
          <div className="flex items-center justify-between gap-2 border-b border-gray-200 bg-gray-50 px-3 py-2">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-gray-500" />
              <span className="text-xs font-medium text-gray-600">进度日志</span>
            </div>
            <button
              type="button"
              aria-label="复制进度日志"
              title="复制进度日志"
              onClick={handleCopyLogs}
              disabled={!logsCopyText}
              className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>

          <div
            ref={leftScrollRef}
            onScroll={handleLeftScroll}
            className="flex-1 space-y-2 overflow-x-hidden overflow-y-auto p-3"
          >
            {logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                <div className="relative mb-3">
                  <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-30" />
                  <div className="relative rounded-full bg-white p-2 shadow-sm">
                    <FileText className="h-5 w-5 text-blue-400" />
                  </div>
                </div>
                <span className="text-xs">等待开始...</span>
              </div>
            ) : (
              logs.map((log) => <LogEntryItem key={log.id} log={log} />)
            )}
          </div>
        </div>

        {/* Right Column - AI Content */}
        <div className="flex min-w-0 w-1/2 flex-col">
          <div className="flex items-center justify-between gap-2 border-b border-gray-200 bg-gray-50 px-3 py-2">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-gray-500" />
              <span className="text-xs font-medium text-gray-600">AI 生成内容</span>
            </div>
            <button
              type="button"
              aria-label="复制AI内容"
              title="复制AI内容"
              onClick={handleCopyAiContent}
              disabled={!aiContent}
              className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>

          <div
            ref={rightScrollRef}
            onScroll={handleRightScroll}
            className="flex-1 overflow-x-hidden overflow-y-auto p-3"
          >
            {aiContent ? (
              <pre className="min-w-0 break-all whitespace-pre-wrap font-mono text-sm text-gray-700">
                {aiContent}
              </pre>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                <div className="relative mb-3">
                  <div className="absolute inset-0 animate-pulse rounded-full bg-purple-100 opacity-30" />
                  <div className="relative rounded-full bg-white p-2 shadow-sm">
                    <Bot className="h-5 w-5 text-purple-400" />
                  </div>
                </div>
                <span className="text-xs">等待生成...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Log Entry Sub-component
function LogEntryItem({ log }: { log: LogEntry }) {
  const getLevelColor = (level: string) => {
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

  const formatTime = (timestamp: number) => {
    return formatLogTime(timestamp);
  };

  return (
    <div className="flex min-w-0 items-start gap-2 text-xs">
      <span className="shrink-0 text-gray-400">{formatTime(log.timestamp)}</span>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${getLevelColor(log.level)}`}>
        {log.level.toUpperCase()}
      </span>
      <span className="min-w-0 break-all whitespace-pre-wrap text-gray-700">{log.message}</span>
    </div>
  );
}

export default DualColumnMessage;
