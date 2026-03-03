'use client';

import React, { useState } from 'react';
import { MessageSquarePlus, FileText } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { cn } from '@/lib/utils';

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
    icon: <FileText className="w-5 h-5" />,
    description: '询价采购类型招标',
  },
  {
    id: 'gngk',
    name: '国内公开',
    icon: <FileText className="w-5 h-5" />,
    description: '国内公开招标类型',
  },
];

interface TenderTypeSidebarProps {
  onNewChat?: (type: 'xjcg' | 'gngk') => void;
}

export function TenderTypeSidebar({ onNewChat }: TenderTypeSidebarProps) {
  const [hoveredType, setHoveredType] = useState<string | null>(null);
  const { createConversation, currentConversationId, conversations, setCurrentConversation } = useChatStore();

  const handleNewChat = (type: 'xjcg' | 'gngk') => {
    const id = createConversation('新对话', type);
    if (onNewChat) {
      onNewChat(type);
    }
  };

  // Get current conversation's tender type for highlighting
  const currentConversation = conversations.find(conv => conv.id === currentConversationId);
  const currentType = currentConversation?.tenderType;

  return (
    <div className="w-16 bg-[var(--background)] border-r border-gray-200 flex flex-col items-center py-4 h-full shadow-sm">
      <div className="text-xs font-medium text-[var(--text-muted)] mb-4">类型</div>
      
      <div className="flex flex-col gap-2">
        {tenderTypes.map((type) => (
          <div
            key={type.id}
            className="relative"
            onMouseEnter={() => setHoveredType(type.id)}
            onMouseLeave={() => setHoveredType(null)}
          >
            <button
              className={cn(
                'w-12 h-12 rounded flex flex-col items-center justify-center gap-1 transition-all duration-200 shadow-sm',
                currentType === type.id
                  ? 'bg-[var(--primary)] text-white shadow-md'
                  : hoveredType === type.id
                    ? 'bg-[var(--primary)]/10 text-[var(--primary)] shadow-md'
                    : 'hover:bg-gray-100 text-[var(--text-muted)] hover:shadow-md'
              )}
              title={type.name}
            >
              {type.icon}
              <span className="text-[10px]">{type.name.slice(0, 2)}</span>
            </button>
            
            {/* Hover Popup */}
            {hoveredType === type.id && (
              <div className="absolute left-full top-0 ml-2 z-50 animate-fade-in-up">
                <div className="bg-[var(--background)] rounded shadow-lg border border-gray-200 p-3 min-w-[160px]">
                  <div className="font-medium text-sm text-[var(--foreground)] mb-1">{type.name}</div>
                  <div className="text-xs text-[var(--text-muted)] mb-3">{type.description}</div>
                  
                  <button
                    onClick={() => handleNewChat(type.id)}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-[var(--primary)] text-white text-sm rounded hover:bg-[var(--primary)]/90 transition-colors duration-200 shadow-sm hover:shadow-md"
                  >
                    <MessageSquarePlus className="w-4 h-4" />
                    新建对话
                  </button>
                </div>
                {/* Arrow */}
                <div className="absolute left-0 top-4 -ml-1 w-2 h-2 bg-[var(--background)] border-l border-b border-gray-200 transform rotate-45"></div>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Recent Conversations */}
      {conversations.length > 0 && (
        <div className="mt-8 w-full px-2">
          <div className="text-[10px] font-medium text-[var(--text-muted)] mb-2 text-center">历史</div>
          <div className="flex flex-col gap-1">
            {conversations.slice(0, 5).map((conv, index) => (
              <button
                key={conv.id}
                onClick={() => setCurrentConversation(conv.id)}
                className={cn(
                  'w-full p-2 rounded text-[10px] text-left truncate transition-all duration-200',
                  currentConversationId === conv.id
                    ? 'bg-[var(--primary)]/10 text-[var(--primary)] shadow-sm'
                    : 'hover:bg-gray-100 text-[var(--text-muted)] hover:shadow-sm'
                )}
                style={{ animationDelay: `${index * 50}ms` }}
                title={conv.title}
              >
                {conv.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


export default TenderTypeSidebar;
