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
  TaskHeartbeatData,
  TaskListData,
  CancelTaskData,
  CreateTaskData,
  GenerateRequest,
  RewriteRequest,
  ConversationHeartbeatData,
  ApiSuccessResponse,
  FileType,
  TaskStatus,
} from '@/types/api';
import type { Conversation } from '@/types/chat';

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
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const config: RequestInit = {
    headers: {
      ...(!(options.body instanceof FormData) && { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    ...options,
  };

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch {
    throw new ApiError(
      `Network request failed: ${endpoint}. Please check backend availability and CORS configuration.`,
      'NETWORK_ERROR',
      0
    );
  }

  const data: unknown = await response.json();
  const payload = (data ?? {}) as Record<string, unknown>;
  const nestedDetail = (payload.detail ?? {}) as Record<string, unknown>;
  const errorObj =
    (payload.error as Record<string, unknown> | undefined) ||
    (nestedDetail.error as Record<string, unknown> | undefined);
  const isExplicitFailure = payload.success === false || nestedDetail.success === false;

  if (!response.ok || isExplicitFailure) {
    throw new ApiError(
      (errorObj?.message as string) || `HTTP error! status: ${response.status}`,
      (errorObj?.code as string) || 'UNKNOWN_ERROR',
      response.status
    );
  }

  // Prefer wrapped success payload: { success: true, data: ... }
  if ('data' in payload) {
    const successData = data as ApiSuccessResponse<T>;
    return successData.data;
  }

  // Compatibility with legacy/flat endpoints that return business fields directly.
  return data as T;
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

export async function uploadFile(file: File, fileType?: FileType): Promise<UploadedFile> {
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

export async function createGenerateTask(params: GenerateRequest): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function createRewriteTask(params: RewriteRequest): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/rewrite', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskData> {
  return request<TaskData>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export async function cancelTask(taskId: string): Promise<CancelTaskData> {
  try {
    return await request<CancelTaskData>(`/api/tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    });
  } catch (error) {
    if (error instanceof ApiError && error.code === 'TASK_CANNOT_CANCEL') {
      return {
        success: true,
        task_id: taskId,
        message: '任务已结束，无需取消',
        was_running: false,
        noop: true,
      };
    }
    throw error;
  }
}

export async function sendTaskHeartbeat(taskId: string): Promise<TaskHeartbeatData> {
  return request<TaskHeartbeatData>(`/api/tasks/${encodeURIComponent(taskId)}/heartbeat`, {
    method: 'POST',
  });
}

export async function sendConversationHeartbeat(
  conversationId: string
): Promise<ConversationHeartbeatData> {
  return request<ConversationHeartbeatData>(
    `/api/conversations/${encodeURIComponent(conversationId)}/heartbeat`,
    {
      method: 'POST',
    }
  );
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
export async function downloadFile(filePath: string, downloadName?: string): Promise<Blob> {
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

/**
 * Get SSE stream URL for a task
 */
export function getTaskStreamUrl(taskId: string): string {
  return `${API_BASE_URL}/api/stream/${encodeURIComponent(taskId)}`;
}

// ============================================
// Chat/Conversation API
// ============================================

/**
 * Save conversation to backend (if supported)
 * POST /api/conversations
 *
 * Note: Current backend may not support this.
 * Mark as TODO if backend endpoint doesn't exist.
 */
export async function saveConversation(conversation: Conversation): Promise<{ id: string }> {
  // TODO: Backend endpoint may not exist yet
  // For now, return mock success
  return { id: conversation.id };
}

/**
 * Get conversation history from backend (if supported)
 * GET /api/conversations
 *
 * Note: Current backend may not support this.
 * Returns empty array for now.
 */
export async function getConversations(): Promise<Conversation[]> {
  // TODO: Backend endpoint may not exist yet
  return [];
}

/**
 * Delete conversation from backend (if supported)
 * DELETE /api/conversations/{id}
 */
export async function deleteConversation(_conversationId: string): Promise<void> {
  void _conversationId;
  return;
}

/**
 * Update conversation title (if supported)
 * PUT /api/conversations/{id}
 */
export async function updateConversationTitle(
  _conversationId: string,
  _title: string
): Promise<void> {
  void _conversationId;
  void _title;
  return;
}

// ============================================
// Extended Task API for Chat
// ============================================

/**
 * Create generation task and return full task data
 * Extended version that returns complete task info for chat integration
 */
export async function createGenerateTaskExtended(
  params: GenerateRequest
): Promise<CreateTaskData & { conversationId?: string }> {
  const result = await createGenerateTask(params);
  return result;
}

/**
 * Download file with progress callback (optional)
 */
export async function downloadFileWithProgress(
  filePath: string,
  downloadName?: string,
  _onProgress?: (progress: number) => void
): Promise<Blob> {
  void _onProgress;
  // Use existing downloadFile logic
  // Optionally add progress tracking
  return downloadFile(filePath, downloadName);
}

// ============================================
// Exports
// ============================================

export { API_BASE_URL };

// Re-export chat-related types for convenience
export type { Conversation, Message } from '@/types/chat';
