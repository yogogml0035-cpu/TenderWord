'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Bot, CheckCircle2, Copy, Loader2, XCircle } from 'lucide-react';
import type { Message } from '@/types/chat';
import type {
  SSECommentAgentHighlight,
  SSECommentAgentRound,
  SSECommentAgentStep,
  SSECommentAgentWriteback,
  SSEContentAgentRound,
  SSEContentAgentStep,
} from '@/types/api';

interface TaskContentMessageProps {
  message: Message;
  maxHeight?: number;
  disabled?: boolean;
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

function getStatusIcon(status: Message['status']) {
  switch (status) {
    case 'generating':
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'error':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'cancelled':
      return <XCircle className="h-4 w-4 text-gray-400" />;
    default:
      return null;
  }
}

function getStatusLabel(message: Message) {
  if (message.status === 'error' && message.metadata?.localTaskReason === 'backend_restart') {
    return '任务已中断';
  }

  const status = message.status;
  switch (status) {
    case 'generating':
      return '生成中...';
    case 'completed':
      return '已完成';
    case 'error':
      return '生成失败';
    case 'cancelled':
      return '已取消';
    default:
      return 'AI 内容';
  }
}

function getBorderColor(status: Message['status']) {
  switch (status) {
    case 'generating':
      return 'border-blue-500';
    case 'completed':
      return 'border-green-500';
    case 'error':
      return 'border-red-500';
    case 'cancelled':
      return 'border-gray-300';
    default:
      return 'border-gray-200';
  }
}

function getContentTitle(message: Message) {
  if (message.metadata?.messageKind === 'agent-step') {
    const node = message.metadata.agentStepNode;
    if (typeof node === 'string' && node.trim()) {
      if (message.metadata.contentAgent || node.trim() === 'content_agent') {
        return '正文智能体';
      }
      if (node.trim() === 'comment_agent') {
        return '批注智能体';
      }
      if (message.metadata.agentStepType === 'final') {
        return `${node.trim()} final`;
      }
      const round = message.metadata.agentStepRound;
      return typeof round === 'number' ? `${node.trim()} round-${round}` : node.trim();
    }
    return '智能体过程';
  }

  if (message.metadata?.taskKind === 'rewrite' || message.metadata?.taskKind === 'edit') {
    return 'AI 修改内容';
  }

  return 'AI 生成内容';
}

function formatCount(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function getLatestRound(commentAgent: SSECommentAgentStep): SSECommentAgentRound | undefined {
  return commentAgent.rounds[commentAgent.rounds.length - 1];
}

function getOverviewRound(commentAgent: SSECommentAgentStep): SSECommentAgentRound | undefined {
  return commentAgent.final_validation || getLatestRound(commentAgent);
}

function getWritebackNotice(writeback?: SSECommentAgentWriteback | null): string | null {
  if (!writeback || writeback.skipped !== 1) {
    return null;
  }
  const issue = writeback.issues.find((item) => item.reason === '目标位置已有批注，已跳过');
  return issue ? '1 条目标位置已有批注，已跳过' : null;
}

function CommentAgentHighlightItem({ highlight }: { highlight: SSECommentAgentHighlight }) {
  return (
    <li className="rounded border border-gray-200 bg-white px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium text-gray-700">#{highlight.index}</span>
        <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-gray-600">
          {highlight.status}
        </span>
        {highlight.reason && <span className="text-gray-500">{highlight.reason}</span>}
      </div>
      {(highlight.original_reference_text || highlight.reference_text) && (
        <div className="mt-1 space-y-1 text-xs leading-5 text-gray-600">
          {highlight.original_reference_text && <p>原始锚点：{highlight.original_reference_text}</p>}
          {highlight.reference_text && <p>当前锚点：{highlight.reference_text}</p>}
        </div>
      )}
      {highlight.candidate_fragments.length > 0 && (
        <div className="mt-2 space-y-1 text-xs leading-5 text-gray-500">
          {highlight.candidate_fragments.map((fragment, index) => (
            <p key={`${highlight.index}-fragment-${index}`}>候选片段：{fragment}</p>
          ))}
        </div>
      )}
    </li>
  );
}

function CommentAgentRoundBlock({ round }: { round: SSECommentAgentRound }) {
  return (
    <section className="rounded border border-gray-200 bg-gray-50/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-gray-700">{round.label || `第 ${round.round} 轮锚点校验`}</h4>
        <p className="text-xs text-gray-500">
          通过 {formatCount(round.passed)} 条 / 需处理 {formatCount(round.failed)} 条 / 跳过 {formatCount(round.skipped)} 条
        </p>
      </div>
      {round.highlights.length > 0 ? (
        <ul className="mt-2 space-y-2">
          {round.highlights.map((highlight, index) => (
            <CommentAgentHighlightItem key={`${round.round}-${highlight.index}-${index}`} highlight={highlight} />
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-gray-500">普通通过项已计入数量。</p>
      )}
    </section>
  );
}

function CommentAgentWritebackBlock({ writeback }: { writeback: SSECommentAgentWriteback }) {
  const notice = getWritebackNotice(writeback);
  return (
    <section className="rounded border border-gray-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-gray-700">Word 写入统计</h4>
        <p className="text-xs text-gray-500">
          尝试 {formatCount(writeback.attempted)} 条 / 成功 {formatCount(writeback.added)} 条 / 失败 {formatCount(writeback.failed)} 条 / 跳过 {formatCount(writeback.skipped)} 条
        </p>
      </div>
      {notice && (
        <div className="mt-2 flex items-start gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          <span>{notice}</span>
        </div>
      )}
      {writeback.issues.length > 0 && (
        <ul className="mt-2 space-y-2">
          {writeback.issues.map((issue, index) => (
            <CommentAgentHighlightItem key={`writeback-${issue.index}-${index}`} highlight={issue} />
          ))}
        </ul>
      )}
    </section>
  );
}

function CommentAgentProcessView({ commentAgent }: { commentAgent: SSECommentAgentStep }) {
  const overview = getOverviewRound(commentAgent);
  const writeback = commentAgent.writeback || null;

  return (
    <div className="space-y-3 text-sm text-gray-700">
      <div className="rounded border border-blue-100 bg-blue-50 px-3 py-2">
        <p className="font-medium text-blue-900">
          {overview
            ? `通过 ${formatCount(overview.passed)} 条 / 需处理 ${formatCount(overview.failed)} 条 / 跳过 ${formatCount(overview.skipped)} 条`
            : '批注锚点校验中'}
        </p>
        {writeback && (
          <p className="mt-1 text-xs text-blue-700">
            成功 {formatCount(writeback.added)} 条 / 跳过 {formatCount(writeback.skipped)} 条 / 失败 {formatCount(writeback.failed)} 条
          </p>
        )}
      </div>

      {commentAgent.rounds.map((round) => (
        <CommentAgentRoundBlock key={round.round} round={round} />
      ))}

      {commentAgent.final_validation && (
        <section className="rounded border border-gray-200 bg-gray-50/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-medium text-gray-700">最终静默复校验</h4>
            <p className="text-xs text-gray-500">
              通过 {formatCount(commentAgent.final_validation.passed)} 条 / 失败 {formatCount(commentAgent.final_validation.failed)} 条 / 跳过 {formatCount(commentAgent.final_validation.skipped)} 条
            </p>
          </div>
        </section>
      )}

      {writeback && <CommentAgentWritebackBlock writeback={writeback} />}
    </div>
  );
}

function getContentAgentPhaseLabel(phase: SSEContentAgentStep['phase']): string {
  switch (phase) {
    case 'draft':
      return '初稿生成';
    case 'audit':
      return '审核发现';
    case 'revision':
      return '修复复核';
    case 'final':
      return '最终完成';
    default:
      return '正文智能体';
  }
}

function getContentAgentRawLabel(round: SSEContentAgentRound): string {
  switch (round.phase) {
    case 'draft':
      return '查看初稿正文';
    case 'audit':
      return '查看审核原始输出';
    case 'revision':
      return '查看修复正文';
    default:
      return '查看原始输出';
  }
}

function ContentAgentRawBlock({ label, content }: { label: string; content?: string | null }) {
  if (!content) {
    return null;
  }
  return (
    <details className="mt-2 rounded border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600">
      <summary className="cursor-pointer select-none font-medium text-gray-600">{label}</summary>
      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-gray-600">
        {content}
      </pre>
    </details>
  );
}

function ContentAgentFindingItem({ finding }: { finding: { evidence: string; fix_hint: string } }) {
  return (
    <li className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <p>
        <span className="font-medium">依据：</span>
        {finding.evidence}
      </p>
      <p className="mt-1">
        <span className="font-medium">修复建议：</span>
        {finding.fix_hint}
      </p>
    </li>
  );
}

function ContentAgentRoundBlock({ round }: { round: SSEContentAgentRound }) {
  return (
    <section className="rounded border border-gray-200 bg-gray-50/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-gray-700">
          {round.label || getContentAgentPhaseLabel(round.phase)}
        </h4>
        <p className="text-xs text-gray-500">
          问题 {formatCount(round.issue_count)} 个 / 修复 {formatCount(round.fix_count)} 个
        </p>
      </div>
      {round.summary && <p className="mt-1 text-xs leading-5 text-gray-600">{round.summary}</p>}
      {round.findings.length > 0 ? (
        <ul className="mt-2 space-y-2">
          {round.findings.map((finding, index) => (
            <ContentAgentFindingItem key={`${round.phase}-${round.round}-${index}`} finding={finding} />
          ))}
        </ul>
      ) : round.phase === 'audit' ? (
        <p className="mt-2 text-xs text-gray-500">普通通过项已计入数量。</p>
      ) : null}
      <ContentAgentRawBlock label={getContentAgentRawLabel(round)} content={round.content} />
    </section>
  );
}

function ContentAgentProcessView({ contentAgent }: { contentAgent: SSEContentAgentStep }) {
  const finalResult = contentAgent.final_result || null;

  return (
    <div className="space-y-3 text-sm text-gray-700">
      <div className="rounded border border-blue-100 bg-blue-50 px-3 py-2">
        <p className="font-medium text-blue-900">
          {contentAgent.summary || `${getContentAgentPhaseLabel(contentAgent.phase)}中`}
        </p>
        <p className="mt-1 text-xs text-blue-700">
          当前阶段：{getContentAgentPhaseLabel(contentAgent.phase)} / 已记录 {contentAgent.rounds.length} 个阶段
        </p>
      </div>

      {contentAgent.rounds.map((round, index) => (
        <ContentAgentRoundBlock key={`${round.phase}-${round.round}-${index}`} round={round} />
      ))}

      {contentAgent.highlights.length > 0 && contentAgent.phase === 'final' && (
        <section className="rounded border border-amber-200 bg-amber-50/70 p-3">
          <h4 className="text-sm font-medium text-amber-800">最终仍需关注</h4>
          <ul className="mt-2 space-y-2">
            {contentAgent.highlights.map((finding, index) => (
              <ContentAgentFindingItem key={`final-highlight-${index}`} finding={finding} />
            ))}
          </ul>
        </section>
      )}

      {finalResult && (
        <section className="rounded border border-gray-200 bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-medium text-gray-700">最终完成</h4>
            <p className="text-xs text-gray-500">
              修复 {formatCount(finalResult.revision_rounds)} 轮 / 正文 {formatCount(finalResult.final_chars)} 字 / 问题 {formatCount(finalResult.issue_count)} 个
            </p>
          </div>
          {finalResult.summary && <p className="mt-1 text-xs leading-5 text-gray-600">{finalResult.summary}</p>}
          <ContentAgentRawBlock label="查看最终正文" content={finalResult.content} />
        </section>
      )}
    </div>
  );
}

export function TaskContentMessage({
  message,
  maxHeight = 320,
  disabled = false,
}: TaskContentMessageProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const content = typeof message.content === 'string' ? message.content : '';
  const progressText = message.metadata?.progressText;
  const progressPercent = message.metadata?.progressPercent;
  const contentTitle = getContentTitle(message);
  const commentAgent = message.metadata?.commentAgent;
  const contentAgent = message.metadata?.contentAgent;
  const copyContent = contentAgent?.final_result?.content || content;
  const isEmptyRunningAgentStep =
    message.metadata?.messageKind === 'agent-step' &&
    message.status === 'generating' &&
    !contentAgent &&
    !commentAgent &&
    content.length === 0;
  const isAgentStep = message.metadata?.messageKind === 'agent-step';

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    setStickToBottom(atBottom);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickToBottom) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [content, commentAgent, contentAgent, stickToBottom]);

  const handleCopyContent = useCallback(() => {
    if (disabled) {
      return;
    }
    void copyPlainText(copyContent);
  }, [copyContent, disabled]);

  return (
    <div className={`overflow-hidden rounded border bg-white shadow-sm ${getBorderColor(message.status)}`}>
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">
            {contentTitle}
          </span>
          <div className="ml-1 flex items-center gap-1.5 text-xs text-gray-500">
            {getStatusIcon(message.status)}
            <span>{getStatusLabel(message)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="复制AI内容"
            title="复制AI内容"
            onClick={handleCopyContent}
            disabled={!copyContent || disabled}
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {(typeof progressText === 'string' || typeof progressPercent === 'number') && (
        <div className="border-b border-gray-100 bg-gray-50/60 px-4 py-1.5 text-xs text-gray-500">
          {typeof progressText === 'string' ? progressText : '处理中'}
          {typeof progressPercent === 'number' ? ` (${Math.round(progressPercent)}%)` : ''}
        </div>
      )}

      {message.error && (
        <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          {message.error}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={`overflow-x-hidden overflow-y-auto p-3 ${isEmptyRunningAgentStep ? 'py-2' : ''}`}
        style={{ maxHeight }}
      >
        {contentAgent ? (
          <ContentAgentProcessView contentAgent={contentAgent} />
        ) : commentAgent ? (
          <CommentAgentProcessView commentAgent={commentAgent} />
        ) : content ? (
          <pre
            className={
              isAgentStep
                ? 'min-w-0 whitespace-pre-wrap break-words text-sm leading-6 text-gray-700'
                : 'min-w-0 break-all whitespace-pre-wrap font-mono text-sm text-gray-700'
            }
          >
            {content}
          </pre>
        ) : isEmptyRunningAgentStep ? (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
            <span>正在调用...</span>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <div className="relative mb-3">
              <div className="absolute inset-0 animate-pulse rounded-full bg-blue-100 opacity-30" />
              <div className="relative rounded-full bg-white p-2 shadow-sm">
                <Bot className="h-5 w-5 text-blue-400" />
              </div>
            </div>
            <span className="text-xs">等待生成...</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default TaskContentMessage;
