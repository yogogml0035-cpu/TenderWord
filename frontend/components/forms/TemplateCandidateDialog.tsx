'use client';

import React from 'react';
import { Loader2, RefreshCcw, X } from 'lucide-react';
import type { TemplateCandidate } from '@/types/api';
import { cn } from '@/lib/utils';
import { ErrorDisplay } from './shared';

export interface TemplateCandidateDialogProps {
  open: boolean;
  candidates: TemplateCandidate[];
  loading: boolean;
  refreshing: boolean;
  selectingRowKey?: string | null;
  error?: string | null;
  notice?: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onSelect: (candidate: TemplateCandidate, rowKey: string) => void;
  getDownloadUrl: (fileUrl: string, downloadName: string) => string;
}

function displayTemplateValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }

  const normalizedValue = String(value).trim();
  return normalizedValue || '--';
}

function buildRowIdentity(candidate: TemplateCandidate): string {
  return [
    candidate.tenderno || 'unknown-tenderno',
    candidate.tendername || 'unknown-tender',
    candidate.year ?? 'unknown-year',
    candidate.zbr || 'unknown-zbr',
    candidate.xbr || 'unknown-xbr',
    candidate.fsg || 'no-fsg',
    candidate.shener || 'no-shener',
  ].join('|');
}

export function buildTemplateCandidateRowKey(
  candidate: TemplateCandidate,
  rowIndex: number
): string {
  return `${buildRowIdentity(candidate)}#${rowIndex}`;
}

function getPriorityBadgeClassName(priority: string): string {
  if (priority === '1') {
    return 'border-red-200 bg-red-50 text-red-700';
  }
  if (priority === '2') {
    return 'border-orange-200 bg-orange-50 text-orange-700';
  }
  return 'border-slate-200 bg-slate-100 text-slate-600';
}

export function TemplateCandidateDialog({
  open,
  candidates,
  loading,
  refreshing,
  selectingRowKey,
  error,
  notice,
  onClose,
  onRefresh,
  onSelect,
  getDownloadUrl,
}: TemplateCandidateDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-2 py-2 sm:px-3 sm:py-3">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="智能抽取模板"
        data-testid="template-candidate-dialog"
        className="flex max-h-[96vh] w-fit min-w-[min(56rem,96vw)] max-w-[96vw] flex-col overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.24)]"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 via-white to-slate-50/80 px-4 py-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">智能抽取模板</h3>
            <p className="mt-0.5 text-xs leading-5 text-slate-500">
              从ERP模板库中选择适合模板，将自动回填到发售稿和送审稿的上传区。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading || refreshing}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors',
                'hover:border-slate-300 hover:bg-slate-100',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              刷新
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              aria-label="关闭模板弹窗"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {error || notice ? (
          <div className="space-y-3 border-b border-slate-100 px-4 py-3">
            {error ? <ErrorDisplay message={error} onDismiss={onClose} /> : null}
            {notice ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                {notice}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto overflow-x-auto px-4 pb-4">
          {loading ? (
            <div className="flex h-56 items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在加载模板列表...
            </div>
          ) : error && candidates.length === 0 ? (
            <div className="flex h-56 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
              当前无法加载模板记录，请根据上方提示调整条件后重试。
            </div>
          ) : candidates.length === 0 ? (
            <div className="flex h-56 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
              当前条件下暂无可展示的模板记录。
            </div>
          ) : (
            <div className="rounded-[18px] border border-slate-200 bg-white">
              <table className="min-w-[75rem] w-max table-fixed divide-y divide-slate-200 text-center text-[13px]">
                <thead className="sticky top-0 z-10 bg-slate-50/95 text-slate-600 backdrop-blur">
                  <tr>
                    <th className="w-[4.25rem] px-2.5 py-2 font-semibold">年份</th>
                    <th className="w-[11rem] px-2.5 py-2 font-semibold">项目</th>
                    <th className="w-[9.5rem] px-2.5 py-2 font-semibold">主办人/协办人</th>
                    <th className="w-[8rem] px-2.5 py-2 font-semibold">采购人</th>
                    <th className="w-[5.5rem] px-2.5 py-2 font-semibold">部门</th>
                    <th className="w-[6.5rem] px-2.5 py-2 font-semibold">行业类型</th>
                    <th className="w-[6.5rem] px-2.5 py-2 font-semibold">招标类型</th>
                    <th className="w-[5rem] px-2.5 py-2 font-semibold">采购方式</th>
                    <th className="w-[4.5rem] px-2.5 py-2 font-semibold text-center">优先级</th>
                    <th className="w-[9.5rem] px-2.5 py-2 font-semibold">推荐模板</th>
                    <th className="w-[5rem] px-2.5 py-2 font-semibold text-center">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white text-slate-700">
                  {candidates.map((candidate, index) => {
                    const rowKey = buildTemplateCandidateRowKey(candidate, index);
                    const isSelecting = selectingRowKey === rowKey;
                    return (
                      <tr
                        key={rowKey}
                        data-testid={`template-candidate-row-${index}`}
                        className="align-top transition-colors hover:bg-slate-50/80"
                      >
                        <td className="px-2.5 py-2 whitespace-nowrap">
                          {displayTemplateValue(candidate.year)}
                        </td>
                        <td className="px-2.5 py-2 font-medium text-slate-900">
                          <span className="block whitespace-normal break-words leading-5 text-center">
                            {displayTemplateValue(candidate.tendername)}
                          </span>
                          <span className="mt-1 block text-center text-xs font-normal text-slate-500">
                            {displayTemplateValue(candidate.tenderno)}
                          </span>
                          {candidate.blocked_reason ? (
                            <span className="mt-1 block text-center text-xs text-amber-700">
                              {candidate.blocked_reason}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-2.5 py-2 text-slate-900">
                          <span className="block whitespace-normal break-words leading-5 text-center">
                            {displayTemplateValue(candidate.zbr)}
                          </span>
                          <span className="mt-1 block whitespace-normal break-words text-center text-xs text-slate-500">
                            {displayTemplateValue(candidate.xbr)}
                          </span>
                        </td>
                        <td className="px-2.5 py-2 whitespace-normal break-words leading-5">
                          {displayTemplateValue(candidate.tname)}
                        </td>
                        <td className="px-2.5 py-2 whitespace-normal break-words leading-5">
                          {displayTemplateValue(candidate.bm)}
                        </td>
                        <td className="px-2.5 py-2 whitespace-normal break-words leading-5">
                          {displayTemplateValue(candidate.hytype)}
                        </td>
                        <td className="px-2.5 py-2 whitespace-normal break-words leading-5">
                          {displayTemplateValue(candidate.tendertype)}
                        </td>
                        <td className="px-2.5 py-2 whitespace-normal break-words leading-5">
                          {displayTemplateValue(candidate.hwlx)}
                        </td>
                        <td className="px-2.5 py-2 text-center">
                          <span
                            data-testid={`template-priority-badge-${index}`}
                            className={cn(
                              'inline-flex min-w-[2.5rem] items-center justify-center rounded-full border px-2.5 py-1 text-xs font-semibold',
                              getPriorityBadgeClassName(candidate.yxj)
                            )}
                          >
                            {displayTemplateValue(candidate.yxj)}
                          </span>
                        </td>
                        <td className="px-2.5 py-2">
                          {candidate.shener ? (
                            <a
                              href={getDownloadUrl(
                                candidate.shener,
                                `${displayTemplateValue(candidate.tendername) === '--' ? '模板' : candidate.tendername}-送审稿`
                              )}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-block whitespace-normal break-words text-center leading-5 text-blue-600 underline-offset-2 hover:text-blue-700 hover:underline"
                            >
                              {`${displayTemplateValue(candidate.tendername) === '--' ? '模板' : candidate.tendername}-送审稿`}
                            </a>
                          ) : (
                            '--'
                          )}
                        </td>
                        <td className="px-2.5 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => onSelect(candidate, rowKey)}
                            disabled={Boolean(selectingRowKey && !isSelecting)}
                            className={cn(
                              'inline-flex min-w-[3.75rem] items-center justify-center whitespace-nowrap rounded-full px-2.5 py-1.5 text-xs font-semibold transition-all',
                              'bg-blue-600 text-white shadow-sm hover:bg-blue-700',
                              'disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600'
                            )}
                          >
                            {isSelecting ? (
                              <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                处理中
                              </>
                            ) : (
                              '选择'
                            )}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TemplateCandidateDialog;
