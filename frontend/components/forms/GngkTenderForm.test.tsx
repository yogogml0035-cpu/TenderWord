import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { GngkTenderForm, type GngkTenderFormData } from './GngkTenderForm';
import type { TenderData } from '@/types/api';

// Mock child components
jest.mock('./TenderNoInput', () => ({
  TenderNoInput: ({
    value,
    onChange,
    onDataFetched,
    required,
    disabled,
  }: {
    value: string;
    onChange: (value: string) => void;
    onDataFetched?: (data: TenderData) => void;
    required?: boolean;
    disabled?: boolean;
  }) => (
    <div data-testid="tender-no-input">
      <label>
        招标编号
        {required && <span className="text-red-500">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="请输入招标编号"
        data-testid="tender-no-input-field"
        disabled={disabled}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (onDataFetched) {
            onDataFetched({
              project_name: '测试项目',
              project_number: 'TEST-001',
              project_content: '测试内容',
              bzj_rule: '测试规则',
              buyer_name: '测试采购人',
              project_zbr_xbr: '张三',
              zbr_xbr_tel: '13800138000',
              zbr_pinyin: 'zhangsan',
              shell_start_date: '2024-01-01',
              shell_end_date: '2024-12-31',
              submit_date: '2024-12-31',
              platform: '测试平台',
              service_fee: '1000',
            } as TenderData);
          }
        }}
        data-testid="fetch-tender-btn"
      >
        获取信息
      </button>
    </div>
  ),
}));

jest.mock('./FileUploader', () => ({
  FileUploader: ({
    label,
    onUpload,
    onFilesChange,
    multiple,
    fileType,
    disabled,
  }: {
    label: string;
    onUpload?: (files: { file_path: string; original_name: string }[]) => void;
    onFilesChange?: (files: { file_path: string; original_name: string }[]) => void;
    multiple?: boolean;
    fileType?: string;
    disabled?: boolean;
  }) => (
    <div data-testid={`file-uploader-${fileType || 'default'}`}>
      <span>{label}</span>
      <input
        type="file"
        multiple={multiple}
        data-testid={`file-input-${fileType || 'default'}`}
        disabled={disabled}
        onChange={(e) => {
          if ((onUpload || onFilesChange) && e.target.files) {
            const files = Array.from(e.target.files).map((file, index) => ({
              file_path: `/uploads/${file.name}`,
              original_name: file.name,
              id: `file-${index}`,
              file: file,
              file_name: file.name,
              size: file.size,
              upload_time: new Date().toISOString(),
            }));
            onUpload?.(files);
            onFilesChange?.(files);
          }
        }}
      />
    </div>
  ),
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  AlertCircle: () => <span data-testid="alert-circle-icon">!</span>,
}));

describe('GngkTenderForm', () => {
  const mockOnSubmit = jest.fn();
  const mockTenderData: TenderData = {
    project_name: '测试国内公开招标项目',
    project_number: 'GNGK-2024-001',
    project_content: '测试项目内容',
    bzj_rule: '测试保证金规则',
    buyer_name: '测试采购单位',
    project_zbr_xbr: '李四',
    zbr_xbr_tel: '13900139000',
    zbr_pinyin: 'lisi',
    shell_start_date: '2024-01-01',
    shell_end_date: '2024-12-31',
    submit_date: '2024-12-31',
    platform: '测试平台',
    service_fee: '2000',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ==========================================
  // Basic Rendering Tests
  // ==========================================
  describe('Rendering', () => {
    it('should render all form sections', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.getByText('招标信息')).toBeInTheDocument();
      expect(screen.getByText('文件上传')).toBeInTheDocument();
      expect(screen.getByText('高级设置（可选）')).toBeInTheDocument();
    });

    it('should render TenderNoInput component', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);
      expect(screen.getByTestId('tender-no-input')).toBeInTheDocument();
    });

    it('should not render the model selector inside the form panel', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);
      expect(screen.queryByTestId('model-select')).not.toBeInTheDocument();
    });

    it('should render all file uploaders', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.getByText('送审稿文件（可选）')).toBeInTheDocument();
      expect(screen.getByText('清洁稿文件（可选）')).toBeInTheDocument();
      expect(screen.getByText('技术参数文件（必填）')).toBeInTheDocument();
    });

    it('should render submit buttons', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);
      // Note: Component has duplicate submit buttons (potential bug)
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      expect(submitButtons.length).toBeGreaterThan(0);
    });

    it('should apply custom className', () => {
      const { container } = render(
        <GngkTenderForm onSubmit={mockOnSubmit} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  // ==========================================
  // Advanced Settings Tests (GNGK-specific)
  // ==========================================
  describe('Advanced Settings', () => {
    it('should render insertion config labels', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.getByText('插入位置前文本')).toBeInTheDocument();
      expect(screen.getByText('插入位置后文本')).toBeInTheDocument();
    });

    it('should have default insertion config values for GNGK', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Query inputs by placeholder since labels are not properly linked
      const inputs = screen.getAllByRole('textbox');
      const beforeInput = inputs.find((input) => input.getAttribute('value')?.includes('第三章'));
      const afterInput = inputs.find((input) => input.getAttribute('value')?.includes('第四章'));

      expect(beforeInput).toHaveValue('第三章 招标内容及要求');
      expect(afterInput).toHaveValue('第四章 投标文件有关格式');
    });

    it('should allow changing insertion config values', async () => {
      const user = userEvent.setup();
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Query inputs by value content
      const inputs = screen.getAllByRole('textbox');
      const beforeInput = inputs.find((input) => input.getAttribute('value')?.includes('第三章'));
      const afterInput = inputs.find((input) => input.getAttribute('value')?.includes('第四章'));

      await user.clear(beforeInput!);
      await user.type(beforeInput!, '新的前文本');

      await user.clear(afterInput!);
      await user.type(afterInput!, '新的后文本');

      expect(beforeInput).toHaveValue('新的前文本');
      expect(afterInput).toHaveValue('新的后文本');
    });
  });

  // ==========================================
  // Tender Data Display Tests
  // ==========================================
  describe('Tender Data Display', () => {
    it('should not display tender data initially', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);
      expect(screen.queryByText('项目名称')).not.toBeInTheDocument();
    });

    it('should display tender data after fetching', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');

      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
        expect(screen.getByText('测试采购人')).toBeInTheDocument();
        expect(screen.getByText('张三')).toBeInTheDocument();
        expect(screen.getAllByText('2024-12-31').length).toBeGreaterThan(0);
      });
    });

    it('should display tender data with initial data prop', () => {
      render(
        <GngkTenderForm
          onSubmit={mockOnSubmit}
          initialTenderNo="GNGK-2024-001"
          initialTenderData={mockTenderData}
        />
      );

      expect(screen.getByText('测试国内公开招标项目')).toBeInTheDocument();
      expect(screen.getByText('测试采购单位')).toBeInTheDocument();
      expect(screen.getByText('李四')).toBeInTheDocument();
      expect(screen.getAllByText('2024-12-31').length).toBeGreaterThan(0);
    });
  });

  // ==========================================
  // Form Validation Tests
  // ==========================================
  describe('Form Validation', () => {
    it('should show error when submitting without tender number', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should show error when submitting without tender data', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByTestId('tender-no-input-field');
      fireEvent.change(input, { target: { value: 'GNGK-2024-001' } });

      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请先获取招标信息')).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should show error when submitting without param files', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Fill tender info
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      // Upload clean draft to satisfy "at least one of origin/clean"
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Submit without files
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请上传至少一个技术参数文件')).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should show error when submitting without origin and clean files', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      const paramInput = screen.getByTestId('file-input-params');
      const file = new File(['test'], 'params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [file] } });

      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('清洁稿和送审稿至少要上传一个文件')).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should clear error when fetching tender data', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Trigger validation error
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
      });

      // Fetch tender data to clear error
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.queryByText('请输入招标编号')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================
  // Form Submission Tests
  // ==========================================
  describe('Form Submission', () => {
    it('should call onSubmit with correct form data', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Fill tender info
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      // Upload param file
      const paramInput = screen.getByTestId('file-input-params');
      const file = new File(['test content'], 'params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [file] } });
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Submit form
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      });

      const submittedData = mockOnSubmit.mock.calls[0][0] as GngkTenderFormData;
      expect(submittedData.tender_no).toBe('GNGK-2024-001');
      expect(submittedData.tender_data.project_name).toBe('测试项目');
      expect(submittedData.model).toBe('deepseek');
      expect(submittedData.files.tender_params).toHaveLength(1);
    });

    it('should include insertion config in submission data', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Fill tender info
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      // Upload param file
      const paramInput = screen.getByTestId('file-input-params');
      const file = new File(['test'], 'params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [file] } });
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Submit
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });

      const submittedData = mockOnSubmit.mock.calls[0][0] as GngkTenderFormData;
      expect(submittedData.insertion_config).toEqual({
        before_text: '第三章 招标内容及要求',
        after_text: '第四章 投标文件有关格式',
      });
    });

    it('should include model selection in submission data', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} initialDraft={{ model: 'qwen' }} />);

      // Fill tender info
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      // Upload param file
      const paramInput = screen.getByTestId('file-input-params');
      const file = new File(['test'], 'params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [file] } });
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Submit
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });

      const submittedData = mockOnSubmit.mock.calls[0][0] as GngkTenderFormData;
      expect(submittedData.model).toBe('qwen');
    });
  });

  // ==========================================
  // Submit Button State Tests
  // ==========================================
  describe('Submit Button State', () => {
    it('should show loading state when isSubmitting is true', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);

      expect(screen.getByText('提交中...')).toBeInTheDocument();
      const buttons = screen.getAllByRole('button');
      const submitButton = buttons.find((btn) => btn.getAttribute('type') === 'submit');
      expect(submitButton).toBeDisabled();
    });

    it('should show normal state when isSubmitting is false', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} isSubmitting={false} />);

      expect(screen.getAllByText('开始生成').length).toBeGreaterThan(0);
    });

    it('should disable button when isSubmitting is true', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);
      const buttons = screen.getAllByRole('button');
      const submitButton = buttons.find((btn) => btn.getAttribute('type') === 'submit');
      expect(submitButton).toBeDisabled();
    });

    it('should disable form controls when isSubmitting is true', () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);

      expect(screen.getByTestId('tender-no-input-field')).toBeDisabled();
      expect(screen.getByTestId('fetch-tender-btn')).toBeDisabled();
      expect(screen.getByTestId('file-input-origin_tender')).toBeDisabled();
      expect(screen.getByTestId('file-input-clean_draft')).toBeDisabled();
      expect(screen.getByTestId('file-input-params')).toBeDisabled();
      expect(screen.getByPlaceholderText('插入位置前的章节标题')).toBeDisabled();
      expect(screen.getByPlaceholderText('插入位置后的章节标题')).toBeDisabled();
    });

    it('should switch the primary button to cancel generation when cancellation is available', async () => {
      const user = userEvent.setup();
      const mockOnCancel = jest.fn();

      render(
        <GngkTenderForm
          onSubmit={mockOnSubmit}
          isSubmitting={true}
          canCancel={true}
          onCancel={mockOnCancel}
        />
      );

      const cancelButton = screen.getByRole('button', { name: '取消生成' });
      expect(cancelButton).toBeEnabled();

      await user.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });
  });

  // ==========================================
  // Error Display Tests
  // ==========================================
  describe('Error Display', () => {
    it('should display error message with AlertCircle icon', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Trigger error
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId('alert-circle-icon')).toBeInTheDocument();
        expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
      });
    });

    it('should hide error after successful fetch', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Trigger error first
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
      });

      // Fetch tender data to clear error
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.queryByText('请输入招标编号')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================
  // File Upload Tests
  // ==========================================
  describe('File Upload', () => {
    it('should accept optional origin tender file', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const originInput = screen.getByTestId('file-input-origin_tender');
      expect(originInput).toBeInTheDocument();
    });

    it('should accept optional clean draft file', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      const cleanInput = screen.getByTestId('file-input-clean_draft');
      expect(cleanInput).toBeInTheDocument();
    });

    it('should require param files for submission', async () => {
      render(<GngkTenderForm onSubmit={mockOnSubmit} />);

      // Fill tender info
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Submit without param files
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('请上传至少一个技术参数文件')).toBeInTheDocument();
      });
    });
  });

  // ==========================================
  // Integration Tests
  // ==========================================
  describe('Integration', () => {
    it('should complete full form submission flow', async () => {
      const mockSubmit = jest.fn().mockResolvedValue(undefined);
      render(<GngkTenderForm onSubmit={mockSubmit} initialDraft={{ model: 'doubao' }} />);

      // Step 1: Enter tender number
      const tenderInput = screen.getByTestId('tender-no-input-field');
      await userEvent.type(tenderInput, 'GNGK-2024-001');

      // Step 2: Fetch tender data
      const fetchBtn = screen.getByTestId('fetch-tender-btn');
      fireEvent.click(fetchBtn);

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      // Step 3: Upload param file
      const paramInput = screen.getByTestId('file-input-params');
      const paramFile = new File(['params content'], 'tech_params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [paramFile] } });
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      // Step 4: Submit
      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledTimes(1);
      });

      const submittedData = mockSubmit.mock.calls[0][0] as GngkTenderFormData;
      expect(submittedData).toMatchObject({
        tender_no: 'GNGK-2024-001',
        model: 'doubao',
      });
    });

    it('should handle async onSubmit', async () => {
      const mockAsyncSubmit = jest
        .fn()
        .mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));
      render(<GngkTenderForm onSubmit={mockAsyncSubmit} />);

      // Setup form
      const input = screen.getByTestId('tender-no-input-field');
      await userEvent.type(input, 'GNGK-2024-001');
      fireEvent.click(screen.getByTestId('fetch-tender-btn'));

      await waitFor(() => {
        expect(screen.getByText('测试项目')).toBeInTheDocument();
      });

      const paramInput = screen.getByTestId('file-input-params');
      const file = new File(['test'], 'params.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(paramInput, { target: { files: [file] } });
      const cleanInput = screen.getByTestId('file-input-clean_draft');
      const cleanFile = new File(['clean'], 'clean.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      fireEvent.change(cleanInput, { target: { files: [cleanFile] } });

      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      fireEvent.click(submitButtons[0]);

      await waitFor(() => {
        expect(mockAsyncSubmit).toHaveBeenCalled();
      });
    });
  });
});
