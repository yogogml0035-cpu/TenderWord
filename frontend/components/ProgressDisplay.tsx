'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { NodeDisplayNames } from '@/types/api';

export interface ProgressDisplayProps {
  percent: number;
  currentNode?: string;
  status: 'idle' | 'running' | 'completed' | 'error';
}

export function ProgressDisplay({ percent, currentNode, status }: ProgressDisplayProps) {
  // 根据状态获取颜色主题
  const getStatusColors = () => {
    switch (status) {
      case 'completed':
        return {
          bar: 'bg-green-500',
          text: 'text-green-600',
          bg: 'bg-green-100',
        };
      case 'error':
        return {
          bar: 'bg-red-500',
          text: 'text-red-600',
          bg: 'bg-red-100',
        };
      case 'running':
      default:
        return {
          bar: 'bg-blue-500',
          text: 'text-blue-600',
          bg: 'bg-blue-100',
        };
    }
  };

  // 获取状态文本
  const getStatusText = () => {
    switch (status) {
      case 'completed':
        return '已完成';
      case 'error':
        return '执行出错';
      case 'running':
        return '正在处理...';
      case 'idle':
      default:
        return '等待开始';
    }
  };

  // 将节点名称映射为中文显示
  const getNodeDisplayName = (nodeName?: string) => {
    if (!nodeName) return '';
    return NodeDisplayNames[nodeName] || nodeName;
  };

  const colors = getStatusColors();
  const statusText = getStatusText();
  const nodeDisplayName = getNodeDisplayName(currentNode);

  // 确保百分比在 0-100 之间
  const clampedPercent = Math.min(100, Math.max(0, percent));

  return (
    <div className="w-full space-y-3">
      {/* 进度条和信息行 */}
      <div className="space-y-2">
        {/* 顶部信息：百分比和状态 */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[var(--foreground)]">任务进度</span>
          <span className={cn('text-sm font-semibold', colors.text)}>{clampedPercent}%</span>
        </div>

        {/* 进度条容器 */}
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={cn('h-full transition-all duration-500 ease-out', colors.bar)}
            style={{ width: `${clampedPercent}%` }}
            role="progressbar"
            aria-valuenow={clampedPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="任务进度"
          />
        </div>

        {/* 底部信息：当前节点和状态 */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span className="text-[var(--text-muted)]">当前步骤:</span>
            {nodeDisplayName ? (
              <span className="font-medium text-[var(--foreground)]">{nodeDisplayName}</span>
            ) : (
              <span className="text-[var(--text-muted)]">--</span>
            )}
          </div>
          <span
            className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', colors.bg, colors.text)}
          >
            {statusText}
          </span>
        </div>
      </div>
    </div>
  );
}

export default ProgressDisplay;
