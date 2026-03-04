'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { XjcgTenderForm, type XjcgTenderFormData } from '@/components/forms/XjcgTenderForm';
import { GngkTenderForm, type GngkTenderFormData } from '@/components/forms/GngkTenderForm';
import { createGenerateTask, ApiError, getDownloadUrl } from '@/lib/api';
import { useTaskProgress } from '@/hooks/useSSE';
import { useHistoryStore } from '@/stores/historyStore';
import type { GenerateRequest, CreateTaskData } from '@/types/api';
import { AlertCircle, RefreshCw, Download, CheckCircle } from 'lucide-react';
import { ProgressDisplay } from '@/components/ProgressDisplay';
import { LogViewer, type LogEntry } from '@/components/LogViewer';

const tenderTypeMap: Record<string, { title: string; description: string }> = {
  xjcg: {
    title: '询价采购',
    description: '创建询价采购招标文件',
  },
  gngk: {
    title: '国内公开',
    description: '创建国内公开招标文件',
  },
};

const convertXjcgFormToApiRequest = (formData: XjcgTenderFormData): GenerateRequest => {
  return {
    tender_no: formData.tender_no,
    tender_data: formData.tender_data,
    model: formData.model,
    files: {
      origin_tender_path: formData.files.origin_tender?.file_path,
      clean_draft_path: formData.files.clean_draft?.file_path,
      tender_param_paths: formData.files.tender_params.map((f) => f.file_path),
    },
    insertion_config: formData.insertion_config,
  };
};

const convertGngkFormToApiRequest = (formData: GngkTenderFormData): GenerateRequest => {
  return {
    tender_no: formData.tender_no,
    tender_data: formData.tender_data,
    model: formData.model,
    files: {
      origin_tender_path: formData.files.origin_tender?.file_path,
      clean_draft_path: formData.files.clean_draft?.file_path,
      tender_param_paths: formData.files.tender_params.map((f) => f.file_path),
    },
    insertion_config: formData.insertion_config,
  };
};

/**
 * 获取用户友好的错误消息
 */
function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const apiError = error as ApiError;
    switch (apiError.status) {
      case 400:
        return `请求参数错误：${apiError.message}`;
      case 401:
        return '未授权，请重新登录';
      case 403:
        return '没有权限执行此操作';
      case 404:
        return '请求的资源不存在';
      case 422:
        return `数据验证失败：${apiError.message}`;
      case 429:
        return '请求过于频繁，请稍后再试';
      case 500:
        return '服务器内部错误，请稍后重试';
      case 502:
      case 503:
      case 504:
        return '服务器暂时不可用，请稍后重试';
      default:
        return apiError.message || '请求失败，请稍后重试';
    }
  }

  // 网络错误
  if (error instanceof TypeError && (error as Error).message.includes('fetch')) {
    return '无法连接到服务器，请检查后端服务是否运行';
  }

  if (error instanceof Error) {
    return (error as Error).message;
  }

  return '发生未知错误，请稍后重试';
}

export default function TenderPage() {
  const params = useParams();
  const type = params.type as string;
  const config = tenderTypeMap[type] || {
    title: '未知类型',
    description: '不支持的招标类型',
  };

  // State management
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastFormData, setLastFormData] = useState<XjcgTenderFormData | GngkTenderFormData | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  // History store
  const { addToHistory, updateHistoryItem } = useHistoryStore();

  // SSE task progress tracking
  const {
    isConnected: sseConnected,
    progress,
    logs,
    status: taskStatus,
    result: taskResult,
    error: sseError,
  } = useTaskProgress(currentTaskId);

  // Convert logs from useTaskProgress to LogViewer format
  const formattedLogs: LogEntry[] = logs.map(log => ({
    timestamp: log.timestamp,
    level: log.level.toLowerCase() as 'info' | 'warning' | 'error',
    message: log.message,
    node: log.node,
  }));

  // Handle SSE error
  useEffect(() => {
    if (sseError) {
      setSubmitError(`任务执行错误: ${sseError}`);
    }
  }, [sseError]);

  // Handle task status updates and update history
  useEffect(() => {
    if (currentTaskId && taskStatus) {
      updateHistoryItem(currentTaskId, {
        status: taskStatus,
        progressPercent: progress?.progressPercent || 0,
        outputFile: taskResult?.output_file,
        outputFileName: taskResult?.file_name,
      });
    }
  }, [taskStatus, progress, taskResult, currentTaskId, updateHistoryItem]);


  // Handle task completion
  useEffect(() => {
    if (taskStatus === 'completed') {
      setShowSuccess(true);
      // Auto-hide success message after 5 seconds
      const timer = setTimeout(() => setShowSuccess(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [taskStatus]);

  const handleXjcgSubmit = async (formData: XjcgTenderFormData) => {
    setLastFormData(formData);
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const apiData = convertXjcgFormToApiRequest(formData);
      const response: CreateTaskData = await createGenerateTask(apiData);
      setCurrentTaskId(response.task_id);
      // Add to history
      addToHistory({
        taskId: response.task_id,
        tenderNo: formData.tender_no,
        tenderType: type as 'xjcg' | 'gngk',
        tenderTypeName: config.title,
        status: 'running',
        model: formData.model,
        progressPercent: 0,
      });
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      setSubmitError(errorMessage);
      console.error('Submit error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGngkSubmit = async (formData: GngkTenderFormData) => {
    setLastFormData(formData);
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const apiData = convertGngkFormToApiRequest(formData);
      const response: CreateTaskData = await createGenerateTask(apiData);
      setCurrentTaskId(response.task_id);
      // Add to history
      addToHistory({
        taskId: response.task_id,
        tenderNo: formData.tender_no,
        tenderType: type as 'xjcg' | 'gngk',
        tenderTypeName: config.title,
        status: 'running',
        model: formData.model,
        progressPercent: 0,
      });
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      setSubmitError(errorMessage);
      console.error('Submit error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 重试提交
  const handleRetry = () => {
    if (lastFormData) {
      if (type === 'xjcg') {
        handleXjcgSubmit(lastFormData as XjcgTenderFormData);
      } else if (type === 'gngk') {
        handleGngkSubmit(lastFormData as GngkTenderFormData);
      }
    }
  };

  // 处理文件下载
  const handleDownload = () => {
    if (taskResult?.output_file) {
      const downloadUrl = getDownloadUrl(taskResult.output_file);
      window.open(downloadUrl, '_blank');
    }
  };

  // Check if type is valid
  const isValidType = ['xjcg', 'gngk'].includes(type);

  return (
    <MainLayout title={config.title} subtitle={config.description}>
      <div className="form-section space-y-6">
        {/* Success Notification */}
        {showSuccess && taskStatus === 'completed' && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-800">
                  任务完成！文档已成功生成
                </p>
                <p className="text-xs text-green-600 mt-1">
                  您可以在下方下载生成的文档
                </p>
              </div>
              <button
                onClick={() => setShowSuccess(false)}
                className="text-green-600 hover:text-green-800 text-sm"
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {submitError && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-[var(--error)] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-[var(--error)] font-medium">
                  提交失败
                </p>
                <p className="text-sm text-[var(--error)] mt-1">
                  {submitError}
                </p>
              </div>
              <button
                onClick={handleRetry}
                disabled={isSubmitting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-[var(--error)] bg-red-100 hover:bg-red-200 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              >
                <RefreshCw className={`w-4 h-4 ${isSubmitting ? 'animate-spin' : ''}`} />
                重试
              </button>
            </div>
          </div>
        )}

        {type === 'xjcg' && (
          <XjcgTenderForm
            onSubmit={handleXjcgSubmit}
            isSubmitting={isSubmitting}
          />
        )}
        {type === 'gngk' && (
          <GngkTenderForm
            onSubmit={handleGngkSubmit}
            isSubmitting={isSubmitting}
          />
        )}
        {!isValidType && (
          <div className="card">
            <div className="flex items-center justify-center h-64 text-[var(--text-muted)]">
              <div className="text-center">
                <p className="text-lg font-medium mb-2 text-[var(--error)]">不支持的招标类型</p>
                <p className="text-sm">请使用有效的招标类型: xjcg (询价采购) 或 gngk (国内公开)</p>
                <div className="mt-4 flex justify-center gap-2">
                  <span className="badge badge-error">类型: {type}</span>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Task Progress Section */}
        {currentTaskId && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
            {/* Progress Display */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">任务进度</h3>
                <span className={`badge ${sseConnected ? 'badge-success' : 'badge-warning'}`}>
                  {sseConnected ? '已连接' : '连接中...'}
                </span>
              </div>
              <ProgressDisplay
                percent={progress.progressPercent}
                currentNode={progress.currentNode}
                status={
                  taskStatus === 'completed' ? 'completed' :
                  taskStatus === 'failed' ? 'error' :
                  taskStatus === 'running' ? 'running' : 'idle'
                }
              />
              
              {/* Download Button - Only show when completed */}
              {taskStatus === 'completed' && taskResult?.output_file && (
                <div className="mt-4 pt-4 border-t border-[var(--border)]">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-green-800">
                        文档生成完成
                      </p>
                      <p className="text-xs text-green-600 mt-1">
                        {taskResult.file_name || taskResult.output_file}
                      </p>
                    </div>
                    <button
                      onClick={handleDownload}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      下载文档
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Log Viewer */}
            {logs.length > 0 && (
              <div className="card">
                <div className="h-64">
                  <LogViewer 
                    logs={formattedLogs}
                    onClear={() => {}}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </MainLayout>
  );
}
