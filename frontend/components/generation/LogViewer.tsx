'use client';

import React, { useRef, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Download, Trash2, Maximize2, Minimize2 } from 'lucide-react';

export interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | string;
  message: string;
  node?: string;
}

export interface LogViewerProps {
  logs: LogEntry[];
  maxHeight?: string;
  autoScroll?: boolean;
  className?: string;
  onClear?: () => void;
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-600',
  WARNING: 'text-yellow-600',
  ERROR: 'text-red-600',
};

const LEVEL_BG_COLORS: Record<string, string> = {
  DEBUG: 'bg-gray-100',
  INFO: 'bg-blue-50',
  WARNING: 'bg-yellow-50',
  ERROR: 'bg-red-50',
};

export function LogViewer({
  logs,
  maxHeight = '300px',
  autoScroll = true,
  className,
  onClear,
}: LogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [filter, setFilter] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL');

  const filteredLogs =
    filter === 'ALL' ? logs : logs.filter((log) => log.level === filter);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleExport = () => {
    const content = logs
      .map(
        (log) =>
          `[${log.timestamp}] [${log.level}]${log.node ? ` [${log.node}]` : ''} ${log.message}`
      )
      .join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div className={cn('st-card', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-[var(--primary)]" />
          <h3 className="font-semibold text-[var(--foreground)]">执行日志</h3>
          <span className="text-xs text-[var(--text-muted)]">({filteredLogs.length} 条)</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="text-xs px-2 py-1 border border-[var(--border)] rounded bg-white"
          >
            <option value="ALL">全部</option>
            <option value="INFO">信息</option>
            <option value="WARNING">警告</option>
            <option value="ERROR">错误</option>
          </select>

          {/* Export */}
          <button
            onClick={handleExport}
            disabled={logs.length === 0}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--foreground)] disabled:opacity-50"
            title="导出日志"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* Clear */}
          {onClear && (
            <button
              onClick={onClear}
              disabled={logs.length === 0}
              className="p-1.5 text-[var(--text-muted)] hover:text-[var(--error)] disabled:opacity-50"
              title="清空日志"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          {/* Expand/Collapse */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--foreground)]"
            title={isExpanded ? '收起' : '展开'}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Log Content */}
      <div
        ref={scrollRef}
        className={cn(
          'overflow-y-auto font-mono text-xs space-y-1 rounded-lg p-3 bg-[#1e1e1e]',
          isExpanded ? 'h-[600px]' : ''
        )}
        style={{ maxHeight: isExpanded ? undefined : maxHeight }}
      >
        {filteredLogs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">暂无日志</div>
        ) : (
          filteredLogs.map((log, index) => (
            <div
              key={index}
              className={cn(
                'flex gap-3 py-1 px-2 rounded',
                LEVEL_BG_COLORS[log.level] || 'bg-gray-800'
              )}
            >
              <span className="text-gray-400 flex-shrink-0">
                {formatTimestamp(log.timestamp)}
              </span>
              <span
                className={cn(
                  'flex-shrink-0 font-bold w-16',
                  LEVEL_COLORS[log.level] || 'text-gray-400'
                )}
              >
                {log.level}
              </span>
              {log.node && (
                <span className="text-purple-400 flex-shrink-0">[{log.node}]</span>
              )}
              <span className="text-gray-300 break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-[var(--text-muted)]">
        <span>自动滚动：{autoScroll ? '开启' : '关闭'}</span>
        {filteredLogs.length > 0 && (
          <span>最新日志：{formatTimestamp(filteredLogs[filteredLogs.length - 1]?.timestamp)}</span>
        )}
      </div>
    </div>
  );
}

export default LogViewer;
