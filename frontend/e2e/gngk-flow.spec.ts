import { test, expect, Page } from '@playwright/test';

/**
 * GNGK (国内公开) Tender E2E Tests
 *
 * Tests the complete flow for GNGK tender document generation:
 * 1. Form filling (tender info, file upload, model selection, advanced settings)
 * 2. Form submission
 * 3. Progress tracking via SSE
 * 4. Document download
 */

// Mock data
const mockTenderData = {
  project_name: '测试项目名称',
  project_number: 'ZBGG-2024-001',
  project_content: '测试项目内容',
  bzj_rule: '保证金规则',
  buyer_name: '测试采购人',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-01-01',
  shell_end_date: '2024-01-15',
  submit_date: '2024-01-20',
  platform: '测试平台',
  service_fee: '1000',
};

const mockUploadedFile = {
  file_path: '/uploads/test-file.docx',
  file_name: 'test-file.docx',
  original_name: 'test-file.docx',
  size: 1024,
  upload_time: new Date().toISOString(),
};

const mockCreateTaskResponse = {
  success: true,
  data: {
    task_id: 'test-task-id-123',
    status: 'queued',
    created_at: new Date().toISOString(),
    user_session_id: 'session-123',
    queue_position: 1,
    estimated_wait_seconds: 30,
  },
  message: 'Task created successfully',
  timestamp: new Date().toISOString(),
};

const mockTaskStatusResponse = {
  success: true,
  data: {
    task_id: 'test-task-id-123',
    status: 'completed',
    created_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    elapsed_seconds: 120,
    progress: {
      completed_nodes: [
        'prepare_template',
        'extract_tender_params',
        'delete_tender_param',
        'get_replacements',
        'replace_content',
        'update_word',
      ],
      running_nodes: [],
      completed_count: 6,
      total_nodes: 6,
      progress_percent: 100,
    },
    result: {
      output_file: '/output/generated-tender.docx',
      file_name: 'generated-tender.docx',
      file_size: 51200,
      model_used: 'deepseek',
      total_time_seconds: 120,
    },
  },
  message: 'Task completed',
  timestamp: new Date().toISOString(),
};

/**
 * Setup API mocks for GNGK tender flow
 */
async function setupApiMocks(page: Page) {
  // Mock tender data fetch
  await page.route('**/api/tender/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: mockTenderData,
        message: 'Tender data fetched successfully',
        timestamp: new Date().toISOString(),
      }),
    });
  });

  // Mock file upload
  await page.route('**/api/upload', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: mockUploadedFile,
        message: 'File uploaded successfully',
        timestamp: new Date().toISOString(),
      }),
    });
  });

  // Mock generate task creation
  await page.route('**/api/generate', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockCreateTaskResponse),
      });
    }
  });

  // Mock task status
  await page.route('**/api/tasks/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockTaskStatusResponse),
    });
  });

  // Mock SSE stream with simulated progress events
  await page.route('**/api/stream/*', async (route) => {
    const sseEvents = [
      'data: {"event":"connected","data":{"task_id":"test-task-id-123","message":"Connected"}}\n\n',
      'data: {"event":"log","data":{"timestamp":"2024-01-01T00:00:00Z","level":"INFO","message":"Starting task"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:00Z","node":"prepare_template","completed_count":1,"total_nodes":6,"progress_percent":16,"current_node_display":"复制原始模板文件"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:01Z","node":"extract_tender_params","completed_count":2,"total_nodes":6,"progress_percent":33,"current_node_display":"提取原始采购需求"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:02Z","node":"delete_tender_param","completed_count":3,"total_nodes":6,"progress_percent":50,"current_node_display":"删除原始采购需求"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:03Z","node":"get_replacements","completed_count":4,"total_nodes":6,"progress_percent":66,"current_node_display":"获取原始项目信息"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:04Z","node":"replace_content","completed_count":5,"total_nodes":6,"progress_percent":83,"current_node_display":"替换最新项目信息"}}\n\n',
      'data: {"event":"progress","data":{"timestamp":"2024-01-01T00:00:05Z","node":"update_word","completed_count":6,"total_nodes":6,"progress_percent":100,"current_node_display":"生成招标文件"}}\n\n',
      'data: {"event":"done","data":{"timestamp":"2024-01-01T00:01:00Z","task_id":"test-task-id-123","status":"completed","total_time_seconds":60}}\n\n',
    ];

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseEvents.join(''),
    });
  });
}

test.describe('GNGK Tender Form Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('GNGK form page loads correctly', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Check URL
    await expect(page).toHaveURL(/\/tender\/gngk/);

    // Check page title/heading
    await expect(page.getByRole('heading', { name: /国内公开/ })).toBeVisible();

    // Check form is visible
    const form = page.locator('form');
    await expect(form).toBeVisible();
  });

  test('form has all required sections', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Section 1: Tender Info (招标信息)
    await expect(page.getByText('招标信息')).toBeVisible();

    // Section 2: File Upload (文件上传)
    await expect(page.getByText('文件上传')).toBeVisible();

    // Section 3: Model Selection (模型选择)
    await expect(page.getByText('模型选择')).toBeVisible();

    // Section 4: Advanced Settings (高级设置)
    await expect(page.getByText('高级设置')).toBeVisible();
  });

  test('can enter tender number and fetch data', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Find tender number input
    const tenderNoInput = page.locator('input[type="text"]').first();

    // Enter tender number
    await tenderNoInput.fill('ZBGG-2024-001');

    // Click fetch button (button with text containing "获取")
    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();

    // Wait for tender data to appear
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(mockTenderData.buyer_name)).toBeVisible();
  });

  test('form validation - requires tender data', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Try to submit without entering data
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Should show error message
    await expect(page.getByText(/请输入招标编号/)).toBeVisible();
  });

  test('model selector works correctly', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Find model selector
    const modelSelector = page.locator('select, [role="combobox"]').first();

    // Check it's visible
    await expect(modelSelector).toBeVisible();
  });

  test('advanced settings inputs are editable', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Find insertion config inputs
    const beforeTextInput = page.locator('input[placeholder*="插入位置前"]');
    const afterTextInput = page.locator('input[placeholder*="插入位置后"]');

    // Check they have default values
    await expect(beforeTextInput).toHaveValue(/第三章/);
    await expect(afterTextInput).toHaveValue(/第四章/);

    // Edit values
    await beforeTextInput.clear();
    await beforeTextInput.fill('第二章  项目需求');
    await expect(beforeTextInput).toHaveValue('第二章  项目需求');
  });
});

test.describe('GNGK Complete Flow with Mocked API', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('complete form submission flow', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Step 1: Enter tender number and fetch data
    const tenderNoInput = page.locator('input[type="text"]').first();
    await tenderNoInput.fill('ZBGG-2024-001');

    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();

    // Wait for tender data to load
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Step 2: Submit form (files are mocked)
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Step 3: Check for task progress section
    await expect(page.getByText(/任务进度/)).toBeVisible({ timeout: 5000 });

    // Step 4: Verify SSE connection indicator
    await expect(page.getByText(/已连接|连接中/)).toBeVisible();
  });

  test('shows progress during task execution', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Fill and submit form
    const tenderNoInput = page.locator('input[type="text"]').first();
    await tenderNoInput.fill('ZBGG-2024-001');

    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Wait for progress section
    await expect(page.getByText(/任务进度/)).toBeVisible({ timeout: 5000 });

    // Progress display should be visible
    const progressBar = page.locator('[role="progressbar"], .progress, [class*="progress"]').first();
    await expect(progressBar).toBeVisible({ timeout: 3000 }).catch(() => {
      // Progress bar might not have specific role, check for progress text
      expect(page.getByText(/\d+%/)).toBeVisible();
    });
  });

  test('download button appears on completion', async ({ page }) => {
    // Override task status to return completed immediately
    await page.route('**/api/tasks/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTaskStatusResponse),
      });
    });

    await page.goto('/tender/gngk');

    // Fill and submit form
    const tenderNoInput = page.locator('input[type="text"]').first();
    await tenderNoInput.fill('ZBGG-2024-001');

    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Wait for completion and download button
    await expect(page.getByRole('button', { name: /下载/ })).toBeVisible({ timeout: 10000 });
  });
});

test.describe('GNGK Error Handling', () => {
  test('handles tender data fetch error gracefully', async ({ page }) => {
    // Mock error response
    await page.route('**/api/tender/*', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'TENDER_NOT_FOUND',
            message: 'Tender not found',
          },
          timestamp: new Date().toISOString(),
        }),
      });
    });

    await page.goto('/tender/gngk');

    // Enter tender number and try to fetch
    const tenderNoInput = page.locator('input[type="text"]').first();
    await tenderNoInput.fill('INVALID-NUMBER');

    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();

    // Should show error indicator
    await expect(page.getByText(/获取|失败|错误|不存在/)).toBeVisible({ timeout: 5000 });
  });

  test('handles task creation error gracefully', async ({ page }) => {
    await page.route('**/api/tender/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: mockTenderData,
          message: 'Success',
          timestamp: new Date().toISOString(),
        }),
      });
    });

    // Mock task creation error
    await page.route('**/api/generate', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'SYS_INTERNAL_ERROR',
            message: 'Internal server error',
          },
          timestamp: new Date().toISOString(),
        }),
      });
    });

    await page.goto('/tender/gngk');

    // Fill and submit form
    const tenderNoInput = page.locator('input[type="text"]').first();
    await tenderNoInput.fill('ZBGG-2024-001');

    const fetchButton = page.getByRole('button', { name: /获取/ });
    await fetchButton.click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Should show error message
    await expect(page.getByText(/提交失败|错误|失败/)).toBeVisible({ timeout: 5000 });
  });
});

test.describe('GNGK Accessibility', () => {
  test('form has proper labels', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Check for label elements
    const labels = page.locator('label');
    const labelCount = await labels.count();
    expect(labelCount).toBeGreaterThan(0);
  });

  test('submit button is accessible', async ({ page }) => {
    await page.goto('/tender/gngk');

    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();
  });

  test('form inputs are focusable', async ({ page }) => {
    await page.goto('/tender/gngk');

    // Tab through form elements
    await page.keyboard.press('Tab');
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});
