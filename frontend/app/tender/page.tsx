'use client';

import React, { useEffect, useState, useCallback, Suspense, useRef, useMemo } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { TenderTypeSidebar } from '@/components/chat/TenderTypeSidebar';
import { FormPanel } from '@/components/chat/FormPanel';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { useUrlParams } from '@/hooks/useUrlParams';
import { useHydrated } from '@/hooks/useHydrated';
import { useChatStore } from '@/stores/chatStore';
import { sendConversationHeartbeat } from '@/lib/api';
import { generateConversationTitle, isDefaultConversationTitle, normalizeTenderNo } from '@/lib/chat-utils';
import { createTenderFetchState, syncTenderDataDraft } from '@/lib/tenderFetch';

/**
 * URL参数处理状态
 */
interface UrlProcessingState {
  isProcessing: boolean;
  error: string | null;
}

const CONVERSATION_HEARTBEAT_INTERVAL_MS = 30_000;
const CONVERSATION_ID_SEPARATOR = '\u0001';

/**
 * 使用页内容组件 - 包含 useSearchParams 的使用
 * 需要被 Suspense 包裹
 */
function TenderPageContent() {
  const { tenderno, tenderType, isValid, hasParams } = useUrlParams();
  const hydrated = useHydrated();
  const processedUrlConversationKeyRef = useRef<string | null>(null);

  const {
    createConversation,
    conversations,
    findConversationByTenderNo,
    getConversationDraft,
    setCurrentConversation,
    setSelectedTenderType,
    updateConversation,
    updateConversationDraft,
    handleBackendRestart,
  } = useChatStore();
  const [urlState, setUrlState] = useState<UrlProcessingState>({
    isProcessing: false,
    error: null,
  });
  const heartbeatInFlightRef = useRef(false);
  const knownInstanceIdRef = useRef<string | null>(null);

  const handleUrlParams = useCallback(async () => {
    if (!hydrated || !hasParams || !isValid) return;

    if (tenderType) {
      setSelectedTenderType(tenderType);
    }

    if (!tenderType || !tenderno) {
      return;
    }

    const normalizedTenderNo = normalizeTenderNo(tenderno);
    if (!normalizedTenderNo) {
      return;
    }

    const urlConversationKey = `${tenderType}:${normalizedTenderNo}`;
    if (processedUrlConversationKeyRef.current === urlConversationKey) {
      return;
    }
    processedUrlConversationKeyRef.current = urlConversationKey;

    const existingConversation = findConversationByTenderNo(normalizedTenderNo, tenderType);
    const conversationId =
      existingConversation?.id || createConversation(normalizedTenderNo, tenderType);
    setCurrentConversation(conversationId);

    if (existingConversation && isDefaultConversationTitle(existingConversation.title)) {
      updateConversation(conversationId, {
        title: generateConversationTitle(normalizedTenderNo),
      });
    }

    const existingDraft = getConversationDraft(conversationId);
    if (existingDraft?.tender_data) {
      updateConversationDraft(conversationId, {
        tender_no: normalizedTenderNo,
        tender_fetch: createTenderFetchState('success'),
      });
      setUrlState({
        isProcessing: false,
        error: null,
      });
      return;
    }

    setUrlState({
      isProcessing: true,
      error: null,
    });

    let nextError: string | null = null;
    await syncTenderDataDraft({
      tenderNo: normalizedTenderNo,
      updateDraft: (updates) => updateConversationDraft(conversationId, updates),
      onError: (message) => {
        nextError = message;
      },
    });

    setUrlState({
      isProcessing: false,
      error: nextError,
    });
  }, [
    hydrated,
    hasParams,
    isValid,
    tenderType,
    tenderno,
    createConversation,
    findConversationByTenderNo,
    getConversationDraft,
    setCurrentConversation,
    setSelectedTenderType,
    updateConversation,
    updateConversationDraft,
  ]);

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
    if (!hydrated || !conversationIdsKey) {
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
            knownInstanceIdRef.current = instanceId;
            handleBackendRestart();
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
  }, [conversationIdsKey, handleBackendRestart, hydrated, updateConversationDraft]);

  const clearError = useCallback(() => {
    if (!hydrated) return;
    setUrlState((prev) => ({ ...prev, error: null }));
  }, [hydrated]);

  return (
    <div className="grid h-screen grid-cols-[auto_minmax(0,2fr)_minmax(0,3fr)] overflow-hidden bg-gray-100">
      <div className="flex-shrink-0">
        <TenderTypeSidebar />
      </div>

      <div className="min-h-0 min-w-0 border-r border-gray-200">
        <FormPanel />
      </div>

      <div className="min-h-0 min-w-0">
        <ChatPanel />
      </div>

      {urlState.isProcessing && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-white/60">
          <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-200 bg-white p-6 shadow-xl">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">正在处理招标信息...</p>
          </div>
        </div>
      )}

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

export default function TenderPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-gray-100">
          <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-200 bg-white p-6 shadow-xl">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">正在加载...</p>
          </div>
        </div>
      }
    >
      <TenderPageContent />
    </Suspense>
  );
}
