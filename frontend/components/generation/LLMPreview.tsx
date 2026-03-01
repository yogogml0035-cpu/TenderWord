'use client';

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Bot, Copy, Check, Download, Maximize2, Minimize2, Sparkles } from 'lucide-react';

export interface LLMPreviewProps {
  /** Current streaming content */
  content: string;
  /** Whether content is still being generated */
  isGenerating?: boolean;
  /** Token count (if available) */
  tokenCount?: number;
  /** Node name where content is from */
  nodeName?: string;
  /** Model name used */
  modelName?: string;
  className?: string;
}

export function LLMPreview({
  content,
  isGenerating = false,
  tokenCount,
  nodeName,
  modelName,
  className,
}: LLMPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when generating
  useEffect(() => {
    if (isGenerating && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [content, isGenerating]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llm_output_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Format content with simple markdown-like rendering
  const formatContent = (text: string): React.ReactNode[] => {
    const lines = text.split('\n');
    return lines.map((line, index) => {
      // Headers
      if (line.startsWith('# ')) {
        return (
          <h1 key={index} className="text-xl font-bold mt-4 mb-2">
            {line.slice(2)}
          </h1>
        );
      }
      if (line.startsWith('## ')) {
        return (
          <h2 key={index} className="text-lg font-bold mt-3 mb-2">
            {line.slice(3)}
          </h2>
        );
      }
      if (line.startsWith('### ')) {
        return (
          <h3 key={index} className="text-base font-bold mt-3 mb-1">
            {line.slice(4)}
          </h3>
        );
      }
      // Bullet points
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return (
          <li key={index} className="ml-4 list-disc">
            {line.slice(2)}
          </li>
        );
      }
      // Numbered list
      if (/^\d+\./.test(line)) {
        return (
          <li key={index} className="ml-4 list-decimal">
            {line.replace(/^\d+\.\s*/, '')}
          </li>
        );
      }
      // Empty line
      if (line.trim() === '') {
        return <div key={index} className="h-2" />;
      }
      // Regular paragraph
      return (
        <p key={index} className="mb-2 leading-relaxed">
          {line}
        </p>
      );
    });
  };

  const displayContent = content || '等待生成内容...';

  return (
    <div className={cn('st-card', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-purple-100 rounded-lg">
            <Bot className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h3 className="font-semibold text-[var(--foreground)]">AI 生成内容</h3>
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
              {modelName && <span>模型：{modelName}</span>}
              {nodeName && <span>节点：{nodeName}</span>}
              {(tokenCount ?? 0) > 0 && <span>Token：{tokenCount}</span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Raw/Formatted toggle */}
          <button
            onClick={() => setShowRaw(!showRaw)}
            className={cn(
              'text-xs px-2 py-1 rounded border',
              showRaw
                ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                : 'bg-white text-[var(--text-muted)] border-[var(--border)] hover:border-[var(--primary)]'
            )}
          >
            {showRaw ? '格式化' : '原始'}
          </button>

          {/* Copy */}
          <button
            onClick={handleCopy}
            disabled={!content}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--foreground)] disabled:opacity-50"
            title="复制内容"
          >
            {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
          </button>

          {/* Download */}
          <button
            onClick={handleDownload}
            disabled={!content}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--foreground)] disabled:opacity-50"
            title="下载内容"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* Expand/Collapse */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--foreground)]"
            title={isExpanded ? '收起' : '展开'}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        ref={contentRef}
        className={cn(
          'overflow-y-auto rounded-lg border border-[var(--border)] bg-[#fafafa]',
          isExpanded ? 'h-[600px]' : 'max-h-[400px]'
        )}
      >
        {isGenerating && !content && (
          <div className="flex items-center justify-center h-32">
            <div className="flex items-center gap-2 text-[var(--text-muted)]">
              <Sparkles className="w-5 h-5 animate-pulse text-[var(--primary)]" />
              <span>AI 正在思考中...</span>
            </div>
          </div>
        )}

        <div className="p-4">
          {showRaw ? (
            <pre className="whitespace-pre-wrap font-mono text-sm text-[var(--foreground)]">
              {displayContent}
            </pre>
          ) : (
            <div className="prose prose-sm max-w-none">
              {formatContent(displayContent)}
            </div>
          )}

          {isGenerating && (
            <span className="inline-block w-2 h-4 bg-[var(--primary)] ml-1 animate-pulse">
              |
            </span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-[var(--text-muted)]">
        <span>
          字数：{content.length} 字符 | 行数：{content.split('\n').length}
        </span>
        {isGenerating && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-[var(--primary)] rounded-full animate-pulse" />
            生成中...
          </span>
        )}
      </div>
    </div>
  );
}

export default LLMPreview;
