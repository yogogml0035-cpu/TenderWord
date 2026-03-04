import React from 'react';
import { cn } from '@/lib/utils';

interface HeaderProps {
  className?: string;
  children?: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export function Header({ className, children, title, subtitle }: HeaderProps) {
  return (
    <header
      className={cn(
        'bg-white',
        className
      )}
    >
      <div className="px-6 py-4 border-b border-[var(--border)]">
        <div className="flex items-start justify-between gap-4">
          {title && (
            <div>
              <h1 className="text-xl font-semibold text-[var(--foreground)]">{title}</h1>
            </div>
          )}
          {children}
        </div>
      </div>
      {subtitle && (
        <div className="px-6 py-2">
          <p className="text-sm text-[var(--text-muted)]">{subtitle}</p>
        </div>
      )}
    </header>
  );
}
