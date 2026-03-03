'use client';

import React, { useRef, useEffect } from 'react';
import { FileText, Bot, Loader2, CheckCircle2, XCircle, Download, RefreshCw } from 'lucide-react';
import type { Message, LogEntry, DualColumnContent } from '@/types/chat';
import { isDualColumnContent } from '@/types/chat';

interface DualColumnMessageProps {
  message: Message;
  onDownload?: (filePath: string, fileName?: string) => void;
  onRetry?: () => void;
  maxHeight?: number;
}

export function DualColumnMessage({ 
  message, 
  onDownload,
  onRetry,
  maxHeight = 400 
}: DualColumnMessageProps) {
  const leftScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);

  const content = message.content;
  const dualContent = isDualColumnContent(content) ? content : null;
  
  const logs = dualContent?.logs || [];
  const aiContent = dualContent?.aiContent?.text || '';
  const isComplete = dualContent?.aiContent?.isComplete || false;

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (leftScrollRef.current) {
      leftScrollRef.current.scrollTop = leftScrollRef.current.scrollHeight;
    }
    if (rightScrollRef.current) {
      rightScrollRef.current.scrollTop = rightScrollRef.current.scrollHeight;
    }
  }, [logs.length, aiContent]);

  const getStatusIcon = () => {
    switch (message.status) {
      case 'generating':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getBorderColor = () => {
    switch (message.status) {
      case 'error':
        return 'border-red-500';
      case 'completed':
        return 'border-green-500';
      case 'generating':
        return 'border-blue-500';
      default:
        return 'border-gray-200';
    }
  };

  const handleDownload = () => {
    if (message.metadata?.outputFile && onDownload) {
      onDownload(message.metadata.outputFile, message.metadata.fileName);
    }
  };

  return (
    <div className={`rounded border ${getBorderColor()} bg-white shadow-sm overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-sm font-medium text-gray-700">
            {message.status === 'generating' && '生成中...'}
            {message.status === 'completed' && '已完成'}
            {message.status === 'error' && '生成失败'}
            {message.status === 'cancelled' && '已取消'}
          </span>
        </div>
        
        {message.status === 'completed' && message.metadata?.outputFile && (
          <button
            onClick={handleDownload}
            className="flex items-center gap-1 px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            <Download className="w-4 h-4" />
            下载文件
          </button>
        )}
        
        {message.status === 'error' && onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 bg-blue-50 rounded hover:bg-blue-100 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            重新生成
          </button>
        )}
      </div>

      {/* Error Message */}
      {message.error && (
        <div className="px-4 py-2 bg-red-50 text-red-600 text-sm border-b border-red-200">
          {message.error}
        </div>
      )}

      {/* Dual Column Content */}
      <div className="flex" style={{ maxHeight: `${maxHeight}px` }}>
        {/* Left Column - Logs */}
        <div className="w-1/2 border-r border-gray-200 flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
            <FileText className="w-4 h-4 text-gray-500" />
            <span className="text-xs font-medium text-gray-600">进度日志</span>
          </div>
          
          <div 
            ref={leftScrollRef}
            className="flex-1 overflow-y-auto p-3 space-y-2"
          >
            {logs.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">等待开始...</div>
            ) : (
              logs.map((log) => (
                <LogEntryItem key={log.id} log={log} />
              ))
            )}
          </div>
        </div>

        {/* Right Column - AI Content */}
        <div className="w-1/2 flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
            <Bot className="w-4 h-4 text-gray-500" />
            <span className="text-xs font-medium text-gray-600">AI 生成内容</span>
          </div>
          
          <div 
            ref={rightScrollRef}
            className="flex-1 overflow-y-auto p-3"
          >
            {aiContent ? (
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                {aiContent}
              </pre>
            ) : (
              <div className="text-xs text-gray-400 text-center py-4">等待生成...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Log Entry Sub-component
function LogEntryItem({ log }: { log: LogEntry }) {
  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-red-600 bg-red-50';
      case 'warn':
        return 'text-yellow-600 bg-yellow-50';
      case 'debug':
        return 'text-gray-500 bg-gray-50';
      default:
        return 'text-blue-600 bg-blue-50';
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="flex items-start gap-2 text-xs">
      <span className="text-gray-400 shrink-0">{formatTime(log.timestamp)}</span>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${getLevelColor(log.level)}`}>
        {log.level.toUpperCase()}
      </span>
      <span className="text-gray-700">{log.message}</span>
    </div>
  );
}

export default DualColumnMessage;
