import React from 'react';
import { Metadata } from 'next';
import { TenderTypeSidebar } from '@/components/chat/TenderTypeSidebar';
import { FormPanel } from '@/components/chat/FormPanel';
import { ChatPanel } from '@/components/chat/ChatPanel';

export const metadata: Metadata = {
  title: 'TenderWord - 聊天式招标生成',
  description: '使用AI生成招标文档',
};

export default function ChatPage() {
  return (
    <div className="h-screen flex overflow-hidden bg-gray-100">
      {/* Left Sidebar - Tender Types */}
      <div className="flex-shrink-0">
        <TenderTypeSidebar />
      </div>

      {/* Middle Column - Form Panel */}
      <div className="flex-1 min-w-0 border-r border-gray-200">
        <FormPanel />
      </div>

      {/* Right Column - Chat Panel */}
      <div className="flex-1 min-w-0">
        <ChatPanel />
      </div>
    </div>
  );
}
