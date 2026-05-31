import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const taskId = 'task-agent-e2e';
const conversationId = 'conv-agent-e2e';
const artifactRoot = path.resolve(__dirname, '../../tasks/template-comment-generation-convergence');
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
      running_nodes: status === 'running' ? ['content_agent'] : [],
      current_node: status === 'running' ? 'content_agent' : '',
      current_node_display: status === 'running' ? 'content_agent' : '',
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
                template: {
                  id: 'template',
                  file_path: 'uploads/template.docx',
                  file_name: 'template.docx',
                  original_name: 'template.docx',
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
  test('renders structured content agent card and download card from mocked agent SSE', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    let generatePayload: Record<string, unknown> | null = null;
    let generateCallCount = 0;
    let releaseGenerateResponse!: () => void;
    const generateResponseGate = new Promise<void>((resolve) => {
      releaseGenerateResponse = resolve;
    });

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
      generateCallCount += 1;
      generatePayload = (await route.request().postDataJSON()) as Record<string, unknown>;
      await generateResponseGate;
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
      const draftRound = {
        round: 1,
        phase: 'draft',
        label: '初稿生成',
        summary: '初稿生成完成，约 10 字。',
        issue_count: 0,
        fix_count: 0,
        content: '这是智能体初稿正文。',
        findings: [],
      };
      const auditRound = {
        round: 1,
        phase: 'audit',
        label: '第 1 轮审核发现',
        summary: '第 1 轮审核发现 1 个问题。',
        issue_count: 1,
        fix_count: 0,
        content: '[{"evidence":"交付范围缺少验收标准","fix_hint":"补充设备验收和交付要求"}]',
        findings: [
          {
            evidence: '交付范围缺少验收标准',
            fix_hint: '补充设备验收和交付要求',
          },
        ],
      };
      const revisionRound = {
        round: 1,
        phase: 'revision',
        label: '第 1 轮修复',
        summary: '第 1 轮修复完成，已处理 1 个问题。',
        issue_count: 1,
        fix_count: 1,
        content: '这是第 1 轮 AI 修改内容，已补充验收标准。',
        findings: auditRound.findings,
      };
      const finalReviewRound = {
        round: 2,
        phase: 'audit',
        label: '第 2 轮修复复核',
        summary: '第 2 轮修复复核通过。',
        issue_count: 0,
        fix_count: 0,
        content: '[]',
        findings: [],
      };
      const body = [
        sseEvent('connected', '0', { task_id: taskId, message: 'connected' }),
        sseEvent('agent_step', '1', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_generate_agent',
          is_complete: true,
          content: '这是智能体初稿正文。',
          findings: [],
          content_agent: {
            phase: 'draft',
            summary: '初稿生成完成，约 10 字。',
            rounds: [draftRound],
            highlights: [],
          },
        }),
        sseEvent('agent_step', '2', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_verify_agent',
          is_complete: true,
          content: '[{"evidence":"交付范围缺少验收标准","fix_hint":"补充设备验收和交付要求"}]',
          findings: [
            {
              evidence: '交付范围缺少验收标准',
              fix_hint: '补充设备验收和交付要求',
            },
          ],
          content_agent: {
            phase: 'audit',
            summary: '第 1 轮审核发现 1 个问题。',
            rounds: [draftRound, auditRound],
            highlights: auditRound.findings,
          },
        }),
        sseEvent('agent_step', '3', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_revise_agent',
          is_complete: true,
          content: '这是第 1 轮 AI 修改内容，已补充验收标准。',
          findings: [],
          content_agent: {
            phase: 'revision',
            summary: '第 1 轮修复完成，已处理 1 个问题。',
            rounds: [draftRound, auditRound, revisionRound],
            highlights: auditRound.findings,
          },
        }),
        sseEvent('agent_step', '4', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'stream',
          round: 2,
          node: 'content_verify_agent',
          is_complete: true,
          content: '[]',
          findings: [],
          content_agent: {
            phase: 'audit',
            summary: '第 2 轮修复复核通过。',
            rounds: [draftRound, auditRound, revisionRound, finalReviewRound],
            highlights: [],
          },
        }),
        sseEvent('agent_step', '5', {
          timestamp: now,
          task_id: taskId,
          task_kind: 'generate',
          step_type: 'final',
          round: 2,
          node: 'content_agent',
          is_complete: true,
          content: '最终完成，修复 1 轮，最终正文约 7 字。',
          findings: [],
          content_agent: {
            phase: 'final',
            summary: '最终完成，修复 1 轮，最终正文约 7 字。',
            rounds: [draftRound, auditRound, revisionRound, finalReviewRound],
            highlights: [],
            final_result: {
              summary: '最终完成，修复 1 轮，最终正文约 7 字。',
              revision_rounds: 1,
              final_chars: 7,
              issue_count: 0,
              content: '这是最终正文。',
            },
          },
        }),
        sseEvent('done', '6', {
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
    await page.getByRole('group', { name: '生成批注' }).getByRole('button', { name: '关' }).click();
    await page.getByRole('button', { name: /开始生成/ }).evaluate((button) => {
      (button as HTMLButtonElement).click();
      (button as HTMLButtonElement).click();
    });
    await expect.poll(() => generateCallCount).toBe(1);
    releaseGenerateResponse();

    await expect.poll(() => generatePayload?.generation_mode).toBe('agent');
    await expect.poll(() => generatePayload?.comment_generation_mode).toBe('off');

    await expect(page.getByText('参数生成智能体')).toHaveCount(1);
    await expect(page.getByText('content_generate_agent')).toHaveCount(0);
    await expect(page.getByText('content_verify_agent round-1', { exact: true })).toHaveCount(0);
    await expect(page.getByText('content_revise_agent round-1', { exact: true })).toHaveCount(0);
    await expect(page.getByText('content_verify_agent round-2', { exact: true })).toHaveCount(0);
    await expect(page.getByText('初稿生成', { exact: true })).toBeVisible();
    await expect(page.getByText('第 1 轮审核发现', { exact: true })).toBeVisible();
    await expect(page.getByText('第 1 轮修复', { exact: true })).toBeVisible();
    await expect(page.getByText('第 2 轮修复复核', { exact: true })).toBeVisible();
    await expect(page.getByText('交付范围缺少验收标准').first()).toBeVisible();
    await expect(page.getByText('补充设备验收和交付要求').first()).toBeVisible();
    await expect(page.getByText('这是智能体初稿正文。')).not.toBeVisible();
    await page.getByText('查看初稿正文').click();
    await expect(page.getByText('这是智能体初稿正文。')).toBeVisible();
    await expect(page.getByText('[]')).not.toBeVisible();
    await expect(page.getByText('evidence: 交付范围缺少验收标准')).toHaveCount(0);
    await expect(page.getByText('这是第 1 轮 AI 修改内容，已补充验收标准。')).not.toBeVisible();
    await expect(page.getByText('AI 生成内容')).toHaveCount(0);
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
