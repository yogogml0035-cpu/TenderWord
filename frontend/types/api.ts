/**
 * API Types - Based on docs/api-contract.md
 * API 类型定义 - 基于 API 契约文档
 */

// ============================================
// Task Status
// ============================================

export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export type TaskKind = 'generate' | 'rewrite';

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

export interface TenderTypeInfo {
  tender_lx: number;
  purchase_method: number;
  fund_lx: number;
}

export interface TenderLookupResponse {
  data: TenderData;
  type: TenderTypeInfo | null;
}

// ============================================
// Template Candidate Types
// ============================================

export interface TemplateCandidate {
  tenderno: string;
  tendername: string;
  tname: string;
  bm: string;
  hytype: string;
  tendertype: string;
  hwlx: string;
  yxj: string;
  zbr: string;
  xbr: string;
  year?: number | null;
  fsg?: string | null;
  shener?: string | null;
  selectable: boolean;
  blocked_reason?: string | null;
}

export interface TemplateCandidateListResponse {
  candidates: TemplateCandidate[];
}

export interface TemplateCandidateSelectPayload {
  tendername: string;
  year?: number | null;
  fsg?: string | null;
  shener?: string | null;
}

export interface TemplateCandidateSelectRequest {
  candidate: TemplateCandidateSelectPayload;
}

export type TemplateSelectedFile = UploadedFile;

export interface TemplateSelectedFiles {
  clean_draft?: TemplateSelectedFile | null;
  origin_tender?: TemplateSelectedFile | null;
}

export interface TemplateSelectFailure {
  slot: 'clean_draft' | 'origin_tender';
  message: string;
}

export interface TemplateSelectResponse {
  selected_files: TemplateSelectedFiles;
  failed_slots: TemplateSelectFailure[];
  partial_success: boolean;
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
  origin_tender?: string;
  clean_draft?: string;
  tender_params: string[];
}

export interface InsertionConfig {
  before_text?: string;
  after_text?: string;
}

export interface GenerateRequest {
  form_type: 'xjcg_tender' | 'gngk_tender';
  tender_data: TenderData;
  file_paths: FilesConfig;
  insertion_config?: InsertionConfig;
  conversation_id?: string;
  model: 'deepseek' | 'qwen' | 'doubao';
}

// ============================================
// Task Progress Types
// ============================================

export interface TaskProgress {
  completed_nodes: string[];
  running_nodes: string[];
  current_node?: string;
  current_node_display?: string;
  progress_text?: string;
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
  task_kind: TaskKind;
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
  current_running_progress?: TaskProgress | null;
  result?: TaskResult | string;
  error?: string;
}

export type TaskResponse = ApiResponse<TaskData>;

export interface TaskListItem {
  task_id: string;
  task_kind: TaskKind;
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  elapsed_time?: number;
  user_session_id?: string;
  queue_position?: number;
  waiting_count?: number;
  progress: TaskProgress;
  current_running_progress?: TaskProgress | null;
  result?: TaskResult | string;
  error?: string;
}

export interface TaskListData {
  success: boolean;
  total: number;
  tasks: TaskListItem[];
  message?: string;
}

export type TaskListResponse = TaskListData;

export interface CancelTaskData {
  success: boolean;
  task_id: string;
  message: string;
  was_running: boolean;
  noop?: boolean;
}

export type CancelTaskResponse = ApiResponse<CancelTaskData>;

export interface TaskHeartbeatData {
  task_id: string;
  alive: boolean;
  task_kind: TaskKind;
  status?: TaskStatus;
}

export type TaskHeartbeatResponse = ApiResponse<TaskHeartbeatData>;

// ============================================
// Create Task Response
// ============================================

export interface CreateTaskData {
  task_id: string;
  task_kind: TaskKind;
  status?: TaskStatus;
  created_at?: string;
  user_session_id?: string;
  queue_position?: number;
  waiting_count?: number;
  estimated_wait_seconds?: number;
}

export type CreateTaskResponse = ApiResponse<CreateTaskData>;

export interface UserStreamMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface UserStreamRequest {
  conversation_id: string;
  model: 'deepseek' | 'qwen' | 'doubao';
  messages: UserStreamMessage[];
}

export interface UserStreamChunkEvent {
  event: 'chunk';
  data: {
    content: string;
  };
}

export interface UserStreamDoneEvent {
  event: 'done';
  data: {
    content: string;
  };
}

export interface UserStreamErrorEvent {
  event: 'error';
  data: {
    code?: string;
    message: string;
  };
}

export type UserStreamRoute = 'reply' | 'rewrite';

export interface UserStreamRouteEvent {
  event: 'route';
  data: {
    route: UserStreamRoute;
  };
}

export interface UserStreamTaskAcceptedEvent {
  event: 'task_accepted';
  data: {
    task_id: string;
    task_kind: TaskKind;
    status?: TaskStatus;
    queue_position?: number;
    waiting_count?: number;
  };
}

export type UserStreamEvent =
  | UserStreamRouteEvent
  | UserStreamTaskAcceptedEvent
  | UserStreamChunkEvent
  | UserStreamDoneEvent
  | UserStreamErrorEvent;

export interface ConversationHeartbeatData {
  conversation_id: string;
  alive: boolean;
  instance_id: string;
  server_time: string;
  rewrite_available: boolean;
}

export type ConversationHeartbeatResponse = ApiResponse<ConversationHeartbeatData>;

// ============================================
// SSE Event Types
// ============================================

export interface SSEConnectedEvent {
  task_id: string;
  message: string;
}

export interface SSELogEvent {
  task_id?: string;
  timestamp: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  message: string;
  node?: string;
}

export interface SSELLMEvent {
  timestamp: string;
  task_id?: string;
  node?: string;
  content: string;
  content_mode?: 'snapshot' | 'chunk';
  is_complete: boolean;
  token_count?: number;
}

export interface SSEProgressEvent {
  timestamp: string;
  task_id: string;
  task_kind: TaskKind;
  status: TaskStatus | 'running';
  progress_text: string;
  current_node?: string;
  node?: string;
  completed_count: number;
  total_nodes: number;
  progress_percent: number;
  current_node_display?: string;
}

export interface SSEStatusEvent {
  timestamp: string;
  status: TaskStatus;
  message?: string;
  result?: TaskResult;
}

export interface SSEErrorEvent {
  timestamp: string;
  task_id: string;
  task_kind: TaskKind;
  error: string;
  node?: string;
  is_fatal: boolean;
}

export interface SSEDoneEvent {
  timestamp: string;
  task_id: string;
  task_kind: TaskKind;
  success: boolean;
  message: string;
  output_file?: string;
  download_url?: string;
  processing_time?: number;
}

export interface SSEHeartbeatEvent {
  timestamp: string;
  task_id: string;
}

export type SSEEventType =
  | 'connected'
  | 'log'
  | 'llm'
  | 'progress'
  | 'status'
  | 'error'
  | 'done'
  | 'heartbeat';

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

  // Rewrite / User Stream
  REWRITE_TARGET_NOT_RESOLVED: 'REWRITE_TARGET_NOT_RESOLVED',
  CONVERSATION_INSTANCE_RESET: 'CONVERSATION_INSTANCE_RESET',
} as const;

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];

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
