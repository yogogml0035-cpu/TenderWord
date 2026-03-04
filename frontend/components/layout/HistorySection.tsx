'use client';

import React from 'react';
import { useHistoryStore } from '@/stores/historyStore';
import { History } from 'lucide-react';

export function HistorySection() {
  const { history } = useHistoryStore();

  if (history.length === 0) {
    return null;
  }

  return (
    <div className="mt-8">
      <p className="mb-2 flex items-center gap-2 px-2 text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
        <History className="h-3 w-3" />
        最近生成
      </p>
      <div className="space-y-1">
        {history.slice(0, 5).map((item) => (
          <div
            key={item.id}
            className="cursor-pointer truncate rounded-md px-2 py-1.5 text-sm text-[var(--text-muted)] transition-colors hover:bg-white/50 hover:text-[var(--foreground)]"
          >
            {item.tenderNo}
          </div>
        ))}
      </div>
    </div>
  );
}
