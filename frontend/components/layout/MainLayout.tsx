'use client';

import React from 'react';
import { useAppStore } from '@/stores/useAppStore';
import { Sidebar, SidebarContent, SidebarHeader } from './Sidebar';
import { Header } from './Header';
import { FileText, History, Settings } from 'lucide-react';
import Link from 'next/link';

interface MainLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export function MainLayout({ children, title, subtitle }: MainLayoutProps) {
  const { history } = useAppStore();

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Sidebar */}
      <Sidebar>
        <SidebarHeader>
          <Link href="/" className="flex items-center gap-2 text-[var(--foreground)]">
            <FileText className="w-6 h-6 text-[var(--primary)]" />
            <span className="font-semibold text-lg">TenderWord</span>
          </Link>
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

          {/* History */}
          {history.length > 0 && (
            <div className="mt-8">
              <p className="px-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <History className="w-3 h-3" />
                最近生成
              </p>
              <div className="space-y-1">
                {history.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    className="px-2 py-1.5 text-sm text-[var(--text-muted)] truncate hover:text-[var(--foreground)] cursor-pointer rounded-md hover:bg-white/50 transition-colors"
                  >
                    {item.tenderNo}
                  </div>
                ))}
              </div>
            </div>
          )}
        </SidebarContent>

        <div className="p-4 border-t border-[var(--border)]">
          <button className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--foreground)] transition-colors">
            <Settings className="w-4 h-4" />
            设置
          </button>
        </div>
      </Sidebar>

      {/* Main Content */}
      <main className="st-main">
        {(title || subtitle) && <Header title={title} subtitle={subtitle} />}
        <div className="st-container py-6">{children}</div>
      </main>
    </div>
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
