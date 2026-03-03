'use client';

import React, { useRef, useEffect, useState } from 'react';
import { User, Bot, Info } from 'lucide-react';
import type { Message } from '@/types/chat';
import { isDualColumnContent } from '@/types/chat';
import { DualColumnMessage } from './DualColumnMessage';

interface MessageListProps {
  messages: Message[];
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: () => void;
  emptyState?: React.ReactNode;
  className?: string;
}

export function MessageList({
  messages,
  onDownload,
  onRetry,
  emptyState,
  className = '',
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [userScrolled, setUserScrolled] = useState(false);

  // Handle scroll events
  const handleScroll = () => {
    if (!containerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 50;
    
    setIsAtBottom(atBottom);
    if (!atBottom) {
      setUserScrolled(true);
    }
  };

  // Auto-scroll to bottom for new messages (if user hasn't manually scrolled up)
  useEffect(() => {
    if (containerRef.current && isAtBottom && !userScrolled) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isAtBottom, userScrolled]);

  // Scroll to bottom button handler
  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
      setUserScrolled(false);
      setIsAtBottom(true);
    }
  };

  if (messages.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full p-8 ${className}`}>
        {emptyState || (
          <div className="text-center max-w-sm">
            {/* Animated Bot Icon */}
            <div className="relative mb-6 inline-block">
              <div className="absolute inset-0 bg-blue-100 rounded-full animate-pulse opacity-50" />
              <div className="relative bg-white rounded-full p-4 shadow-md border border-blue-100">
                <Bot className="w-10 h-10 text-blue-500" />
              </div>
            </div>
            <h3 className="text-lg font-medium text-gray-700 mb-2">开始一个新的对话</h3>
            <p className="text-sm text-gray-500">在左侧选择招标类型并填写表单以开始生成文档</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`relative h-full ${className}`}>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto p-4 space-y-4"
      >
        {messages.map((message, index) => (
          <div 
            key={message.id}
            className="animate-message-appear"
            style={{ animationDelay: `${Math.min(index * 100, 500)}ms` }}
          >
            <MessageItem
              message={message}
              onDownload={onDownload}
              onRetry={onRetry}
            />
          </div>
        ))}
      </div>

      {/* Scroll to bottom button */}
      {!isAtBottom && messages.length > 0 && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 p-2 bg-white rounded shadow-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors duration-200"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}
    </div>
  );
}

// Individual Message Item
interface MessageItemProps {
  message: Message;
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: () => void;
}

function MessageItem({ message, onDownload, onRetry }: MessageItemProps) {
  const isDualColumn = isDualColumnContent(message.content);

  // Render AI message with dual columns
  if (message.type === 'ai' && isDualColumn) {
    return (
      <div className="flex gap-3 animate-fade-in-up">
        <div className="flex-shrink-0 w-8 h-8 rounded bg-blue-100 flex items-center justify-center shadow-sm">
          <Bot className="w-5 h-5 text-blue-600" />
        </div>
        
        <div className="flex-1">
          <DualColumnMessage
            message={message}
            onDownload={onDownload}
            onRetry={onRetry}
          />
        </div>
      </div>
    );
  }

  // Render user message
  if (message.type === 'user') {
    return (
      <div className="flex gap-3 justify-end animate-fade-in-up">
        <div className="flex-1 max-w-[80%]">
          <div className="bg-blue-500 text-white rounded rounded-tr-sm px-4 py-2.5 shadow-sm">
            <p className="text-sm">{typeof message.content === 'string' ? message.content : '...'}</p>
          </div>
          <div className="text-right mt-1">
            <span className="text-[10px] text-gray-400">
              {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </div>
        
        <div className="flex-shrink-0 w-8 h-8 rounded bg-gray-200 flex items-center justify-center shadow-sm">
          <User className="w-5 h-5 text-gray-600" />
        </div>
      </div>
    );
  }

  // Render system message
  if (message.type === 'system') {
    return (
      <div className="flex justify-center animate-fade-in-up">
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded text-xs text-gray-600 shadow-sm">
          <Info className="w-4 h-4" />
          <span>{typeof message.content === 'string' ? message.content : 'System message'}</span>
        </div>
      </div>
    );
  }

  return null;
}

export default MessageList;
