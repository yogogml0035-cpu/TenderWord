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
  );
}
