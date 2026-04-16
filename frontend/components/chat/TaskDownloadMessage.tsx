'use client';

import React from 'react';
import { CheckCircle2, Download, FileText } from 'lucide-react';
import type { Message } from '@/types/chat';

interface TaskDownloadMessageProps {
  message: Message;
  onDownload?: (filePath: string, fileName?: string) => void;
  disabled?: boolean;
}

export function TaskDownloadMessage({
  message,
  onDownload,
  disabled = false,
}: TaskDownloadMessageProps) {
  const outputFile = typeof message.metadata?.outputFile === 'string' ? message.metadata.outputFile : '';
  const isModifyTask = message.metadata?.taskKind === 'rewrite' || message.metadata?.taskKind === 'edit';
  const styleWriteback =
    typeof message.metadata?.styleWriteback === 'object' && message.metadata.styleWriteback !== null
      ? message.metadata.styleWriteback
      : null;
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

      <div className="px-4 py-3 text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-gray-400" />
          <span className="truncate">{fileName}</span>
        </div>
        {styleWriteback?.summary ? (
          <p className="mt-2 text-xs leading-5 text-slate-500">{styleWriteback.summary}</p>
        ) : null}
      </div>
    </div>
  );
}

export default TaskDownloadMessage;
