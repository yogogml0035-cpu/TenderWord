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
    
    // Check for tender type selector or buttons
    const tenderSelector = page.locator('[data-testid="tender-type"], select, button').first();
    await expect(tenderSelector).toBeVisible();
  });
});

/**
 * Tender Forms Navigation Tests
 */

test.describe('Tender Form Navigation', () => {
  test('can navigate to XJCG (询价采购) tender form', async ({ page }) => {
    await page.goto('/tender/xjcg');
    
    // Check page loaded
    await expect(page).toHaveURL(/\/tender\/xjcg/);
    
    // Check for form elements
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('can navigate to GKZB (公开招标) tender form', async ({ page }) => {
    await page.goto('/tender/gkzb');
    
    // Check page loaded
    await expect(page).toHaveURL(/\/tender\/gkzb/);
    
    // Check for form elements
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('can navigate to YQZB (邀请招标) tender form', async ({ page }) => {
    await page.goto('/tender/yqzb');
    
    // Check page loaded
    await expect(page).toHaveURL(/\/tender\/yqzb/);
    
    // Check for form elements
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('navigation links work from homepage', async ({ page }) => {
    await page.goto('/');
    
    // Find and click navigation link to tender forms
    // This depends on actual UI implementation
    const tenderLink = page.locator('a[href*="/tender"]').first();
    
    if (await tenderLink.isVisible().catch(() => false)) {
      await tenderLink.click();
      await expect(page).toHaveURL(/\/tender\//);
    }
  });
});
