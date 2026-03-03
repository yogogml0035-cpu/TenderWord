'use client';

import React, { useCallback } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { downloadFile } from '@/lib/api';

interface ChatPanelProps {
  className?: string;
}

export function ChatPanel({ className = '' }: ChatPanelProps) {
  const {
    getCurrentConversation,
    addMessage,
    hasActiveTasks,
  } = useChatStore();

  const conversation = getCurrentConversation();
  const messages = conversation?.messages || [];
  const isLoading = hasActiveTasks();

  const handleSendMessage = (content: string) => {
    if (!conversation) return;

    // Add user message
    addMessage(conversation.id, {
      type: 'user',
      content,
      status: 'sent',
    });

    // Note: In a real implementation, you might want to:
    // 1. Send to backend for chat-based regeneration
    // 2. Or just store locally for now
    // For this version, we'll just add the message
  };

  const handleRetry = useCallback(() => {
    if (!conversation) return;
    
    // Find the last user message
    const lastUserMessage = [...messages]
      .reverse()
      .find(m => m.type === 'user');
    
    if (lastUserMessage && typeof lastUserMessage.content === 'string') {
      handleSendMessage(lastUserMessage.content);
    }
  }, [messages, conversation, handleSendMessage]);

  const handleDownload = async (filePath: string, fileName?: string) => {
    try {
      const blob = await downloadFile(filePath, fileName);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName || filePath.split('/').pop() || 'download';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      alert('下载失败，请重试');
    }
  };

  // Empty state when no conversation selected
  if (!conversation) {
    return (
      <div className={`flex flex-col h-full bg-gray-50 ${className}`}>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-gray-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <h3 className="text-lg font-medium text-gray-600 mb-2">欢迎使用 TenderWord</h3>
            <p className="text-sm">请在左侧选择招标类型并开始新对话</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="font-medium text-gray-900">{conversation.title}</h2>
          <p className="text-xs text-gray-500">
            {conversation.tenderType === 'xjcg' ? '询价采购' : '国内公开'}
          </p>
        </div>
        <div className="text-xs text-gray-400">
          {messages.length} 条消息
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-hidden">
        <MessageList
          messages={messages}
          onDownload={handleDownload}
          onRetry={handleRetry}
        />
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSendMessage}
        disabled={isLoading}
        loading={isLoading}
        placeholder={isLoading ? '生成中，请稍候...' : '输入消息...'}
      />
    </div>
  );
}

export default ChatPanel;
