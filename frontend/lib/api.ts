/**
 * API Client for TenderWord Backend
 * Based on docs/api-contract.md
 * 
 * 使用 fetch API 实现的 API 客户端
 */

import type {
  TenderData,
  UploadedFile,
  MultipleUploadResult,
  TaskData,
  TaskListData,
  CancelTaskData,
  CreateTaskData,
  GenerateRequest,
  ApiSuccessResponse,
  ApiErrorResponse,
  FileType,
  TaskStatus,
} from '@/types/api';

// ============================================
// Configuration
// ============================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================
// Helper Functions
// ============================================

/**
 * Generic API request function with error handling
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const config: RequestInit = {
    headers: {
      ...(!(options.body instanceof FormData) && { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  const data = await response.json();

  if (!response.ok || data.success === false) {
    const errorData = data as ApiErrorResponse;
    throw new ApiError(
      errorData.error?.message || `HTTP error! status: ${response.status}`,
      errorData.error?.code || 'UNKNOWN_ERROR',
      response.status
    );
  }

  const successData = data as ApiSuccessResponse<T>;
  return successData.data;
}

/**
 * Custom API Error class
 */
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string = 'UNKNOWN_ERROR', status: number = 500) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

// ============================================
// Base API Client
// ============================================

export const api = {
  get: <T>(endpoint: string, options?: RequestInit) =>
    request<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body: unknown, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(body),
    }),

  put: <T>(endpoint: string, body: unknown, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  delete: <T>(endpoint: string, options?: RequestInit) =>
    request<T>(endpoint, { ...options, method: 'DELETE' }),
};

// ============================================
// Tender API
// ============================================

/**
 * 获取招标数据
 * GET /api/tender/{tender_no}
 */
export async function fetchTenderData(tenderNo: string): Promise<TenderData> {
  return request<TenderData>(`/api/tender/${encodeURIComponent(tenderNo)}`);
}

// ============================================
// File Upload API
// ============================================

export async function uploadFile(
  file: File,
  fileType?: FileType
): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append('file', file);
  if (fileType) {
    formData.append('file_type', fileType);
  }

  return request<UploadedFile>('/api/upload', {
    method: 'POST',
    body: formData,
    headers: {}, // Let browser set Content-Type for FormData
  });
}

export async function uploadFiles(
  files: File[],
  fileType?: FileType
): Promise<MultipleUploadResult> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (fileType) {
    formData.append('file_type', fileType);
  }

  return request<MultipleUploadResult>('/api/upload/multiple', {
    method: 'POST',
    body: formData,
    headers: {}, // Let browser set Content-Type for FormData
  });
}

// ============================================
// Task API
// ============================================

export async function createGenerateTask(
  params: GenerateRequest
): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskData> {
  return request<TaskData>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export async function cancelTask(taskId: string): Promise<CancelTaskData> {
  return request<CancelTaskData>(`/api/tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
  });
}

export async function getTaskList(options?: {
  status?: TaskStatus | 'all';
  page?: number;
  pageSize?: number;
  userSessionId?: string;
}): Promise<TaskListData> {
  const params = new URLSearchParams();
  
  if (options?.status) {
    params.append('status', options.status);
  }
  if (options?.page) {
    params.append('page', options.page.toString());
  }
  if (options?.pageSize) {
    params.append('page_size', options.pageSize.toString());
  }
  if (options?.userSessionId) {
    params.append('user_session_id', options.userSessionId);
  }

  const queryString = params.toString();
  const endpoint = queryString ? `/api/tasks?${queryString}` : '/api/tasks';

  return request<TaskListData>(endpoint);
}

// ============================================
// Download API
// ============================================

/**
 * 下载生成文件
 * GET /api/download/{file_path}
 */
export async function downloadFile(
  filePath: string,
  downloadName?: string
): Promise<Blob> {
  const params = new URLSearchParams();
  if (downloadName) {
    params.append('download_name', downloadName);
  }

  const queryString = params.toString();
  const endpoint = queryString
    ? `/api/download/${encodeURIComponent(filePath)}?${queryString}`
    : `/api/download/${encodeURIComponent(filePath)}`;

  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new ApiError(`Download failed: ${response.status}`, 'DOWNLOAD_FAILED', response.status);
  }

  return response.blob();
}

/**
 * 获取下载 URL（用于直接下载）
 */
export function getDownloadUrl(filePath: string, downloadName?: string): string {
  const params = new URLSearchParams();
  if (downloadName) {
    params.append('download_name', downloadName);
  }

  const queryString = params.toString();
  return queryString
    ? `${API_BASE_URL}/api/download/${encodeURIComponent(filePath)}?${queryString}`
    : `${API_BASE_URL}/api/download/${encodeURIComponent(filePath)}`;
}

// ============================================
// SSE Stream API
// ============================================


// ============================================
// Exports
// ============================================

export { API_BASE_URL };
