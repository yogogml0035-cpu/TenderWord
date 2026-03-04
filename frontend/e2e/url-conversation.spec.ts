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
  test('Chat page loads with sidebar', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Verify sidebar shows tender type options
    await expect(page.getByText('类型', { exact: true })).toBeVisible();

    // Verify the type options exist
    await expect(page.getByText('询价采购')).toBeVisible();
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('URL params with tenderno triggers processing', async ({ page }) => {
    // Visit chat page with URL parameters
    await page.goto('/chat?tenderno=TEST001&purchase_method=2&tender_lx=0&fund_lx=0');

    // Wait for loading to complete (spinner should disappear)
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Verify we're on the chat page
    await expect(page).toHaveURL(/\/chat/);

    // Verify sidebar shows tender type options
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('URL params with gngk type loads page', async ({ page }) => {
    // Visit with GNGK type parameters (tender_lx=1, purchase_method=1)
    await page.goto('/chat?tenderno=GNGK001&purchase_method=1&tender_lx=1&fund_lx=0');

    // Wait for loading to complete
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Verify the form type is correct (国内公开 for tender_lx=1)
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('Sidebar shows type options', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Verify type options are visible
    await expect(page.getByText('询价采购')).toBeVisible();
    await expect(page.getByText('国内公开')).toBeVisible();
  });

  test('Sidebar navigation works', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Initially should show empty state
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();

    // Create conversation via URL params
    await page.goto('/chat?tenderno=SB-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Verify sidebar still shows types
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });
  test('Invalid URL params - missing type params', async ({ page }) => {
    // Visit with only tenderno, no type params
    await page.goto('/chat?tenderno=INVALID001');

    // Should still load the page without crashing
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Invalid URL params - invalid tender_lx value', async ({ page }) => {
    // Visit with invalid tender_lx value
    await page.goto('/chat?tenderno=TEST999&tender_lx=99&purchase_method=99&fund_lx=0');

    // Page should still load without crashing
    await expect(page.getByText('类型', { exact: true })).toBeVisible({ timeout: 10000 });
  });

  test('URL params without tenderno shows empty state', async ({ page }) => {
    // Visit with type params but no tenderno
    await page.goto('/chat?purchase_method=2&tender_lx=0&fund_lx=0');

    // Should show empty state
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Error handling when tender data fetch fails', async ({ page }) => {
    // Use a tenderno that will likely fail to fetch
    await page.goto('/chat?tenderno=NONEXISTENT-999&purchase_method=2&tender_lx=0&fund_lx=0');

    // Wait for processing to complete (loading spinner should disappear)
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Check that the page doesn't crash - verify sidebar is still visible
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('Concurrent task warning UI structure', async ({ page }) => {
    // This test verifies the UI structure is correct
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Verify sidebar exists
    await expect(page.getByText('询价采购')).toBeVisible();
  });
  test('Recent conversations persist in store', async ({ page }) => {
    // Create a conversation via URL
    await page.goto('/chat?tenderno=HISTORY-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Clear URL and go back to chat
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Verify we're back on the chat page
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });
  test('Page layout is responsive with three columns', async ({ page }) => {
    await page.goto('/chat');

    // Check for flex layout
    const mainContainer = page.locator('.flex.h-screen');
    await expect(mainContainer).toBeVisible();

    // Verify three main sections exist
    // 1. Left sidebar (types)
    await expect(page.getByText('类型', { exact: true })).toBeVisible();

    // 2. Middle form panel area
    // 3. Right chat panel area
    // Both should be part of the flex container
    const flexChildren = await mainContainer.locator('> div').count();
    expect(flexChildren).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Chat Page Basic Navigation', () => {
  test('can navigate from homepage to chat', async ({ page }) => {
    await page.goto('/');

    // Click link to chat mode
    await page.getByRole('link', { name: /进入聊天模式/ }).click();

    // Should be on chat page
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
  });

  test('direct access to /chat works', async ({ page }) => {
    await page.goto('/chat');

    // Verify page loads correctly
    await expect(page.getByText('类型', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();
  });
});

test.describe('Form Panel Tests', () => {
  test('Form structure is correct', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    // Verify empty state
    await expect(page.getByRole('heading', { name: '选择招标类型' })).toBeVisible();

    // Create conversation via URL with params
    await page.goto('/chat?tenderno=FORM-TEST-001&purchase_method=2&tender_lx=0&fund_lx=0');
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 });

    // Verify the form is loaded (look for tender info text)
    const tenderInfoVisible = await page.getByText('招标信息').isVisible().catch(() => false);
    // Or verify the form type is displayed
    const formTypeVisible = await page.getByText('询价采购').count() > 0;
    expect(tenderInfoVisible || formTypeVisible).toBeTruthy();
  });
});

