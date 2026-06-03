'use client';

import React from 'react';
import { CheckCircle2, Download, FileText, MessageSquarePlus, TriangleAlert } from 'lucide-react';
import type { Message } from '@/types/chat';

interface TaskDownloadMessageProps {
  message: Message;
  onDownload?: (filePath: string, fileName?: string) => void;
  onCommentSupplement?: (message: Message) => void;
  disabled?: boolean;
  commentSupplementDisabled?: boolean;
}

export function TaskDownloadMessage({
  message,
  onDownload,
  onCommentSupplement,
  disabled = false,
  commentSupplementDisabled = false,
}: TaskDownloadMessageProps) {
  const outputFile =
    typeof message.metadata?.outputFile === 'string' ? message.metadata.outputFile : '';
  const taskKind = message.metadata?.taskKind;
  const isModifyTask = taskKind === 'rewrite';
  const isGenerateTask = taskKind === 'generate';
  const commentWarning = message.metadata?.commentWriteback?.warning === true;
  const fileName =
    typeof message.metadata?.fileName === 'string' && message.metadata.fileName.length > 0
      ? message.metadata.fileName
      : outputFile
        ? outputFile.split(/[\\/]/).pop() || outputFile
        : '生成文件';

  const handleDownload = () => {
    if (!outputFile || !onDownload) {
      return;
    }
    if (disabled) {
      return;
    }
    onDownload(outputFile, fileName);
  };

  const handleCommentSupplement = () => {
    if (!outputFile || !onCommentSupplement || commentSupplementDisabled) {
      return;
    }
    onCommentSupplement(message);
  };

  return (
    <div className="overflow-hidden rounded border border-green-500 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-gray-700">
            {isModifyTask ? '修改文档已更新' : '文档已生成'}
          </span>
        </div>
        <button
          onClick={handleDownload}
          disabled={!outputFile || disabled}
          className="flex items-center gap-1 rounded bg-blue-500 px-3 py-1.5 text-sm text-white shadow-sm transition-colors duration-200 hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Download className="h-4 w-4" />
          {isModifyTask ? '下载修改文档' : '下载文件'}
        </button>
      </div>

      <div className="space-y-3 px-4 py-3 text-sm text-gray-600">
        {commentWarning && (
          <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
            <TriangleAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>文档已生成，部分批注未写入</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-gray-400" />
          <span className="truncate">{fileName}</span>
        </div>
        {isGenerateTask && (
          <button
            type="button"
            onClick={handleCommentSupplement}
            disabled={!outputFile || !onCommentSupplement || commentSupplementDisabled}
            className="inline-flex items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-700 transition-colors duration-200 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <MessageSquarePlus className="h-4 w-4" />
            补充批注
          </button>
        )}
      </div>
    </div>
  );
}

export default TaskDownloadMessage;
