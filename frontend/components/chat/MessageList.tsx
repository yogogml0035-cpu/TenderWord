'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { User, Bot, Info, Loader2, RefreshCw, Copy, Check } from 'lucide-react';
import type { Message } from '@/types/chat';
import { TaskLogMessage } from './TaskLogMessage';
import { TaskContentMessage } from './TaskContentMessage';
import { TaskDownloadMessage } from './TaskDownloadMessage';

interface MessageListProps {
  messages: Message[];
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: (message: Message) => void;
  emptyState?: React.ReactNode;
  interactionDisabled?: boolean;
  className?: string;
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((?:https?:\/\/[^\s)]+)\))/g;
  const parts = text.split(pattern);

  return parts
    .filter((part): part is string => typeof part === 'string' && part.length > 0)
    .map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={`md-bold-${index}`}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={`md-code-${index}`}
            className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[13px] text-slate-700"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      const linkMatch = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
      if (linkMatch) {
        return (
          <a
            key={`md-link-${index}`}
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 underline"
          >
            {linkMatch[1]}
          </a>
        );
      }
      return <React.Fragment key={`md-text-${index}`}>{part}</React.Fragment>;
    });
}

function SimpleMarkdown({ content }: { content: string }) {
  const segments = content.split('```');
  return (
    <div className="space-y-2 text-sm leading-6 text-slate-700">
      {segments.map((segment, index) => {
        const isCode = index % 2 === 1;
        if (isCode) {
          return (
            <pre
              key={`code-${index}`}
              className="overflow-x-auto rounded border border-slate-200 bg-slate-900/95 p-3 font-mono text-xs text-slate-100"
            >
              {segment.trim()}
            </pre>
          );
        }

        const lines = segment.split('\n');
        return (
          <div key={`text-${index}`} className="space-y-1">
            {lines.map((line, lineIndex) => (
              <p key={`line-${index}-${lineIndex}`} className="whitespace-pre-wrap break-words">
                {renderInlineMarkdown(line)}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}

async function copyPlainText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'absolute';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

export function MessageList({
  messages,
  onDownload,
  onRetry,
  emptyState,
  interactionDisabled = false,
  className = '',
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [userScrolled, setUserScrolled] = useState(false);

  const handleScroll = () => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 50;

    setIsAtBottom(atBottom);
    if (!atBottom) {
      setUserScrolled(true);
    }
  };

  useEffect(() => {
    if (containerRef.current && isAtBottom && !userScrolled) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isAtBottom, userScrolled]);

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
            <MemoMessageItem
              message={message}
              interactionDisabled={interactionDisabled}
              onDownload={onDownload}
              onRetry={onRetry}
            />
          </div>
        ))}
      </div>

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

interface MessageItemProps {
  message: Message;
  interactionDisabled?: boolean;
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: (message: Message) => void;
}

function MessageItem({ message, interactionDisabled = false, onDownload, onRetry }: MessageItemProps) {
  const [copied, setCopied] = useState(false);
  const [showUserActions, setShowUserActions] = useState(false);
  const copyResetTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copyResetTimerRef.current !== null) {
        window.clearTimeout(copyResetTimerRef.current);
      }
    };
  }, []);

  const handleCopyUserMessage = useCallback(() => {
    if (interactionDisabled || message.type !== 'user' || typeof message.content !== 'string') {
      return;
    }

    void copyPlainText(message.content)
      .then(() => {
        setCopied(true);
        if (copyResetTimerRef.current !== null) {
          window.clearTimeout(copyResetTimerRef.current);
        }
        copyResetTimerRef.current = window.setTimeout(() => {
          setCopied(false);
          copyResetTimerRef.current = null;
        }, 1500);
      })
      .catch(() => {
        setCopied(false);
      });
  }, [interactionDisabled, message.content, message.type]);

  if (message.type === 'ai') {
    const messageKind = message.metadata?.messageKind;

    return (
      <div className="animate-fade-in-up flex gap-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-blue-100 shadow-sm">
          <Bot className="h-5 w-5 text-blue-600" />
        </div>

        <div className="min-w-0 flex-1">
          {messageKind === 'task-log' && <TaskLogMessage message={message} disabled={interactionDisabled} />}
          {messageKind === 'task-content' && (
            <TaskContentMessage
              message={message}
              disabled={interactionDisabled}
              onRetry={onRetry ? () => onRetry(message) : undefined}
            />
          )}
          {messageKind === 'agent-step' && (
            <TaskContentMessage
              message={message}
              disabled={interactionDisabled}
              onRetry={onRetry ? () => onRetry(message) : undefined}
            />
          )}
          {messageKind === 'task-download' && (
            <TaskDownloadMessage
              message={message}
              disabled={interactionDisabled}
              onDownload={onDownload}
            />
          )}
          {!messageKind && (
            <div className="rounded border border-gray-200 bg-white px-4 py-3 shadow-sm">
              <SimpleMarkdown content={typeof message.content === 'string' ? message.content : '...'} />

              {message.status === 'generating' && (
                <div className="mt-3 flex items-center gap-2 text-xs text-blue-600">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>回复生成中...</span>
                </div>
              )}

              {(message.status === 'error' || message.status === 'cancelled') && onRetry && (
                <div className="mt-3 flex items-center justify-between gap-3 border-t border-slate-100 pt-2">
                  <span className="text-xs text-rose-500">
                    {message.status === 'cancelled' ? '已取消，保留部分内容' : '回复失败，保留部分内容'}
                  </span>
                  <button
                    type="button"
                    onClick={() => onRetry(message)}
                    disabled={interactionDisabled}
                    className="inline-flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-600 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重试
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (message.type === 'user') {
    const userContent = typeof message.content === 'string' ? message.content : '';

    return (
      <div className="animate-fade-in-up flex items-start justify-end gap-3">
        <div
          data-testid="user-message-frame"
          className="min-w-0 w-fit max-w-[65%]"
          onMouseEnter={() => setShowUserActions(true)}
          onMouseLeave={() => setShowUserActions(false)}
          onFocusCapture={() => setShowUserActions(true)}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setShowUserActions(false);
            }
          }}
        >
          <div
            data-testid="user-message-bubble"
            className="w-fit max-w-full rounded-2xl rounded-tr-sm bg-blue-500 px-4 py-2.5 text-white shadow-sm"
          >
            <p data-testid="user-message-text" className="whitespace-pre-wrap break-words text-sm leading-6">
              {userContent || '...'}
            </p>
          </div>

          <div className="relative mt-1 h-7">
            <div
              data-testid="user-message-time"
              className={`absolute inset-y-0 right-0 flex items-center transition-opacity duration-150 ${
                showUserActions ? 'opacity-0' : 'opacity-100'
              }`}
            >
              <span className="text-[10px] text-gray-400">
                {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>

            <div
              data-testid="user-message-actions"
              className={`absolute inset-y-0 right-0 flex items-center gap-3 text-slate-400 transition-opacity duration-150 ${
                showUserActions ? 'opacity-100' : 'pointer-events-none opacity-0'
              }`}
            >
              <button
                type="button"
                aria-label="复制用户消息"
                title="复制用户消息"
                onClick={handleCopyUserMessage}
                disabled={!userContent || interactionDisabled}
                tabIndex={showUserActions ? 0 : -1}
                className="inline-flex h-7 w-7 items-center justify-center transition-colors duration-200 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
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
