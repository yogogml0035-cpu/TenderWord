'use client';

import { cn } from '@/lib/utils';

export const secondaryActionButtonClassName = cn(
  'inline-flex h-11 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-[var(--border)] bg-[var(--secondary-bg)] px-4 text-sm font-semibold text-[var(--foreground)] transition-all',
  'hover:border-[var(--primary)]/20 hover:bg-slate-100',
  'focus:ring-2 focus:ring-[var(--primary)]/15 focus:outline-none',
  'disabled:cursor-not-allowed disabled:opacity-50'
);
