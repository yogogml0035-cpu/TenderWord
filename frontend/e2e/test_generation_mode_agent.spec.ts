import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const taskId = 'task-agent-e2e';
const conversationId = 'conv-agent-e2e';
const artifactRoot = path.resolve(__dirname, '../../tasks/deepagents-generation-mode-refactor');
const screenshotsDir = path.join(artifactRoot, 'screenshots');
const logsDir = path.join(artifactRoot, 'logs');

function taskStatus(status: 'running' | 'completed' = 'running') {
  return {
    task_id: taskId,
    task_kind: 'generate',
    status,
    created_at: '2026-05-27T14:30:00Z',
    progress: {
      completed_nodes: [],
      running_nodes: status === 'running' ? ['host_agent'] : [],
      current_node: status === 'running' ? 'host_agent' : '',
      current_node_display: status === 'running' ? 'host_agent' : '',
      progress_text: status === 'running' ? '智能体生成中' : '已完成',
      completed_count: status === 'running' ? 3 : 8,
      total_nodes: 8,
      progress_percent: status === 'running' ? 38 : 100,
    },
    result:
      status === 'completed'
        ? {
            output_file: 'outputs/agent-e2e.docx',
            file_name: 'agent-e2e.docx',
            file_size: 1024,
            model_used: 'deepseek',
            total_time_seconds: 1,
          }
        : undefined,
  };
}

function sseEvent(event: string, id: string, data: Record<string, unknown>) {
  return [`id: ${id}`, `event: ${event}`, `data: ${JSON.stringify(data)}`, '', ''].join('\n');
}

async function seedConversation(page: Page) {
  await page.addInitScript(({ conversationId }) => {
    window.sessionStorage.setItem(
      'chat-storage',
      JSON.stringify({
        state: {
          conversations: [
            {
              id: conversationId,
              title: 'AGENT-E2E-001',
              tenderType: 'xjcg',
              createdAt: 1,
              updatedAt: 1,
              messages: [],
            },
          ],
          currentConversationId: conversationId,
          selectedTenderType: 'xjcg',
          activeTaskIds: [],
          taskSummaries: {},
          unreadConversationResults: {},
          conversationDrafts: {
            [conversationId]: {
              tender_no: 'AGENT-E2E-001',
              tender_lx: 0,
              fund_lx: 0,
              model: 'deepseek',
              generation_mode: 'workflow',
              generation_style: 'template',
              style_writeback_mode: 'full',
              insertion_config: {
                before_text: '第三章  采购需求',
                after_text: '第四章  响应文件有关格式',
              },
              tender_fetch: { status: 'success' },
              tender_data: {
                project_name: '智能体 E2E 项目',
                project_number: 'AGENT-E2E-001',
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
                  upload_time: '2026-05-27T14:30:00Z',
                },
                tender_params: [
                  {
                    id: 'params',
                    file_path: 'uploads/params.docx',
                    file_name: 'params.docx',
                    original_name: 'params.docx',
                    size: 256,
                    upload_time: '2026-05-27T14:30:00Z',
                  },
                ],
              },
            },
          },
        },
        version: 0,
      })
    );
  }, { conversationId });
}

test.describe('Generation mode agent flow', () => {
  test('renders draft, audit, revision, and download cards from mocked agent SSE', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    let generatePayload: Record<string, unknown> | null = null;

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedConversation(page);

    await page.route('**/api/conversations/*/heartbeat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            conversation_id: conversationId,
            alive: true,
            instance_id: 'agent-e2e-instance',
            server_time: '2026-05-27T14:30:00Z',
            rewrite_available: true,
          },
        }),
      });
    });

    await page.route(`**/api/tasks/${taskId}/heartbeat`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            task_id: taskId,
            alive: true,
            task_kind: 'generate',
            status: 'running',
          },
        }),
      });
    });

    await page.route(`**/api/tasks/${taskId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: taskStatus('running') }),
      });
    });

    await page.route('**/api/generate', async (route) => {
      generatePayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            task_id: taskId,
            task_kind: 'generate',
            status: 'running',
            created_at: '2026-05-27T14:30:00Z',
          },
        }),
      });
    });

    await page.route(`**/api/stream/${taskId}**`, async (route) => {
      const now = '2026-05-27T14:30:01Z';
      const body = [
        sseEvent('connected', '0', { task_id: taskId, message: 'connected' }),
        sseEvent('agent_step', '1', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'draft',
          round: 0,
          node: 'host_agent',
          is_complete: true,
          content: '这是智能体初稿正文。',
          findings: [],
        }),
        sseEvent('agent_step', '2', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'audit',
          round: 1,
          node: 'host_agent',
          is_complete: true,
          content: null,
          findings: [
            {
              evidence: '交付范围缺少验收标准',
              fix_hint: '补充设备验收和交付要求',
            },
          ],
        }),
        sseEvent('agent_step', '3', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'revision',
          round: 1,
          node: 'host_agent',
          is_complete: true,
          content: '这是第 1 轮 AI 修改内容，已补充验收标准。',
          findings: [],
        }),
        sseEvent('done', '4', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          success: true,
          message: '生成完成',
          output_file: 'outputs/agent-e2e.docx',
          file_name: 'agent-e2e.docx',
        }),
      ].join('');

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream; charset=utf-8',
        headers: {
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
        body,
      });
    });

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: '询价采购' })).toBeVisible();
    await page.getByRole('group', { name: '生成方式' }).getByRole('button', { name: '智能体' }).click();
    await page.getByRole('button', { name: /开始生成/ }).click();

    await expect.poll(() => generatePayload?.generation_mode).toBe('agent');

    await expect(page.getByText('AI 初稿内容')).toBeVisible();
    await expect(page.getByText('这是智能体初稿正文。')).toBeVisible();
    await expect(page.getByText('智能体审核意见')).toBeVisible();
    await expect(page.getByText('第 1 轮审核')).toBeVisible();
    await expect(page.getByText('evidence: 交付范围缺少验收标准')).toBeVisible();
    await expect(page.getByText('fix_hint: 补充设备验收和交付要求')).toBeVisible();
    await expect(page.getByText('AI 修改内容', { exact: true })).toBeVisible();
    await expect(page.getByText('这是第 1 轮 AI 修改内容，已补充验收标准。')).toBeVisible();
    await expect(page.getByRole('button', { name: '下载文件' })).toBeVisible();

    fs.mkdirSync(screenshotsDir, { recursive: true });
    fs.mkdirSync(logsDir, { recursive: true });
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-015-agent-e2e.png'),
      fullPage: true,
    });
    fs.writeFileSync(
      path.join(logsDir, 'us-015-browser-console.log'),
      consoleErrors.length > 0 ? consoleErrors.join('\n') : 'no console errors\n',
      'utf8'
    );

    expect(consoleErrors).toEqual([]);
  });
});
