import React from 'react';

import { HistorySection } from './HistorySection';
import { Sidebar, SidebarContent, SidebarHeader } from './Sidebar';
import { Header } from './Header';
import { FileText, Settings } from 'lucide-react';
import Link from 'next/link';

interface MainLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export function MainLayout({ children, title, subtitle }: MainLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Sidebar */}
      <Sidebar>
        <SidebarHeader>
          <Link href="/" className="flex items-center gap-2 text-[var(--foreground)]">
            <FileText className="w-6 h-6 text-[var(--primary)]" />
            <span className="font-semibold text-lg">招标文件生成</span>
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
            <NavLink href="/tender/gngk" icon={<FileText className="w-4 h-4" />}>
              国内公开
            </NavLink>
          </nav>

          {/* History */}
          <HistorySection />
        </SidebarContent>

        <div className="p-4 border-t border-[var(--border)]">
          <button className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--foreground)] transition-colors">
            <Settings className="w-4 h-4" />
            设置
          </button>
        </div>
      </Sidebar>

      {/* Main Content */}
      <main className="main-content">
        {(title || subtitle) && <Header title={title} subtitle={subtitle} />}
        <div className="container-wide py-6">{children}</div>
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
