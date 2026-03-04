'use client';

import React, { useEffect, useState, useCallback, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, AlertCircle } from 'lucide-react';
import { TenderTypeSidebar } from '@/components/chat/TenderTypeSidebar';
import { FormPanel } from '@/components/chat/FormPanel';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { useUrlParams } from '@/hooks/useUrlParams';
import { useChatStore } from '@/stores/chatStore';
import { fetchTenderData } from '@/lib/api';
import type { TenderData } from '@/types/api';
import type { TenderType } from '@/types';

/**
 * URL参数处理状态
 */
interface UrlProcessingState {
  isProcessing: boolean;
  error: string | null;
  tenderData: TenderData | null;
}

/**
 * Chat页面内容组件 - 包含useSearchParams的使用
 * 需要被Suspense包裹
 */
function ChatPageContent() {
  const router = useRouter();
  const { tenderno, tenderType, isValid, hasParams } = useUrlParams();

  const {
    findConversationByTenderNo,
    createConversation,
    setCurrentConversation,
    setSelectedTenderType,
  } = useChatStore();
  const [mounted, setMounted] = useState(false);

  // URL参数处理状态
  const [urlState, setUrlState] = useState<UrlProcessingState>({
    isProcessing: false,
    error: null,
    tenderData: null,
  });

  // Fix hydration: wait for client mount before accessing persisted store
  useEffect(() => {
    setMounted(true);
  }, []);

  /**
   * 处理URL参数 - 获取招标数据
   */
  const handleUrlParams = useCallback(async () => {
    if (!mounted || !hasParams || !tenderno) return;

    setUrlState((prev) => ({ ...prev, isProcessing: true, error: null }));

    try {
      const data = await fetchTenderData(tenderno);
      setUrlState((prev) => ({
        ...prev,
        isProcessing: false,
        tenderData: data,
      }));

      // 设置招标类型
      if (tenderType) {
        setSelectedTenderType(tenderType);
      }

      // 查找或创建会话
      const existingConv = findConversationByTenderNo(tenderno);
      if (existingConv) {
        setCurrentConversation(existingConv.id);
      } else {
        const newConv = createConversation(tenderno, tenderType);
        setCurrentConversation(newConv.id);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取招标数据失败';
      setUrlState((prev) => ({
        ...prev,
        isProcessing: false,
        error: errorMessage,
      }));
    }
  }, [mounted, hasParams, tenderno, tenderType, findConversationByTenderNo, createConversation, setCurrentConversation, setSelectedTenderType]);

  // 处理URL参数（只执行一次，且在mounted后）
  useEffect(() => {
    if (!mounted) return;
    handleUrlParams();
  }, [mounted, hasParams, isValid, handleUrlParams]);

  /**
   * 清除错误提示
   */
  const clearError = useCallback(() => {
    if (!mounted) return;
    setUrlState((prev) => ({ ...prev, error: null }));
  }, [mounted]);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      {/* Left Sidebar - Tender Types */}
      <div className="flex-shrink-0">
        <TenderTypeSidebar />
      </div>

      {/* Middle Column - Form Panel */}
      <div className="min-w-0 flex-1 border-r border-gray-200">
        <FormPanel initialTenderData={urlState.tenderData} />
      </div>

      {/* Right Column - Chat Panel */}
      <div className="min-w-0 flex-1">
        <ChatPanel />
      </div>

      {/* URL参数处理中的加载遮罩 */}
      {urlState.isProcessing && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-white/60">
          <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-200 bg-white p-6 shadow-xl">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">正在处理招标信息...</p>
          </div>
        </div>
      )}

      {/* 错误提示（非阻塞式) */}
      {urlState.error && !urlState.isProcessing && (
        <div className="fixed bottom-4 right-4 z-50 animate-slide-in-up">
          <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 shadow-lg">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">获取招标数据失败</p>
              <p className="mt-1 text-xs text-red-600">{urlState.error}</p>
              <p className="mt-1 text-xs text-red-500">
                招标编号已填入表单，您可以手动填写其他信息或重试。
              </p>
            </div>
            <button
              onClick={clearError}
              className="text-red-400 transition-colors hover:text-red-600"
              aria-label="关闭提示"
            >
              <svg
                className="h-4 w-4"
                width={16}
                height={16}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Chat页面主组件 - 使用Suspense包裹内容组件
 * 这是为了支持Next.js 16的useSearchParams需要在Suspense边界内使用
 */
export default function ChatPage() {
  return (
    <Suspense
      fallback={(
        <div className="flex h-screen items-center justify-center bg-gray-100">
          <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-200 bg-white p-6 shadow-xl">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">正在加载...</p>
          </div>
        </div>
      )}
    >
      <ChatPageContent />
    </Suspense>
  );
}
