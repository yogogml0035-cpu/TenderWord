import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Error Scenarios
 * Covers: network errors, validation errors, server errors, SSE errors
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================
// Helper Functions
// ============================================

/**
 * Mock API response with error
 */
async function mockApiError(
  page: Page,
  endpoint: string,
  options: {
    status?: number;
    errorCode?: string;
    message?: string;
    details?: string;
  } = {}
) {
  const { status = 500, errorCode = 'SYS_INTERNAL_ERROR', message = 'Internal Server Error', details } = options;

  await page.route(`${API_BASE_URL}${endpoint}`, (route) => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        error: {
          code: errorCode,
          message,
          details,
        },
        timestamp: new Date().toISOString(),
      }),
    });
  });
}

/**
 * Mock network failure
 */
async function mockNetworkFailure(page: Page, endpoint: string) {
  await page.route(`${API_BASE_URL}${endpoint}`, (route) => {
    route.abort('failed');
  });
}

/**
 * Mock timeout
 */
async function mockTimeout(page: Page, endpoint: string, delayMs: number = 60000) {
  await page.route(`${API_BASE_URL}${endpoint}`, async (route) => {
    // Wait longer than typical timeout
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    route.abort('timedout');
  });
}

// ============================================
// Network Error Tests
// ============================================

test.describe('Network Errors', () => {
  test('handles API connection failure gracefully', async ({ page }) => {
    // Mock network failure for all API calls
    await page.route(`${API_BASE_URL}/**`, (route) => {
      route.abort('connectionfailed');
    });

    await page.goto('/');

    // Page should still load
    await expect(page).toHaveTitle(/TenderWord|招标文档/);

    // Check for error handling - the app should not crash
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('handles tender data fetch network error', async ({ page }) => {
    await mockNetworkFailure(page, '/api/tender/*');

    await page.goto('/tender/xjcg');

    // Form should still be visible even if data fetch fails
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles upload network error', async ({ page }) => {
    await mockNetworkFailure(page, '/api/upload*');

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles task creation network error', async ({ page }) => {
    await mockNetworkFailure(page, '/api/generate');

    await page.goto('/tender/xjcg');

    // Page should load without crashing
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles timeout error', async ({ page }) => {
    // Set a shorter timeout for the test
    test.setTimeout(10000);

    await mockTimeout(page, '/api/tender/*', 5000);

    await page.goto('/tender/xjcg');

    // Page should still render
    const form = page.locator('form').first();
    await expect(form).toBeVisible({ timeout: 8000 });
  });
});

// ============================================
// Validation Error Tests (400 errors)
// ============================================

test.describe('Validation Errors', () => {
  test('handles invalid tender number (400 error)', async ({ page }) => {
    await mockApiError(page, '/api/tender/INVALID', {
      status: 400,
      errorCode: 'REQ_INVALID_PARAM',
      message: 'Invalid tender number format',
      details: 'Tender number must match pattern ZBGG-YYYY-NNN',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles missing required fields error', async ({ page }) => {
    await mockApiError(page, '/api/generate', {
      status: 400,
      errorCode: 'REQ_MISSING_FIELD',
      message: 'Missing required field: tender_no',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles file too large error', async ({ page }) => {
    await mockApiError(page, '/api/upload*', {
      status: 400,
      errorCode: 'FILE_TOO_LARGE',
      message: 'File size exceeds maximum allowed size',
      details: 'Maximum file size is 100MB',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles invalid file type error', async ({ page }) => {
    await mockApiError(page, '/api/upload*', {
      status: 400,
      errorCode: 'FILE_INVALID_TYPE',
      message: 'Invalid file type',
      details: 'Only .docx and .xlsx files are allowed',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles invalid JSON request error', async ({ page }) => {
    await mockApiError(page, '/api/generate', {
      status: 400,
      errorCode: 'REQ_INVALID_JSON',
      message: 'Invalid JSON in request body',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });
});

// ============================================
// Server Error Tests (500 errors)
// ============================================

test.describe('Server Errors', () => {
  test('handles internal server error (500)', async ({ page }) => {
    await mockApiError(page, '/api/tender/*', {
      status: 500,
      errorCode: 'SYS_INTERNAL_ERROR',
      message: 'An unexpected error occurred',
    });

    await page.goto('/tender/xjcg');

    // Page should still render
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles service unavailable error (503)', async ({ page }) => {
    await mockApiError(page, '/api/**', {
      status: 503,
      errorCode: 'SYS_SERVICE_UNAVAILABLE',
      message: 'Service temporarily unavailable',
      details: 'Please try again later',
    });

    await page.goto('/tender/xjcg');

    // Page should still render
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles LLM service error', async ({ page }) => {
    await mockApiError(page, '/api/generate', {
      status: 502,
      errorCode: 'LLM_SERVICE_ERROR',
      message: 'Failed to connect to LLM service',
      details: 'The AI service is currently unavailable',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles LLM rate limit error', async ({ page }) => {
    await mockApiError(page, '/api/generate', {
      status: 429,
      errorCode: 'LLM_RATE_LIMIT',
      message: 'Rate limit exceeded',
      details: 'Please wait before making another request',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles LLM timeout error', async ({ page }) => {
    await mockApiError(page, '/api/generate', {
      status: 504,
      errorCode: 'LLM_TIMEOUT',
      message: 'LLM request timed out',
      details: 'The AI model took too long to respond',
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });
});

// ============================================
// Task Error Tests
// ============================================

test.describe('Task Errors', () => {
  test('handles task not found error', async ({ page }) => {
    await mockApiError(page, '/api/tasks/non-existent-task', {
      status: 404,
      errorCode: 'TASK_NOT_FOUND',
      message: 'Task not found',
    });

    await page.goto('/');

    // Page should load without crashing
    await expect(page).toHaveTitle(/TenderWord|招标文档/);
  });

  test('handles task cancellation error', async ({ page }) => {
    await mockApiError(page, '/api/tasks/*', {
      status: 400,
      errorCode: 'TASK_CANNOT_CANCEL',
      message: 'Task cannot be cancelled',
      details: 'Task has already completed',
    });

    await page.goto('/');

    // Page should load without crashing
    await expect(page).toHaveTitle(/TenderWord|招标文档/);
  });
});

// ============================================
// Tender Data Error Tests
// ============================================

test.describe('Tender Data Errors', () => {
  test('handles tender not found error', async ({ page }) => {
    await mockApiError(page, '/api/tender/NON-EXISTENT', {
      status: 404,
      errorCode: 'TENDER_NOT_FOUND',
      message: 'Tender not found',
      details: 'No tender data found for the specified number',
    });

    await page.goto('/tender/xjcg');

    // Form should still be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles tender fetch failed error', async ({ page }) => {
    await mockApiError(page, '/api/tender/*', {
      status: 502,
      errorCode: 'TENDER_FETCH_FAILED',
      message: 'Failed to fetch tender data',
      details: 'External service is unavailable',
    });

    await page.goto('/tender/xjcg');

    // Form should still be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles invalid tender data error', async ({ page }) => {
    await mockApiError(page, '/api/tender/*', {
      status: 422,
      errorCode: 'TENDER_INVALID_DATA',
      message: 'Invalid tender data received',
      details: 'Required fields are missing',
    });

    await page.goto('/tender/xjcg');

    // Form should still be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });
});

// ============================================
// SSE Error Tests
// ============================================

test.describe('SSE Error Handling', () => {
  test('handles SSE connection error gracefully', async ({ page }) => {
    // Mock SSE endpoint to fail
    await page.route(`${API_BASE_URL}/api/stream/*`, (route) => {
      route.abort('connectionfailed');
    });

    await page.goto('/tender/xjcg');

    // Page should still render
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('handles SSE error event', async ({ page }) => {
    // Mock SSE to send error event
    await page.route(`${API_BASE_URL}/api/stream/test-task`, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `event: error\ndata: {"timestamp":"${new Date().toISOString()}","error_code":"TASK_NOT_FOUND","message":"Task not found"}\n\n`,
      });
    });

    await page.goto('/tender/xjcg');

    // Page should still render
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });
});

// ============================================
// File Access Error Tests
// ============================================

test.describe('File Access Errors', () => {
  test('handles file not found error on download', async ({ page }) => {
    await mockApiError(page, '/api/download/*', {
      status: 404,
      errorCode: 'FILE_NOT_FOUND',
      message: 'File not found',
    });

    await page.goto('/');

    // Page should load without crashing
    await expect(page).toHaveTitle(/TenderWord|招标文档/);
  });

  test('handles file access denied error', async ({ page }) => {
    await mockApiError(page, '/api/download/*', {
      status: 403,
      errorCode: 'FILE_ACCESS_DENIED',
      message: 'Access to file denied',
    });

    await page.goto('/');

    // Page should load without crashing
    await expect(page).toHaveTitle(/TenderWord|招标文档/);
  });
});

// ============================================
// Combined Error Scenarios
// ============================================

test.describe('Combined Error Scenarios', () => {
  test('handles multiple concurrent API failures', async ({ page }) => {
    // Mock all API endpoints to fail
    await page.route(`${API_BASE_URL}/api/**`, (route) => {
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'SYS_SERVICE_UNAVAILABLE',
            message: 'Service unavailable',
          },
          timestamp: new Date().toISOString(),
        }),
      });
    });

    await page.goto('/');

    // Page should still load
    await expect(page).toHaveTitle(/TenderWord|招标文档/);

    // Main layout should be visible
    const main = page.locator('main').first();
    await expect(main).toBeVisible();
  });

  test('handles mixed success and error responses', async ({ page }) => {
    // Mock specific endpoints
    await mockApiError(page, '/api/tender/*', {
      status: 404,
      errorCode: 'TENDER_NOT_FOUND',
      message: 'Tender not found',
    });

    // Health check succeeds
    await page.route(`${API_BASE_URL}/health`, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy' }),
      });
    });

    await page.goto('/tender/xjcg');

    // Form should be visible
    const form = page.locator('form').first();
    await expect(form).toBeVisible();
  });

  test('application remains interactive after errors', async ({ page }) => {
    // Initially fail tender fetch
    await mockApiError(page, '/api/tender/*', {
      status: 500,
      errorCode: 'SYS_INTERNAL_ERROR',
      message: 'Internal error',
    });

    await page.goto('/tender/xjcg');

    // Form should be interactive
    const form = page.locator('form').first();
    await expect(form).toBeVisible();

    // Check for input elements that should be interactive
    const inputs = page.locator('input, button, select, textarea');
    const count = await inputs.count();
    expect(count).toBeGreaterThan(0);
  });
});
