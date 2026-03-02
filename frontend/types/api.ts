/**
 * API Types - Based on docs/api-contract.md
 * API 类型定义 - 基于 API 契约文档
 */

// ============================================
// Task Status
// ============================================

export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

// ============================================
// Tender Data Types
// ============================================

export interface TenderData {
  project_name: string;
  project_number: string;
  project_content: string;
  bzj_rule: string;
  buyer_name: string;
  project_zbr_xbr: string;
  zbr_xbr_tel: string;
  zbr_pinyin: string;
  shell_start_date: string;
  shell_end_date: string;
  submit_date: string;
  platform: string;
  service_fee: string;
}

// ============================================
// File Upload Types
// ============================================

export interface UploadedFile {
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time?: string;
}

export type FileType = 'clean_draft' | 'origin_tender' | 'params' | 'qualification';

// ============================================
// Generate Task Types
// ============================================

export interface FilesConfig {
  origin_tender_path?: string;
  clean_draft_path?: string;
  tender_param_paths: string[];
}

export interface InsertionConfig {
  before_text?: string;
  after_text?: string;
}

export interface GenerateRequest {
  tender_no: string;
  tender_data: TenderData;
  files: FilesConfig;
  model: 'deepseek' | 'qwen' | 'doubao';
  insertion_config?: InsertionConfig;
}

// ============================================
// Task Progress Types
// ============================================

export interface TaskProgress {
  completed_nodes: string[];
  running_nodes: string[];
  current_node?: string;
  completed_count: number;
  total_nodes: number;
  progress_percent: number;
}

export interface TaskResult {
  output_file: string;
  file_name: string;
  file_size: number;
  model_used: string;
  total_time_seconds: number;
}

// ============================================
// API Response Types
// ============================================

export interface ApiSuccessResponse<T> {
  success: true;
  data: T;
  message: string;
  timestamp: string;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: string;
  };
  timestamp: string;
}

export type ApiResponse<T> = ApiSuccessResponse<T> | ApiErrorResponse;

// ============================================
// Tender API Response
// ============================================

export type TenderDataResponse = ApiResponse<TenderData>;

// ============================================
// Upload API Response
// ============================================

export type UploadResponse = ApiResponse<UploadedFile>;

export interface MultipleUploadResult {
  uploaded_files: UploadedFile[];
  total_count: number;
  success_count: number;
  failed_count: number;
}

export type UploadMultipleResponse = ApiResponse<MultipleUploadResult>;

// ============================================
// Task API Response
// ============================================

export interface TaskData {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  elapsed_seconds?: number;
  user_session_id?: string;
  queue_position?: number;
  estimated_wait_seconds?: number;
  waiting_count?: number;
  progress: TaskProgress;
  result?: TaskResult;
}

export type TaskResponse = ApiResponse<TaskData>;

export interface TaskListItem {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  user_session_id?: string;
  queue_position?: number;
  progress: TaskProgress;
}

export interface TaskListData {
  tasks: TaskListItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  summary: {
    total: number;
    queued: number;
    running: number;
    completed: number;
    failed: number;
    cancelled: number;
  };
}

export type TaskListResponse = ApiResponse<TaskListData>;

export interface CancelTaskData {
  task_id: string;
  status: TaskStatus;
  cancelled_at: string;
}

export type CancelTaskResponse = ApiResponse<CancelTaskData>;

// ============================================
// Create Task Response
// ============================================

export interface CreateTaskData {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  user_session_id: string;
  queue_position: number;
  estimated_wait_seconds: number;
}

export type CreateTaskResponse = ApiResponse<CreateTaskData>;

// ============================================
// SSE Event Types
// ============================================

export interface SSEConnectedEvent {
  task_id: string;
  message: string;
}

export interface SSELogEvent {
  timestamp: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  message: string;
  node?: string;
}

export interface SSELLMEvent {
  timestamp: string;
  node: string;
  content: string;
  is_complete: boolean;
  token_count?: number;
}

export interface SSEProgressEvent {
  timestamp: string;
  node: string;
  completed_count: number;
  total_nodes: number;
  progress_percent: number;
  current_node_display: string;
}

export interface SSEStatusEvent {
  timestamp: string;
  status: TaskStatus;
  message?: string;
  result?: TaskResult;
}

export interface SSEErrorEvent {
  timestamp: string;
  error_code: string;
  message: string;
  details?: string;
}

export interface SSEDoneEvent {
  timestamp: string;
  task_id: string;
  status: TaskStatus;
  total_time_seconds: number;
}

export interface SSEHeartbeatEvent {
  timestamp: string;
  task_id: string;
}

export type SSEEventType = 'connected' | 'log' | 'llm' | 'progress' | 'status' | 'error' | 'done' | 'heartbeat';

// ============================================
// Error Codes
// ============================================

export const ErrorCodes = {
  // System
  SYS_INTERNAL_ERROR: 'SYS_INTERNAL_ERROR',
  SYS_SERVICE_UNAVAILABLE: 'SYS_SERVICE_UNAVAILABLE',
  SYS_TIMEOUT: 'SYS_TIMEOUT',

  // Request
  REQ_INVALID_PARAM: 'REQ_INVALID_PARAM',
  REQ_MISSING_FIELD: 'REQ_MISSING_FIELD',
  REQ_INVALID_JSON: 'REQ_INVALID_JSON',
  REQ_UNSUPPORTED_MEDIA_TYPE: 'REQ_UNSUPPORTED_MEDIA_TYPE',

  // Task
  TASK_NOT_FOUND: 'TASK_NOT_FOUND',
  TASK_CANNOT_CANCEL: 'TASK_CANNOT_CANCEL',
  TASK_ALREADY_EXISTS: 'TASK_ALREADY_EXISTS',

  // File
  FILE_NOT_FOUND: 'FILE_NOT_FOUND',
  FILE_TOO_LARGE: 'FILE_TOO_LARGE',
  FILE_INVALID_TYPE: 'FILE_INVALID_TYPE',
  FILE_UPLOAD_FAILED: 'FILE_UPLOAD_FAILED',
  FILE_ACCESS_DENIED: 'FILE_ACCESS_DENIED',

  // Tender
  TENDER_NOT_FOUND: 'TENDER_NOT_FOUND',
  TENDER_FETCH_FAILED: 'TENDER_FETCH_FAILED',
  TENDER_INVALID_DATA: 'TENDER_INVALID_DATA',

  // LLM
  LLM_TIMEOUT: 'LLM_TIMEOUT',
  LLM_RATE_LIMIT: 'LLM_RATE_LIMIT',
  LLM_SERVICE_ERROR: 'LLM_SERVICE_ERROR',
  LLM_INVALID_MODEL: 'LLM_INVALID_MODEL',
} as const;

export type ErrorCode = typeof ErrorCodes[keyof typeof ErrorCodes];

// ============================================
// Node Display Names
// ============================================

export const NodeDisplayNames: Record<string, string> = {
  prepare_template: '复制原始模板文件',
  extract_tender_params: '提取原始采购需求',
  delete_tender_param: '删除原始采购需求',
  get_replacements: '获取原始项目信息',
  replace_content: '替换最新项目信息',
  generate_polished_text: 'AI生成采购需求',
  update_word: '生成招标文件',
};
