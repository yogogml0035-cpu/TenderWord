import {
  ApiError,
  cancelTask,
  createCommentSupplementTask,
  createGenerateTask,
  downloadFile,
  fetchTemplateCandidates,
  fetchTenderData,
  fetchTenderDataWithType,
  getTemplateCandidateDownloadUrl,
  getTaskStatus,
  selectTemplateCandidate,
  sendTaskHeartbeat,
  streamAgentRun,
  streamNdjson,
  uploadFile,
} from '@/lib/api';
import type {
  AgentRunEvent,
  AgentRunStreamRequest,
  CommentSupplementTaskRequest,
  GenerateRequest,
  TemplateCandidateSelectRequest,
} from '@/types/api';

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
    template: '/uploads/template.docx',
    tender_params: ['/uploads/params.xlsx'],
  },
  generation_mode: 'workflow',
  comment_generation_mode: 'on',
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

const validCommentSupplementTaskRequest: CommentSupplementTaskRequest = {
  conversation_id: 'conv-1',
  source_file: 'D:/UploadFiles/output.docx',
  model: 'deepseek',
};

const validAgentRunStreamRequest: AgentRunStreamRequest = {
  conversation_id: 'conv-1',
  message: '请改写第三包',
  model: 'deepseek',
  selected_skills: ['rewrite'],
  context_snapshot: {
    rewrite_available: true,
    uploaded_files: [],
  },
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

  describe('createCommentSupplementTask', () => {
    it('should create a comment supplement task through the project API', async () => {
      const fetchSpy = jest.fn().mockResolvedValue({
        ok: true,
        status: 202,
        json: async () => ({
          success: true,
          task_id: 'comment-task-123',
          task_kind: 'comment_supplement',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        }),
      } as unknown as Response) as unknown as FetchMock;
      globalThis.fetch = fetchSpy;

      const result = await createCommentSupplementTask(validCommentSupplementTaskRequest);

      expect(result.task_id).toBe('comment-task-123');
      expect(result.task_kind).toBe('comment_supplement');
      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [url, init] = fetchSpy.mock.calls[0];
      expect(String(url)).toContain('/api/comment-supplement');
      expect((init as RequestInit).method).toBe('POST');
      expect(JSON.parse((init as RequestInit).body as string)).toEqual(
        validCommentSupplementTaskRequest
      );
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
        data: { project_name: 'Test Project', ifdzpt2: 2, ifzgcg: 2 },
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
      expect(result.data.ifzgcg).toBe(2);
      expect(result.type).toEqual({
        tender_lx: 2,
        purchase_method: 0,
        fund_lx: 1,
      });
    });

    it('returns warning when upstream purchase method is unsupported', async () => {
      globalThis.fetch = mockFetchJson({
        success: true,
        data: { project_name: 'Unsupported Project' },
        type: {
          tender_lx: 0,
          purchase_method: 9,
          fund_lx: 0,
        },
        warning: {
          code: 'TENDER_UNSUPPORTED_PURCHASE_METHOD',
          message: '当前采购方式暂不支持',
          details: { purchase_method: 9 },
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });

      const result = await fetchTenderDataWithType('0811-DSITC261472');
      expect(result.data.project_name).toBe('Unsupported Project');
      expect(result.type).toEqual({
        tender_lx: 0,
        purchase_method: 9,
        fund_lx: 0,
      });
      expect(result.warning?.message).toBe('当前采购方式暂不支持');
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
          selected_file: {
            file_path: 'D:/UploadFiles/test.docx',
            file_name: 'test.docx',
            original_name: 'test.docx',
            size: 100,
            upload_time: new Date().toISOString(),
          },
        },
        message: 'OK',
        timestamp: new Date().toISOString(),
      });
      globalThis.fetch = fetchSpy;

      const result = await selectTemplateCandidate(validTemplateSelectRequest);

      expect(result.selected_file.file_name).toBe('test.docx');
      const [, init] = fetchSpy.mock.calls[0];
      expect(JSON.parse(String((init as RequestInit).body))).toEqual(validTemplateSelectRequest);
    });

    it('builds template candidate download URL with encoded params', () => {
      const downloadName = '测试模板-模板';
      const url = getTemplateCandidateDownloadUrl(
        'http://10.11.1.224/dongsong/servlet/export.DownLoad?fileID=123',
        downloadName
      );

      expect(url).toContain('/api/template-candidates/download?');
      expect(url).toContain('file_url=http%3A%2F%2F10.11.1.224%2Fdongsong%2Fservlet%2Fexport.DownLoad%3FfileID%3D123');
      expect(url).toContain(`download_name=${encodeURIComponent(downloadName)}`);
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

  describe('streamAgentRun', () => {
    it('parses ordinary assistant replies and ignores unknown events', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({
          event: 'run_started',
          data: {
            run_id: 'run-1',
            conversation_id: 'conv-1',
            model: 'deepseek',
            runtime: 'deepagents',
            selected_skills: ['rewrite'],
          },
        }) + '\n',
        JSON.stringify({
          event: 'done',
          data: {
            run_id: 'run-1',
            message: '你好，我可以继续帮你完善任务上下文。',
          },
        }) + '\n',
        JSON.stringify({ event: 'mystery', data: { ignored: true } }) + '\n',
      ]);

      const events: AgentRunEvent[] = [];

      await streamAgentRun(validAgentRunStreamRequest, {
        onEvent: (event) => {
          events.push(event);
        },
      });

      expect(events).toEqual([
        {
          event: 'run_started',
          data: {
            run_id: 'run-1',
            conversation_id: 'conv-1',
            model: 'deepseek',
            runtime: 'deepagents',
            selected_skills: ['rewrite'],
          },
        },
        {
          event: 'done',
          data: {
            run_id: 'run-1',
            message: '你好，我可以继续帮你完善任务上下文。',
          },
        },
      ]);
    });

    it('parses needs_input follow-up events', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({
          event: 'run_started',
          data: {
            run_id: 'run-need-input',
            conversation_id: 'conv-1',
            model: 'deepseek',
            runtime: 'fake',
            selected_skills: ['rewrite'],
          },
        }) + '\n',
        JSON.stringify({
          event: 'needs_input',
          data: {
            run_id: 'run-need-input',
            message: '请先上传要重写的 Word 文件。',
            selected_skill: 'rewrite',
            missing_requirements: ['uploaded_word_file'],
          },
        }) + '\n',
      ]);

      const events: AgentRunEvent[] = [];

      await streamAgentRun(validAgentRunStreamRequest, {
        onEvent: (event) => {
          events.push(event);
        },
      });

      expect(events).toEqual([
        {
          event: 'run_started',
          data: {
            run_id: 'run-need-input',
            conversation_id: 'conv-1',
            model: 'deepseek',
            runtime: 'fake',
            selected_skills: ['rewrite'],
          },
        },
        {
          event: 'needs_input',
          data: {
            run_id: 'run-need-input',
            message: '请先上传要重写的 Word 文件。',
            selected_skill: 'rewrite',
            missing_requirements: ['uploaded_word_file'],
          },
        },
      ]);
    });

    it('parses backend null optional fields in agent run events', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({
          event: 'thinking_stage',
          data: {
            run_id: 'run-null-optionals',
            stage: 'understand',
            label: '理解需求',
            status: 'completed',
            summary: '已接收用户消息并等待能力确认。',
            selected_skill: null,
            guard_result: null,
            tool_name: null,
          },
        }) + '\n',
        JSON.stringify({
          event: 'thinking_stage',
          data: {
            run_id: 'run-null-optionals',
            stage: 'guard',
            label: '检查上下文',
            status: 'completed',
            summary: 'fake runtime 暂时只支持 rewrite 任务创建。',
            selected_skill: null,
            guard_result: 'needs_input',
            tool_name: null,
          },
        }) + '\n',
        JSON.stringify({
          event: 'needs_input',
          data: {
            run_id: 'run-null-optionals',
            message: '请说明这次要执行 rewrite。',
            selected_skill: null,
            missing_requirements: ['selected_skill'],
          },
        }) + '\n',
        JSON.stringify({
          event: 'done',
          data: {
            run_id: 'run-null-optionals',
            message: '本轮无需创建任务。',
            task_id: null,
            selected_skill: null,
          },
        }) + '\n',
      ]);

      const events: AgentRunEvent[] = [];

      await streamAgentRun(validAgentRunStreamRequest, {
        onEvent: (event) => {
          events.push(event);
        },
      });

      expect(events).toEqual([
        {
          event: 'thinking_stage',
          data: {
            run_id: 'run-null-optionals',
            stage: 'understand',
            label: '理解需求',
            status: 'completed',
            summary: '已接收用户消息并等待能力确认。',
            selected_skill: undefined,
            guard_result: undefined,
            tool_name: undefined,
          },
        },
        {
          event: 'thinking_stage',
          data: {
            run_id: 'run-null-optionals',
            stage: 'guard',
            label: '检查上下文',
            status: 'completed',
            summary: 'fake runtime 暂时只支持 rewrite 任务创建。',
            selected_skill: undefined,
            guard_result: 'needs_input',
            tool_name: undefined,
          },
        },
        {
          event: 'needs_input',
          data: {
            run_id: 'run-null-optionals',
            message: '请说明这次要执行 rewrite。',
            selected_skill: undefined,
            missing_requirements: ['selected_skill'],
          },
        },
        {
          event: 'done',
          data: {
            run_id: 'run-null-optionals',
            message: '本轮无需创建任务。',
            task_id: undefined,
            selected_skill: undefined,
          },
        },
      ]);
    });

    it('parses task_accepted and error terminal events', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({
          event: 'task_accepted',
          data: {
            run_id: 'run-1',
            task_id: 'task-1',
            task_kind: 'rewrite',
            status: 'queued',
            queue_position: 0,
            waiting_count: 0,
          },
        }) + '\n',
        JSON.stringify({
          event: 'error',
          data: {
            run_id: 'run-1',
            code: 'AGENT_RUN_FAILED',
            message: 'agent run 执行失败，请稍后重试',
          },
        }) + '\n',
      ]);

      const events: AgentRunEvent[] = [];

      await streamAgentRun(validAgentRunStreamRequest, {
        onEvent: (event) => {
          events.push(event);
        },
      });

      expect(events).toEqual([
        {
          event: 'task_accepted',
          data: {
            run_id: 'run-1',
            task_id: 'task-1',
            task_kind: 'rewrite',
            status: 'queued',
            queue_position: 0,
            waiting_count: 0,
          },
        },
        {
          event: 'error',
          data: {
            run_id: 'run-1',
            code: 'AGENT_RUN_FAILED',
            message: 'agent run 执行失败，请稍后重试',
          },
        },
      ]);
    });

    it('throws ApiError on malformed NDJSON lines', async () => {
      globalThis.fetch = mockFetchStream([
        JSON.stringify({
          event: 'run_started',
          data: {
            run_id: 'run-1',
            conversation_id: 'conv-1',
            model: 'deepseek',
            runtime: 'fake',
            selected_skills: ['rewrite'],
          },
        }) + '\n',
        'not-json\n',
      ]);

      await expect(streamAgentRun(validAgentRunStreamRequest)).rejects.toMatchObject({
        name: 'ApiError',
        code: 'AGENT_RUN_STREAM_PROTOCOL_ERROR',
      });
    });

    it('converts HTTP error payloads into ApiError', async () => {
      globalThis.fetch = mockFetchStream([], {
        ok: false,
        status: 422,
        json: {
          detail: {
            success: false,
            error: {
              code: 'REQ_INVALID_AGENT_CONTEXT',
              message: 'context_snapshot 非法',
            },
          },
        },
      });

      await expect(streamAgentRun(validAgentRunStreamRequest)).rejects.toMatchObject({
        name: 'ApiError',
        code: 'REQ_INVALID_AGENT_CONTEXT',
        status: 422,
      });
    });
  });

  describe('uploadFile', () => {
    it('should return uploaded file info on success', async () => {
      const fetchSpy = mockFetchJson({
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
      globalThis.fetch = fetchSpy;

      const file = new File(['test'], 'test.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const result = await uploadFile(file, 'rewrite_source');
      expect(result.file_path).toBe('/uploads/test.docx');

      const [, init] = fetchSpy.mock.calls[0];
      const body = (init as RequestInit).body as FormData;
      expect(body.get('file_type')).toBe('rewrite_source');
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
      const result = await uploadFile(file, 'rewrite_source');
      expect(result.file_path).toBe('/uploads/flat-test.docx');
    });
  });
});
