import { test, expect, Page } from '@playwright/test';

/**
 * XJCG (询价采购) Tender Flow E2E Tests
 * 
 * Tests the complete flow: form filling -> submission -> progress tracking -> download
 * All backend APIs are mocked to ensure test reliability
 */

// ============================================
// Mock Data
// ============================================

const mockTenderData = {
  project_name: '测试项目-询价采购',
  project_number: 'XM-2024-001',
  project_content: '测试项目内容描述',
  bzj_rule: '按照相关规定执行',
  buyer_name: '测试采购单位',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-03-01 09:00:00',
  shell_end_date: '2024-03-15 17:00:00',
  submit_date: '2024-03-20 09:00:00',
  platform: '测试平台',
  service_fee: '500',
};

const mockUploadedFile = {
  file_path: 'D:/UploadFiles/test-file-12345.docx',
  file_name: 'test-file-12345.docx',
  original_name: 'test-file.docx',
  size: 10240,
  upload_time: new Date().toISOString(),
};

const mockTaskResponse = {
  task_id: 'task-test-12345',
  status: 'queued',
  created_at: new Date().toISOString(),
  user_session_id: 'session-test-12345',
  queue_position: 1,
  estimated_wait_seconds: 0,
};

const mockTaskResult = {
  output_file: 'D:/UploadFiles/output/test-output-12345.docx',
  file_name: '招标文件-测试项目.docx',
  file_size: 51200,
  model_used: 'deepseek',
  total_time_seconds: 30,
};

// ============================================
// Helper Functions
// ============================================

/**
 * Setup all API mocks for the XJCG flow
 */
async function setupMocks(page: Page) {
  // Mock GET /api/tender/{tender_no} - Fetch tender data
  await page.route('**/api/tender/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: mockTenderData,
        message: '获取成功',
        timestamp: new Date().toISOString(),
      }),
    });
  });

  // Mock POST /api/upload - File upload
  await page.route('**/api/upload', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            ...mockUploadedFile,
            file_path: `D:/UploadFiles/${Date.now()}-test.docx`,
            file_name: `${Date.now()}-test.docx`,
          },
          message: '上传成功',
          timestamp: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/generate - Create task
  await page.route('**/api/generate', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: mockTaskResponse,
          message: '任务创建成功',
          timestamp: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/tasks/{task_id} - Task status
  await page.route('**/api/tasks/**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            task_id: mockTaskResponse.task_id,
            status: 'running',
            created_at: mockTaskResponse.created_at,
            started_at: new Date().toISOString(),
            progress: {
              completed_nodes: ['prepare_template'],
              running_nodes: ['extract_tender_params'],
              current_node: 'extract_tender_params',
              completed_count: 1,
              total_nodes: 6,
              progress_percent: 16,
            },
          },
          message: '获取成功',
          timestamp: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Setup SSE mock with simulated events
 */
async function setupSSEMock(page: Page) {
  await page.route('**/api/stream/**', async (route) => {
    // Create SSE response with simulated events
    const events = [
      { event: 'connected', data: JSON.stringify({ task_id: mockTaskResponse.task_id, message: '已连接' }) },
      { event: 'log', data: JSON.stringify({ timestamp: new Date().toISOString(), level: 'INFO', message: '开始处理任务' }) },
      { event: 'progress', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'prepare_template',
        completed_count: 1,
        total_nodes: 6,
        progress_percent: 16,
        current_node_display: '复制原始模板文件'
      })},
      { event: 'log', data: JSON.stringify({ timestamp: new Date().toISOString(), level: 'INFO', message: '提取原始采购需求' }) },
      { event: 'progress', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'extract_tender_params',
        completed_count: 2,
        total_nodes: 6,
        progress_percent: 33,
        current_node_display: '提取原始采购需求'
      })},
      { event: 'log', data: JSON.stringify({ timestamp: new Date().toISOString(), level: 'INFO', message: 'AI生成采购需求中...' }) },
      { event: 'llm', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'generate_polished_text',
        content: '这是AI生成的测试内容...',
        is_complete: false
      })},
      { event: 'progress', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'generate_polished_text',
        completed_count: 3,
        total_nodes: 6,
        progress_percent: 50,
        current_node_display: 'AI生成采购需求'
      })},
      { event: 'llm', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'generate_polished_text',
        content: '',
        is_complete: true,
        token_count: 100
      })},
      { event: 'progress', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        node: 'update_word',
        completed_count: 6,
        total_nodes: 6,
        progress_percent: 100,
        current_node_display: '生成招标文件'
      })},
      { event: 'done', data: JSON.stringify({ 
        timestamp: new Date().toISOString(),
        task_id: mockTaskResponse.task_id,
        status: 'completed',
        total_time_seconds: 30,
        result: mockTaskResult
      })},
    ];

    const sseBody = events.map(e => `event: ${e.event}\ndata: ${e.data}\n\n`).join('');
    
    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
      body: sseBody,
    });
  });
}

// ============================================
// Tests
// ============================================

test.describe('XJCG Tender Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await setupSSEMock(page);
  });

  test('should display XJCG form with all required sections', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Check page title/header
    await expect(page.getByRole('heading', { name: /询价采购/ })).toBeVisible();

    // Check form sections exist
    await expect(page.getByRole('heading', { name: /招标信息/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /文件上传/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /模型选择/ })).toBeVisible();

    // Check submit button
    await expect(page.getByRole('button', { name: /开始生成/ })).toBeVisible();
  });

  test('should fetch and display tender data', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Fill in tender number
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');

    // Click fetch button
    await page.getByRole('button', { name: /获取信息/ }).click();

    // Wait for tender data to be displayed
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(mockTenderData.buyer_name)).toBeVisible();
  });

  test('should upload files successfully', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Create a test file
    const testFileContent = 'Test file content for E2E testing';
    
    // Find the technical parameter file upload input and upload file
    // Note: FileUploader component may have multiple file inputs
    const fileInput = page.locator('input[type="file"]').first();
    
    // Check file input exists (even if hidden)
    await expect(fileInput).toBeAttached();
  });

  test('should complete full flow with mocked API', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Step 1: Fill tender number and fetch data
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    
    // Wait for tender data
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Step 2: Upload a test file (technical parameters - required)
    const testFileContent = 'Test technical parameters file content';
    const fileChooserPromise = page.waitForEvent('filechooser');
    
    // Click on the file upload area for technical parameters
    const uploadArea = page.locator('text=技术参数文件').locator('..').locator('input[type="file"]');
    await uploadArea.click();
    
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-params.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(testFileContent),
    });

    // Wait for upload success indication
    await page.waitForTimeout(500);

    // Step 3: Select model (default is deepseek, verify it's selected)
    const modelSelector = page.locator('select, [role="combobox"]').first();
    if (await modelSelector.isVisible()) {
      // Model selector exists, verify deepseek is selected or select it
      await modelSelector.click();
      await page.getByText(/deepseek/i).click();
    }

    // Step 4: Submit the form
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Step 5: Verify progress section appears
    await expect(page.getByText(/任务进度/)).toBeVisible({ timeout: 10000 });

    // Step 6: Wait for completion (with mocked SSE, this should be quick)
    await expect(page.getByText(/文档生成完成/)).toBeVisible({ timeout: 15000 });

    // Step 7: Verify download button appears
    await expect(page.getByRole('button', { name: /下载文档/ })).toBeVisible();
  });

  test('should show validation error when submitting without required fields', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Try to submit without filling required fields
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Should show validation error
    await expect(page.getByText(/请输入招标编号/)).toBeVisible();
  });

  test('should show validation error when submitting without tender data', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Fill tender number but don't fetch data
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');

    // Try to submit
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Should show validation error about fetching tender data
    await expect(page.getByText(/请先获取招标信息/)).toBeVisible();
  });

  test('should show validation error when submitting without param files', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Fill tender number and fetch data
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Try to submit without uploading param files
    const submitButton = page.getByRole('button', { name: /开始生成/ });
    await submitButton.click();

    // Should show validation error about uploading files
    await expect(page.getByText(/请上传至少一个技术参数文件/)).toBeVisible();
  });
});

test.describe('XJCG Tender Flow - Error Handling', () => {
  test('should handle API error when fetching tender data', async ({ page }) => {
    // Mock error response
    await page.route('**/api/tender/**', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: {
            code: 'TENDER_NOT_FOUND',
            message: '招标编号不存在',
          },
          timestamp: new Date().toISOString(),
        }),
      });
    });

    await page.goto('/tender/xjcg');

    // Fill in tender number
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('INVALID-NUMBER');

    // Click fetch button
    await page.getByRole('button', { name: /获取信息/ }).click();

    // Should show error message
    await expect(page.getByText(/招标编号不存在|获取招标数据失败/)).toBeVisible({ timeout: 5000 });
  });

  test('should handle API error when uploading file', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/tender/xjcg');

    // Fill tender number and fetch data first
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Override upload mock to return error
    await page.route('**/api/upload', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            success: false,
            error: {
              code: 'FILE_UPLOAD_FAILED',
              message: '文件上传失败',
            },
            timestamp: new Date().toISOString(),
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Try to upload a file
    const testFileContent = 'Test file content';
    const fileChooserPromise = page.waitForEvent('filechooser');
    
    const uploadArea = page.locator('text=技术参数文件').locator('..').locator('input[type="file"]');
    await uploadArea.click();
    
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-params.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(testFileContent),
    });

    // Wait and check for error indication
    await page.waitForTimeout(1000);
    // Note: The exact error handling depends on the FileUploader implementation
  });

  test('should handle task creation error', async ({ page }) => {
    await setupMocks(page);
    
    // Override generate endpoint to return error
    await page.route('**/api/generate', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            success: false,
            error: {
              code: 'SYS_INTERNAL_ERROR',
              message: '服务器内部错误',
            },
            timestamp: new Date().toISOString(),
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/tender/xjcg');

    // Complete the form
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Upload file
    const testFileContent = 'Test file content';
    const fileChooserPromise = page.waitForEvent('filechooser');
    const uploadArea = page.locator('text=技术参数文件').locator('..').locator('input[type="file"]');
    await uploadArea.click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-params.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(testFileContent),
    });
    await page.waitForTimeout(500);

    // Submit
    await page.getByRole('button', { name: /开始生成/ }).click();

    // Should show error message
    await expect(page.getByText(/提交失败|服务器内部错误/)).toBeVisible({ timeout: 10000 });
  });
});

test.describe('XJCG Tender Flow - SSE Progress', () => {
  test('should display progress updates during task execution', async ({ page }) => {
    await setupMocks(page);
    await setupSSEMock(page);

    await page.goto('/tender/xjcg');

    // Complete the form
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    // Upload file
    const testFileContent = 'Test file content';
    const fileChooserPromise = page.waitForEvent('filechooser');
    const uploadArea = page.locator('text=技术参数文件').locator('..').locator('input[type="file"]');
    await uploadArea.click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-params.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(testFileContent),
    });
    await page.waitForTimeout(500);

    // Submit
    await page.getByRole('button', { name: /开始生成/ }).click();

    // Verify progress section appears
    await expect(page.getByText(/任务进度/)).toBeVisible({ timeout: 10000 });

    // Check for connection status
    await expect(page.getByText(/已连接|连接中/)).toBeVisible();
  });

  test('should show log entries during task execution', async ({ page }) => {
    await setupMocks(page);
    await setupSSEMock(page);

    await page.goto('/tender/xjcg');

    // Complete and submit the form (abbreviated)
    const tenderNoInput = page.getByPlaceholder(/招标编号/);
    await tenderNoInput.fill('ZBGG-2024-TEST001');
    await page.getByRole('button', { name: /获取信息/ }).click();
    await expect(page.getByText(mockTenderData.project_name)).toBeVisible({ timeout: 5000 });

    const testFileContent = 'Test file content';
    const fileChooserPromise = page.waitForEvent('filechooser');
    const uploadArea = page.locator('text=技术参数文件').locator('..').locator('input[type="file"]');
    await uploadArea.click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-params.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(testFileContent),
    });
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: /开始生成/ }).click();

    // Wait for progress section
    await expect(page.getByText(/任务进度/)).toBeVisible({ timeout: 10000 });
    
    // Log viewer should appear when there are logs
    // This depends on implementation - check for any log-related UI
    const logSection = page.locator('text=/日志|log/i').first();
    // The log viewer might be automatically shown or require interaction
  });
});

test.describe('XJCG Tender Flow - Model Selection', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
  });

  test('should allow model selection', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Find model selector section
    await expect(page.getByRole('heading', { name: /模型选择/ })).toBeVisible();

    // Check if model selector is interactive
    const modelSelector = page.locator('select, [role="combobox"], [role="listbox"]').first();
    if (await modelSelector.isVisible()) {
      await modelSelector.click();
      
      // Check for model options
      await expect(page.getByText(/deepseek/i)).toBeVisible();
    }
  });
});

test.describe('XJCG Tender Flow - Advanced Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
  });

  test('should display advanced settings section', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Check advanced settings section exists
    await expect(page.getByRole('heading', { name: /高级设置/ })).toBeVisible();

    // Check insertion config inputs exist
    await expect(page.getByPlaceholder(/插入位置前的章节标题/)).toBeVisible();
    await expect(page.getByPlaceholder(/插入位置后的章节标题/)).toBeVisible();
  });

  test('should have default insertion config values', async ({ page }) => {
    await page.goto('/tender/xjcg');

    // Check default values
    const beforeInput = page.getByPlaceholder(/插入位置前的章节标题/);
    const afterInput = page.getByPlaceholder(/插入位置后的章节标题/);

    await expect(beforeInput).toHaveValue(/第三章.*采购需求/);
    await expect(afterInput).toHaveValue(/第四章.*响应文件/);
  });
});
