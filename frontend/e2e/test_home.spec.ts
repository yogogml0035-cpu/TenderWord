import { test, expect } from '@playwright/test';

/**
 * Homepage E2E Tests
 */

test.describe('Homepage', () => {
  test('homepage redirects to the tender workspace', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/TenderWord|招标文档/);
    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
  });

  test('workspace content elements exist after root redirect', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '欢迎使用体验' })).toBeVisible();
    await expect(page.getByText('开始新对话：')).toBeVisible();
  });

  test('tender type selection is available after root redirect', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByTestId('tender-type-button-xjcg')).toBeVisible();
    await expect(page.getByTestId('tender-type-button-gngk')).toBeVisible();
    await expect(page.getByTestId('tender-type-button-gjgk')).toBeVisible();
  });

  test('root route keeps the tender workspace usable', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
  });
});
