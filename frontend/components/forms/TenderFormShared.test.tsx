import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TenderFormShared, type BaseTenderFormData } from './TenderFormShared';
import type { UploadedFile } from './FileUploader';
import type { TenderData } from './TenderNoInput';
import type { ConversationFormDraft } from '@/stores/chatStore';

const mockTenderData: TenderData = {
  project_name: '测试项目',
  project_number: 'TEST-001',
  project_content: '测试内容',
  bzj_rule: '测试保证金规则',
  buyer_name: '测试采购人',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-01-01',
  shell_end_date: '2024-12-31',
  submit_date: '2024-12-31',
  platform: '测试平台',
  service_fee: '1000',
};

const mockUploadFactoryByType: Record<string, () => UploadedFile[]> = {};

function buildUploadedFile(
  fileType: string,
  overrides: Partial<UploadedFile> = {}
): UploadedFile {
  return {
    id: `${fileType}-id`,
    file_path: `D:/UploadFiles/${fileType}.docx`,
    file_name: `${fileType}.docx`,
    original_name: `${fileType}.docx`,
    size: 1024,
    upload_time: '2024-01-01T00:00:00.000Z',
    file_type: 'application/docx',
    ...overrides,
  };
}

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
        aria-label="模拟获取招标信息"
        disabled={disabled}
        onClick={() => onDataFetched?.(mockTenderData)}
      >
        获取信息
      </button>
    </div>
  ),
}));

jest.mock('./FileUploader', () => ({
  FileUploader: ({
    label,
    onFilesChange,
    fileType,
    disabled,
  }: {
    label: string;
    onFilesChange?: (files: UploadedFile[]) => void;
    fileType?: string;
    disabled?: boolean;
  }) => (
    <div data-testid={`file-uploader-${fileType || 'default'}`}>
      <span>{label}</span>
      <button
        type="button"
        aria-label={`上传${label}`}
        disabled={disabled}
        onClick={() => {
          const factory = mockUploadFactoryByType[fileType || 'default'];
          onFilesChange?.(factory ? factory() : []);
        }}
      >
        上传
      </button>
    </div>
  ),
}));

function renderSharedForm(options?: {
  tenderType?: 'xjcg' | 'gngk';
  onSubmit?: (data: BaseTenderFormData) => Promise<void> | void;
  initialDraft?: ConversationFormDraft | null;
  onDraftChange?: (updates: Partial<ConversationFormDraft>) => void;
  isSubmitting?: boolean;
  canCancel?: boolean;
  onCancel?: () => Promise<void> | void;
}) {
  return render(
    <TenderFormShared
      tenderType={options?.tenderType || 'xjcg'}
      onSubmit={options?.onSubmit || jest.fn()}
      initialDraft={options?.initialDraft}
      onDraftChange={options?.onDraftChange}
      isSubmitting={options?.isSubmitting}
      canCancel={options?.canCancel}
      onCancel={options?.onCancel}
    />
  );
}

describe('TenderFormShared', () => {
  beforeEach(() => {
    mockUploadFactoryByType.clean_draft = () => [buildUploadedFile('clean_draft')];
    mockUploadFactoryByType.origin_tender = () => [buildUploadedFile('origin_tender')];
    mockUploadFactoryByType.params = () => [buildUploadedFile('params')];
  });

  it.each([
    ['xjcg', '模板文件（可选）', '第三章  采购需求', '第四章  响应文件有关格式'],
    ['gngk', '模板文件（可选）', '第三章 招标内容及要求', '第四章 投标文件有关格式'],
  ] as const)(
    'injects variant defaults for %s',
    (tenderType, cleanLabel, beforeText, afterText) => {
      renderSharedForm({ tenderType });

      expect(screen.getByText(cleanLabel)).toBeInTheDocument();
      expect(screen.getByPlaceholderText('插入位置前的章节标题')).toHaveValue(beforeText);
      expect(screen.getByPlaceholderText('插入位置后的章节标题')).toHaveValue(afterText);
    }
  );

  it('shows tender data after fetch', async () => {
    const user = userEvent.setup();
    renderSharedForm();

    await user.click(screen.getByLabelText('模拟获取招标信息'));

    expect(screen.getByText('测试项目')).toBeInTheDocument();
    expect(screen.getByText('测试采购人')).toBeInTheDocument();
  });

  it('validates tender number is required', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    renderSharedForm({ onSubmit });

    await user.click(screen.getByRole('button', { name: '开始生成' }));

    expect(screen.getByText('请输入招标编号')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('requires at least one clean/template or origin file', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    renderSharedForm({ onSubmit });

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByLabelText('模拟获取招标信息'));
    await user.click(screen.getByLabelText('上传技术参数文件（必填）'));
    await user.click(screen.getByRole('button', { name: '开始生成' }));

    expect(screen.getByText('清洁稿和送审稿至少要上传一个文件')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('requires technical parameter files', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    renderSharedForm({ onSubmit });

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByLabelText('模拟获取招标信息'));
    await user.click(screen.getByLabelText('上传模板文件（可选）'));
    await user.click(screen.getByRole('button', { name: '开始生成' }));

    expect(screen.getByText('请上传至少一个技术参数文件')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('requires uploaded technical parameter file_path before submit', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    mockUploadFactoryByType.params = () => [
      buildUploadedFile('params', {
        file_path: '',
        original_name: 'params-unuploaded.docx',
      }),
    ];

    renderSharedForm({ onSubmit });

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByLabelText('模拟获取招标信息'));
    await user.click(screen.getByLabelText('上传模板文件（可选）'));
    await user.click(screen.getByLabelText('上传技术参数文件（必填）'));
    await user.click(screen.getByRole('button', { name: '开始生成' }));

    expect(screen.getByText('请先上传技术参数文件: params-unuploaded.docx')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits with updated insertion config', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    renderSharedForm({ onSubmit });

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByLabelText('模拟获取招标信息'));
    await user.click(screen.getByLabelText('上传模板文件（可选）'));
    await user.click(screen.getByLabelText('上传技术参数文件（必填）'));

    const beforeInput = screen.getByPlaceholderText('插入位置前的章节标题');
    const afterInput = screen.getByPlaceholderText('插入位置后的章节标题');
    await user.clear(beforeInput);
    await user.type(beforeInput, '新前文本');
    await user.clear(afterInput);
    await user.type(afterInput, '新后文本');

    await user.click(screen.getByRole('button', { name: '开始生成' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      tender_no: 'TEST-001',
      tender_data: mockTenderData,
      insertion_config: {
        before_text: '新前文本',
        after_text: '新后文本',
      },
      files: {
        clean_draft: expect.objectContaining({ file_path: 'D:/UploadFiles/clean_draft.docx' }),
        tender_params: [expect.objectContaining({ file_path: 'D:/UploadFiles/params.docx' })],
      },
    });
  });

  it('supports draft initialization and draft sync callbacks', async () => {
    const user = userEvent.setup();
    const onDraftChange = jest.fn();
    const initialDraft: ConversationFormDraft = {
      tender_no: 'INIT-001',
      tender_data: mockTenderData,
      model: 'qwen',
      insertion_config: {
        before_text: '初始前文本',
        after_text: '初始后文本',
      },
      files: {
        clean_draft: {
          id: 'draft-clean',
          file_path: 'D:/UploadFiles/draft-clean.docx',
          file_name: 'draft-clean.docx',
          original_name: 'draft-clean.docx',
          size: 1024,
          upload_time: '2024-01-01T00:00:00.000Z',
        },
        tender_params: [],
      },
    };

    renderSharedForm({ initialDraft, onDraftChange });

    expect(screen.getByLabelText('招标编号输入框')).toHaveValue('INIT-001');
    expect(screen.getByDisplayValue('初始前文本')).toBeInTheDocument();
    expect(screen.getByDisplayValue('初始后文本')).toBeInTheDocument();

    await user.type(screen.getByLabelText('招标编号输入框'), 'A');
    await user.click(screen.getByLabelText('上传技术参数文件（必填）'));
    await user.clear(screen.getByPlaceholderText('插入位置前的章节标题'));
    await user.type(screen.getByPlaceholderText('插入位置前的章节标题'), '更新前文本');

    await waitFor(() =>
      expect(onDraftChange).toHaveBeenCalledWith(
        expect.objectContaining({
          tender_no: 'INIT-001A',
        })
      )
    );
    expect(onDraftChange).toHaveBeenCalledWith(
      expect.objectContaining({
        files: expect.objectContaining({
          tender_params: [expect.objectContaining({ file_path: 'D:/UploadFiles/params.docx' })],
        }),
      })
    );
    expect(onDraftChange).toHaveBeenCalledWith(
      expect.objectContaining({
        insertion_config: expect.objectContaining({
          before_text: '更新前文本',
        }),
      })
    );
  });

  it('switches primary action to cancel when canCancel is true', async () => {
    const user = userEvent.setup();
    const onCancel = jest.fn();
    renderSharedForm({
      isSubmitting: true,
      canCancel: true,
      onCancel,
    });

    const cancelButton = screen.getByRole('button', { name: '取消生成' });
    expect(cancelButton).toBeEnabled();

    await user.click(cancelButton);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
