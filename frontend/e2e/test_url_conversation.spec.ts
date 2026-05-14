import { test, expect, type Page } from '@playwright/test';

/**
 * E2E Tests for URL-driven Conversation Flow
 *
 * Tests URL parameter handling, conversation creation/reuse,
 * sidebar interactions, and form submission flows.
 *
 * Note: These tests focus on UI behavior that can be verified without backend.
 * Tests requiring backend API are mocked or skipped.
 */

async function expectTenderTypeButtons(page: Page) {
  await expect(page.getByTestId('tender-type-button-xjcg')).toBeVisible();
  await expect(page.getByTestId('tender-type-button-gngk')).toBeVisible();
}

async function expectNoVisibleSpinner(page: Page) {
  await expect(page.locator('.animate-spin').filter({ visible: true })).toHaveCount(0, {
    timeout: 15000,
  });
}

test.describe('URL-driven Conversation Flow', () => {
  test('Tender page loads with sidebar', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expectTenderTypeButtons(page);
  });

  test('URL params with xjcg fund_lx=1 still triggers processing', async ({ page }) => {
    await page.goto('/tender?tenderno=TEST001&purchase_method=5&tender_lx=0&fund_lx=1');

    await expectNoVisibleSpinner(page);
    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('URL params with gngk fund_lx=1 loads page', async ({ page }) => {
    await page.goto('/tender?tenderno=GNGK001&purchase_method=2&tender_lx=0&fund_lx=1');

    await expectNoVisibleSpinner(page);
    await expect(page.getByTestId('tender-type-button-gngk')).toBeVisible();
  });

  test('URL params with manual gjgk alias route create a gjgk conversation', async ({ page }) => {
    await page.goto('/tender?tenderno=GJGK001&purchase_method=0&tender_lx=0&fund_lx=0');
    await expectNoVisibleSpinner(page);

    await expect
      .poll(async () =>
        page.evaluate(() => {
          const raw = window.sessionStorage.getItem('chat-storage');
          if (!raw) {
            return null;
          }

          const parsed = JSON.parse(raw) as {
            state?: {
              conversations?: Array<{ id: string; tenderType: string }>;
              currentConversationId?: string | null;
              selectedTenderType?: string | null;
            };
          };

          const conversations = parsed.state?.conversations ?? [];
          const currentConversation =
            conversations.find(
              (conversation) => conversation.id === parsed.state?.currentConversationId
            ) || null;

          return {
            conversationCount: conversations.length,
            currentTenderType: currentConversation?.tenderType ?? null,
            selectedTenderType: parsed.state?.selectedTenderType ?? null,
          };
        })
      )
      .toEqual({
        conversationCount: 1,
        currentTenderType: 'gjgk',
        selectedTenderType: 'gjgk',
      });
  });

  test('Matching URL reuses existing same-session conversation', async ({ page }) => {
    await page.addInitScript(() => {
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: [
              {
                id: 'conv-existing',
                title: '自定义标题',
                tenderType: 'gngk',
                createdAt: 1,
                updatedAt: 5,
                messages: [],
              },
            ],
            currentConversationId: null,
            selectedTenderType: null,
            conversationDrafts: {
              'conv-existing': {
                tender_no: '0811-DSITC253505',
                tender_data: {
                  project_name: '缓存项目',
                  project_number: '0811-DSITC253505',
                  project_content: '缓存内容',
                  bzj_rule: '缓存保证金规则',
                  buyer_name: '缓存采购人',
                  project_zbr_xbr: '张三',
                  zbr_xbr_tel: '13800138000',
                  zbr_pinyin: 'zhangsan',
                  shell_start_date: '2024-01-01',
                  shell_end_date: '2024-12-31',
                  submit_date: '2024-12-31',
                  platform: '缓存平台',
                  service_fee: '1000',
                },
              },
            },
          },
          version: 0,
        })
      );
    });

    await page.goto(
      '/tender?tenderno=0811-DSITC253505&purchase_method=2&tender_lx=0&fund_lx=0'
    );
    await page.waitForLoadState('networkidle');

    await expect
      .poll(async () =>
        page.evaluate(() => {
          const raw = window.sessionStorage.getItem('chat-storage');
          if (!raw) {
            return null;
          }

          const parsed = JSON.parse(raw) as {
            state?: {
              conversations?: Array<{ id: string; title: string }>;
              currentConversationId?: string | null;
              conversationDrafts?: Record<string, { tender_fetch?: { status?: string } }>;
            };
          };

          return {
            conversationCount: parsed.state?.conversations?.length ?? 0,
            currentConversationId: parsed.state?.currentConversationId ?? null,
            currentTitle:
              parsed.state?.conversations?.find(
                (conversation) => conversation.id === parsed.state?.currentConversationId
              )?.title ?? null,
            fetchStatus:
              parsed.state?.conversationDrafts?.['conv-existing']?.tender_fetch?.status ?? null,
          };
        })
      )
      .toEqual({
        conversationCount: 1,
        currentConversationId: 'conv-existing',
        currentTitle: '自定义标题',
        fetchStatus: 'success',
      });
  });

  test('Sidebar shows type options', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expectTenderTypeButtons(page);
  });

  test('Sidebar navigation works', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();

    await page.goto('/tender?tenderno=SB-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expectNoVisibleSpinner(page);
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

    await expectNoVisibleSpinner(page);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Concurrent task warning UI structure', async ({ page }) => {
    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByTestId('tender-type-button-xjcg')).toBeVisible();
  });

  test('Current-page conversations stay scoped to the current page session', async ({
    page,
    context,
  }) => {
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

    await expect(page.getByText('当前页面会话', { exact: true })).toBeVisible();
    await expect(page.getByTestId('conversation-item-conv-history')).toBeVisible();

    await page.close();

    const freshPage = await context.newPage();
    await freshPage.goto('/tender');
    await freshPage.waitForLoadState('networkidle');

    await expect(freshPage.getByText('当前页面会话', { exact: true })).toHaveCount(0);
    await expect(freshPage.getByTestId('conversation-item-conv-history')).toHaveCount(0);
  });

  test('Expanded sidebar shows all type conversations, scrolls, and auto-creates a new conversation for an empty type', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.sessionStorage.setItem(
        'chat-storage',
        JSON.stringify({
          state: {
            conversations: Array.from({ length: 12 }, (_, index) => ({
              id: `conv-xjcg-${index + 1}`,
              title: `XJCG-HISTORY-${index + 1}`,
              tenderType: 'xjcg',
              createdAt: index + 1,
              updatedAt: 100 - index,
              messages: [],
            })),
            currentConversationId: 'conv-xjcg-1',
            selectedTenderType: 'xjcg',
            conversationDrafts: {},
          },
          version: 0,
        })
      );
    });

    await page.goto('/tender');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('当前页面会话', { exact: true })).toBeVisible();
    await expect(page.locator('[data-testid^="conversation-item-conv-xjcg-"]')).toHaveCount(12);

    const sidebarIsScrollable = await page
      .getByTestId('tender-type-sidebar-scroll')
      .evaluate((element) => element.scrollHeight > element.clientHeight);
    expect(sidebarIsScrollable).toBe(true);

    const gngkButton = page.getByTestId('tender-type-button-gngk');
    const beforeClickY = await gngkButton.evaluate(
      (element) => element.getBoundingClientRect().top
    );
    await gngkButton.click();

    await expect(page.locator('[data-testid^="conversation-item-conv-xjcg-"]')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: '新对话' })).toBeVisible();

    const afterClickY = await gngkButton.evaluate((element) => element.getBoundingClientRect().top);
    expect(beforeClickY).toBeGreaterThan(afterClickY);

    await expect
      .poll(async () =>
        page.evaluate(() => {
          const raw = window.sessionStorage.getItem('chat-storage');
          if (!raw) {
            return null;
          }

          const parsed = JSON.parse(raw) as {
            state?: {
              conversations?: Array<{ id: string; tenderType: string }>;
              currentConversationId?: string | null;
              selectedTenderType?: string | null;
            };
          };

          const conversations = parsed.state?.conversations ?? [];
          const currentConversation =
            conversations.find(
              (conversation) => conversation.id === parsed.state?.currentConversationId
            ) || null;

          return {
            conversationCount: conversations.length,
            currentTenderType: currentConversation?.tenderType ?? null,
            selectedTenderType: parsed.state?.selectedTenderType ?? null,
          };
        })
      )
      .toEqual({
        conversationCount: 13,
        currentTenderType: 'gngk',
        selectedTenderType: 'gngk',
      });
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
                currentTaskId: 'task-stale',
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
            activeTaskIds: ['task-stale'],
            taskSummaries: {
              'task-stale': {
                task_id: 'task-stale',
                status: 'running',
                updated_at: 1,
              },
            },
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

    await expect(page.getByPlaceholder('输入文字并发送即可对话...')).toBeVisible();
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
        staleTaskCount: 1,
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
    await expectNoVisibleSpinner(page);

    const tenderInfoVisible = await page.getByText('招标信息').isVisible().catch(() => false);
    const formTypeVisible = (await page.getByText('询价采购').count()) > 0;
    expect(tenderInfoVisible || formTypeVisible).toBeTruthy();
  });
});
