import { test, expect } from '@playwright/test';

/**
 * Homepage E2E Tests
 */

test.describe('Homepage', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');

    // Check page title
    await expect(page).toHaveTitle(/TenderWord|招标文档/);

    // Check main heading exists
    const heading = page.getByRole('heading', { level: 1 });
    await expect(heading).toBeVisible();
  });

  test('main navigation elements exist', async ({ page }) => {
    await page.goto('/');

    // Check for navigation or menu elements
    const nav = page.locator('nav, header').first();
    await expect(nav).toBeVisible();

    // Check for main content area
    const main = page.locator('main').first();
    await expect(main).toBeVisible();
  });

  test('tender type selection is available', async ({ page }) => {
    await page.goto('/');

    const chatLink = page.getByRole('link', { name: /进入使用/ });
    await expect(chatLink).toBeVisible();
  });

  test('can navigate to tender workspace from homepage', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /进入使用/ }).click();

    await expect(page).toHaveURL(/\/tender/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
  });
});
