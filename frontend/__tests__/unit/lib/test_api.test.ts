import {
  ApiError,
  cancelTask,
  createEditTask,
  createGenerateTask,
  downloadFile,
  fetchTemplateCandidates,
  fetchTenderData,
  fetchTenderDataWithType,
  getTemplateCandidateDownloadUrl,
  getTaskStatus,
  selectTemplateCandidate,
  sendTaskHeartbeat,
  streamNdjson,
  streamUserMessage,
  uploadFile,
} from '@/lib/api';
import type { EditTaskRequest, GenerateRequest, TemplateCandidateSelectRequest, UserStreamEvent } from '@/types/api';

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

function mockFetchStream(lines: string[], options?: { ok?: boolean; status?: number; json?: unknown }): FetchMock {
  const ok = options?.ok ?? true;
  const status = options?.status ?? 200;
  const encodedLines = lines.map((line) => new TextEncoder().encode(line));

  return jest.fn().mockResolvedValue({
    ok,
    status,
    json: async () => options?.json,
    body: ok
      ? {
          getReader: () => {
            let index = 0;
            return {
              read: async () => {
                if (index >= encodedLines.length) {
                  return { value: undefined, done: true };
                }
                const nextValue = encodedLines[index];
                index += 1;
                return { value: nextValue, done: false };
              },
            };
          },
        }
      : undefined,
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
    tender_lx: 0,
    fund_source_lx: 1,
  },
  file_paths: {
    tender_params: ['/uploads/params.xlsx'],
  },
  style_writeback_mode: 'full',
  model: 'deepseek',
};

const validTemplateSelectRequest: TemplateCandidateSelectRequest = {
  candidate: {
    tendername: '测试模板',
    year: 2026,
    fsg: 'http://10.11.1.224/fsg',
    shener: 'http://10.11.1.224/shener',
  },
};

const validEditTaskRequest: EditTaskRequest = {
  conversation_id: 'conv-1',
  form_type: 'xjcg_tender',
  model: 'deepseek',
  edit_prompt: '请把交付日期改成合同签订后 30 天内',
  file_path: 'D:/UploadFiles/edit.docx',
  insertion_config: {
    before_text: '第三章 采购需求',
    after_text: '第四章 响应文件有关格式',
  },
  tender_lx: 0,
  fund_source_lx: 1,
  tender_data_snapshot: validGenerateRequest.tender_data,
};

describe('API Client', () => {
  beforeEach(() => {
    globalThis.fetch = jest.fn() as unknown as typeof fetch;
  });

  describe('createGenerateTask', () => {
    it('should return task info on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { task_id: 'test-task-123', task_kind: 'generate', status: 'queued', queue_position: 1 },
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
          data: { task_id: 'new-task-id', task_kind: 'generate', status: 'queued' },
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

  describe('createEditTask', () => {
    it('should return task info on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        task_id: 'edit-task-123',
        task_kind: 'edit',
        status: 'queued',
        queue_position: 0,
        waiting_count: 0,
      });

      const result = await createEditTask(validEditTaskRequest);
      expect(result.task_id).toBe('edit-task-123');
      expect(result.task_kind).toBe('edit');
      expect(result.status).toBe('queued');
    });

    it('should send correct request body', async () => {
      const fetchSpy = jest.fn().mockResolvedValue({
        ok: true,
        status: 202,
        json: async () => ({
          success: true,
          task_id: 'edit-task-123',
          task_kind: 'edit',
          status: 'queued',
        }),
      } as unknown as Response) as unknown as FetchMock;
      globalThis.fetch = fetchSpy;

      await createEditTask(validEditTaskRequest);

      const [, init] = fetchSpy.mock.calls[0];
      const body = (init as RequestInit).body as string;
      expect(JSON.parse(body)).toEqual(validEditTaskRequest);
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
    it('normalizes gjgk project_number from tender number when upstream returns a truncated code', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: {
          project_name: 'Test Project',
          project_number: 'TC0639',
        },
        type: {
          tender_lx: 1,
          purchase_method: 0,
          fund_lx: 1,
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await fetchTenderDataWithType('0811-264DSITC0639');
      expect(result.data.project_number).toBe('264DSITC0639');
    });

    it('returns tender data and type info together when requested', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { project_name: 'Test Project', ifdzpt2: 2 },
        type: {
          tender_lx: 2,
          purchase_method: 0,
          fund_lx: 1,
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await fetchTenderDataWithType('ZBGG-2024-001');
      expect(result.data.project_name).toBe('Test Project');
      expect(result.data.ifdzpt2).toBe(2);
      expect(result.type).toEqual({
        tender_lx: 2,
        purchase_method: 0,
        fund_lx: 1,
      });
    });

    it('drops invalid tender type info when fund_lx is outside 0|1', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { project_name: 'Test Project' },
        type: {
          tender_lx: 9,
          purchase_method: 0,
          fund_lx: 2,
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await fetchTenderDataWithType('ZBGG-2024-001');
      expect(result.data.project_name).toBe('Test Project');
      expect(result.type).toBeNull();
    });

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

  describe('template candidate API', () => {
    it('fetches template candidates with encoded query params', async () => {
      const fetchSpy = mockFetchJson({
        success: true,
        data: {
          candidates: [
            {
              tenderno: '0811-DSITC260194',
              tendername: '测试模板',
              tname: '上海市中医医院',
              bm: '采购处',
              hytype: '医疗行业',
              tendertype: '国内公开',
              hwlx: '货物',
              yxj: '1',
              zbr: '张三',
              xbr: '李四',
              year: 2026,
              selectable: true,
            },
          ],
          ranking: {
            applied: true,
            mode: 'ai',
            reason: 'ai_ranked',
            message: '已按优先级排序；同优先级模板已按项目名称相关性重排。',
          },
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });
      globalThis.fetch = fetchSpy;

      const result = await fetchTemplateCandidates({
        tenderno: '0811/TEST',
        project_name: '细胞电转仪',
      });

      expect(result.candidates[0]).toMatchObject({
        tenderno: '0811-DSITC260194',
        tendername: '测试模板',
        tname: '上海市中医医院',
        bm: '采购处',
        hytype: '医疗行业',
        tendertype: '国内公开',
        hwlx: '货物',
        yxj: '1',
      });
      expect(result.ranking?.reason).toBe('ai_ranked');
      const [url] = fetchSpy.mock.calls[0];
      expect(String(url)).toContain('tenderno=0811%2FTEST');
      expect(String(url)).toContain('project_name=%E7%BB%86%E8%83%9E%E7%94%B5%E8%BD%AC%E4%BB%AA');
      expect(String(url)).not.toContain('purchase_method=');
    });

    it('posts template selection payload', async () => {
      const fetchSpy = mockFetchJson({
        success: true,
        data: {
          selected_files: {
            clean_draft: {
              file_path: 'D:/UploadFiles/test.docx',
              file_name: 'test.docx',
              original_name: 'test.docx',
              size: 100,
              upload_time: new Date().toISOString(),
            },
          },
          failed_slots: [],
          partial_success: false,
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });
      globalThis.fetch = fetchSpy;

      const result = await selectTemplateCandidate(validTemplateSelectRequest);

      expect(result.selected_files.clean_draft?.file_name).toBe('test.docx');
      const [, init] = fetchSpy.mock.calls[0];
      expect(JSON.parse(String((init as RequestInit).body))).toEqual(validTemplateSelectRequest);
    });

    it('builds template candidate download URL with encoded params', () => {
      const url = getTemplateCandidateDownloadUrl(
        'http://10.11.1.224/dongsong/servlet/export.DownLoad?fileID=123',
        '测试模板-发售稿'
      );

      expect(url).toContain('/api/template-candidates/download?');
      expect(url).toContain('file_url=http%3A%2F%2F10.11.1.224%2Fdongsong%2Fservlet%2Fexport.DownLoad%3FfileID%3D123');
      expect(url).toContain('download_name=%E6%B5%8B%E8%AF%95%E6%A8%A1%E6%9D%BF-%E5%8F%91%E5%94%AE%E7%A8%BF');
    });
  });

  describe('getTaskStatus', () => {
    it('should return task status on success', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: {
          task_id: 'test-task-123',
          task_kind: 'generate',
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
          task_kind: 'generate',
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

  describe('streamNdjson', () => {
    it('dispatches parsed events line by line', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({ event: 'known', data: { value: 'first' } }) + '\n',
        JSON.stringify({ event: 'known', data: { value: 'second' } }) + '\n',
      ]);

      const events: string[] = [];

      await streamNdjson<{ event: 'known'; data: { value: string } }>({
        endpoint: '/api/test-stream',
        parseEvent: (payload) => {
          const event = payload as { event?: string; data?: { value?: string } };
          if (event.event !== 'known' || typeof event.data?.value !== 'string') {
            return null;
          }
          return { event: 'known', data: { value: event.data.value } };
        },
        onEvent: (event) => {
          events.push(event.data.value);
        },
      });

      expect(events).toEqual(['first', 'second']);
    });

    it('throws ApiError on malformed NDJSON lines', async () => {
      globalThis.fetch = mockFetchStream(['{"event":"known","data":{"value":"ok"}}\n', 'not-json\n']);

      await expect(
        streamNdjson({
          endpoint: '/api/test-stream',
          parseEvent: (payload) => payload as { event: 'known'; data: { value: string } },
        })
      ).rejects.toMatchObject({
        name: 'ApiError',
        code: 'STREAM_PROTOCOL_ERROR',
      });
    });

    it('ignores events dropped by the parser without aborting the stream', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({ event: 'known', data: { value: 'first' } }) + '\n',
        JSON.stringify({ event: 'unknown', data: { value: 'skip' } }) + '\n',
        JSON.stringify({ event: 'known', data: { value: 'last' } }) + '\n',
      ]);

      const events: string[] = [];

      await streamNdjson<{ event: 'known'; data: { value: string } }>({
        endpoint: '/api/test-stream',
        parseEvent: (payload) => {
          const event = payload as { event?: string; data?: { value?: string } };
          if (event.event !== 'known' || typeof event.data?.value !== 'string') {
            return null;
          }
          return { event: 'known', data: { value: event.data.value } };
        },
        onEvent: (event) => {
          events.push(event.data.value);
        },
      });

      expect(events).toEqual(['first', 'last']);
    });

    it('rethrows AbortError from the underlying fetch', async () => {
      const controller = new AbortController();
      globalThis.fetch = jest
        .fn()
        .mockImplementation(
          async (_url, init) =>
            await new Promise<Response>((_resolve, reject) => {
              (init?.signal as AbortSignal | undefined)?.addEventListener(
                'abort',
                () => reject(new DOMException('Aborted', 'AbortError')),
                { once: true }
              );
            })
        ) as unknown as typeof fetch;

      const promise = streamNdjson({
        endpoint: '/api/test-stream',
        signal: controller.signal,
        parseEvent: () => null,
      });

      controller.abort();

      await expect(promise).rejects.toHaveProperty('name', 'AbortError');
    });
  });

  describe('streamUserMessage', () => {
    it('parses reply-route events and ignores unknown events', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({ event: 'route', data: { route: 'reply' } }) + '\n',
        JSON.stringify({ event: 'mystery', data: { ignored: true } }) + '\n',
        JSON.stringify({ event: 'done', data: { content: '你好' } }) + '\n',
      ]);

      const events: UserStreamEvent[] = [];

      await streamUserMessage(
        {
          conversation_id: 'conv-1',
          model: 'deepseek',
          messages: [{ role: 'user', content: '你好' }],
        },
        {
          onEvent: (event) => {
            events.push(event);
          },
        }
      );

      expect(events).toEqual([
        { event: 'route', data: { route: 'reply' } },
        { event: 'done', data: { content: '你好' } },
      ]);
    });

    it('converts HTTP error payloads into ApiError', async () => {
      globalThis.fetch = mockFetchStream([], {
        ok: false,
        status: 400,
        json: {
          detail: {
            success: false,
            error: {
              code: 'REQ_MISSING_FIELD',
              message: 'messages 不能为空',
            },
          },
        },
      });

      await expect(
        streamUserMessage({
          conversation_id: 'conv-1',
          model: 'deepseek',
          messages: [{ role: 'user', content: '你好' }],
        })
      ).rejects.toMatchObject({
        name: 'ApiError',
        code: 'REQ_MISSING_FIELD',
        status: 400,
      });
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
