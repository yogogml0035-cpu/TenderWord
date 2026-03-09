'use client';

import React, { useEffect, useState, useCallback, Suspense, useRef, useMemo } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { TenderTypeSidebar } from '@/components/chat/TenderTypeSidebar';
import { FormPanel } from '@/components/chat/FormPanel';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { useUrlParams } from '@/hooks/useUrlParams';
import { useHydrated } from '@/hooks/useHydrated';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import { useHistoryStore } from '@/stores/historyStore';
import { fetchTenderData, sendConversationHeartbeat } from '@/lib/api';

/**
 * URL参数处理状态
 */
interface UrlProcessingState {
  isProcessing: boolean;
  error: string | null;
}

interface ConversationInstanceResetState {
  previousInstanceId: string;
  nextInstanceId: string;
}

const CONVERSATION_HEARTBEAT_INTERVAL_MS = 30_000;
const CONVERSATION_ID_SEPARATOR = '\u0001';

/**
 * Chat页面内容组件 - 包含useSearchParams的使用
 * 需要被Suspense包裹
 */
function ChatPageContent() {
  const { tenderno, tenderType, isValid, hasParams } = useUrlParams();
  const hydrated = useHydrated();
  const processedUrlConversationKeyRef = useRef<string | null>(null);

  const {
    createConversation,
    conversations,
    setCurrentConversation,
    setSelectedTenderType,
    updateConversationDraft,
    resetSessionState,
  } = useChatStore();
  // URL参数处理状态
  const [urlState, setUrlState] = useState<UrlProcessingState>({
    isProcessing: false,
    error: null,
  });
  const [instanceResetState, setInstanceResetState] = useState<ConversationInstanceResetState | null>(
    null
  );
  const heartbeatInFlightRef = useRef(false);
  const knownInstanceIdRef = useRef<string | null>(null);

  /**
   * 处理URL参数 - 获取招标数据
   */
  const handleUrlParams = useCallback(async () => {
    if (!hydrated || !hasParams || !isValid) return;

    if (tenderType) {
      setSelectedTenderType(tenderType);
    }

    if (!tenderType || !tenderno) {
      return;
    }

    const urlConversationKey = `${tenderType}:${tenderno}`;
    if (processedUrlConversationKeyRef.current === urlConversationKey) {
      return;
    }
    processedUrlConversationKeyRef.current = urlConversationKey;

    setUrlState((prev) => ({ ...prev, isProcessing: true, error: null }));

    try {
      const data = await fetchTenderData(tenderno);
      const newConversationId = createConversation(tenderno, tenderType);
      setCurrentConversation(newConversationId);
      updateConversationDraft(newConversationId, {
        tender_no: tenderno,
        tender_data: data,
      });

      setUrlState((prev) => ({
        ...prev,
        isProcessing: false,
      }));
    } catch (err) {
      const newConversationId = createConversation(tenderno, tenderType);
      setCurrentConversation(newConversationId);
      updateConversationDraft(newConversationId, { tender_no: tenderno });

      const errorMessage = err instanceof Error ? err.message : '获取招标数据失败';
      setUrlState((prev) => ({
        ...prev,
        isProcessing: false,
        error: errorMessage,
      }));
    }
  }, [
    hydrated,
    hasParams,
    isValid,
    tenderType,
    tenderno,
    createConversation,
    setCurrentConversation,
    setSelectedTenderType,
    updateConversationDraft,
  ]);

  // 处理URL参数（只执行一次，且在mounted后）
  useEffect(() => {
    if (!hydrated) return;

    const timer = window.setTimeout(() => {
      void handleUrlParams();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [hydrated, hasParams, isValid, handleUrlParams]);

  const conversationIds = useMemo(
    () => conversations.map((conversation) => conversation.id).filter((id) => id.length > 0),
    [conversations]
  );
  const conversationIdsKey = useMemo(
    () => conversationIds.join(CONVERSATION_ID_SEPARATOR),
    [conversationIds]
  );

  useEffect(() => {
    if (!hydrated || !conversationIdsKey || instanceResetState) {
      return;
    }

    let disposed = false;

    const heartbeat = async () => {
      if (disposed || heartbeatInFlightRef.current) {
        return;
      }

      const activeConversationIds = conversationIdsKey
        .split(CONVERSATION_ID_SEPARATOR)
        .filter((id) => id.length > 0);
      if (activeConversationIds.length === 0) {
        return;
      }

      heartbeatInFlightRef.current = true;
      try {
        const heartbeatResults = await Promise.allSettled(
          activeConversationIds.map((conversationId) => sendConversationHeartbeat(conversationId))
        );
        if (disposed) {
          return;
        }

        for (const result of heartbeatResults) {
          if (result.status !== 'fulfilled') {
            continue;
          }

          const instanceId = result.value.instance_id;
          const knownInstanceId = knownInstanceIdRef.current;

          if (!knownInstanceId) {
            knownInstanceIdRef.current = instanceId;
            continue;
          }

          if (instanceId !== knownInstanceId) {
            setInstanceResetState({
              previousInstanceId: knownInstanceId,
              nextInstanceId: instanceId,
            });
            knownInstanceIdRef.current = instanceId;
            return;
          }
        }
      } finally {
        heartbeatInFlightRef.current = false;
      }
    };

    void heartbeat();

    const intervalId = window.setInterval(() => {
      void heartbeat();
    }, CONVERSATION_HEARTBEAT_INTERVAL_MS);

    const handleFocus = () => {
      void heartbeat();
    };
    const handlePageShow = () => {
      void heartbeat();
    };
    const handleOnline = () => {
      void heartbeat();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void heartbeat();
      }
    };

    window.addEventListener('focus', handleFocus);
    window.addEventListener('pageshow', handlePageShow);
    window.addEventListener('online', handleOnline);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('pageshow', handlePageShow);
      window.removeEventListener('online', handleOnline);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [conversationIdsKey, hydrated, instanceResetState]);

  /**
   * 清除错误提示
   */
  const clearError = useCallback(() => {
    if (!hydrated) return;
    setUrlState((prev) => ({ ...prev, error: null }));
  }, [hydrated]);

  const handleConfirmInstanceReset = useCallback(() => {
    useChatStreamStore.setState({ streams: {} });
    useChatTaskSessionStore.getState().clearSessions();
    useHistoryStore.getState().clearHistory();
    resetSessionState();

    processedUrlConversationKeyRef.current = null;
    knownInstanceIdRef.current = null;
    setInstanceResetState(null);
    setUrlState({
      isProcessing: false,
      error: null,
    });
  }, [resetSessionState]);

  return (
    <div className="grid h-screen grid-cols-[auto_minmax(0,2fr)_minmax(0,3fr)] overflow-hidden bg-gray-100">
      {/* Left Sidebar - Tender Types */}
      <div className="flex-shrink-0">
        <TenderTypeSidebar />
      </div>

      {/* Middle Column - Form Panel */}
      <div className="min-h-0 min-w-0 border-r border-gray-200">
        <FormPanel />
      </div>

      {/* Right Column - Chat Panel */}
      <div className="min-h-0 min-w-0">
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

      {instanceResetState && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/45 p-6">
          <div className="w-full max-w-lg rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-slate-900">检测到服务已重启</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  为避免旧会话状态与新实例不一致，当前标签页会话需要重置。确认后会清空本标签页中的会话、任务、普通聊天记录、润色状态与未读标记。
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  实例变化：{instanceResetState.previousInstanceId} →{' '}
                  {instanceResetState.nextInstanceId}
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={handleConfirmInstanceReset}
                className="inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-600"
              >
                确认并重置会话
              </button>
            </div>
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
