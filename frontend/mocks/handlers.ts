/**
 * MSW Handlers for API mocking
 * Mock handlers for TenderWord backend API
 */

import { http, HttpResponse, delay } from 'msw';
import type {
  GenerateRequest,
  CreateTaskData,
  ApiSuccessResponse,
  ApiErrorResponse,
} from '@/types/api';

const API_BASE_URL = 'http://localhost:8000';

// Sample success response for generate task
const createSuccessGenerateResponse = (
  overrides?: Partial<CreateTaskData>
): ApiSuccessResponse<CreateTaskData> => ({
  success: true,
  data: {
    task_id: 'test-task-123',
    status: 'queued',
    created_at: '2024-01-01T00:00:00Z',
    user_session_id: 'session-123',
    queue_position: 1,
    estimated_wait_seconds: 30,
    ...overrides,
  },
  message: 'Task created successfully',
  timestamp: '2024-01-01T00:00:00Z',
});

// Sample error response
const createErrorResponse = (code: string, message: string): ApiErrorResponse => ({
  success: false,
  error: {
    code,
    message,
    details: 'Additional error details here',
  },
  timestamp: '2024-01-01T00:00:00Z',
});

// Sample tender data
const sampleTenderData = {
  project_name: 'Test Project',
  project_number: 'ZBGG-2024-001',
  project_content: 'Test project content',
  bzj_rule: '保证金规则',
  buyer_name: 'Test Buyer',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-01-01',
  shell_end_date: '2024-01-31',
  submit_date: '2024-02-01',
  platform: 'Test Platform',
  service_fee: '1000',
};

export const handlers = [
  // POST /api/generate - Success
  http.post(`${API_BASE_URL}/api/generate`, async ({ request }) => {
    const body = (await request.json()) as GenerateRequest;

    // Validate required fields
    if (!body.form_type || !body.tender_data || !body.file_paths || !body.model) {
      return HttpResponse.json(
        createErrorResponse('REQ_MISSING_FIELD', 'Missing required fields'),
        { status: 400 }
      );
    }

    // Simulate network delay
    await delay(10);

    return HttpResponse.json(createSuccessGenerateResponse());
  }),

  // GET /api/tender/:tender_no - Success
  http.get(`${API_BASE_URL}/api/tender/:tenderNo`, async () => {
    await delay(10);
    return HttpResponse.json({
      success: true,
      data: sampleTenderData,
      message: 'Tender data fetched successfully',
      timestamp: '2024-01-01T00:00:00Z',
    });
  }),

  // GET /api/download/:filePath - Success (returns blob)
  http.get(`${API_BASE_URL}/api/download/:filePath`, async () => {
    await delay(10);
    // Create a mock blob response
    const blob = new Blob(['Mock file content'], { type: 'application/octet-stream' });
    return new HttpResponse(blob, {
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename="mock-file.docx"',
      },
    });
  }),

  // GET /api/tasks/:taskId - Success
  http.get(`${API_BASE_URL}/api/tasks/:taskId`, async ({ params }) => {
    await delay(10);
    return HttpResponse.json({
      success: true,
      data: {
        task_id: params.taskId,
        status: 'running',
        created_at: '2024-01-01T00:00:00Z',
        started_at: '2024-01-01T00:00:05Z',
        progress: {
          completed_nodes: ['prepare_template', 'extract_tender_params'],
          running_nodes: ['delete_tender_param'],
          completed_count: 2,
          total_nodes: 6,
          progress_percent: 33,
        },
      },
      message: 'Task status retrieved',
      timestamp: '2024-01-01T00:00:00Z',
    });
  }),

  // DELETE /api/tasks/:taskId - Success
  http.delete(`${API_BASE_URL}/api/tasks/:taskId`, async ({ params }) => {
    await delay(10);
    return HttpResponse.json({
      success: true,
      data: {
        task_id: params.taskId,
        status: 'cancelled',
        cancelled_at: '2024-01-01T00:00:00Z',
      },
      message: 'Task cancelled successfully',
      timestamp: '2024-01-01T00:00:00Z',
    });
  }),

  // POST /api/upload - Success
  http.post(`${API_BASE_URL}/api/upload`, async () => {
    await delay(10);
    return HttpResponse.json({
      success: true,
      data: {
        file_path: '/uploads/test-file.docx',
        file_name: 'test-file.docx',
        original_name: 'original-file.docx',
        size: 1024,
        upload_time: '2024-01-01T00:00:00Z',
      },
      message: 'File uploaded successfully',
      timestamp: '2024-01-01T00:00:00Z',
    });
  }),
];

// Error handlers for testing error scenarios
export const errorHandlers = {
  // 400 Bad Request
  badRequest: http.post(`${API_BASE_URL}/api/generate`, async () => {
    await delay(10);
    return HttpResponse.json(
      createErrorResponse('REQ_INVALID_PARAM', 'Invalid request parameters'),
      { status: 400 }
    );
  }),

  // 500 Server Error
  serverError: http.post(`${API_BASE_URL}/api/generate`, async () => {
    await delay(10);
    return HttpResponse.json(createErrorResponse('SYS_INTERNAL_ERROR', 'Internal server error'), {
      status: 500,
    });
  }),

  // Network Error (by not returning a response)
  networkError: http.post(`${API_BASE_URL}/api/generate`, () => {
    return HttpResponse.error();
  }),

  // 404 Not Found for download
  downloadNotFound: http.get(`${API_BASE_URL}/api/download/:filePath`, async () => {
    await delay(10);
    return HttpResponse.json(createErrorResponse('FILE_NOT_FOUND', 'File not found'), {
      status: 404,
    });
  }),

  // 500 for download
  downloadError: http.get(`${API_BASE_URL}/api/download/:filePath`, async () => {
    await delay(10);
    return new HttpResponse(null, { status: 500 });
  }),
};

// Task not found handler
export const taskNotFoundHandler = http.get(`${API_BASE_URL}/api/tasks/:taskId`, async () => {
  await delay(10);
  return HttpResponse.json(createErrorResponse('TASK_NOT_FOUND', 'Task not found'), {
    status: 404,
  });
});
