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
        'bg-white border-b border-[var(--border)] px-6 py-4',
        className
      )}
    >
      {title && (
        <div>
          <h1 className="text-xl font-semibold text-[var(--foreground)]">{title}</h1>
          {subtitle && (
            <p className="text-sm text-[var(--text-muted)] mt-1">{subtitle}</p>
          )}
        </div>
      )}
      {children}
    </header>
  );
}
