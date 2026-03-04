/**
 * API Integration Tests
 * Tests for lib/api.ts using MSW (Mock Service Worker)
 */

import { server, errorHandlers } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import {
  createGenerateTask,
  downloadFile,
  fetchTenderData,
  getTaskStatus,
  cancelTask,
  uploadFile,
  ApiError,
} from '@/lib/api';
import type { GenerateRequest } from '@/types/api';

const API_BASE_URL = 'http://localhost:8000';

// Sample valid request data
const validGenerateRequest: GenerateRequest = {
  tender_no: 'ZBGG-2024-001',
  tender_data: {
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
  },
  files: {
    tender_param_paths: ['/uploads/params.xlsx'],
  },
  model: 'deepseek',
};

describe('API Client', () => {
  describe('createGenerateTask', () => {
    describe('success scenario', () => {
      it('should return task_id on successful task creation', async () => {
        const result = await createGenerateTask(validGenerateRequest);

        expect(result).toHaveProperty('task_id');
        expect(result.task_id).toBe('test-task-123');
        expect(result.status).toBe('queued');
        expect(result.queue_position).toBe(1);
      });

      it('should send correct request body', async () => {
        let requestBody: GenerateRequest | null = null;

        server.use(
          http.post(`${API_BASE_URL}/api/generate`, async ({ request }) => {
            requestBody = (await request.json()) as GenerateRequest;
            return HttpResponse.json({
              success: true,
              data: { task_id: 'new-task-id', status: 'queued' },
              message: 'Task created',
              timestamp: new Date().toISOString(),
            });
          })
        );

        await createGenerateTask(validGenerateRequest);

        expect(requestBody).toEqual(validGenerateRequest);
      });
    });

    describe('400 error (validation failure)', () => {
      it('should throw ApiError with status 400 for invalid params', async () => {
        server.use(errorHandlers.badRequest);

        await expect(createGenerateTask(validGenerateRequest)).rejects.toThrow(ApiError);

        try {
          await createGenerateTask(validGenerateRequest);
        } catch (error) {
          expect(error).toBeInstanceOf(ApiError);
          expect((error as ApiError).status).toBe(400);
          expect((error as ApiError).code).toBe('REQ_INVALID_PARAM');
        }
      });

      it('should include error message from response', async () => {
        server.use(errorHandlers.badRequest);

        try {
          await createGenerateTask(validGenerateRequest);
          fail('Should have thrown an error');
        } catch (error) {
          expect(error).toBeInstanceOf(ApiError);
          expect((error as ApiError).message).toBe('Invalid request parameters');
        }
      });
    });

    describe('500 error (server error)', () => {
      it('should throw ApiError with status 500 for server errors', async () => {
        server.use(errorHandlers.serverError);

        await expect(createGenerateTask(validGenerateRequest)).rejects.toThrow(ApiError);

        try {
          await createGenerateTask(validGenerateRequest);
        } catch (error) {
          expect(error).toBeInstanceOf(ApiError);
          expect((error as ApiError).status).toBe(500);
          expect((error as ApiError).code).toBe('SYS_INTERNAL_ERROR');
        }
      });
    });

    describe('network error', () => {
      it('should throw error for network failures', async () => {
        server.use(errorHandlers.networkError);

        await expect(createGenerateTask(validGenerateRequest)).rejects.toThrow();
      });
    });
  });

  describe('downloadFile', () => {
    describe('success scenario', () => {
      it('should return Blob on successful download', async () => {
        const result = await downloadFile('test-file.docx');

        expect(result).toBeInstanceOf(Blob);
        expect(result.type).toBe('application/octet-stream');
      });

      it('should encode file path in URL', async () => {
        let requestedUrl = '';

        server.use(
          http.get(`${API_BASE_URL}/api/download/:filePath`, ({ request }) => {
            requestedUrl = request.url;
            return new HttpResponse(new Blob(['test']), {
              headers: { 'Content-Type': 'application/octet-stream' },
            });
          })
        );

        await downloadFile('path/with spaces/file.docx');

        expect(requestedUrl).toContain('path%2Fwith%20spaces%2Ffile.docx');
      });

      it('should include download_name parameter when provided', async () => {
        let requestedUrl = '';

        server.use(
          http.get(`${API_BASE_URL}/api/download/:filePath`, ({ request }) => {
            requestedUrl = request.url;
            return new HttpResponse(new Blob(['test']), {
              headers: { 'Content-Type': 'application/octet-stream' },
            });
          })
        );

        await downloadFile('test-file.docx', 'custom-name.docx');

        expect(requestedUrl).toContain('download_name=custom-name.docx');
      });
    });

    describe('error scenarios', () => {
      it('should throw ApiError for 404 not found', async () => {
        server.use(errorHandlers.downloadNotFound);

        await expect(downloadFile('nonexistent.docx')).rejects.toThrow(ApiError);

        try {
          await downloadFile('nonexistent.docx');
        } catch (error) {
          expect(error).toBeInstanceOf(ApiError);
          expect((error as ApiError).status).toBe(404);
        }
      });

      it('should throw ApiError for 500 server error', async () => {
        server.use(errorHandlers.downloadError);

        await expect(downloadFile('error.docx')).rejects.toThrow(ApiError);

        try {
          await downloadFile('error.docx');
        } catch (error) {
          expect(error).toBeInstanceOf(ApiError);
          expect((error as ApiError).status).toBe(500);
        }
      });
    });
  });

  describe('fetchTenderData', () => {
    it('should return tender data for valid tender_no', async () => {
      const result = await fetchTenderData('ZBGG-2024-001');

      expect(result).toHaveProperty('project_name');
      expect(result.project_name).toBe('Test Project');
    });

    it('should encode tender_no in URL', async () => {
      let requestedUrl = '';

      server.use(
        http.get(`${API_BASE_URL}/api/tender/:tenderNo`, ({ request }) => {
          requestedUrl = request.url;
          return HttpResponse.json({
            success: true,
            data: { project_name: 'Test' },
            message: 'OK',
            timestamp: new Date().toISOString(),
          });
        })
      );

      await fetchTenderData('ZB/2024-001');

      expect(requestedUrl).toContain('ZB%2F2024-001');
    });
  });

  describe('getTaskStatus', () => {
    it('should return task status for valid task_id', async () => {
      const result = await getTaskStatus('test-task-123');

      expect(result).toHaveProperty('task_id');
      expect(result).toHaveProperty('status');
      expect(result).toHaveProperty('progress');
    });
  });

  describe('cancelTask', () => {
    it('should return cancelled task data', async () => {
      const result = await cancelTask('test-task-123');

      expect(result).toHaveProperty('task_id');
      expect(result.status).toBe('cancelled');
      expect(result).toHaveProperty('cancelled_at');
    });
  });

  describe('uploadFile', () => {
    it('should return uploaded file data', async () => {
      const file = new File(['test content'], 'test.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });

      const result = await uploadFile(file);

      expect(result).toHaveProperty('file_path');
      expect(result).toHaveProperty('file_name');
      expect(result).toHaveProperty('original_name');
    });

    it('should include file_type when provided', async () => {
      let requestBody: FormData | null = null;

      server.use(
        http.post(`${API_BASE_URL}/api/upload`, async ({ request }) => {
          requestBody = (await request.formData()) as FormData;
          return HttpResponse.json({
            success: true,
            data: { file_path: '/uploads/test.docx' },
            message: 'OK',
            timestamp: new Date().toISOString(),
          });
        })
      );

      const file = new File(['test'], 'test.docx');
      await uploadFile(file, 'clean_draft');

      // FormData values can be checked
      expect(((requestBody as unknown) as FormData).get('file_type')).toBe('clean_draft');
    });
  });
});

describe('ApiError', () => {
  it('should create ApiError with default values', () => {
    const error = new ApiError('Test error');

    expect(error.message).toBe('Test error');
    expect(error.code).toBe('UNKNOWN_ERROR');
    expect(error.status).toBe(500);
    expect(error.name).toBe('ApiError');
  });

  it('should create ApiError with custom values', () => {
    const error = new ApiError('Not found', 'FILE_NOT_FOUND', 404);

    expect(error.message).toBe('Not found');
    expect(error.code).toBe('FILE_NOT_FOUND');
    expect(error.status).toBe(404);
  });
});
