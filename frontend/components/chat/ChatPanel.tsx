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
      <div className={`flex flex-col h-full bg-gradient-to-br from-slate-50 to-gray-100 ${className}`}>
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            {/* Animated Icon Container */}
            <div className="relative mb-8 inline-block">
              <div className="absolute inset-0 bg-blue-100 rounded-full animate-pulse opacity-50" />
              <div className="relative bg-white rounded-full p-6 shadow-lg border border-blue-100">
                <svg
                  className="w-16 h-16 text-blue-500"
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
              </div>
            </div>
            
            {/* Welcome Text */}
            <h3 className="text-2xl font-semibold text-gray-800 mb-3 tracking-tight">
              欢迎使用 TenderWord
            </h3>
            <p className="text-gray-500 mb-6 leading-relaxed">
              智能招标文档生成助手，让文档创建更高效
            </p>
            
            {/* Instructions */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl p-4 border border-gray-200/50 shadow-sm">
              <p className="text-sm text-gray-600 mb-3 font-medium">开始新对话：</p>
              <div className="space-y-2">
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-semibold">1</span>
                  <span>在左侧选择招标类型</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-semibold">2</span>
                  <span>填写招标信息并上传文件</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-semibold">3</span>
                  <span>AI 自动生成招标文档</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white shadow-sm ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="font-medium text-gray-900">{conversation.title}</h2>
          <p className="text-xs text-gray-500">
            {conversation.tenderType === 'xjcg' ? '询价采购' : '国内公开'}
          </p>
        </div>
        <div className="text-xs text-gray-400 px-2 py-1 bg-gray-100 rounded">
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
