import { expect, test, type Page } from '@playwright/test';

const conversationId = 'conv-agent-run-chat-panel';
const stableInstanceId = 'agent-run-chat-panel-instance';
const us005ScreenshotPath = '../tasks/agent-run-skill-chat-refactor/screenshots/us-005-capability-chip.png';

function toNdjsonLines(events: Array<Record<string, unknown>>): string {
  return `${events.map((event) => JSON.stringify(event)).join('\n')}\n`;
}

async function seedConversation(
  page: Page,
  options?: {
    messages?: Array<Record<string, unknown>>;
  }
) {
  await page.addInitScript(
    ({ conversationId: seededConversationId, messages }) => {
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: [
              {
                id: seededConversationId,
                title: 'US003-001',
                tenderType: 'xjcg',
                createdAt: 1,
                updatedAt: 1,
                messages: messages || [],
              },
            ],
            currentConversationId: seededConversationId,
            selectedTenderType: 'xjcg',
            activeTaskIds: [],
            taskSummaries: {},
            unreadConversationResults: {},
            conversationDrafts: {
              [seededConversationId]: {
                tender_no: 'US003-001',
                tender_lx: 0,
                fund_lx: 0,
                model: 'deepseek',
                tender_fetch: { status: 'success' },
              },
            },
          },
          version: 0,
        })
      );
    },
    {
      conversationId,
      messages: options?.messages || [],
    }
  );
}

async function stubConversationHeartbeat(page: Page) {
  await page.route('**/api/conversations/*/heartbeat', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          conversation_id: conversationId,
          alive: true,
          instance_id: stableInstanceId,
          server_time: '2026-06-02T11:30:00Z',
          rewrite_available: true,
        },
      }),
    });
  });
}

async function stubClipboard(page: Page) {
  await page.addInitScript(() => {
    const clipboardState = { text: '' };
    Object.defineProperty(window, '__testClipboard', {
      configurable: true,
      value: clipboardState,
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          clipboardState.text = text;
        },
      },
    });
  });
}

test.describe('Agent run chat panel', () => {
  test('shows the slash skill picker and sends the selected rewrite skill in the payload', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    let agentRunPayload: Record<string, unknown> | null = null;

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedConversation(page);
    await stubConversationHeartbeat(page);

    await page.route('**/api/agent/runs/stream', async (route) => {
      agentRunPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: toNdjsonLines([
          {
            event: 'done',
            data: {
              run_id: 'run-slash-picker',
              message: 'rewrite 能力已收到，请继续描述修改目标。',
              selected_skill: 'rewrite',
            },
          },
        ]),
      });
    });

    await page.goto('/tender');
    await expect(page.getByRole('heading', { name: 'US003-001' })).toBeVisible();

    const textarea = page.getByPlaceholder('输入文字并发送即可对话...');
    await textarea.fill('/');
    await expect(page.getByTestId('chat-skill-picker')).toBeVisible();

    await page.getByTestId('chat-skill-option-rewrite').click();
    await expect(page.getByTestId('chat-selected-skill-rewrite')).toBeVisible();
    await expect(textarea).toHaveValue('');

    await textarea.fill('请帮我改写第三包');
    await page.getByTestId('chat-send-button').click();

    await expect(page.getByText('rewrite 能力已收到，请继续描述修改目标。')).toBeVisible();

    expect(agentRunPayload).toMatchObject({
      conversation_id: conversationId,
      message: '请帮我改写第三包',
      model: 'deepseek',
      selected_skills: ['rewrite'],
      context_snapshot: {
        rewrite_available: false,
        uploaded_files: [],
      },
    });
    expect(consoleErrors).toEqual([]);
  });

  test('renders fake rewrite task cards without polling fake task endpoints', async ({ page }) => {
    const consoleErrors: string[] = [];
    const taskRequests: string[] = [];
    let agentRunPayload: Record<string, unknown> | null = null;

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedConversation(page, {
      messages: [
        {
          id: 'msg-download',
          conversationId,
          type: 'ai',
          content: 'output.docx',
          timestamp: 1,
          status: 'completed',
          taskId: 'task-generate-finished',
          metadata: {
            messageKind: 'task-download',
            taskKind: 'generate',
            outputFile: 'D:/UploadFiles/output.docx',
            fileName: 'output.docx',
          },
        },
      ],
    });
    await stubConversationHeartbeat(page);

    await page.route('**/api/tasks/**', async (route) => {
      taskRequests.push(route.request().url());
      await route.fulfill({
        status: 418,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'UNEXPECTED_FAKE_TASK_REQUEST',
            message: 'fake task should not be polled',
          },
        }),
      });
    });

    await page.route('**/api/agent/runs/stream', async (route) => {
      agentRunPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: toNdjsonLines([
          {
            event: 'run_started',
            data: {
              run_id: 'run-fake-rewrite',
              conversation_id: conversationId,
              model: 'deepseek',
              runtime: 'fake',
              selected_skills: [],
            },
          },
          {
            event: 'thinking_stage',
            data: {
              run_id: 'run-fake-rewrite',
              stage: 'understand',
              label: '理解需求',
              status: 'completed',
              summary: '已识别为 rewrite 请求：请帮我改写第三包',
              selected_skill: 'rewrite',
            },
          },
          {
            event: 'task_accepted',
            data: {
              run_id: 'run-fake-rewrite',
              task_id: 'fake-rewrite-task-e2e',
              task_kind: 'rewrite',
              status: 'queued',
              queue_position: 0,
              waiting_count: 0,
            },
          },
          {
            event: 'done',
            data: {
              run_id: 'run-fake-rewrite',
              message: '已为你创建 rewrite 任务。',
              task_id: 'fake-rewrite-task-e2e',
              selected_skill: 'rewrite',
            },
          },
        ]),
      });
    });

    await page.goto('/tender');
    await expect(page.getByRole('heading', { name: 'US003-001' })).toBeVisible();

    await page.getByPlaceholder('输入文字并发送即可对话...').fill('请帮我改写第三包');
    await page.getByTestId('chat-send-button').click();

    await expect(page.getByText('修改进度')).toBeVisible();
    await expect(page.getByText('AI 修改内容')).toBeVisible();
    await expect(page.getByText('请帮我改写第三包')).toBeVisible();

    await expect
      .poll(() => taskRequests.length, {
        timeout: 1000,
      })
      .toBe(0);

    expect(agentRunPayload).toMatchObject({
      conversation_id: conversationId,
      message: '请帮我改写第三包',
      model: 'deepseek',
      selected_skills: [],
      context_snapshot: {
        rewrite_available: true,
        uploaded_files: [],
      },
    });
    expect(consoleErrors).toEqual([]);
  });

  test('renders needs_input follow-up messages from the new agent run endpoint', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const taskRequests: string[] = [];
    let agentRunPayload: Record<string, unknown> | null = null;

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedConversation(page);
    await stubConversationHeartbeat(page);

    await page.route('**/api/tasks/**', async (route) => {
      taskRequests.push(route.request().url());
      await route.fulfill({
        status: 418,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'UNEXPECTED_TASK_REQUEST',
            message: 'ordinary needs_input should not create a task',
          },
        }),
      });
    });

    await page.route('**/api/agent/runs/stream', async (route) => {
      agentRunPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: toNdjsonLines([
          {
            event: 'run_started',
            data: {
              run_id: 'run-needs-input',
              conversation_id: conversationId,
              model: 'deepseek',
              runtime: 'fake',
              selected_skills: [],
            },
          },
          {
            event: 'thinking_stage',
            data: {
              run_id: 'run-needs-input',
              stage: 'guard',
              label: '检查上下文',
              status: 'completed',
              summary: 'fake runtime 暂时只支持 rewrite 或 edit 任务创建。',
              guard_result: 'needs_input',
            },
          },
          {
            event: 'needs_input',
            data: {
              run_id: 'run-needs-input',
              message: '请说明这次要执行 rewrite 还是 edit。',
              missing_requirements: ['selected_skill'],
            },
          },
        ]),
      });
    });

    await page.goto('/tender');
    await expect(page.getByRole('heading', { name: 'US003-001' })).toBeVisible();

    await page.getByPlaceholder('输入文字并发送即可对话...').fill('你好');
    await page.getByTestId('chat-send-button').click();

    await expect(page.getByText('请说明这次要执行 rewrite 还是 edit。')).toBeVisible();

    expect(agentRunPayload).toMatchObject({
      conversation_id: conversationId,
      message: '你好',
      model: 'deepseek',
      selected_skills: [],
      context_snapshot: {
        rewrite_available: false,
        uploaded_files: [],
      },
    });
    expect(taskRequests).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test('shows rewrite capability chips and restores the replay prefix when copying user messages', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    let agentRunPayload: Record<string, unknown> | null = null;

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedConversation(page);
    await stubConversationHeartbeat(page);
    await stubClipboard(page);

    await page.route('**/api/agent/runs/stream', async (route) => {
      agentRunPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: toNdjsonLines([
          {
            event: 'done',
            data: {
              run_id: 'run-user-capability-chip',
              message: 'rewrite 任务需求已收到。',
              selected_skill: 'rewrite',
            },
          },
        ]),
      });
    });

    await page.goto('/tender');
    await expect(page.getByRole('heading', { name: 'US003-001' })).toBeVisible();

    const textarea = page.getByPlaceholder('输入文字并发送即可对话...');
    await textarea.fill('$rewrite 改写第三包');
    await page.getByTestId('chat-send-button').click();

    await expect(page.getByTestId('user-message-capability-chip-rewrite')).toBeVisible();
    await expect(page.getByTestId('user-message-text')).toHaveText('改写第三包');
    await expect(page.getByText('rewrite 任务需求已收到。')).toBeVisible();

    await page.getByTestId('user-message-frame').hover();
    await page.getByRole('button', { name: '复制用户消息' }).click();

    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (
              window as Window & {
                __testClipboard?: { text: string };
              }
            ).__testClipboard?.text || ''
        )
      )
      .toBe('$rewrite 改写第三包');

    await page.screenshot({ path: us005ScreenshotPath });

    expect(agentRunPayload).toMatchObject({
      conversation_id: conversationId,
      message: '改写第三包',
      model: 'deepseek',
      selected_skills: ['rewrite'],
    });
    expect(consoleErrors).toEqual([]);
  });
});
