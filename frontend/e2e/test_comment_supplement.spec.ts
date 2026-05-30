import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const conversationId = 'conv-comment-supplement-e2e';
const generateDoneTaskId = 'task-generate-done-e2e';
const commentSupplementTaskId = 'task-comment-supplement-e2e';
const agentGenerateTaskId = 'task-agent-generate-comment-e2e';
const workflowGenerateTaskId = 'task-workflow-generate-comment-e2e';
const artifactRoot = path.resolve(__dirname, '../../tasks/comment-supplement-comment-agent');
const screenshotsDir = path.join(artifactRoot, 'screenshots');
const logsDir = path.join(artifactRoot, 'logs');

type TaskKind = 'generate' | 'comment_supplement';
type GenerationMode = 'workflow' | 'agent';

function ensureArtifactDirs() {
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(logsDir, { recursive: true });
}

function sseEvent(event: string, id: string, data: Record<string, unknown>) {
  return [`id: ${id}`, `event: ${event}`, `data: ${JSON.stringify(data)}`, '', ''].join('\n');
}

function taskStatus(taskId: string, taskKind: TaskKind, currentNode = 'comment_agent') {
  return {
    task_id: taskId,
    task_kind: taskKind,
    status: 'running',
    created_at: '2026-05-30T10:00:00Z',
    progress: {
      completed_nodes: [],
      running_nodes: [currentNode],
      current_node: currentNode,
      current_node_display: currentNode,
      progress_text: '处理中',
      completed_count: 2,
      total_nodes: 5,
      progress_percent: 40,
    },
  };
}

async function routeCommonHeartbeat(page: Page) {
  await page.route('**/api/conversations/*/heartbeat', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          conversation_id: conversationId,
          alive: true,
          instance_id: 'comment-supplement-e2e-instance',
          server_time: '2026-05-30T10:00:00Z',
          rewrite_available: true,
        },
      }),
    });
  });
}

async function routeRunningTask(
  page: Page,
  taskId: string,
  taskKind: TaskKind,
  currentNode: string,
  streamBody: string
) {
  await page.route(`**/api/tasks/${taskId}/heartbeat`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          task_id: taskId,
          alive: true,
          task_kind: taskKind,
          status: 'running',
        },
      }),
    });
  });

  await page.route(`**/api/tasks/${taskId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: taskStatus(taskId, taskKind, currentNode) }),
    });
  });

  await page.route(`**/api/stream/${taskId}**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream; charset=utf-8',
      headers: {
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
      body: streamBody,
    });
  });
}

async function seedConversation(
  page: Page,
  options: {
    generationMode: GenerationMode;
    currentTaskId?: string;
    taskKind?: TaskKind;
    currentNode?: string;
    messages?: Array<Record<string, unknown>>;
    taskMessageMap?: Record<string, Record<string, string>>;
  }
) {
  await page.addInitScript(
    ({ conversationId, options }) => {
      const currentTaskId = options.currentTaskId;
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: [
              {
                id: conversationId,
                title: 'COMMENT-E2E-001',
                tenderType: 'xjcg',
                createdAt: 1,
                updatedAt: 1,
                currentTaskId,
                messages: options.messages || [],
              },
            ],
            currentConversationId: conversationId,
            selectedTenderType: 'xjcg',
            activeTaskIds: currentTaskId ? [currentTaskId] : [],
            taskMessageMap: options.taskMessageMap || {},
            taskSummaries: currentTaskId
              ? {
                  [currentTaskId]: {
                    task_kind: options.taskKind || 'generate',
                    status: 'running',
                    current_node: options.currentNode || 'content_agent',
                    current_node_display: options.currentNode || 'content_agent',
                  },
                }
              : {},
            unreadConversationResults: {},
            conversationDrafts: {
              [conversationId]: {
                tender_no: 'COMMENT-E2E-001',
                tender_lx: 0,
                fund_lx: 0,
                model: 'deepseek',
                generation_mode: options.generationMode,
                generation_style: 'template',
                style_writeback_mode: 'full',
                insertion_config: {
                  before_text: '第三章  采购需求',
                  after_text: '第四章  响应文件有关格式',
                },
                tender_fetch: { status: 'success' },
                tender_data: {
                  project_name: '补充批注 E2E 项目',
                  project_number: 'COMMENT-E2E-001',
                  project_content: '采购一批测试设备',
                  bzj_rule: '不收取保证金',
                  buyer_name: '测试采购人',
                  project_zbr_xbr: '张三',
                  zbr_xbr_tel: '13800138000',
                  zbr_pinyin: 'zhangsan',
                  shell_start_date: '2026-05-01',
                  shell_end_date: '2026-05-10',
                  submit_date: '2026-05-20',
                  platform: '电子采购平台',
                  service_fee: '1000',
                  tender_lx: 0,
                  fund_source_lx: 0,
                },
                files: {
                  clean_draft: {
                    id: 'clean-draft',
                    file_path: 'uploads/clean-draft.docx',
                    file_name: 'clean-draft.docx',
                    original_name: 'clean-draft.docx',
                    size: 128,
                    upload_time: '2026-05-30T10:00:00Z',
                  },
                  tender_params: [
                    {
                      id: 'params',
                      file_path: 'uploads/params.docx',
                      file_name: 'params.docx',
                      original_name: 'params.docx',
                      size: 256,
                      upload_time: '2026-05-30T10:00:00Z',
                    },
                  ],
                },
              },
            },
          },
          version: 0,
        })
      );
    },
    { conversationId, options }
  );
}

function collectConsoleErrors(page: Page) {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => {
    consoleErrors.push(error.message);
  });
  return consoleErrors;
}

function writeConsoleLog(fileName: string, consoleErrors: string[]) {
  ensureArtifactDirs();
  fs.writeFileSync(
    path.join(logsDir, fileName),
    consoleErrors.length > 0 ? consoleErrors.join('\n') : 'no console errors\n',
    'utf8'
  );
}

test.describe('Comment supplement and comment_agent mocked flows', () => {
  test('creates a comment_supplement task from a generate download card and renders the comment_agent result', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page);
    let supplementPayload: Record<string, unknown> | null = null;
    const now = '2026-05-30T10:00:01Z';
    const generateDownloadMessage = {
      id: 'msg-generate-download',
      conversationId,
      type: 'ai',
      content: 'generate-output.docx',
      timestamp: 1,
      status: 'completed',
      taskId: generateDoneTaskId,
      metadata: {
        messageKind: 'task-download',
        taskKind: 'generate',
        outputFile: 'outputs/generate-output.docx',
        fileName: 'generate-output.docx',
        commentWriteback: {
          summary: 'AI 批注写入: 生成 3 条，成功 1 条，失败 2 条',
          generated: 3,
          added: 1,
          failed: 2,
          skipped: 0,
          warning: true,
        },
      },
    };

    await seedConversation(page, {
      generationMode: 'workflow',
      messages: [generateDownloadMessage],
      taskMessageMap: {
        [generateDoneTaskId]: {
          downloadMessageId: 'msg-generate-download',
        },
      },
    });
    await routeCommonHeartbeat(page);

    const supplementStream = [
      sseEvent('connected', '0', { task_id: commentSupplementTaskId, message: 'connected' }),
      sseEvent('agent_step', '1', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content: '正在校验补充批注锚点。',
        findings: [],
      }),
      sseEvent('agent_step', '2', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content: '已写入 2 条补充批注。',
        findings: [],
      }),
      sseEvent('done', '3', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        success: true,
        message: '补充批注完成',
        output_file: 'outputs/supplement-output.docx',
        file_name: 'supplement-output.docx',
        comment_writeback: {
          summary: 'AI 批注写入: 生成 2 条，成功 2 条，失败 0 条',
          generated: 2,
          added: 2,
          failed: 0,
          skipped: 0,
          warning: false,
        },
      }),
    ].join('');

    await page.route('**/api/comment-supplement', async (route) => {
      supplementPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            task_id: commentSupplementTaskId,
            task_kind: 'comment_supplement',
            status: 'running',
            queue_position: 0,
            waiting_count: 0,
          },
        }),
      });
    });
    await routeRunningTask(
      page,
      commentSupplementTaskId,
      'comment_supplement',
      'comment_agent',
      supplementStream
    );

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('generate-output.docx')).toBeVisible();
    await expect(page.getByText('文档已生成，部分批注未写入')).toBeVisible();
    await page.getByRole('button', { name: '补充批注' }).click();

    await expect.poll(() => supplementPayload).toEqual({
      conversation_id: conversationId,
      source_file: 'outputs/generate-output.docx',
      model: 'deepseek',
    });
    await expect(page.getByText('comment_agent', { exact: true })).toBeVisible();
    await expect(page.getByText('正在校验补充批注锚点。')).toBeVisible();
    await expect(page.getByText('已写入 2 条补充批注。')).toBeVisible();
    await expect(page.getByText('supplement-output.docx')).toBeVisible();
    await expect(page.getByRole('button', { name: '下载文件' })).toHaveCount(2);
    await expect(page.getByRole('button', { name: '补充批注' })).toHaveCount(1);

    ensureArtifactDirs();
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-010-comment-supplement-flow.png'),
      fullPage: true,
    });
    writeConsoleLog('us-010-comment-supplement-console.log', consoleErrors);

    expect(consoleErrors).toEqual([]);
  });

  test('renders content agent and comment_agent cards for agent generate SSE', async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    const now = '2026-05-30T10:05:01Z';
    const stream = [
      sseEvent('connected', '0', { task_id: agentGenerateTaskId, message: 'connected' }),
      sseEvent('agent_step', '1', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '正文智能体已完成初稿。',
        findings: [],
      }),
      sseEvent('agent_step', '2', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content: '批注智能体正在修复锚点。',
        findings: [],
      }),
      sseEvent('agent_step', '3', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content: '批注智能体完成写入检查。',
        findings: [],
      }),
      sseEvent('done', '4', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        success: true,
        message: '生成完成',
        output_file: 'outputs/agent-comment-output.docx',
        file_name: 'agent-comment-output.docx',
      }),
    ].join('');

    await seedConversation(page, {
      generationMode: 'agent',
      currentTaskId: agentGenerateTaskId,
      taskKind: 'generate',
      currentNode: 'content_agent',
    });
    await routeCommonHeartbeat(page);
    await routeRunningTask(page, agentGenerateTaskId, 'generate', 'content_agent', stream);

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('content_generate_agent round-1', { exact: true })).toBeVisible();
    await expect(page.getByText('正文智能体已完成初稿。')).toBeVisible();
    await expect(page.getByText('comment_agent', { exact: true })).toBeVisible();
    await expect(page.getByText('批注智能体正在修复锚点。')).toBeVisible();
    await expect(page.getByText('批注智能体完成写入检查。')).toBeVisible();
    await expect(page.getByText('agent-comment-output.docx')).toBeVisible();

    ensureArtifactDirs();
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-010-agent-generate-comment-agent.png'),
      fullPage: true,
    });
    writeConsoleLog('us-010-agent-generate-console.log', consoleErrors);

    expect(consoleErrors).toEqual([]);
  });

  test('does not render comment_agent cards for workflow generate SSE', async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    const now = '2026-05-30T10:10:01Z';
    const stream = [
      sseEvent('connected', '0', { task_id: workflowGenerateTaskId, message: 'connected' }),
      sseEvent('agent_step', '1', {
        timestamp: now,
        task_id: workflowGenerateTaskId,
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content: 'workflow 不应展示这条批注智能体消息。',
        findings: [],
      }),
      sseEvent('done', '2', {
        timestamp: now,
        task_id: workflowGenerateTaskId,
        task_kind: 'generate',
        success: true,
        message: '生成完成',
        output_file: 'outputs/workflow-output.docx',
        file_name: 'workflow-output.docx',
      }),
    ].join('');

    await seedConversation(page, {
      generationMode: 'workflow',
      currentTaskId: workflowGenerateTaskId,
      taskKind: 'generate',
      currentNode: 'generate_polished_text',
    });
    await routeCommonHeartbeat(page);
    await routeRunningTask(page, workflowGenerateTaskId, 'generate', 'generate_polished_text', stream);

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('workflow-output.docx')).toBeVisible();
    await expect(page.getByText('comment_agent', { exact: true })).toHaveCount(0);
    await expect(page.getByText('workflow 不应展示这条批注智能体消息。')).toHaveCount(0);

    ensureArtifactDirs();
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-010-workflow-no-comment-agent.png'),
      fullPage: true,
    });
    writeConsoleLog('us-010-workflow-generate-console.log', consoleErrors);

    expect(consoleErrors).toEqual([]);
  });
});
