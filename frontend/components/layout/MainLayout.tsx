import React from 'react';

import { HistorySection } from './HistorySection';
import { Sidebar, SidebarContent, SidebarHeader } from './Sidebar';
import { Header } from './Header';
import { FileText, MessageSquare, Settings } from 'lucide-react';
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
            <FileText className="h-6 w-6 text-[var(--primary)]" />
            <span className="text-lg font-semibold">招标文件生成</span>
          </Link>
        </SidebarHeader>

        <SidebarContent>
          {/* Navigation */}
          <nav className="space-y-1">
            <p className="mb-2 px-2 text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
              模式
            </p>
            <NavLink href="/chat" icon={<MessageSquare className="h-4 w-4" />}>
              三栏聊天
            </NavLink>
          </nav>

          {/* History */}
          <HistorySection />
        </SidebarContent>

        <div className="border-t border-[var(--border)] p-4">
          <button className="flex items-center gap-2 text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--foreground)]">
            <Settings className="h-4 w-4" />
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
      className="flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-white hover:text-[var(--foreground)]"
    >
      {icon}
      {children}
    </Link>
  );
}
