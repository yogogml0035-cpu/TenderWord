'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface TenderInfoItem {
  /** Label for the info item */
  label: string;
  /** Value to display */
  value: string | number | null | undefined;
  /** Optional key for React rendering */
  key?: string;
}

export interface InfoCardProps {
  /** Tender information items to display */
  items: TenderInfoItem[];
  /** Additional CSS classes */
  className?: string;
  /** Loading state */
  isLoading?: boolean;
  /** Number of skeleton rows to show when loading */
  skeletonRows?: number;
  /** Number of columns in the grid */
  columns?: 1 | 2 | 3 | 4;
  /** Optional card title */
  title?: string;
  /** Empty state message when no items have values */
  emptyMessage?: string;
}

/**
 * InfoCard - 统一信息展示组件（招标数据）
 * 
 * Displays tender information in a clean, read-only format.
 * Based on XJCG's tender data display pattern (Section 1).
 * 
 * Features:
 * - Clean read-only styling
 * - Loading skeleton state
 * - Responsive grid layout
 * - Empty state handling
 */
export function InfoCard({
  items,
  className,
  isLoading = false,
  skeletonRows = 4,
  columns = 2,
  title,
  emptyMessage = '暂无数据',
}: InfoCardProps) {
  const validItems = items.filter(
    (item) => item.value !== null && item.value !== undefined && item.value !== ''
  );

  const columnClasses = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  };

  if (isLoading) {
    return (
      <div
        className={cn(
          'mt-4 space-y-2 rounded-lg border border-green-200 bg-green-50 p-4',
          className
        )}
      >
        {title && (
          <h4 className="mb-3 text-sm font-semibold text-green-800">
            {title}
          </h4>
        )}
        <div className={cn('grid gap-4', columnClasses[columns])}>
          {Array.from({ length: skeletonRows }).map((_, index) => (
            <div key={index} className="space-y-1">
              <div className="h-3 w-16 animate-pulse rounded bg-[var(--border-color)]" />
              <div className="h-4 w-3/4 animate-pulse rounded bg-[var(--border-color)]" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (validItems.length === 0) {
    return (
      <div
        className={cn(
          'mt-4 rounded-lg border border-green-200 bg-green-50 p-4 text-center',
          className
        )}
      >
        <p className="text-sm text-green-700">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'mt-4 space-y-2 rounded-lg border border-green-200 bg-green-50 p-4',
        className
      )}
    >
      {title && (
        <h4 className="mb-3 text-sm font-semibold text-green-800">
          {title}
        </h4>
      )}
      <div className={cn('grid gap-4', columnClasses[columns])}>
        {validItems.map((item, index) => (
          <div key={item.key || index} className="space-y-1">
            <p className="text-xs text-green-700/80">
              {item.label}
            </p>
            <p className="break-words whitespace-pre-wrap text-sm font-medium text-green-900">
              {item.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default InfoCard;
