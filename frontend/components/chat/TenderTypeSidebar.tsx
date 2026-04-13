'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Edit2, FileText, History, MessageSquarePlus, MoreHorizontal, Trash2 } from 'lucide-react';
import type { TenderType as TenderTypeId } from '@/types';
import type { Conversation } from '@/types/chat';
import { useChatStore } from '@/stores/chatStore';
import { useHydrated } from '@/hooks/useHydrated';
import { syncBrowserUrlToConversation } from '@/utils/tenderTypeMapper';
import { cn } from '@/lib/utils';

interface SidebarTenderType {
  id: TenderTypeId;
  name: string;
  icon: React.ReactNode;
  description: string;
}

const tenderTypes: SidebarTenderType[] = [
  {
    id: 'xjcg',
    name: '询价采购',
    icon: <FileText className="h-5 w-5" />,
    description: '询价采购类型招标',
  },
  {
    id: 'gngk',
    name: '国内公开',
    icon: <FileText className="h-5 w-5" />,
    description: '国内公开招标类型',
  },
  {
    id: 'gjgk',
    name: '国际公开',
    icon: <FileText className="h-5 w-5" />,
    description: '国际公开招标类型',
  },
];

interface TenderTypeSidebarProps {
  onNewChat?: (type: TenderTypeId) => void;
}

interface EditingState {
  conversationId: string | null;
  tempTitle: string;
}

function sortConversationsByUpdatedAtDesc(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function TenderTypeSidebar({ onNewChat }: TenderTypeSidebarProps) {
  const hydrated = useHydrated();
  const [contextMenuConversationId, setContextMenuConversationId] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingState>({ conversationId: null, tempTitle: '' });
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const contextMenuTriggerRef = useRef<HTMLButtonElement | null>(null);
  const editingInputRef = useRef<HTMLInputElement>(null);
  const {
    conversations,
    createConversation,
    currentConversationId,
    deleteConversation,
    isConversationUnreadResult,
    selectedTenderType,
    setCurrentConversation,
    setSelectedTenderType,
    taskSummaries,
    updateConversation,
  } = useChatStore();

  const currentConversation = hydrated
    ? conversations.find((conversation) => conversation.id === currentConversationId) || null
    : null;
  const expandedType = selectedTenderType || currentConversation?.tenderType || null;

  const conversationsByType = useMemo(
    () =>
      tenderTypes.reduce(
        (accumulator, tenderType) => ({
          ...accumulator,
          [tenderType.id]: sortConversationsByUpdatedAtDesc(
            conversations.filter((conversation) => conversation.tenderType === tenderType.id)
          ),
        }),
        {} as Record<TenderTypeId, Conversation[]>
      ),
    [conversations]
  );

  const typeIndicators = useMemo(() => {
    const indicators: Record<
      TenderTypeId,
      { unread: boolean; running: boolean; queued: boolean }
    > = {
      xjcg: { unread: false, running: false, queued: false },
      gngk: { unread: false, running: false, queued: false },
      gjgk: { unread: false, running: false, queued: false },
    };

    for (const conversation of conversations) {
      if (conversation.id === currentConversationId) {
        continue;
      }

      const slot = indicators[conversation.tenderType];
      if (!slot) {
        continue;
      }

      if (isConversationUnreadResult(conversation.id)) {
        slot.unread = true;
        continue;
      }

      const taskId = conversation.currentTaskId;
      if (!taskId) {
        continue;
      }

      const summary = taskSummaries[taskId];
      if (!summary) {
        continue;
      }

      if (summary.status === 'running') {
        slot.running = true;
      } else if (summary.status === 'queued') {
        slot.queued = true;
      }
    }

    return indicators;
  }, [conversations, currentConversationId, isConversationUnreadResult, taskSummaries]);

  useEffect(() => {
    if (!contextMenuConversationId) {
      return undefined;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isInMenu = contextMenuRef.current?.contains(target);
      const isOnTrigger = contextMenuTriggerRef.current?.contains(target);
      if (!isInMenu && !isOnTrigger) {
        contextMenuTriggerRef.current = null;
        setContextMenuConversationId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [contextMenuConversationId]);

  useEffect(() => {
    if (editing.conversationId && editingInputRef.current) {
      editingInputRef.current.focus();
      editingInputRef.current.select();
    }
  }, [editing.conversationId]);

  const closeContextMenu = () => {
    contextMenuTriggerRef.current = null;
    setContextMenuConversationId(null);
  };

  const handleTypeClick = (type: TenderTypeId) => {
    closeContextMenu();
    setSelectedTenderType(type);

    const typeConversations = conversationsByType[type];
    if (typeConversations.length > 0) {
      // setCurrentConversation already syncs URL via syncUrlToCurrentConversation
      setCurrentConversation(typeConversations[0].id);
      return;
    }

    createConversation('新对话', type);
    // Reset URL to type defaults for a new blank conversation
    syncBrowserUrlToConversation({ tenderType: type });
  };

  const handleNewChat = (type: TenderTypeId) => {
    closeContextMenu();
    setSelectedTenderType(type);
    createConversation('新对话', type);
    // Reset URL to type defaults for a blank new conversation
    syncBrowserUrlToConversation({ tenderType: type });
    if (onNewChat) {
      onNewChat(type);
    }
  };

  const handleConversationSelect = (conversationId: string) => {
    closeContextMenu();
    setCurrentConversation(conversationId);
  };

  const handleDelete = (conversationId: string) => {
    closeContextMenu();
    deleteConversation(conversationId);
    if (editing.conversationId === conversationId) {
      setEditing({ conversationId: null, tempTitle: '' });
    }
  };

  const handleStartRename = (conversationId: string) => {
    const conversation = conversations.find((item) => item.id === conversationId);
    closeContextMenu();
    if (!conversation) {
      return;
    }

    setEditing({
      conversationId,
      tempTitle: conversation.title,
    });
  };

  const handleSaveRename = () => {
    if (editing.conversationId && editing.tempTitle.trim()) {
      updateConversation(editing.conversationId, { title: editing.tempTitle.trim() });
    }
    setEditing({ conversationId: null, tempTitle: '' });
  };

  const getConversationBadge = (conversationId: string, currentTaskId?: string) => {
    if (conversationId === currentConversationId) {
      return null;
    }

    if (isConversationUnreadResult(conversationId)) {
      return {
        label: '未读结果',
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      };
    }

    if (!currentTaskId) {
      return null;
    }

    const summary = taskSummaries[currentTaskId];
    if (!summary) {
      return null;
    }

    if (summary.status === 'running') {
      return {
        label: '运行中',
        className: 'border-blue-200 bg-blue-50 text-blue-700',
      };
    }

    if (summary.status === 'queued') {
      return {
        label: '排队中',
        className: 'border-amber-200 bg-amber-50 text-amber-700',
      };
    }

    return null;
  };

  return (
    <div className="flex h-full min-h-0 w-50 min-w-36 flex-col overflow-hidden border-r border-gray-200 bg-[var(--background)] shadow-sm">
      <div className="border-b border-gray-200 px-3 py-3">
        <div className="text-xs font-medium tracking-[0.2em] text-[var(--text-muted)] uppercase">
          类型
        </div>
      </div>

      <div
        className="min-h-0 flex-1 overflow-y-auto px-2 py-2"
        data-testid="tender-type-sidebar-scroll"
      >
        <div className="space-y-2.5">
          {tenderTypes.map((type) => {
            const typeConversations = conversationsByType[type.id];
            const isExpanded = expandedType === type.id;
            const indicator = typeIndicators[type.id];

            return (
              <section
                key={type.id}
                className="space-y-2"
                data-testid={`tender-type-group-${type.id}`}
              >
                <button
                  type="button"
                  onClick={() => handleTypeClick(type.id)}
                  className={cn(
                    'relative flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left transition-all duration-200',
                    isExpanded
                      ? 'border-[var(--primary)]/20 bg-[var(--primary)] text-white shadow-md'
                      : 'border-transparent bg-white text-[var(--text-muted)] hover:border-gray-200 hover:shadow-sm'
                  )}
                  aria-expanded={isExpanded}
                  data-testid={`tender-type-button-${type.id}`}
                >
                  {indicator?.unread ? (
                    <span
                      className="absolute top-2.5 right-2.5 h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_0_2px_rgba(255,255,255,0.9)]"
                      aria-label="有未读结果"
                    />
                  ) : indicator?.running ? (
                    <span
                      className="absolute top-2.5 right-2.5 h-2.5 w-2.5 rounded-full bg-blue-500 shadow-[0_0_0_2px_rgba(255,255,255,0.9)]"
                      aria-label="有运行中任务"
                    />
                  ) : indicator?.queued ? (
                    <span
                      className="absolute top-2.5 right-2.5 h-2.5 w-2.5 rounded-full bg-amber-500 shadow-[0_0_0_2px_rgba(255,255,255,0.9)]"
                      aria-label="有排队任务"
                    />
                  ) : null}

                  <div
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                      isExpanded ? 'bg-white/15' : 'bg-gray-100 text-[var(--primary)]'
                    )}
                  >
                    <span className="scale-90">{type.icon}</span>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-semibold">{type.name}</span>
                      <span
                        className={cn(
                          'rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                          isExpanded ? 'bg-white/15 text-white' : 'bg-gray-100 text-gray-500'
                        )}
                      >
                        {typeConversations.length}
                      </span>
                    </div>
                    <p
                      className={cn(
                        'mt-0.5 truncate text-[11px]',
                        isExpanded ? 'text-white/80' : 'text-[var(--text-muted)]'
                      )}
                    >
                      {type.description}
                    </p>
                  </div>
                </button>

                {isExpanded && (
                  <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
                    <div className="border-b border-gray-100 p-2">
                      <button
                        type="button"
                        onClick={() => handleNewChat(type.id)}
                        className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--primary)] px-2 py-2 text-xs font-medium text-white transition-colors hover:bg-[var(--primary)]/90"
                        data-testid={`tender-type-new-chat-${type.id}`}
                      >
                        <MessageSquarePlus className="h-3.5 w-3.5" />
                        新建对话
                      </button>
                    </div>

                    <div className="px-2 py-2">
                      <div className="mb-2 flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                        <History className="h-3 w-3" />
                        当前页面会话
                      </div>

                      {typeConversations.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-2.5 py-3 text-[11px] text-[var(--text-muted)]">
                          当前类型暂无会话，点击上方按钮可直接新建。
                        </div>
                      ) : (
                        <div
                          className="space-y-1"
                          data-testid={`tender-type-conversations-${type.id}`}
                        >
                          {typeConversations.map((conversation) => {
                            const badge = getConversationBadge(
                              conversation.id,
                              conversation.currentTaskId
                            );
                            const isCurrent = currentConversationId === conversation.id;
                            const isEditing = editing.conversationId === conversation.id;
                            const isMenuOpen = contextMenuConversationId === conversation.id;

                            return (
                              <div
                                key={conversation.id}
                                className={cn(
                                  'relative rounded-lg border transition-colors',
                                  isCurrent
                                    ? 'border-blue-200 bg-blue-50'
                                    : 'border-transparent bg-white hover:border-gray-200 hover:bg-gray-50'
                                )}
                                data-testid={`conversation-item-${conversation.id}`}
                              >
                                {isEditing ? (
                                  <div className="px-2.5 py-2.5">
                                    <input
                                      ref={editingInputRef}
                                      type="text"
                                      value={editing.tempTitle}
                                      onChange={(event) =>
                                        setEditing((previous) => ({
                                          ...previous,
                                          tempTitle: event.target.value,
                                        }))
                                      }
                                      onKeyDown={(event) => {
                                        if (event.key === 'Enter') {
                                          handleSaveRename();
                                        } else if (event.key === 'Escape') {
                                          setEditing({ conversationId: null, tempTitle: '' });
                                        }
                                      }}
                                      onBlur={handleSaveRename}
                                      className="w-full rounded-md border border-blue-300 px-2.5 py-2 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                    />
                                  </div>
                                ) : (
                                  <div className="flex items-start gap-1.5 px-2.5 py-2">
                                    <button
                                      type="button"
                                      onClick={() => handleConversationSelect(conversation.id)}
                                      className="min-w-0 flex-1 text-left"
                                    >
                                      <div
                                        className={cn(
                                          'truncate text-xs font-medium',
                                          isCurrent ? 'text-blue-700' : 'text-gray-800'
                                        )}
                                      >
                                        {conversation.title}
                                      </div>
                                      <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[10px] text-gray-400">
                                        <span>
                                          {new Date(conversation.updatedAt).toLocaleDateString('zh-CN')}
                                        </span>
                                        {badge ? (
                                          <span
                                            className={cn(
                                              'inline-flex rounded-full border px-1.5 py-0.5 font-medium',
                                              badge.className
                                            )}
                                          >
                                            {badge.label}
                                          </span>
                                        ) : null}
                                      </div>
                                    </button>

                                    <button
                                      type="button"
                                      aria-label="更多操作"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        contextMenuTriggerRef.current = event.currentTarget;
                                        setContextMenuConversationId((previous) =>
                                          previous === conversation.id ? null : conversation.id
                                        );
                                      }}
                                      className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-700"
                                    >
                                      <MoreHorizontal className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                )}

                                {isMenuOpen ? (
                                  <div
                                    ref={contextMenuRef}
                                    className="absolute top-9 right-2 z-20 min-w-[110px] rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
                                  >
                                    <button
                                      type="button"
                                      onClick={() => handleStartRename(conversation.id)}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-gray-700 transition-colors hover:bg-gray-100"
                                    >
                                      <Edit2 className="h-3.5 w-3.5" />
                                      重命名
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDelete(conversation.id)}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-red-600 transition-colors hover:bg-red-50"
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                      删除
                                    </button>
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default TenderTypeSidebar;
