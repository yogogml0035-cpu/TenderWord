'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { MessageSquarePlus, History, Trash2, Edit2, MoreHorizontal } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';

interface NewChatPopupProps {
  type: 'xjcg' | 'gngk';
  typeName: string;
  description: string;
  isVisible: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onMouseEnter?: React.MouseEventHandler<HTMLDivElement>;
  onMouseLeave?: React.MouseEventHandler<HTMLDivElement>;
  position?: 'right' | 'left';
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  conversationId: string | null;
}

interface EditingState {
  conversationId: string | null;
  tempTitle: string;
}

export function NewChatPopup({
  type,
  typeName,
  description,
  isVisible,
  onClose,
  onNewChat,
  onMouseEnter,
  onMouseLeave,
  position = 'right',
}: NewChatPopupProps) {
  const CONTEXT_MENU_WIDTH = 140;
  const CONTEXT_MENU_HEIGHT = 88;
  const CONTEXT_MENU_GAP = 8;

  const { conversations, setCurrentConversation, currentConversationId, deleteConversation, updateConversation } = useChatStore();

  // Context menu state
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    conversationId: null,
  });

  // Inline editing state
  const [editing, setEditing] = useState<EditingState>({
    conversationId: null,
    tempTitle: '',
  });

  const contextMenuRef = useRef<HTMLDivElement>(null);
  const contextMenuTriggerRef = useRef<HTMLButtonElement | null>(null);
  const editingInputRef = useRef<HTMLInputElement>(null);

  // Filter conversations by type
  const typeConversations = conversations.filter((c) => c.tenderType === type).slice(0, 5);

  // Open context menu by trigger button position
  const openContextMenu = useCallback((
    conversationId: string,
    triggerRect: DOMRect,
    triggerEl: HTMLButtonElement
  ) => {
    const maxX = window.innerWidth - CONTEXT_MENU_WIDTH - CONTEXT_MENU_GAP;
    const maxY = window.innerHeight - CONTEXT_MENU_HEIGHT - CONTEXT_MENU_GAP;
    const menuX = triggerRect.right - CONTEXT_MENU_WIDTH;
    const menuY = triggerRect.bottom + 4;
    const safeX = Math.max(CONTEXT_MENU_GAP, Math.min(menuX, maxX));
    const safeY = Math.max(CONTEXT_MENU_GAP, Math.min(menuY, maxY));
    contextMenuTriggerRef.current = triggerEl;

    setContextMenu((prev) => {
      // Toggle: clicking the same item's trigger closes the menu
      if (prev.visible && prev.conversationId === conversationId) {
        contextMenuTriggerRef.current = null;
        return {
          visible: false,
          x: 0,
          y: 0,
          conversationId: null,
        };
      }

      return {
        visible: true,
        x: safeX,
        y: safeY,
        conversationId,
      };
    });
  }, []);

  // Close context menu
  const closeContextMenu = useCallback(() => {
    contextMenuTriggerRef.current = null;
    setContextMenu({
      visible: false,
      x: 0,
      y: 0,
      conversationId: null,
    });
  }, []);

  // Handle delete conversation
  const handleDelete = useCallback(() => {
    if (contextMenu.conversationId) {
      deleteConversation(contextMenu.conversationId);
      closeContextMenu();
    }
  }, [contextMenu.conversationId, deleteConversation, closeContextMenu]);

  // Start inline editing
  const handleStartRename = useCallback(() => {
    if (contextMenu.conversationId) {
      const conversation = conversations.find((c) => c.id === contextMenu.conversationId);
      if (conversation) {
        setEditing({
          conversationId: contextMenu.conversationId,
          tempTitle: conversation.title,
        });
      }
      closeContextMenu();
    }
  }, [contextMenu.conversationId, conversations, closeContextMenu]);

  // Save rename
  const handleSaveRename = useCallback(() => {
    if (editing.conversationId && editing.tempTitle.trim()) {
      updateConversation(editing.conversationId, { title: editing.tempTitle.trim() });
    }
    setEditing({ conversationId: null, tempTitle: '' });
  }, [editing.conversationId, editing.tempTitle, updateConversation]);

  // Cancel rename
  const handleCancelRename = useCallback(() => {
    setEditing({ conversationId: null, tempTitle: '' });
  }, []);

  // Handle editing input key events
  const handleEditingKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSaveRename();
    } else if (e.key === 'Escape') {
      handleCancelRename();
    }
  }, [handleSaveRename, handleCancelRename]);

  // Handle editing input blur
  const handleEditingBlur = useCallback(() => {
    handleSaveRename();
  }, [handleSaveRename]);

  // Click outside to close context menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      const isInMenu = contextMenuRef.current?.contains(target);
      const isOnTrigger = contextMenuTriggerRef.current?.contains(target);
      if (!isInMenu && !isOnTrigger) {
        closeContextMenu();
      }
    };

    if (contextMenu.visible) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [contextMenu.visible, closeContextMenu]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (editing.conversationId && editingInputRef.current) {
      editingInputRef.current.focus();
      editingInputRef.current.select();
    }
  }, [editing.conversationId]);


  if (!isVisible) return null;

  return (
    <div
      className={`absolute ${position === 'right' ? 'left-full' : 'right-full'} animate-scale-in top-0 z-50`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="min-w-[200px] rounded border border-gray-200 bg-white py-3 shadow-lg">
        {/* Header */}
        <div className="border-b border-gray-200 px-4 pb-3">
          <h3 className="font-medium text-gray-900">{typeName}</h3>
          <p className="mt-1 text-xs text-gray-500">{description}</p>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={onNewChat}
            className="flex w-full items-center justify-center gap-2 rounded bg-blue-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors duration-200 hover:bg-blue-600 hover:shadow-md"
          >
            <MessageSquarePlus className="h-4 w-4" />
            新建对话
          </button>
        </div>

        {/* Recent Conversations */}
        {typeConversations.length > 0 && (
          <>
            <div className="border-y border-gray-200 bg-gray-50 px-4 py-2">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <History className="h-3.5 w-3.5" />
                最近对话
              </div>
            </div>

            <div className="max-h-[150px] overflow-y-auto">
              {typeConversations.map((conv, index) => (
                <div
                  key={conv.id}
                  className={`animate-fade-in-up cursor-pointer transition-colors duration-200 ${
                    currentConversationId === conv.id
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-50'
                  } `}
                  style={{ animationDelay: `${index * 50}ms` }}
                  title={conv.title}
                >
                  {editing.conversationId === conv.id ? (
                    <div className="px-4 py-2.5">
                      <input
                        ref={editingInputRef}
                        type="text"
                        value={editing.tempTitle}
                        onChange={(e) => setEditing((prev) => ({ ...prev, tempTitle: e.target.value }))}
                        onKeyDown={handleEditingKeyDown}
                        onBlur={handleEditingBlur}
                        className="w-full rounded border border-blue-400 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-4 py-2.5">
                      <button
                        onClick={() => {
                          setCurrentConversation(conv.id);
                          onClose();
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <div className="truncate text-sm">{conv.title}</div>
                        <div className="mt-0.5 text-[10px] text-gray-400">
                          {new Date(conv.updatedAt).toLocaleDateString('zh-CN')}
                        </div>
                      </button>
                      <button
                        type="button"
                        aria-label="更多操作"
                        onClick={(e) => {
                          e.stopPropagation();
                          openContextMenu(
                            conv.id,
                            e.currentTarget.getBoundingClientRect(),
                            e.currentTarget
                          );
                        }}
                        className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-700"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Context Menu */}
            {contextMenu.visible && createPortal(
              <div
                ref={contextMenuRef}
                className="fixed z-[100] min-w-[120px] rounded border border-gray-200 bg-white py-1 shadow-lg"
                style={{ left: contextMenu.x, top: contextMenu.y }}
              >
                <button
                  onClick={handleStartRename}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-100"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                  重命名
                </button>
                <button
                  onClick={handleDelete}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-600 transition-colors hover:bg-red-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </button>
              </div>,
              document.body
            )}
          </>
        )}
      </div>

      {/* Arrow */}
      <div
        className={`absolute top-4 h-2 w-2 rotate-45 transform border-gray-200 bg-white ${
          position === 'right'
            ? 'left-0 -ml-1 border-b border-l'
            : 'right-0 -mr-1 border-t border-r'
        } `}
      />
    </div>
  );
}

export default NewChatPopup;
