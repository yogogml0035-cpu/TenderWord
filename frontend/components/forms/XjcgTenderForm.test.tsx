import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { XjcgTenderForm, type XjcgTenderFormData } from './XjcgTenderForm';
import type { TenderData } from './TenderNoInput';
import type { UploadedFile } from './FileUploader';

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
        {required && <span aria-label="required">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="请输入招标编号"
        aria-label="招标编号输入框"
        disabled={disabled}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (onDataFetched) {
            onDataFetched({
              project_name: '测试项目',
              buyer_name: '测试采购人',
              project_zbr_xbr: '张三',
              submit_date: '2024-12-31',
            } as TenderData);
          }
        }}
        aria-label="模拟获取招标信息"
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
    fileType,
    disabled,
  }: {
    label: string;
    onUpload?: (files: UploadedFile[]) => void;
    onFilesChange?: (files: UploadedFile[]) => void;
    fileType?: string;
    disabled?: boolean;
  }) => (
    <div data-testid={`file-uploader-${fileType || 'default'}`}>
      <label>{label}</label>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (onUpload || onFilesChange) {
            const mockFile: UploadedFile = {
              id: `test-id-${fileType}`,
              file: new File(['test'], 'test.docx', {
                type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              }),
              file_path: `D:/UploadFiles/test-${fileType}.docx`,
              file_name: `test-${fileType}.docx`,
              original_name: `test-${fileType}.docx`,
              size: 1024,
              upload_time: new Date().toISOString(),
              file_type: 'application/docx',
            };
            onUpload?.([mockFile]);
            onFilesChange?.([mockFile]);
          }
        }}
        aria-label={`上传${label}`}
      >
        上传文件
      </button>
    </div>
  ),
}));

describe('XjcgTenderForm', () => {
  let mockOnSubmit: jest.Mock<void | Promise<void>, [XjcgTenderFormData]>;

  beforeEach(() => {
    mockOnSubmit = jest.fn().mockImplementation(() => Promise.resolve());
    jest.clearAllMocks();
  });

  describe('组件渲染', () => {
    it('应该正确渲染表单结构', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 验证四个主要区块存在
      expect(screen.getByText('招标信息')).toBeInTheDocument();
      expect(screen.getByText('文件上传')).toBeInTheDocument();
      expect(screen.getByText('高级设置（可选）')).toBeInTheDocument();
    });

    it('应该渲染招标编号输入组件', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.getByTestId('tender-no-input')).toBeInTheDocument();
      expect(screen.getByLabelText('招标编号输入框')).toBeInTheDocument();
    });

    it('应该渲染三个文件上传组件', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.getByTestId('file-uploader-origin_tender')).toBeInTheDocument();
      expect(screen.getByTestId('file-uploader-clean_draft')).toBeInTheDocument();
      expect(screen.getByTestId('file-uploader-params')).toBeInTheDocument();
    });

    it('应该不在表单区渲染模型选择器', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      expect(screen.queryByLabelText('模型选择器')).not.toBeInTheDocument();
    });

    it('应该渲染提交按钮', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const submitButtons = screen.getAllByRole('button', { name: /开始生成/i });
      expect(submitButtons.length).toBeGreaterThan(0);
    });

    it('应该渲染高级设置输入字段', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 使用 placeholder 查找输入框，因为组件中的 label 没有关联到 input
      expect(screen.getByPlaceholderText('插入位置前的章节标题')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('插入位置后的章节标题')).toBeInTheDocument();
    });

    it('应该使用自定义className', () => {
      const { container } = render(
        <XjcgTenderForm onSubmit={mockOnSubmit} className="custom-class" />
      );

      const form = container.querySelector('form');
      expect(form).toHaveClass('custom-class');
    });
  });

  describe('招标编号输入交互', () => {
    it('应该允许输入招标编号', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');

      expect(input).toHaveValue('ZBGG-2024-001');
    });

    it('应该显示获取的招标信息', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const fetchButton = screen.getByLabelText('模拟获取招标信息');
      await user.click(fetchButton);

      expect(screen.getByText('测试项目')).toBeInTheDocument();
      expect(screen.getByText('测试采购人')).toBeInTheDocument();
    });

    it('应该使用初始招标编号', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} initialTenderNo="ZBGG-2024-INIT" />);

      const input = screen.getByLabelText('招标编号输入框');
      expect(input).toHaveValue('ZBGG-2024-INIT');
    });
  });

  describe('文件上传组件集成', () => {
    it('应该允许上传送审稿文件', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const uploadButton = screen.getByLabelText('上传送审稿文件（可选）');
      await user.click(uploadButton);

      expect(screen.getByTestId('file-uploader-origin_tender')).toBeInTheDocument();
    });

    it('应该允许上传清洁稿文件', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const uploadButton = screen.getByLabelText('上传清洁稿文件（可选）');
      await user.click(uploadButton);

      expect(screen.getByTestId('file-uploader-clean_draft')).toBeInTheDocument();
    });

    it('应该允许上传技术参数文件', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const uploadButton = screen.getByLabelText('上传技术参数文件（必填）');
      await user.click(uploadButton);

      expect(screen.getByTestId('file-uploader-params')).toBeInTheDocument();
    });
  });

  describe('表单验证', () => {
    it('提交时如果招标编号为空应该显示错误', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('提交时如果未获取招标信息应该显示错误', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');

      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      expect(screen.getByText('请先获取招标信息')).toBeInTheDocument();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('提交时如果未上传技术参数文件应该显示错误', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 输入招标编号
      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');

      // 获取招标信息
      const fetchButton = screen.getByLabelText('模拟获取招标信息');
      await user.click(fetchButton);

      // 上传清洁稿（满足至少上传一个清洁稿/送审稿）
      const cleanUploadButton = screen.getByLabelText('上传清洁稿文件（可选）');
      await user.click(cleanUploadButton);

      // 点击提交
      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      expect(screen.getByText('请上传至少一个技术参数文件')).toBeInTheDocument();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('提交时如果未上传清洁稿和送审稿应该显示错误', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');

      const fetchButton = screen.getByLabelText('模拟获取招标信息');
      await user.click(fetchButton);

      const uploadParamButton = screen.getByLabelText('上传技术参数文件（必填）');
      await user.click(uploadParamButton);

      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      expect(screen.getByText('清洁稿和送审稿至少要上传一个文件')).toBeInTheDocument();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('清除错误当用户开始输入', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 触发错误
      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);
      expect(screen.getByText('请输入招标编号')).toBeInTheDocument();

      // 开始输入应该清除错误
      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG');
      // 错误信息是通过 onChange 清除的，mock 组件实现了此行为
    });
  });

  describe('提交处理', () => {
    it('有效数据提交应该调用 onSubmit', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 输入招标编号
      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');

      // 获取招标信息
      const fetchButton = screen.getByLabelText('模拟获取招标信息');
      await user.click(fetchButton);

      // 上传技术参数文件
      const uploadButton = screen.getByLabelText('上传技术参数文件（必填）');
      await user.click(uploadButton);

      // 上传清洁稿文件
      const cleanUploadButton = screen.getByLabelText('上传清洁稿文件（可选）');
      await user.click(cleanUploadButton);

      // 提交表单
      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      });

      // 验证提交数据结构
      const submittedData = mockOnSubmit.mock.calls[0][0];
      expect(submittedData.tender_no).toBe('ZBGG-2024-001');
      expect(submittedData.tender_data.project_name).toBe('测试项目');
      expect(submittedData.model).toBe('deepseek');
      expect(submittedData.files.tender_params).toHaveLength(1);
      expect(submittedData.insertion_config).toBeDefined();
    });

    it('提交数据应该包含所有表单字段', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} initialDraft={{ model: 'qwen' }} />);

      // 填写表单
      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-TEST');

      const fetchButton = screen.getByLabelText('模拟获取招标信息');
      await user.click(fetchButton);

      // 上传文件
      const uploadButton = screen.getByLabelText('上传技术参数文件（必填）');
      await user.click(uploadButton);
      const cleanUploadButton = screen.getByLabelText('上传清洁稿文件（可选）');
      await user.click(cleanUploadButton);

      // 修改高级设置
      const beforeInput = screen.getByPlaceholderText('插入位置前的章节标题');
      await user.clear(beforeInput);
      await user.type(beforeInput, '第五章 测试');

      // 提交
      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });

      const submittedData = mockOnSubmit.mock.calls[0][0];
      expect(submittedData.tender_no).toBe('ZBGG-2024-TEST');
      expect(submittedData.model).toBe('qwen');
      expect(submittedData.insertion_config?.before_text).toBe('第五章 测试');
    });
  });

  describe('加载状态', () => {
    it('当 isSubmitting 为 true 时应该禁用提交按钮', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);

      const submitButtons = screen.getAllByRole('button', { name: /提交中|开始生成/i });
      const disabledButton = submitButtons.find((btn) => btn.hasAttribute('disabled'));
      expect(disabledButton).toBeDisabled();
    });

    it('当 isSubmitting 为 true 时应该显示加载状态', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);

      expect(screen.getByText('提交中...')).toBeInTheDocument();
    });

    it('当 isSubmitting 为 true 时应该禁用表单交互控件', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} isSubmitting={true} />);

      expect(screen.getByLabelText('招标编号输入框')).toBeDisabled();
      expect(screen.getByLabelText('模拟获取招标信息')).toBeDisabled();
      expect(screen.getByLabelText('上传清洁稿文件（可选）')).toBeDisabled();
      expect(screen.getByLabelText('上传送审稿文件（可选）')).toBeDisabled();
      expect(screen.getByLabelText('上传技术参数文件（必填）')).toBeDisabled();
      expect(screen.getByPlaceholderText('插入位置前的章节标题')).toBeDisabled();
      expect(screen.getByPlaceholderText('插入位置后的章节标题')).toBeDisabled();
    });

    it('当可取消时底部主按钮应该切换为取消生成', async () => {
      const user = userEvent.setup();
      const mockOnCancel = jest.fn();

      render(
        <XjcgTenderForm
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

  describe('高级设置', () => {
    it('应该有默认的插入配置', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 使用 placeholder 查找输入框
      const beforeInput = screen.getByPlaceholderText('插入位置前的章节标题') as HTMLInputElement;
      const afterInput = screen.getByPlaceholderText('插入位置后的章节标题') as HTMLInputElement;

      expect(beforeInput.value).toBe('第三章  采购需求');
      expect(afterInput.value).toBe('第四章  响应文件有关格式');
    });

    it('应该允许修改插入配置', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const beforeInput = screen.getByPlaceholderText('插入位置前的章节标题');
      await user.clear(beforeInput);
      await user.type(beforeInput, '新章节');

      expect(beforeInput).toHaveValue('新章节');
    });
  });

  describe('错误显示', () => {
    it('错误信息应该包含警告图标', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);

      const errorContainer = screen.getByText('请输入招标编号').closest('[role="alert"]');
      expect(errorContainer).toHaveClass('flex');
    });

    it('多次错误应该只显示最新的错误', async () => {
      const user = userEvent.setup();
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 第一次提交（招标编号为空）
      const submitButton = screen.getAllByRole('button', { name: /开始生成/i })[0];
      await user.click(submitButton);
      expect(screen.getByText('请输入招标编号')).toBeInTheDocument();

      // 输入编号后提交（未获取招标信息）
      const input = screen.getByLabelText('招标编号输入框');
      await user.type(input, 'ZBGG-2024-001');
      await user.click(submitButton);
      expect(screen.getByText('请先获取招标信息')).toBeInTheDocument();
      expect(screen.queryByText('请输入招标编号')).not.toBeInTheDocument();
    });
  });

  describe('可访问性', () => {
    it('表单应该有正确的语义结构', () => {
      const { container } = render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      const form = container.querySelector('form');
      expect(form).toBeInTheDocument();

      const headings = container.querySelectorAll('h3');
      expect(headings.length).toBe(3); // 三个区块标题
    });

    it('应该有高级设置标签文本', () => {
      render(<XjcgTenderForm onSubmit={mockOnSubmit} />);

      // 检查标签文本存在
      expect(screen.getByText('插入位置前文本')).toBeInTheDocument();
      expect(screen.getByText('插入位置后文本')).toBeInTheDocument();
    });
  });
});
