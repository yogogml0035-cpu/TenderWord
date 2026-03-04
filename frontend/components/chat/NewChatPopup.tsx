'use client';

import React, { useState, useEffect } from 'react';
import { MessageSquarePlus, History } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';

interface NewChatPopupProps {
  type: 'xjcg' | 'gngk';
  typeName: string;
  description: string;
  isVisible: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onMouseEnter?: React.MouseEventHandler<HTMLDivElement>;
  onMouseLeave?: React.MouseEventHandler<HTMLDivElement>;
  position?: 'right' | 'left';
}

export function NewChatPopup({
  type,
  typeName,
  description,
  isVisible,
  onClose,
  onNewChat,
  onMouseEnter,
  onMouseLeave,
  position = 'right',
}: NewChatPopupProps) {
  const [mounted, setMounted] = useState(false);
  const { conversations, setCurrentConversation, currentConversationId } = useChatStore();

  // Fix hydration: wait for client mount before accessing persisted store
  useEffect(() => {
    setMounted(true);
  }, []);

  // Filter conversations by type (only after mount)
  const typeConversations = mounted
    ? conversations.filter((c) => c.tenderType === type).slice(0, 5)
    : [];


  if (!isVisible) return null;

  return (
    <div
      className={`absolute ${position === 'right' ? 'left-full' : 'right-full'} animate-scale-in top-0 z-50`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="min-w-[200px] rounded border border-gray-200 bg-white py-3 shadow-lg">
        {/* Header */}
        <div className="border-b border-gray-200 px-4 pb-3">
          <h3 className="font-medium text-gray-900">{typeName}</h3>
          <p className="mt-1 text-xs text-gray-500">{description}</p>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={onNewChat}
            className="flex w-full items-center justify-center gap-2 rounded bg-blue-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors duration-200 hover:bg-blue-600 hover:shadow-md"
          >
            <MessageSquarePlus className="h-4 w-4" />
            新建对话
          </button>
        </div>

        {/* Recent Conversations */}
        {typeConversations.length > 0 && (
          <>
            <div className="border-y border-gray-200 bg-gray-50 px-4 py-2">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <History className="h-3.5 w-3.5" />
                最近对话
              </div>
            </div>

            <div className="max-h-[150px] overflow-y-auto">
              {typeConversations.map((conv, index) => (
                <button
                  key={conv.id}
                  onClick={() => {
                    setCurrentConversation(conv.id);
                    onClose();
                  }}
                  className={`animate-fade-in-up w-full truncate px-4 py-2.5 text-left text-sm transition-colors duration-200 ${
                    currentConversationId === conv.id
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-50'
                  } `}
                  style={{ animationDelay: `${index * 50}ms` }}
                  title={conv.title}
                >
                  <div className="truncate">{conv.title}</div>
                  <div className="mt-0.5 text-[10px] text-gray-400">
                    {new Date(conv.updatedAt).toLocaleDateString('zh-CN')}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Arrow */}
      <div
        className={`absolute top-4 h-2 w-2 rotate-45 transform border-gray-200 bg-white ${
          position === 'right'
            ? 'left-0 -ml-1 border-b border-l'
            : 'right-0 -mr-1 border-t border-r'
        } `}
      />
    </div>
  );
}
export default NewChatPopup;
