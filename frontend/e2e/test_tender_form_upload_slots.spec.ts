import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const artifactRoot = path.resolve(__dirname, '../../tasks/template-comment-generation-convergence');
const screenshotsDir = path.join(artifactRoot, 'screenshots');
const logsDir = path.join(artifactRoot, 'logs');

async function seedTenderFormConversation(page: Page) {
  await page.addInitScript(() => {
    window.sessionStorage.setItem(
      'chat-storage',
      JSON.stringify({
        state: {
          conversations: [
            {
              id: 'conv-upload-slots',
              title: 'UPLOAD-SLOTS-001',
              tenderType: 'xjcg',
              createdAt: 1,
              updatedAt: 1,
              messages: [],
            },
          ],
          currentConversationId: 'conv-upload-slots',
          selectedTenderType: 'xjcg',
          activeTaskIds: [],
          taskSummaries: {},
          conversationDrafts: {
            'conv-upload-slots': {
              tender_no: 'UPLOAD-SLOTS-001',
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
              tender_type_info: {
                tender_lx: 0,
                purchase_method: 5,
                fund_lx: 0,
              },
              tender_data: {
                project_name: '上传位验收项目',
                project_number: 'UPLOAD-SLOTS-001',
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
                tender_params: [],
              },
            },
          },
        },
        version: 0,
      })
    );
  });
}

test.describe('Tender form upload slots', () => {
  test('shows only required template and technical parameter upload controls', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await seedTenderFormConversation(page);
    await page.route('**/api/conversations/*/heartbeat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            conversation_id: 'conv-upload-slots',
            alive: true,
            instance_id: 'upload-slots-instance',
            server_time: '2026-05-31T02:50:00Z',
            rewrite_available: true,
          },
        }),
      });
    });

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: '询价采购' })).toBeVisible();
    await expect(page.getByTestId('file-uploader-template-card')).toBeVisible();
    await expect(page.getByTestId('file-uploader-params-card')).toBeVisible();
    await expect(page.getByText('模板文件（必填）')).toHaveCount(1);
    await expect(page.getByText('技术参数文件（必填）')).toHaveCount(1);
    await expect(page.getByTestId(/file-uploader-.*-card/)).toHaveCount(2);

    await page.getByRole('button', { name: '开始生成' }).click();
    await expect(page.getByText('请上传模板文件')).toBeVisible();

    fs.mkdirSync(screenshotsDir, { recursive: true });
    fs.mkdirSync(logsDir, { recursive: true });
    await page.screenshot({
      path: path.join(screenshotsDir, 'us-001-upload-slots.png'),
      fullPage: true,
    });
    fs.writeFileSync(
      path.join(logsDir, 'us-001-browser-console.log'),
      consoleErrors.length > 0 ? consoleErrors.join('\n') : 'no console errors\n',
      'utf8'
    );

    expect(consoleErrors).toEqual([]);
  });
});
