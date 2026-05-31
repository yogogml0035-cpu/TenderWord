import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const conversationId = 'conv-comment-supplement-e2e';
const generateDoneTaskId = 'task-generate-done-e2e';
const commentSupplementTaskId = 'task-comment-supplement-e2e';
const agentGenerateTaskId = 'task-agent-generate-comment-e2e';
const workflowGenerateTaskId = 'task-workflow-generate-comment-e2e';
const artifactRoot = path.resolve(__dirname, '../../tasks/template-comment-generation-convergence');
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
      completed_count: 1,
      total_nodes: 3,
      progress_percent: 33.3,
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
                  template: {
                    id: 'template',
                    file_path: 'uploads/template.docx',
                    file_name: 'template.docx',
                    original_name: 'template.docx',
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
        step_type: 'tool_snapshot',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content:
          '第 1 轮锚点校验\n#1 需修复: 原始锚点「★7.投标人须提供售后服务承诺」 -> 当前锚点「★7.投标人须提供售后服务承诺」',
        findings: [],
        comment_agent: {
          phase: 'validation_round',
          rounds: [
            {
              round: 1,
              label: '第 1 轮锚点校验',
              passed: 6,
              failed: 1,
              skipped: 0,
              highlights: [
                {
                  index: 7,
                  status: '需修复',
                  reason: '当前锚点未在最终正文中精确匹配',
                  original_reference_text: '★7.投标人须提供售后服务承诺',
                  reference_text: '★7.投标人须提供售后服务承诺',
                  candidate_fragments: ['7.投标人须提供售后服务承诺'],
                },
              ],
            },
          ],
          highlights: [],
        },
      }),
      sseEvent('agent_step', '2', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        step_type: 'tool_snapshot',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content: '第 2 轮修复复核\n#7 已修复: 当前锚点「7.投标人须提供售后服务承诺」',
        findings: [],
        comment_agent: {
          phase: 'validation_round',
          rounds: [
            {
              round: 1,
              label: '第 1 轮锚点校验',
              passed: 6,
              failed: 1,
              skipped: 0,
              highlights: [],
            },
            {
              round: 2,
              label: '第 2 轮修复复核',
              passed: 7,
              failed: 0,
              skipped: 0,
              highlights: [
                {
                  index: 7,
                  status: '已修复',
                  reason: '锚点已通过校验',
                  original_reference_text: '★7.投标人须提供售后服务承诺',
                  reference_text: '7.投标人须提供售后服务承诺',
                  candidate_fragments: [],
                },
              ],
            },
          ],
          highlights: [],
        },
      }),
      sseEvent('agent_step', '3', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        step_type: 'final',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content: 'comment_agent 最终写入统计\nWord 写入尝试 8 条，成功 7 条，失败 0 条，跳过 1 条。',
        findings: [],
        comment_agent: {
          phase: 'final',
          rounds: [
            {
              round: 1,
              label: '第 1 轮锚点校验',
              passed: 6,
              failed: 1,
              skipped: 0,
              highlights: [
                {
                  index: 7,
                  status: '需修复',
                  reason: '当前锚点未在最终正文中精确匹配',
                  original_reference_text: '★7.投标人须提供售后服务承诺',
                  reference_text: '★7.投标人须提供售后服务承诺',
                  candidate_fragments: ['7.投标人须提供售后服务承诺'],
                },
              ],
            },
            {
              round: 2,
              label: '第 2 轮修复复核',
              passed: 7,
              failed: 0,
              skipped: 0,
              highlights: [
                {
                  index: 7,
                  status: '已修复',
                  reason: '锚点已通过校验',
                  original_reference_text: '★7.投标人须提供售后服务承诺',
                  reference_text: '7.投标人须提供售后服务承诺',
                  candidate_fragments: [],
                },
              ],
            },
          ],
          highlights: [],
          final_validation: {
            round: 0,
            label: '最终静默复校验',
            passed: 7,
            failed: 0,
            skipped: 0,
            highlights: [],
          },
          writeback: {
            attempted: 8,
            added: 7,
            failed: 0,
            skipped: 1,
            issues: [
              {
                index: 8,
                status: '已跳过',
                reason: '目标位置已有批注，已跳过',
                original_reference_text: '',
                reference_text: '售后服务承诺',
                candidate_fragments: [],
              },
            ],
          },
        },
      }),
      sseEvent('done', '4', {
        timestamp: now,
        task_id: commentSupplementTaskId,
        task_kind: 'comment_supplement',
        success: true,
        message: '补充批注完成',
        output_file: 'outputs/supplement-output.docx',
        file_name: 'supplement-output.docx',
        comment_writeback: {
          summary: 'AI 批注写入: 生成 8 条，成功 7 条，失败 0 条，跳过 1 条',
          generated: 8,
          added: 7,
          failed: 0,
          skipped: 1,
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
    await expect(page.getByText('批注生成智能体', { exact: true })).toBeVisible();
    await expect(page.getByText('第 1 轮锚点校验')).toBeVisible();
    await expect(page.getByText('第 2 轮修复复核')).toBeVisible();
    await expect(page.getByText('当前锚点未在最终正文中精确匹配')).toBeVisible();
    await expect(page.getByText('成功 7 条 / 跳过 1 条 / 失败 0 条')).toBeVisible();
    await expect(page.getByText('1 条目标位置已有批注，已跳过')).toBeVisible();
    await expect(page.getByText('工具轮次 3')).toHaveCount(0);
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
        content: '参数生成智能体已完成初稿。',
        findings: [],
      }),
      sseEvent('agent_step', '2', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        step_type: 'tool_snapshot',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content:
          '第 1 轮锚点校验\n通过 1 条，失败 0 条，跳过 0 条。',
        findings: [],
        comment_agent: {
          phase: 'validation_round',
          rounds: [
            {
              round: 1,
              label: '第 1 轮锚点校验',
              passed: 1,
              failed: 0,
              skipped: 0,
              highlights: [],
            },
          ],
          highlights: [],
        },
      }),
      sseEvent('agent_step', '3', {
        timestamp: now,
        task_id: agentGenerateTaskId,
        task_kind: 'generate',
        step_type: 'final',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content:
          'comment_agent 最终写入统计\nWord 写入尝试 1 条，成功 1 条，失败 0 条，跳过 0 条。',
        findings: [],
        comment_agent: {
          phase: 'final',
          rounds: [
            {
              round: 1,
              label: '第 1 轮锚点校验',
              passed: 1,
              failed: 0,
              skipped: 0,
              highlights: [],
            },
          ],
          highlights: [],
          final_validation: {
            round: 0,
            label: '最终静默复校验',
            passed: 1,
            failed: 0,
            skipped: 0,
            highlights: [],
          },
          writeback: {
            attempted: 1,
            added: 1,
            failed: 0,
            skipped: 0,
            issues: [],
          },
        },
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
    await expect(page.getByText('参数生成智能体已完成初稿。')).toBeVisible();
    await expect(page.getByText('批注生成智能体', { exact: true })).toBeVisible();
    await expect(page.getByText('第 1 轮锚点校验')).toBeVisible();
    await expect(page.getByText('普通通过项已计入数量。')).toBeVisible();
    await expect(page.getByText('成功 1 条 / 跳过 0 条 / 失败 0 条')).toBeVisible();
    await expect(page.getByText('工具轮次 3')).toHaveCount(0);
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
        content: 'workflow 不应展示这条批注生成智能体消息。',
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
    await expect(page.getByText('批注生成智能体', { exact: true })).toHaveCount(0);
    await expect(page.getByText('workflow 不应展示这条批注生成智能体消息。')).toHaveCount(0);

    ensureArtifactDirs();
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-010-workflow-no-comment-agent.png'),
      fullPage: true,
    });
    writeConsoleLog('us-010-workflow-generate-console.log', consoleErrors);

    expect(consoleErrors).toEqual([]);
  });
});
