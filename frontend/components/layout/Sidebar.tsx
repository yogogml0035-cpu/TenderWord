'use client';

import React from 'react';
import { cn, formatDate } from '@/lib/utils';
import { useHistoryStore, type HistoryItem } from '@/stores/historyStore';
import { useAppStore } from '@/stores/useAppStore';
import Link from 'next/link';
import {
  FileText,
  History,
  Settings,
  Trash2,
  Download,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  X,
} from 'lucide-react';

interface SidebarProps {
  className?: string;
  children?: React.ReactNode;
}

export function Sidebar({ className, children }: SidebarProps) {
  return (
    <aside
      className={cn(
        'st-sidebar flex flex-col',
        className
      )}
    >
      {children}
    </aside>
  );
}

export function SidebarHeader({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={cn('p-4 border-b border-[var(--border)]', className)}>
      {children}
    </div>
  );
}

export function SidebarContent({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={cn('flex-1 overflow-y-auto p-4', className)}>
      {children}
    </div>
  );
}

export function SidebarFooter({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={cn('p-4 border-t border-[var(--border)]', className)}>
      {children}
    </div>
  );
}

// Enhanced Sidebar with History
export function SidebarWithHistory({ className }: { className?: string }) {
  const { history, clearHistory, removeFromHistory } = useHistoryStore();
  const { sidebarOpen, setSidebarOpen } = useAppStore();

  if (!sidebarOpen) {
    return (
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed left-0 top-1/2 -translate-y-1/2 p-2 bg-white border border-l-0 border-[var(--border)] rounded-r-lg shadow-md hover:bg-gray-50 z-50"
      >
        <History className="w-5 h-5 text-[var(--text-muted)]" />
      </button>
    );
  }

  return (
    <Sidebar className={className}>
      <SidebarHeader>
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-[var(--foreground)]">
            <FileText className="w-6 h-6 text-[var(--primary)]" />
            <span className="font-semibold text-lg">TenderWord</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 text-[var(--text-muted)] hover:text-[var(--foreground)] lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {/* Navigation */}
        <nav className="space-y-1">
          <p className="px-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
            招标类型
          </p>
          <NavLink href="/tender/xjcg" icon={<FileText className="w-4 h-4" />}>
            询价采购
          </NavLink>
          <NavLink href="/tender/gkzb" icon={<FileText className="w-4 h-4" />}>
            公开招标
          </NavLink>
          <NavLink href="/tender/yqzb" icon={<FileText className="w-4 h-4" />}>
            邀请招标
          </NavLink>
        </nav>

        {/* History Section */}
        <div className="mt-8">
          <div className="flex items-center justify-between px-2 mb-2">
            <p className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider flex items-center gap-2">
              <History className="w-3 h-3" />
              生成历史
              {history.length > 0 && (
                <span className="bg-[var(--primary)] text-white text-[10px] px-1.5 py-0.5 rounded-full">
                  {history.length}
                </span>
              )}
            </p>
            {history.length > 0 && (
              <button
                onClick={clearHistory}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--error)] flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                清空
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div className="px-2 py-8 text-center">
              <History className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
              <p className="text-xs text-[var(--text-muted)]">暂无生成记录</p>
            </div>
          ) : (
            <div className="space-y-1">
              {history.slice(0, 10).map((item) => (
                <HistoryItemCard
                  key={item.id}
                  item={item}
                  onRemove={() => removeFromHistory(item.id)}
                />
              ))}
              {history.length > 10 && (
                <p className="text-xs text-[var(--text-muted)] text-center py-2">
                  还有 {history.length - 10} 条记录...
                </p>
              )}
            </div>
          )}
        </div>
      </SidebarContent>

      <SidebarFooter>
        <button className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--foreground)] transition-colors w-full">
          <Settings className="w-4 h-4" />
          设置
        </button>
      </SidebarFooter>
    </Sidebar>
  );
}

function NavLink({
  href,
  children,
  icon,
}: {
  href: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 px-2 py-2 text-sm font-medium text-[var(--text-muted)] rounded-md hover:bg-white hover:text-[var(--foreground)] transition-colors"
    >
      {icon}
      {children}
    </Link>
  );
}

function HistoryItemCard({
  item,
  onRemove,
}: {
  item: HistoryItem;
  onRemove: () => void;
}) {
  const getStatusIcon = () => {
    switch (item.status) {
      case 'completed':
        return <CheckCircle2 className="w-3 h-3 text-[var(--success)]" />;
      case 'failed':
        return <XCircle className="w-3 h-3 text-[var(--error)]" />;
      case 'cancelled':
        return <AlertCircle className="w-3 h-3 text-[var(--warning)]" />;
      default:
        return <Clock className="w-3 h-3 text-[var(--info)]" />;
    }
  };

  const getStatusBadgeClass = () => {
    switch (item.status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-blue-100 text-blue-800';
    }
  };

  return (
    <div className="group relative p-2 rounded-md hover:bg-white/50 transition-colors">
      <div className="flex items-start gap-2">
        {getStatusIcon()}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--foreground)] truncate font-medium">
            {item.tenderNo}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn('text-[10px] px-1.5 py-0.5 rounded', getStatusBadgeClass())}>
              {item.status === 'completed' && '已完成'}
              {item.status === 'failed' && '失败'}
              {item.status === 'cancelled' && '取消'}
              {item.status === 'running' && '执行中'}
              {item.status === 'queued' && '排队中'}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {formatDate(item.createdAt)}
            </span>
          </div>
          {item.outputFile && (
            <a
              href={`/api/download/${encodeURIComponent(item.outputFile)}`}
              className="flex items-center gap-1 mt-1 text-xs text-[var(--primary)] hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <Download className="w-3 h-3" />
              下载文件
            </a>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="opacity-0 group-hover:opacity-100 p-1 text-[var(--text-muted)] hover:text-[var(--error)] transition-opacity"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

export default Sidebar;
