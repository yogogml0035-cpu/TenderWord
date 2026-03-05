'use client';

import React, { useEffect, useRef, useState } from 'react';
import { FileText } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { cn } from '@/lib/utils';
import { NewChatPopup } from '@/components/chat/NewChatPopup';

interface TenderType {
  id: 'xjcg' | 'gngk';
  name: string;
  icon: React.ReactNode;
  description: string;
}

const tenderTypes: TenderType[] = [
  {
    id: 'xjcg',
    name: '询价采购',
    icon: <FileText className="h-5 w-5" />,
    description: '询价采购类型招标',
  },
  {
    id: 'gngk',
    name: '国内公开',
    icon: <FileText className="h-5 w-5" />,
    description: '国内公开招标类型',
  },
];

interface TenderTypeSidebarProps {
  onNewChat?: (type: 'xjcg' | 'gngk') => void;
}

export function TenderTypeSidebar({ onNewChat }: TenderTypeSidebarProps) {
  const [hoveredType, setHoveredType] = useState<TenderType['id'] | null>(null);
  const [mounted, setMounted] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { createConversation, currentConversationId, conversations, setCurrentConversation } = useChatStore();

  // Fix hydration: wait for client mount before accessing persisted store
  useEffect(() => {
    setMounted(true);
  }, []);
  const clearCloseTimer = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const openPopup = (typeId: TenderType['id']) => {
    clearCloseTimer();
    setHoveredType(typeId);
  };

  const scheduleClosePopup = () => {
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => setHoveredType(null), 200);
  };

  const handleTypeClick = (type: 'xjcg' | 'gngk') => {
    // Filter conversations by this tender type
    const typeConversations = conversations.filter(
      (conv) => conv.tenderType === type
    );

    if (typeConversations.length > 0) {
      // Find the most recent conversation (by updatedAt)
      const mostRecent = typeConversations.reduce((prev, current) =>
        prev.updatedAt > current.updatedAt ? prev : current
      );
      setCurrentConversation(mostRecent.id);
    } else {
      // No conversations exist - create a new one with default title
      createConversation('新对话', type, '新对话');
      // The createConversation method already sets currentConversationId in the store
    }
  };

  const handleNewChat = (type: 'xjcg' | 'gngk') => {
    createConversation('新对话', type);
    if (onNewChat) {
      onNewChat(type);
    }
  };

  // Get current conversation's tender type for highlighting (only after mount)
  const currentConversation = mounted ? conversations.find((conv) => conv.id === currentConversationId) : null;
  const currentType = currentConversation?.tenderType;

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
    };
  }, []);

  return (
    <div className="flex h-full w-28 flex-col items-center border-r border-gray-200 bg-[var(--background)] py-4 shadow-sm">
      <div className="mb-4 text-xs font-medium text-[var(--text-muted)]">类型</div>

      <div className="flex flex-col gap-2">
        {tenderTypes.map((type) => (
          <div
            key={type.id}
            className="relative pr-2"
            onMouseEnter={() => openPopup(type.id)}
            onMouseLeave={scheduleClosePopup}
          >
            <button
              onClick={() => handleTypeClick(type.id)}
              className={cn(
                'flex h-14 w-24 flex-col items-center justify-center gap-1 rounded-lg shadow-sm transition-all duration-200',
                currentType === type.id
                  ? 'bg-[var(--primary)] text-white shadow-md'
                  : hoveredType === type.id
                    ? 'bg-[var(--primary)]/10 text-[var(--primary)] shadow-md'
                    : 'text-[var(--text-muted)] hover:bg-gray-100 hover:shadow-md'
              )}
              title={type.name}
            >
              {type.icon}
              <span className="text-[11px] font-medium">{type.name}</span>
            </button>

            <NewChatPopup
              type={type.id}
              typeName={type.name}
              description={type.description}
              isVisible={hoveredType === type.id}
              onClose={() => {
                clearCloseTimer();
                setHoveredType(null);
              }}
              onNewChat={() => handleNewChat(type.id)}
              onMouseEnter={() => openPopup(type.id)}
              onMouseLeave={scheduleClosePopup}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default TenderTypeSidebar;
