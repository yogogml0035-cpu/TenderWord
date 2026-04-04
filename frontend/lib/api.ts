/**
 * API Client for TenderWord Backend
 * Based on docs/api-contract.md
 *
 * 使用 fetch API 实现的 API 客户端
 */

import type {
  TenderData,
  TenderLookupResponse,
  TenderTypeInfo,
  TemplateCandidateListResponse,
  TemplateCandidateSelectRequest,
  TemplateSelectResponse,
  UploadedFile,
  MultipleUploadResult,
  TaskData,
  TaskHeartbeatData,
  TaskListData,
  CancelTaskData,
  CreateTaskData,
  EditTaskRequest,
  GenerateRequest,
  ConversationHeartbeatData,
  ApiSuccessResponse,
  FileType,
  TaskKind,
  TaskStatus,
  UserStreamEvent,
  UserStreamRequest,
} from '@/types/api';
import type { Conversation } from '@/types/chat';
import { resolveApiBaseUrl } from '@/lib/apiBaseUrl';

// ============================================
// Configuration
// ============================================

const API_BASE_URL = resolveApiBaseUrl();

type JsonRecord = Record<string, unknown>;

type StreamEventParser<TEvent> = (payload: unknown) => TEvent | null;

interface StreamNdjsonOptions<TEvent> extends Omit<RequestInit, 'body'> {
  endpoint: string;
  body?: unknown;
  onEvent?: (event: TEvent) => void | Promise<void>;
  parseEvent: StreamEventParser<TEvent>;
  defaultErrorMessage?: string;
  defaultErrorCode?: string;
  protocolErrorMessage?: string;
  protocolErrorCode?: string;
  noBodyMessage?: string;
}

// ============================================
// Helper Functions
// ============================================

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError';
}

function extractErrorInfo(payload: unknown): {
  explicitFailure: boolean;
  errorMessage?: string;
  errorCode?: string;
} {
  const payloadRecord = isRecord(payload) ? payload : {};
  const nestedDetail = isRecord(payloadRecord.detail) ? payloadRecord.detail : {};
  const errorObj =
    (isRecord(payloadRecord.error) ? payloadRecord.error : undefined) ||
    (isRecord(nestedDetail.error) ? nestedDetail.error : undefined);

  return {
    explicitFailure: payloadRecord.success === false || nestedDetail.success === false,
    errorMessage: typeof errorObj?.message === 'string' ? errorObj.message : undefined,
    errorCode: typeof errorObj?.code === 'string' ? errorObj.code : undefined,
  };
}

function buildApiError(
  payload: unknown,
  status: number,
  fallbackMessage: string,
  fallbackCode: string
): ApiError {
  const errorInfo = extractErrorInfo(payload);
  return new ApiError(
    errorInfo.errorMessage || fallbackMessage,
    errorInfo.errorCode || fallbackCode,
    status
  );
}

async function parseJsonSafely(response: Response): Promise<unknown | undefined> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function normalizeRequestConfig(options: RequestInit = {}): RequestInit {
  return {
    headers: {
      ...(!(options.body instanceof FormData) && { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    ...options,
  };
}

function serializeRequestBody(body: unknown): RequestInit['body'] | undefined {
  if (body === undefined) {
    return undefined;
  }
  if (body === null) {
    return null;
  }
  if (
    typeof body === 'string' ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body) ||
    (typeof ReadableStream !== 'undefined' && body instanceof ReadableStream)
  ) {
    return body as RequestInit['body'];
  }
  return JSON.stringify(body);
}

function createStreamRequestConfig(
  options: Omit<
    StreamNdjsonOptions<unknown>,
    | 'endpoint'
    | 'parseEvent'
    | 'onEvent'
    | 'defaultErrorMessage'
    | 'defaultErrorCode'
    | 'protocolErrorMessage'
    | 'protocolErrorCode'
    | 'noBodyMessage'
  >
) {
  const serializedBody = serializeRequestBody(options.body);
  const headers = new Headers(options.headers);

  if (
    serializedBody !== undefined &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }

  return {
    ...options,
    headers,
    body: serializedBody,
  } satisfies RequestInit;
}

function parseUserStreamEvent(payload: unknown): UserStreamEvent | null {
  if (!isRecord(payload) || typeof payload.event !== 'string' || !('data' in payload) || !isRecord(payload.data)) {
    return null;
  }

  switch (payload.event) {
    case 'route': {
      const route = payload.data.route;
      if (route !== 'reply' && route !== 'rewrite') {
        return null;
      }
      return {
        event: 'route',
        data: { route },
      };
    }
    case 'task_accepted': {
      const taskKind = payload.data.task_kind;
      const taskId = payload.data.task_id;
      if (taskKind !== 'generate' && taskKind !== 'rewrite' && taskKind !== 'edit') {
        return null;
      }
      if (typeof taskId !== 'string' || !taskId) {
        return null;
      }

      const status = payload.data.status;
      const taskStatus =
        status === 'queued' ||
        status === 'running' ||
        status === 'completed' ||
        status === 'failed' ||
        status === 'cancelled'
          ? status
          : undefined;

      return {
        event: 'task_accepted',
        data: {
          task_id: taskId,
          task_kind: taskKind as TaskKind,
          status: taskStatus as TaskStatus | undefined,
          queue_position:
            typeof payload.data.queue_position === 'number' ? payload.data.queue_position : undefined,
          waiting_count:
            typeof payload.data.waiting_count === 'number' ? payload.data.waiting_count : undefined,
        },
      };
    }
    case 'chunk':
    case 'done':
      return {
        event: payload.event,
        data: {
          content: typeof payload.data.content === 'string' ? payload.data.content : '',
        },
      };
    case 'error':
      return {
        event: 'error',
        data: {
          code: typeof payload.data.code === 'string' ? payload.data.code : undefined,
          message: typeof payload.data.message === 'string' ? payload.data.message : '',
        },
      };
    default:
      return null;
  }
}

/**
 * Generic API request function with error handling
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const config = normalizeRequestConfig(options);

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
  const { explicitFailure } = extractErrorInfo(data);

  if (!response.ok || explicitFailure) {
    throw buildApiError(data, response.status, `HTTP error! status: ${response.status}`, 'UNKNOWN_ERROR');
  }

  // Prefer wrapped success payload: { success: true, data: ... }
  const payload = (data ?? {}) as Record<string, unknown>;
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

export async function streamNdjson<TEvent>({
  endpoint,
  onEvent,
  parseEvent,
  defaultErrorMessage = '流式请求失败',
  defaultErrorCode = 'STREAM_REQUEST_ERROR',
  protocolErrorMessage = '流式响应协议错误',
  protocolErrorCode = 'STREAM_PROTOCOL_ERROR',
  noBodyMessage = '流式响应不可用',
  ...options
}: StreamNdjsonOptions<TEvent>): Promise<void> {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = createStreamRequestConfig(options);

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError(
      `Network request failed: ${endpoint}. Please check backend availability and CORS configuration.`,
      'NETWORK_ERROR',
      0
    );
  }

  if (!response.ok) {
    const payload = await parseJsonSafely(response);
    throw buildApiError(payload, response.status, defaultErrorMessage, defaultErrorCode);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError(noBodyMessage, defaultErrorCode, response.status || 500);
  }

  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const dispatchLine = async (rawLine: string) => {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      return;
    }

    let parsedPayload: unknown;
    try {
      parsedPayload = JSON.parse(trimmed);
    } catch {
      throw new ApiError(protocolErrorMessage, protocolErrorCode, response.status || 500);
    }

    const event = parseEvent(parsedPayload);
    if (!event) {
      return;
    }

    await onEvent?.(event);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      await dispatchLine(line);
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    await dispatchLine(buffer);
  }
}

export async function streamUserMessage(
  payload: UserStreamRequest,
  options: {
    signal?: AbortSignal;
    onEvent?: (event: UserStreamEvent) => void | Promise<void>;
  } = {}
): Promise<void> {
  return streamNdjson<UserStreamEvent>({
    endpoint: '/api/user/stream',
    method: 'POST',
    body: payload,
    signal: options.signal,
    onEvent: options.onEvent,
    parseEvent: parseUserStreamEvent,
    defaultErrorMessage: '聊天请求失败',
    defaultErrorCode: 'CHAT_STREAM_ERROR',
    protocolErrorMessage: '聊天流协议错误',
    protocolErrorCode: 'CHAT_STREAM_PROTOCOL_ERROR',
    noBodyMessage: '聊天流不可用',
  });
}

// ============================================
// Tender API
// ============================================

/**
 * 获取招标数据
 * GET /api/tender/{tender_no}
 */
function parseTenderTypeInfo(payload: unknown): TenderTypeInfo | null {
  if (!isRecord(payload)) {
    return null;
  }

  const tender_lx = payload.tender_lx;
  const purchase_method = payload.purchase_method;
  const fund_lx = payload.fund_lx;

  if (
    (tender_lx !== 0 && tender_lx !== 1) ||
    typeof purchase_method !== 'number' ||
    (fund_lx !== 0 && fund_lx !== 1)
  ) {
    return null;
  }

  return {
    tender_lx,
    purchase_method,
    fund_lx,
  };
}

function isGjgkTenderTypeInfo(tenderTypeInfo: TenderTypeInfo | null): boolean {
  return Boolean(
    tenderTypeInfo &&
      tenderTypeInfo.purchase_method === 0
  );
}

function stripTenderNumberPrefix(value: string | null | undefined): string | null {
  const normalized = String(value || '').replace(/\s+/g, '').trim();
  if (!normalized) {
    return null;
  }

  const prefixedMatch = normalized.match(/^\d+-([A-Za-z0-9]+)$/);
  if (prefixedMatch) {
    return prefixedMatch[1];
  }

  return /^[A-Za-z0-9]+$/.test(normalized) ? normalized : null;
}

function normalizeGjgkProjectNumber(
  projectNumber: string | null | undefined,
  tenderNo: string
): string {
  return (
    stripTenderNumberPrefix(tenderNo) ||
    stripTenderNumberPrefix(projectNumber) ||
    String(projectNumber || '')
  );
}

export async function fetchTenderDataWithType(tenderNo: string): Promise<TenderLookupResponse> {
  const url = `${API_BASE_URL}/api/tender/${encodeURIComponent(tenderNo)}`;

  let response: Response;
  try {
    response = await fetch(url, normalizeRequestConfig({ method: 'GET' }));
  } catch {
    throw new ApiError(
      `Network request failed: /api/tender/${encodeURIComponent(tenderNo)}. Please check backend availability and CORS configuration.`,
      'NETWORK_ERROR',
      0
    );
  }

  const data: unknown = await response.json();
  const { explicitFailure } = extractErrorInfo(data);

  if (!response.ok || explicitFailure) {
    throw buildApiError(data, response.status, `HTTP error! status: ${response.status}`, 'UNKNOWN_ERROR');
  }

  const payload = isRecord(data) ? data : {};
  const tenderTypeInfo = parseTenderTypeInfo(payload.type);
  const tenderData = 'data' in payload ? (payload.data as TenderData) : (data as TenderData);
  const normalizedTenderData =
    isGjgkTenderTypeInfo(tenderTypeInfo)
      ? {
          ...tenderData,
          project_number: normalizeGjgkProjectNumber(tenderData.project_number, tenderNo),
        }
      : tenderData;

  return {
    data: normalizedTenderData,
    type: tenderTypeInfo,
  };
}

export async function fetchTenderData(tenderNo: string): Promise<TenderData> {
  const result = await fetchTenderDataWithType(tenderNo);
  return result.data;
}

export async function fetchTemplateCandidates(params: {
  tenderno: string;
  project_name?: string | null;
}): Promise<TemplateCandidateListResponse> {
  const query = new URLSearchParams({
    tenderno: params.tenderno,
  });
  const projectName = params.project_name?.trim();
  if (projectName) {
    query.append('project_name', projectName);
  }
  return request<TemplateCandidateListResponse>(`/api/template-candidates?${query.toString()}`);
}

export async function selectTemplateCandidate(
  payload: TemplateCandidateSelectRequest
): Promise<TemplateSelectResponse> {
  return request<TemplateSelectResponse>('/api/template-candidates/select', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getTemplateCandidateDownloadUrl(fileUrl: string, downloadName?: string): string {
  const query = new URLSearchParams();
  query.append('file_url', fileUrl);
  if (downloadName) {
    query.append('download_name', downloadName);
  }
  return `${API_BASE_URL}/api/template-candidates/download?${query.toString()}`;
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

export async function createEditTask(params: EditTaskRequest): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/edit', {
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
