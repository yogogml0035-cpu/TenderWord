'use client';

import React, { useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  node?: string;
}

export interface LogViewerProps {
  logs: LogEntry[];
  onClear?: () => void;
}

export function LogViewer({ logs, onClear }: LogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const getLevelStyles = (level: string) => {
    switch (level.toLowerCase()) {
      case 'info':
        return 'text-gray-600 bg-gray-50';
      case 'warning':
      case 'warn':
        return 'text-yellow-700 bg-yellow-50';
      case 'error':
      case 'err':
        return 'text-red-700 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getLevelBadgeStyles = (level: string) => {
    switch (level.toLowerCase()) {
      case 'info':
        return 'bg-gray-200 text-gray-700';
      case 'warning':
      case 'warn':
        return 'bg-yellow-200 text-yellow-800';
      case 'error':
      case 'err':
        return 'bg-red-200 text-red-800';
      default:
        return 'bg-gray-200 text-gray-700';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-[var(--border)] bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--background-secondary)] px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-[var(--foreground)]">实时日志</span>
          <span className="text-xs text-[var(--text-muted)]">({logs.length} 条)</span>
        </div>
        {onClear && logs.length > 0 && (
          <button
            onClick={onClear}
            className="rounded px-2 py-1 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--border)]"
            type="button"
          >
            清空
          </button>
        )}
      </div>

      {/* Log List */}
      <div ref={scrollRef} className="flex-1 space-y-1 overflow-y-auto p-2 font-mono text-sm">
        {logs.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-[var(--text-muted)]">
            暂无日志
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className={cn('flex items-start gap-2 rounded p-2', getLevelStyles(log.level))}
            >
              {/* Timestamp */}
              <span className="flex-shrink-0 text-xs whitespace-nowrap opacity-70">
                {formatTimestamp(log.timestamp)}
              </span>

              {/* Level Badge */}
              <span
                className={cn(
                  'flex-shrink-0 rounded px-1.5 py-0.5 text-xs font-medium uppercase',
                  getLevelBadgeStyles(log.level)
                )}
              >
                {log.level.toUpperCase()}
              </span>

              {/* Node info (if available) */}
              {log.node && <span className="flex-shrink-0 text-xs opacity-60">[{log.node}]</span>}

              {/* Message */}
              <span className="flex-1 break-words">{log.message}</span>
            </div>
          ))
        )}
        {/* Bottom anchor for auto-scroll */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default LogViewer;
