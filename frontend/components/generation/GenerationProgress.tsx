'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react';

export interface GenerationProgressProps {
  /** Current progress percentage (0-100) */
  progress: number;
  /** Total number of nodes */
  totalNodes: number;
  /** Number of completed nodes */
  completedNodes: number;
  /** Current node name */
  currentNode?: string;
  /** Current node display name */
  currentNodeDisplay?: string;
  /** Current status */
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | null;
  /** Estimated time remaining in seconds */
  estimatedTime?: number;
  /** Error message */
  error?: string | null;
  className?: string;
}

const NODE_NAME_MAP: Record<string, string> = {
  prepare_template: '复制原始模板文件',
  extract_tender_params: '提取原始采购需求',
  delete_tender_param: '删除原始采购需求',
  get_replacements: '获取原始项目信息',
  replace_content: '替换最新项目信息',
  generate_polished_text: 'AI生成采购需求',
  update_word: '生成招标文件',
};

export function GenerationProgress({
  progress,
  totalNodes,
  completedNodes,
  currentNode,
  currentNodeDisplay,
  status,
  estimatedTime,
  error,
  className,
}: GenerationProgressProps) {
  const getStatusIcon = () => {
    switch (status) {
      case 'queued':
        return <Clock className="w-5 h-5 text-[var(--text-muted)]" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-[var(--primary)] animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-[var(--success)]" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-[var(--error)]" />;
      case 'cancelled':
        return <AlertCircle className="w-5 h-5 text-[var(--warning)]" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'queued':
        return '排队中';
      case 'running':
        return '生成中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '生成失败';
      case 'cancelled':
        return '已取消';
      default:
        return '等待中';
    }
  };

  const getStatusBadgeClass = () => {
    switch (status) {
      case 'queued':
        return 'st-badge-info';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'st-badge-success';
      case 'failed':
        return 'st-badge-error';
      case 'cancelled':
        return 'st-badge-warning';
      default:
        return 'st-badge-info';
    }
  };

  const displayNodeName = currentNodeDisplay || NODE_NAME_MAP[currentNode || ''] || currentNode;

  return (
    <div className={cn('st-card', className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {getStatusIcon()}
          <div>
            <p className="font-medium text-[var(--foreground)]">{getStatusText()}</p>
            {status === 'running' && displayNodeName && (
              <p className="text-sm text-[var(--text-muted)]">正在执行：{displayNodeName}</p>
            )}
          </div>
        </div>
        <span className={cn('st-badge', getStatusBadgeClass())}>
          {Math.round(progress)}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="st-progress-bar">
        <div
          className="st-progress-fill"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>

      {/* Progress Details */}
      <div className="flex items-center justify-between mt-3 text-sm">
        <p className="text-[var(--text-muted)]">
          已完成节点：{completedNodes} / {totalNodes}
        </p>
        {estimatedTime !== undefined && estimatedTime > 0 && status === 'running' && (
          <p className="text-[var(--text-muted)]">
            预计剩余：{formatTime(estimatedTime)}
          </p>
        )}
      </div>

      {/* Node Progress */}
      {totalNodes > 0 && (
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
          {Array.from({ length: totalNodes }, (_, i) => {
            const isCompleted = i < completedNodes;
            const isCurrent = i === completedNodes && status === 'running';
            return (
              <div
                key={i}
                className={cn(
                  'h-1.5 rounded-full transition-colors',
                  isCompleted
                    ? 'bg-[var(--success)]'
                    : isCurrent
                    ? 'bg-[var(--primary)]'
                    : 'bg-[var(--secondary-bg)]'
                )}
              />
            );
          })}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-[var(--error)] mt-0.5" />
            <p className="text-sm text-[var(--error)]">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.ceil(seconds)}秒`;
  }
  if (seconds < 3600) {
    return `${Math.ceil(seconds / 60)}分钟`;
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.ceil((seconds % 3600) / 60);
  return `${hours}小时${minutes > 0 ? `${minutes}分` : ''}`;
}

export default GenerationProgress;
