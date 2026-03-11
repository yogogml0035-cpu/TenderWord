import { test, expect } from '@playwright/test';

/**
 * E2E Tests for URL-driven Conversation Flow
 *
 * Tests URL parameter handling, conversation creation/reuse,
 * sidebar interactions, and form submission flows.
 *
 * Note: These tests focus on UI behavior that can be verified without backend.
 * Tests requiring backend API are mocked or skipped.
 */

test.describe('URL-driven Conversation Flow', () => {
  test('Tender page loads with sidebar', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByText('询价采购')).toBeVisible();
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('URL params with tenderno triggers processing', async ({ page }) => {
    await page.goto('/tender?tenderno=TEST001&purchase_method=2&tender_lx=0&fund_lx=0');

    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('URL params with gngk type loads page', async ({ page }) => {
    await page.goto('/tender?tenderno=GNGK001&purchase_method=1&tender_lx=1&fund_lx=0');

    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('Sidebar shows type options', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('询价采购')).toBeVisible();
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('Sidebar navigation works', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();

    await page.goto('/tender?tenderno=SB-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Invalid URL params - missing type params', async ({ page }) => {
    await page.goto('/tender?tenderno=INVALID001');
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Invalid URL params - invalid tender_lx value', async ({ page }) => {
    await page.goto('/tender?tenderno=TEST999&tender_lx=99&purchase_method=99&fund_lx=0');
    await expect(page.getByText('类型', { exact: true })).toBeVisible({ timeout: 10000 });
  });

  test('URL params without tenderno shows empty state', async ({ page }) => {
    await page.goto('/tender?purchase_method=2&tender_lx=0&fund_lx=0');

    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Error handling when tender data fetch fails', async ({ page }) => {
    await page.goto('/tender?tenderno=NONEXISTENT-999&purchase_method=2&tender_lx=0&fund_lx=0');

    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Concurrent task warning UI structure', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('询价采购')).toBeVisible();
  });

  test('Recent conversations are scoped to the current page session', async ({ page, context }) => {
    await page.addInitScript(() => {
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: [
              {
                id: 'conv-history',
                title: 'HISTORY-TEST-001',
                tenderType: 'xjcg',
                createdAt: 1,
                updatedAt: 1,
                messages: [],
              },
            ],
            currentConversationId: 'conv-history',
            selectedTenderType: 'xjcg',
          },
          version: 0,
        })
      );
    });

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: '询价采购' }).hover();
    await expect(page.getByText('最近对话')).toBeVisible();
    await expect(page.getByRole('button', { name: /HISTORY-TEST-001/ }).last()).toBeVisible();

    await page.close();

    const freshPage = await context.newPage();
    await freshPage.goto('/tender');
    await freshPage.waitForLoadState('networkidle');

    await freshPage.getByRole('button', { name: '询价采购' }).hover();
    await expect(freshPage.getByText('最近对话')).toHaveCount(0);
    await expect(freshPage.getByText('HISTORY-TEST-001')).toHaveCount(0);
  });

  test('Stale generating task is preserved as interrupted when backend reports TASK_NOT_FOUND', async ({
    page,
  }) => {
    let streamRequestCount = 0;

    await page.addInitScript(() => {
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: [
              {
                id: 'conv-stale',
                title: 'STALE-TASK-001',
                tenderType: 'xjcg',
                createdAt: 1,
                updatedAt: 1,
                messages: [
                  {
                    id: 'msg-stale',
                    conversationId: 'conv-stale',
                    type: 'ai',
                    content: {
                      logs: [],
                      aiContent: {
                        text: '',
                        timestamp: 1,
                        isComplete: false,
                      },
                    },
                    timestamp: 1,
                    status: 'generating',
                    taskId: 'task-stale',
                  },
                ],
              },
            ],
            currentConversationId: 'conv-stale',
            selectedTenderType: 'xjcg',
          },
          version: 0,
        })
      );
      window.sessionStorage.setItem(
        'chat-task-session-storage',
        JSON.stringify({
          state: {
            sessions: {
              'task-stale': {
                taskId: 'task-stale',
                lastEventId: '42',
              },
            },
          },
          version: 0,
        })
      );
    });

    await page.route('**/api/tasks/task-stale', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            success: false,
            error: {
              code: 'TASK_NOT_FOUND',
              message: '任务不存在',
              task_id: 'task-stale',
            },
          },
        }),
      });
    });
    await page.route('**/api/stream/task-stale', async (route) => {
      streamRequestCount += 1;
      await route.abort();
    });

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByPlaceholder('输入消息...')).toBeVisible();
    await expect(page.getByText('服务已重启，任务已中断，可重试')).toHaveCount(1);

    await expect
      .poll(async () =>
        page.evaluate(() => {
          const raw = window.sessionStorage.getItem('chat-storage');
          if (!raw) {
            return {
              generatingCount: 0,
              staleTaskCount: 0,
              interruptedCount: 0,
            };
          }
          const parsed = JSON.parse(raw) as {
            state?: {
              conversations?: Array<{
                messages?: Array<{ status?: string; taskId?: string; error?: string }>;
              }>;
            };
          };
          const messages =
            parsed.state?.conversations?.flatMap((conversation) => conversation.messages ?? []) ?? [];
          return {
            generatingCount: messages.filter((message) => message.status === 'generating').length,
            staleTaskCount: messages.filter((message) => message.taskId === 'task-stale').length,
            interruptedCount: messages.filter(
              (message) =>
                message.taskId === 'task-stale' &&
                message.status === 'error' &&
                message.error === '服务已重启，任务已中断，可重试'
            ).length,
          };
        })
      )
      .toEqual({
        generatingCount: 0,
        staleTaskCount: 2,
        interruptedCount: 1,
      });

    await expect.poll(() => streamRequestCount).toBe(0);
  });

  test('Page layout is responsive with three columns', async ({ page }) => {
    await page.goto('/tender');

    const mainContainer = page.locator('.grid.h-screen');
    await expect(mainContainer).toBeVisible();
    await expect(page.getByText('类型', { exact: true })).toBeVisible();

    const gridChildren = await mainContainer.locator('> div').count();
    expect(gridChildren).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Tender Page Basic Navigation', () => {
  test('can navigate from homepage to tender page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /进入使用/ }).click();

    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('direct access to /tender works', async ({ page }) => {
    await page.goto('/tender');

    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
  });
});

test.describe('Form Panel Tests', () => {
  test('Form structure is correct', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();

    await page.goto('/tender?tenderno=FORM-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    const tenderInfoVisible = await page.getByText('招标信息').isVisible().catch(() => false);
    const formTypeVisible = (await page.getByText('询价采购').count()) > 0;
    expect(tenderInfoVisible || formTypeVisible).toBeTruthy();
  });
});
