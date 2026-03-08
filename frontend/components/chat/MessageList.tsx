'use client';

import React, { useRef, useEffect, useState } from 'react';
import { User, Bot, Info } from 'lucide-react';
import type { Message } from '@/types/chat';
import { TaskLogMessage } from './TaskLogMessage';
import { TaskContentMessage } from './TaskContentMessage';
import { TaskDownloadMessage } from './TaskDownloadMessage';

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
      <div className={`flex h-full items-center justify-center p-8 ${className}`}>
        {emptyState || (
          <div className="max-w-sm text-center">
            {/* Animated Bot Icon */}
            <div className="relative mb-6 inline-block">
              <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-50" />
              <div className="relative rounded-full border border-blue-100 bg-white p-4 shadow-md">
                <Bot className="h-10 w-10 text-blue-500" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-medium text-gray-700">开始一个新的对话</h3>
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
        className="h-full space-y-4 overflow-x-hidden overflow-y-auto p-4"
      >
        {messages.map((message, index) => (
          <div
            key={message.id}
            className="animate-message-appear"
            style={{ animationDelay: `${Math.min(index * 100, 500)}ms` }}
          >
            <MemoMessageItem message={message} onDownload={onDownload} onRetry={onRetry} />
          </div>
        ))}
      </div>

      {/* Scroll to bottom button */}
      {!isAtBottom && messages.length > 0 && (
        <button
          onClick={scrollToBottom}
          className="absolute right-4 bottom-4 rounded border border-gray-200 bg-white p-2 text-gray-600 shadow-lg transition-colors duration-200 hover:bg-gray-50"
        >
          <svg
            className="h-5 w-5"
            width={20}
            height={20}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
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
  if (message.type === 'ai') {
    const messageKind = message.metadata?.messageKind;

    return (
      <div className="animate-fade-in-up flex gap-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-blue-100 shadow-sm">
          <Bot className="h-5 w-5 text-blue-600" />
        </div>

        <div className="min-w-0 flex-1">
          {messageKind === 'task-log' && <TaskLogMessage message={message} />}
          {messageKind === 'task-content' && <TaskContentMessage message={message} onRetry={onRetry} />}
          {messageKind === 'task-download' && (
            <TaskDownloadMessage message={message} onDownload={onDownload} />
          )}
          {!messageKind && (
            <div className="rounded border border-gray-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-sm text-gray-700">
                {typeof message.content === 'string' ? message.content : '...'}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Render user message
  if (message.type === 'user') {
    return (
      <div className="animate-fade-in-up flex items-start justify-end gap-3">
        <div
          data-testid="user-message-frame"
          className="min-w-0 w-fit max-w-[40%]"
        >
          <div
            data-testid="user-message-bubble"
            className="w-fit max-w-full rounded-2xl rounded-tr-sm bg-blue-500 px-4 py-2.5 text-white shadow-sm"
          >
            <p
              data-testid="user-message-text"
              className="whitespace-pre-wrap break-words text-sm leading-6"
            >
              {typeof message.content === 'string' ? message.content : '...'}
            </p>
          </div>
          <div className="mt-1 text-right">
            <span className="text-[10px] text-gray-400">
              {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </div>

        <div
          data-testid="user-message-avatar"
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-gray-200 shadow-sm"
        >
          <User className="h-5 w-5 text-gray-600" />
        </div>
      </div>
    );
  }

  // Render system message
  if (message.type === 'system') {
    return (
      <div className="animate-fade-in-up flex justify-center">
        <div className="flex items-center gap-2 rounded bg-gray-100 px-4 py-2 text-xs text-gray-600 shadow-sm">
          <Info className="h-4 w-4" />
          <span>{typeof message.content === 'string' ? message.content : 'System message'}</span>
        </div>
      </div>
    );
  }

  return null;
}

const MemoMessageItem = React.memo(MessageItem);

export default MessageList;
