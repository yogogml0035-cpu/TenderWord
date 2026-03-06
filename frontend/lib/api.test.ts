import {
  ApiError,
  cancelTask,
  createGenerateTask,
  downloadFile,
  fetchTenderData,
  getTaskStatus,
  sendTaskHeartbeat,
  uploadFile,
} from '@/lib/api';
import type { GenerateRequest } from '@/types/api';

type FetchMock = jest.MockedFunction<typeof fetch>;

function mockFetchJson(value: unknown, options?: { ok?: boolean; status?: number }): FetchMock {
  const ok = options?.ok ?? true;
  const status = options?.status ?? 200;

  return jest.fn().mockResolvedValue({
    ok,
    status,
    json: async () => value,
  } as unknown as Response) as unknown as FetchMock;
}

function mockFetchBlob(value: Blob, options?: { ok?: boolean; status?: number }): FetchMock {
  const ok = options?.ok ?? true;
  const status = options?.status ?? 200;

  return jest.fn().mockResolvedValue({
    ok,
    status,
    blob: async () => value,
  } as unknown as Response) as unknown as FetchMock;
}

const validGenerateRequest: GenerateRequest = {
  form_type: 'xjcg_tender',
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
  file_paths: {
    tender_params: ['/uploads/params.xlsx'],
  },
  model: 'deepseek',
};

describe('API Client', () => {
  beforeEach(() => {
    globalThis.fetch = jest.fn() as unknown as typeof fetch;
  });

  describe('createGenerateTask', () => {
    it('should return task info on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { task_id: 'test-task-123', status: 'queued', queue_position: 1 },
        message: 'Task created',
        timestamp: new Date().toISOString(),
      });

      const result = await createGenerateTask(validGenerateRequest);
      expect(result.task_id).toBe('test-task-123');
      expect(result.status).toBe('queued');
      expect(result.queue_position).toBe(1);
    });

    it('should send correct request body', async () => {
      const fetchSpy = jest.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: { task_id: 'new-task-id', status: 'queued' },
          message: 'OK',
          timestamp: new Date().toISOString(),
        }),
      } as unknown as Response) as unknown as FetchMock;
      globalThis.fetch = fetchSpy;

      await createGenerateTask(validGenerateRequest);

      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [, init] = fetchSpy.mock.calls[0];
      const body = (init as RequestInit).body as string;
      expect(JSON.parse(body)).toEqual(validGenerateRequest);
    });

    it('should throw ApiError on API error response', async () => {
      globalThis.fetch = mockFetchJson(
        {
          success: false,
          error: { code: 'REQ_INVALID_PARAM', message: 'Invalid request parameters' },
          timestamp: new Date().toISOString(),
        },
        { ok: false, status: 400 }
      );

      await expect(createGenerateTask(validGenerateRequest)).rejects.toBeInstanceOf(ApiError);
      await expect(createGenerateTask(validGenerateRequest)).rejects.toMatchObject({
        status: 400,
        code: 'REQ_INVALID_PARAM',
      });
    });

    it('should throw on network error', async () => {
      globalThis.fetch = jest
        .fn()
        .mockRejectedValue(new Error('Network error')) as unknown as typeof fetch;
      await expect(createGenerateTask(validGenerateRequest)).rejects.toBeInstanceOf(ApiError);
      await expect(createGenerateTask(validGenerateRequest)).rejects.toMatchObject({
        code: 'NETWORK_ERROR',
        status: 0,
      });
    });
  });

  describe('downloadFile', () => {
    it('should return Blob on success', async () => {
      const blob = new Blob(['test'], { type: 'application/octet-stream' });
      globalThis.fetch = mockFetchBlob(blob, { ok: true, status: 200 });

      const result = await downloadFile('test-file.docx');
      expect(result).toBeInstanceOf(Blob);
      expect(result.type).toBe('application/octet-stream');
    });

    it('should encode file path in URL', async () => {
      const blob = new Blob(['test'], { type: 'application/octet-stream' });
      const fetchSpy = mockFetchBlob(blob, { ok: true, status: 200 });
      globalThis.fetch = fetchSpy;

      await downloadFile('path/with spaces/file.docx');

      const [url] = fetchSpy.mock.calls[0];
      expect(String(url)).toContain('path%2Fwith%20spaces%2Ffile.docx');
    });

    it('should include download_name when provided', async () => {
      const blob = new Blob(['test'], { type: 'application/octet-stream' });
      const fetchSpy = mockFetchBlob(blob, { ok: true, status: 200 });
      globalThis.fetch = fetchSpy;

      await downloadFile('test-file.docx', 'custom-name.docx');

      const [url] = fetchSpy.mock.calls[0];
      expect(String(url)).toContain('download_name=custom-name.docx');
    });

    it('should throw ApiError on non-ok response', async () => {
      globalThis.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 404,
      } as unknown as Response) as unknown as typeof fetch;
      await expect(downloadFile('missing.docx')).rejects.toBeInstanceOf(ApiError);
      await expect(downloadFile('missing.docx')).rejects.toMatchObject({ status: 404 });
    });
  });

  describe('fetchTenderData', () => {
    it('should return tender data on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { project_name: 'Test Project' },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await fetchTenderData('ZBGG-2024-001');
      expect(result.project_name).toBe('Test Project');
    });

    it('should encode tender_no in URL', async () => {
      const fetchSpy = mockFetchJson({
        success: true,
        data: { project_name: 'Test' },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });
      globalThis.fetch = fetchSpy;

      await fetchTenderData('ZB/2024-001');
      const [url] = fetchSpy.mock.calls[0];
      expect(String(url)).toContain('ZB%2F2024-001');
    });
  });

  describe('getTaskStatus', () => {
    it('should return task status on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: {
          task_id: 'test-task-123',
          status: 'running',
          created_at: new Date().toISOString(),
          progress: {
            completed_nodes: [],
            running_nodes: ['extract_tender_params'],
            current_node: 'extract_tender_params',
            completed_count: 1,
            total_nodes: 7,
            progress_percent: 14.3,
          },
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await getTaskStatus('test-task-123');
      expect(result.task_id).toBe('test-task-123');
      expect(result.status).toBe('running');
      expect(result.progress.progress_percent).toBe(14.3);
    });
  });

  describe('cancelTask', () => {
    it('should return cancel result on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        task_id: 'test-task-123',
        message: '任务已取消',
        was_running: true,
      });

      const result = await cancelTask('test-task-123');
      expect(result.task_id).toBe('test-task-123');
      expect(result.noop).toBeUndefined();
    });

    it('should treat TASK_CANNOT_CANCEL as non-fatal noop', async () => {
      globalThis.fetch = mockFetchJson(
        {
          detail: {
            success: false,
            error: { code: 'TASK_CANNOT_CANCEL', message: '任务已结束，无需取消' },
            timestamp: new Date().toISOString(),
          },
        },
        { ok: false, status: 409 }
      );

      const result = await cancelTask('test-task-123');
      expect(result.task_id).toBe('test-task-123');
      expect(result.noop).toBe(true);
    });
  });

  describe('sendTaskHeartbeat', () => {
    it('should return heartbeat status on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: {
          task_id: 'test-task-123',
          alive: true,
          status: 'running',
        },
        message: 'Heartbeat received',
        timestamp: new Date().toISOString(),
      });

      const result = await sendTaskHeartbeat('test-task-123');
      expect(result.task_id).toBe('test-task-123');
      expect(result.alive).toBe(true);
      expect(result.status).toBe('running');
    });
  });

  describe('uploadFile', () => {
    it('should return uploaded file info on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: {
          file_path: '/uploads/test.docx',
          file_name: 'test.docx',
          original_name: 'test.docx',
          size: 4,
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const file = new File(['test'], 'test.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const result = await uploadFile(file, 'clean_draft');
      expect(result.file_path).toBe('/uploads/test.docx');
    });

    it('should handle flat upload response without data wrapper', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        file_path: '/uploads/flat-test.docx',
        file_name: 'flat-test.docx',
        original_name: 'flat-test.docx',
        file_size: 4,
        content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        upload_time: new Date().toISOString(),
      });

      const file = new File(['test'], 'flat-test.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const result = await uploadFile(file, 'clean_draft');
      expect(result.file_path).toBe('/uploads/flat-test.docx');
    });
  });
});
