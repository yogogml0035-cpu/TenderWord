'use client';

import React from 'react';
import { MessageSquarePlus, History } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';

interface NewChatPopupProps {
  type: 'xjcg' | 'gngk';
  typeName: string;
  description: string;
  isVisible: boolean;
  onClose: () => void;
  onNewChat: () => void;
  position?: 'right' | 'left';
}

export function NewChatPopup({
  type,
  typeName,
  description,
  isVisible,
  onClose,
  onNewChat,
  position = 'right',
}: NewChatPopupProps) {
  const { conversations, setCurrentConversation, currentConversationId } = useChatStore();
  
  // Filter conversations by type
  const typeConversations = conversations
    .filter((c) => c.tenderType === type)
    .slice(0, 5);

  if (!isVisible) return null;

  return (
    <div 
      className={`
        absolute ${position === 'right' ? 'left-full ml-2' : 'right-full mr-2'} top-0 z-50
        animate-scale-in
      `}
    >
      <div className="bg-white rounded shadow-lg border border-gray-200 py-3 min-w-[200px]">
        {/* Header */}
        <div className="px-4 pb-3 border-b border-gray-200">
          <h3 className="font-medium text-gray-900">{typeName}</h3>
          <p className="text-xs text-gray-500 mt-1">{description}</p>
        </div>
        
        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-500 text-white text-sm font-medium rounded hover:bg-blue-600 transition-colors duration-200 shadow-sm hover:shadow-md"
          >
            <MessageSquarePlus className="w-4 h-4" />
            新建对话
          </button>
        </div>
        
        {/* Recent Conversations */}
        {typeConversations.length > 0 && (
          <>
            <div className="px-4 py-2 bg-gray-50 border-y border-gray-200">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <History className="w-3.5 h-3.5" />
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
                  className={`
                    w-full px-4 py-2.5 text-left text-sm truncate
                    transition-colors duration-200
                    animate-fade-in-up
                    ${currentConversationId === conv.id
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-50'
                    }
                  `}
                  style={{ animationDelay: `${index * 50}ms` }}
                  title={conv.title}
                >
                  <div className="truncate">{conv.title}</div>
                  <div className="text-[10px] text-gray-400 mt-0.5">
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
        className={`
          absolute top-4 w-2 h-2 bg-white border-gray-200 transform rotate-45
          ${position === 'right' 
            ? 'left-0 -ml-1 border-l border-b' 
            : 'right-0 -mr-1 border-r border-t'}
        `}
      />
    </div>
  );
}
export default NewChatPopup;
