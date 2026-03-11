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
  MessageSquare,
} from 'lucide-react';

interface SidebarProps {
  className?: string;
  children?: React.ReactNode;
}

export function Sidebar({ className, children }: SidebarProps) {
  return <aside className={cn('sidebar flex flex-col', className)}>{children}</aside>;
}

export function SidebarHeader({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn('border-b border-[var(--border)] px-6 py-4', className)}>{children}</div>
  );
}

export function SidebarContent({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return <div className={cn('flex-1 overflow-y-auto p-4', className)}>{children}</div>;
}

export function SidebarFooter({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return <div className={cn('border-t border-[var(--border)] p-4', className)}>{children}</div>;
}

// Enhanced Sidebar with History
export function SidebarWithHistory({ className }: { className?: string }) {
  const { history, clearHistory, removeFromHistory } = useHistoryStore();
  const { sidebarOpen, setSidebarOpen } = useAppStore();

  if (!sidebarOpen) {
    return (
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-1/2 left-0 z-50 -translate-y-1/2 rounded-r-lg border border-l-0 border-[var(--border)] bg-white p-2 shadow-md hover:bg-gray-50"
      >
        <History className="h-5 w-5 text-[var(--text-muted)]" />
      </button>
    );
  }

  return (
    <Sidebar className={className}>
      <SidebarHeader>
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-[var(--foreground)]">
            <FileText className="h-6 w-6 text-[var(--primary)]" />
            <span className="text-lg font-semibold">TenderWord</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 text-[var(--text-muted)] hover:text-[var(--foreground)] lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {/* Navigation */}
        <nav className="space-y-1">
          <p className="mb-2 px-2 text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
            模式
          </p>
          <NavLink href="/tender" icon={<MessageSquare className="h-4 w-4" />}>
            三栏聊天
          </NavLink>
        </nav>

        {/* History Section */}

        {/* History Section */}
        <div className="mt-8">
          <div className="mb-2 flex items-center justify-between px-2">
            <p className="flex items-center gap-2 text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
              <History className="h-3 w-3" />
              生成历史
              {history.length > 0 && (
                <span className="rounded-full bg-[var(--primary)] px-1.5 py-0.5 text-[10px] text-white">
                  {history.length}
                </span>
              )}
            </p>
            {history.length > 0 && (
              <button
                onClick={clearHistory}
                className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--error)]"
              >
                <Trash2 className="h-3 w-3" />
                清空
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div className="px-2 py-8 text-center">
              <History className="mx-auto mb-2 h-8 w-8 text-[var(--text-muted)] opacity-50" />
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
                <p className="py-2 text-center text-xs text-[var(--text-muted)]">
                  还有 {history.length - 10} 条记录...
                </p>
              )}
            </div>
          )}
        </div>
      </SidebarContent>

      <SidebarFooter>
        <button className="flex w-full items-center gap-2 text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--foreground)]">
          <Settings className="h-4 w-4" />
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
      className="flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-white hover:text-[var(--foreground)]"
    >
      {icon}
      {children}
    </Link>
  );
}

function HistoryItemCard({ item, onRemove }: { item: HistoryItem; onRemove: () => void }) {
  const getStatusIcon = () => {
    switch (item.status) {
      case 'completed':
        return <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />;
      case 'failed':
        return <XCircle className="h-3 w-3 text-[var(--error)]" />;
      case 'cancelled':
        return <AlertCircle className="h-3 w-3 text-[var(--warning)]" />;
      default:
        return <Clock className="h-3 w-3 text-[var(--info)]" />;
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
    <div className="group relative rounded-md p-2 transition-colors hover:bg-white/50">
      <div className="flex items-start gap-2">
        {getStatusIcon()}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-[var(--foreground)]">{item.tenderNo}</p>
          <div className="mt-0.5 flex items-center gap-2">
            <span className={cn('rounded px-1.5 py-0.5 text-[10px]', getStatusBadgeClass())}>
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
              className="mt-1 flex items-center gap-1 text-xs text-[var(--primary)] hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <Download className="h-3 w-3" />
              下载文件
            </a>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="p-1 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[var(--error)]"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

export default Sidebar;
