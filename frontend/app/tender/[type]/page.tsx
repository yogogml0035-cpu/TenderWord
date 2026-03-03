'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { XjcgTenderForm, type XjcgTenderFormData } from '@/components/forms/XjcgTenderForm';
import { GngkTenderForm, type GngkTenderFormData } from '@/components/forms/GngkTenderForm';
import { createGenerateTask, ApiError } from '@/lib/api';
import type { GenerateRequest, CreateTaskData } from '@/types/api';
import { AlertCircle, RefreshCw } from 'lucide-react';

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

  const handleXjcgSubmit = async (formData: XjcgTenderFormData) => {
    setLastFormData(formData);
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const apiData = convertXjcgFormToApiRequest(formData);
      const response: CreateTaskData = await createGenerateTask(apiData);
      setCurrentTaskId(response.task_id);
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

  // Check if type is valid
  const isValidType = ['xjcg', 'gngk'].includes(type);

  return (
    <MainLayout title={config.title} subtitle={config.description}>
      <div className="form-section space-y-6">
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
      </div>
    </MainLayout>
  );
}
