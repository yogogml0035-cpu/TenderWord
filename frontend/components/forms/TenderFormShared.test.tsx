import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TenderFormShared, type BaseTenderFormData } from './TenderFormShared';
import type { UploadedFile } from './FileUploader';
import type { ConversationFormDraft } from '@/stores/chatStore';
import { ApiError } from '@/lib/api';
import type { TenderData, TemplateCandidate } from '@/types/api';

const mockSyncTenderDataDraft = jest.fn();
const mockUseUrlParams = jest.fn();
const mockFetchTemplateCandidates = jest.fn();
const mockSelectTemplateCandidate = jest.fn();
const mockGetTemplateCandidateDownloadUrl = jest.fn();

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
    onFetch,
    isLoading,
    isSuccess,
    error,
    required,
    disabled,
  }: {
    value: string;
    onChange: (value: string) => void;
    onFetch?: () => Promise<void> | void;
    isLoading?: boolean;
    isSuccess?: boolean;
    error?: string | null;
    required?: boolean;
    disabled?: boolean;
  }) => (
    <div
      data-testid="tender-no-input"
      data-fetch-status={isLoading ? 'loading' : error ? 'error' : isSuccess ? 'success' : 'idle'}
    >
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
        disabled={disabled || isLoading}
        onClick={() => void onFetch?.()}
      >
        获取信息
      </button>
      {error ? <p>{error}</p> : null}
    </div>
  ),
}));

jest.mock('@/lib/tenderFetch', () => ({
  createTenderFetchState: (status: string, error?: string) => (error ? { status, error } : { status }),
  resolveTenderFetchState: (state: { status: string } | undefined, data: TenderData | null | undefined) =>
    state || (data ? { status: 'success' } : { status: 'idle' }),
  syncTenderDataDraft: (...args: unknown[]) => mockSyncTenderDataDraft(...args),
}));

jest.mock('@/hooks/useUrlParams', () => ({
  useUrlParams: () => mockUseUrlParams(),
}));

jest.mock('@/lib/api', () => {
  class MockApiError extends Error {
    code: string;
    status: number;

    constructor(message: string, code = 'UNKNOWN_ERROR', status = 500) {
      super(message);
      this.name = 'ApiError';
      this.code = code;
      this.status = status;
    }
  }

  return {
    ApiError: MockApiError,
    fetchTemplateCandidates: (...args: unknown[]) => mockFetchTemplateCandidates(...args),
    selectTemplateCandidate: (...args: unknown[]) => mockSelectTemplateCandidate(...args),
    getTemplateCandidateDownloadUrl: (...args: unknown[]) => mockGetTemplateCandidateDownloadUrl(...args),
  };
});

jest.mock('./FileUploader', () => ({
  FileUploader: ({
    label,
    onFilesChange,
    fileType,
    disabled,
    initialFiles,
  }: {
    label: string;
    onFilesChange?: (files: UploadedFile[]) => void;
    fileType?: string;
    disabled?: boolean;
    initialFiles?: UploadedFile[];
  }) => (
    <div data-testid={`file-uploader-${fileType || 'default'}`}>
      <span>{label}</span>
      {initialFiles?.map((file) => (
        <p key={file.id}>{file.original_name}</p>
      ))}
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
  initialTenderNo?: string;
  initialTenderData?: TenderData | null;
  onDraftChange?: (updates: Partial<ConversationFormDraft>) => void;
  isSubmitting?: boolean;
  canCancel?: boolean;
  onCancel?: () => Promise<void> | void;
}) {
  return render(
    <TenderFormShared
      tenderType={options?.tenderType || 'xjcg'}
      onSubmit={options?.onSubmit || jest.fn()}
      initialTenderNo={options?.initialTenderNo}
      initialTenderData={options?.initialTenderData}
      initialDraft={options?.initialDraft}
      onDraftChange={options?.onDraftChange}
      isSubmitting={options?.isSubmitting}
      canCancel={options?.canCancel}
      onCancel={options?.onCancel}
    />
  );
}

function setUrlParams(options?: {
  tenderType?: 'xjcg' | 'gngk';
  hasParams?: boolean;
  isValid?: boolean;
}) {
  const searchParams =
    options?.hasParams === false
      ? new URLSearchParams('')
      : new URLSearchParams(
          options?.tenderType === 'gngk'
            ? 'tenderno=TEST-001&tender_lx=0&purchase_method=2&fund_lx=0'
            : 'tenderno=TEST-001&tender_lx=0&purchase_method=5&fund_lx=0'
        );

  mockUseUrlParams.mockReturnValue({
    tenderno: options?.hasParams === false ? undefined : 'TEST-001',
    tenderType: options?.hasParams === false ? undefined : options?.tenderType || 'xjcg',
    isValid: options?.isValid ?? true,
    errors: [],
    searchParams,
    hasParams: options?.hasParams ?? true,
  });
}

function buildTemplateCandidate(overrides: Partial<TemplateCandidate> = {}): TemplateCandidate {
  return {
    tenderno: '0811-DSITC260194',
    tendername: '测试模板',
    tname: '上海市中医医院',
    bm: '采购处',
    hytype: '医疗行业',
    tendertype: '国内公开',
    hwlx: '货物',
    yxj: '1',
    zbr: '张三',
    xbr: '李四',
    year: 2026,
    fsg: 'http://10.11.1.224/fsg',
    shener: 'http://10.11.1.224/shener',
    selectable: true,
    blocked_reason: null,
    ...overrides,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

describe('TenderFormShared', () => {
  beforeEach(() => {
    mockSyncTenderDataDraft.mockReset();
    mockUseUrlParams.mockReset();
    mockFetchTemplateCandidates.mockReset();
    mockSelectTemplateCandidate.mockReset();
    mockGetTemplateCandidateDownloadUrl.mockReset();
    mockSyncTenderDataDraft.mockImplementation(
      async ({
        tenderNo,
        updateDraft,
      }: {
        tenderNo: string;
        updateDraft: (updates: Partial<ConversationFormDraft>) => void;
      }) => {
        updateDraft({
          tender_no: tenderNo,
          tender_data: mockTenderData,
          tender_fetch: { status: 'success' },
        });
        return mockTenderData;
      }
    );
    mockUploadFactoryByType.clean_draft = () => [buildUploadedFile('clean_draft')];
    mockUploadFactoryByType.origin_tender = () => [buildUploadedFile('origin_tender')];
    mockUploadFactoryByType.params = () => [buildUploadedFile('params')];
    setUrlParams();
    mockFetchTemplateCandidates.mockResolvedValue({
      candidates: [buildTemplateCandidate()],
    });
    mockGetTemplateCandidateDownloadUrl.mockImplementation(
      (fileUrl: string, downloadName?: string) =>
        `/api/template-candidates/download?file_url=${encodeURIComponent(fileUrl)}&download_name=${encodeURIComponent(downloadName || '')}`
    );
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

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByLabelText('模拟获取招标信息'));

    expect(mockSyncTenderDataDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        tenderNo: 'TEST-001',
      })
    );
    expect(screen.getByText('测试项目')).toBeInTheDocument();
    expect(screen.getByText('测试采购人')).toBeInTheDocument();
    expect(screen.getByTestId('tender-no-input')).toHaveAttribute('data-fetch-status', 'success');
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
      tender_fetch: {
        status: 'success',
      },
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
    expect(screen.getByTestId('tender-no-input')).toHaveAttribute('data-fetch-status', 'success');

    await user.type(screen.getByLabelText('招标编号输入框'), 'A');
    await user.click(screen.getByLabelText('上传技术参数文件（必填）'));
    await user.clear(screen.getByPlaceholderText('插入位置前的章节标题'));
    await user.type(screen.getByPlaceholderText('插入位置前的章节标题'), '更新前文本');

    await waitFor(() =>
      expect(onDraftChange).toHaveBeenCalledWith(
        expect.objectContaining({
          tender_no: 'INIT-001A',
          tender_fetch: { status: 'idle' },
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

  it('shows template extraction button even when URL params do not match current tender type', () => {
    setUrlParams({ tenderType: 'xjcg' });
    const { rerender } = renderSharedForm({ tenderType: 'xjcg' });

    expect(screen.getByRole('button', { name: '智能抽取模板' })).toBeInTheDocument();

    setUrlParams({ tenderType: 'gngk' });
    rerender(
      <TenderFormShared
        tenderType="xjcg"
        onSubmit={jest.fn()}
      />
    );

    expect(screen.getByRole('button', { name: '智能抽取模板' })).toBeInTheDocument();
  });

  it('shows explicit error when template extraction is unavailable for current page params', async () => {
    const user = userEvent.setup();
    setUrlParams({ hasParams: false });
    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    const dialog = await screen.findByTestId('template-candidate-dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText('请先输入招标编号，再智能抽取模板')).toBeInTheDocument();
    expect(mockFetchTemplateCandidates).not.toHaveBeenCalled();
    expect(screen.queryByTestId('template-feedback')).not.toBeInTheDocument();
  });

  it('opens dialog immediately and shows loading state while loading candidates by current tender number', async () => {
    const user = userEvent.setup();
    setUrlParams({ hasParams: false });
    const templateCandidateLookup = createDeferred<{
      candidates: TemplateCandidate[];
    }>();
    mockFetchTemplateCandidates.mockReturnValueOnce(templateCandidateLookup.promise);
    renderSharedForm({
      initialTenderNo: 'TEST-001',
    });

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    const dialog = await screen.findByTestId('template-candidate-dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText('正在加载模板列表...')).toBeInTheDocument();
    expect(mockFetchTemplateCandidates).toHaveBeenCalledWith({
      tenderno: 'TEST-001',
    });

    templateCandidateLookup.resolve({
      candidates: [buildTemplateCandidate()],
    });

    await waitFor(() => expect(mockFetchTemplateCandidates).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByText('测试模板-送审稿')).toBeInTheDocument();
  });

  it('uses current input tender number when URL params are missing', async () => {
    const user = userEvent.setup();
    setUrlParams({ hasParams: false });
    renderSharedForm();

    await user.type(screen.getByLabelText('招标编号输入框'), 'TEST-001');
    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    expect(await screen.findByTestId('template-candidate-dialog')).toBeInTheDocument();
    expect(mockFetchTemplateCandidates).toHaveBeenCalledWith({
      tenderno: 'TEST-001',
    });
  });

  it('uses current url tender number when input is empty', async () => {
    const user = userEvent.setup();
    setUrlParams({ hasParams: true });
    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    expect(await screen.findByTestId('template-candidate-dialog')).toBeInTheDocument();
    expect(mockFetchTemplateCandidates).toHaveBeenCalledWith({
      tenderno: 'TEST-001',
    });
  });

  it('shows template candidate fetch failure inside dialog instead of inline form feedback', async () => {
    const user = userEvent.setup();
    setUrlParams({ hasParams: false });
    mockFetchTemplateCandidates.mockRejectedValueOnce(
      new ApiError('模板候选获取失败', 'TEMPLATE_CANDIDATE_FETCH_FAILED', 500)
    );
    renderSharedForm({
      initialTenderNo: 'TEST-001',
    });

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    const dialog = await screen.findByTestId('template-candidate-dialog');
    expect(dialog).toBeInTheDocument();
    expect(await within(dialog).findByText('模板候选获取失败')).toBeInTheDocument();
    expect(screen.queryByTestId('template-feedback')).not.toBeInTheDocument();
  });

  it('loads template candidates into dialog, reuses cache, and refreshes on demand', async () => {
    const user = userEvent.setup();
    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    const dialog = await screen.findByTestId('template-candidate-dialog');
    expect(dialog).toBeInTheDocument();
    expect(mockFetchTemplateCandidates).toHaveBeenCalledTimes(1);
    expect(within(dialog).getByRole('columnheader', { name: '年份' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '项目' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '主办人/协办人' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '采购人' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '部门' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '行业类型' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '招标类型' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '采购方式' })).toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '优先级' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('columnheader', { name: '发售稿' })).not.toBeInTheDocument();
    expect(within(dialog).getByRole('columnheader', { name: '推荐模板' })).toBeInTheDocument();
    expect(within(dialog).getByText('从ERP模板库中选择适合模板，将自动回填到发售稿和送审稿的上传区。')).toBeInTheDocument();
    expect(screen.getByText('测试模板-送审稿')).toBeInTheDocument();
    expect(within(dialog).getByText('0811-DSITC260194')).toBeInTheDocument();
    expect(within(dialog).getByText('张三')).toBeInTheDocument();
    expect(within(dialog).getByText('李四')).toBeInTheDocument();
    expect(within(dialog).getByText('上海市中医医院')).toBeInTheDocument();
    expect(within(dialog).getByText('采购处')).toBeInTheDocument();
    expect(within(dialog).getByText('医疗行业')).toBeInTheDocument();
    expect(within(dialog).getByText('国内公开')).toBeInTheDocument();
    expect(within(dialog).getByText('货物')).toBeInTheDocument();
    expect(within(dialog).getByTestId('template-priority-badge-0')).toHaveTextContent('1');
    expect(within(dialog).getByTestId('template-priority-badge-0')).toHaveClass('bg-red-50', 'text-red-700');
    expect(within(dialog).getByRole('button', { name: '选择' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '关闭模板弹窗' }));
    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

    expect(mockFetchTemplateCandidates).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: '刷新' }));
    await waitFor(() => expect(mockFetchTemplateCandidates).toHaveBeenCalledTimes(2));
  });

  it('renders candidates with duplicate tender name and year without duplicate key warnings', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockFetchTemplateCandidates.mockResolvedValue({
      candidates: [
        buildTemplateCandidate({
          tenderno: '0811-DSITC260574',
          tendername: '电子上消化道内窥镜等设备',
          year: 2026,
          zbr: '张三',
          xbr: '李四',
          fsg: 'http://10.11.1.224/fsg-1',
          shener: 'http://10.11.1.224/shener-1',
        }),
        buildTemplateCandidate({
          tenderno: '0811-DSITC260575',
          tendername: '电子上消化道内窥镜等设备',
          year: 2026,
          zbr: '王五',
          xbr: '赵六',
          fsg: 'http://10.11.1.224/fsg-2',
          shener: 'http://10.11.1.224/shener-2',
        }),
      ],
    });

    try {
      renderSharedForm();

      await user.click(screen.getByRole('button', { name: '智能抽取模板' }));

      const dialog = await screen.findByTestId('template-candidate-dialog');
      expect(within(dialog).getAllByText('电子上消化道内窥镜等设备')).toHaveLength(2);

      const duplicateKeyWarnings = consoleErrorSpy.mock.calls.filter((call) =>
        call.some(
          (arg) =>
            typeof arg === 'string' && arg.includes('Encountered two children with the same key')
        )
      );
      expect(duplicateKeyWarnings).toHaveLength(0);
    } finally {
      consoleErrorSpy.mockRestore();
    }
  });

  it('warns instead of selecting old template candidates', async () => {
    const user = userEvent.setup();
    mockFetchTemplateCandidates.mockResolvedValue({
      candidates: [
        buildTemplateCandidate({
          tendername: '旧模板',
          year: 2024,
          selectable: false,
          blocked_reason: '该模板过旧不能选择，仅供下载参考',
        }),
      ],
    });

    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));
    const dialog = await screen.findByTestId('template-candidate-dialog');
    await user.click(within(dialog).getByRole('button', { name: '选择' }));

    expect(screen.getAllByText('该模板过旧不能选择，仅供下载参考').length).toBeGreaterThan(0);
    expect(mockSelectTemplateCandidate).not.toHaveBeenCalled();
  });

  it('fills both upload slots after successful template selection without showing template feedback', async () => {
    const user = userEvent.setup();
    mockSelectTemplateCandidate.mockResolvedValue({
      selected_files: {
        clean_draft: {
          file_path: 'D:/UploadFiles/测试模板-送审稿.docx',
          file_name: '测试模板-送审稿.docx',
          original_name: '测试模板-送审稿.docx',
          size: 1024,
          upload_time: '2026-01-01T00:00:00.000Z',
        },
        origin_tender: {
          file_path: 'D:/UploadFiles/测试模板-送审稿_副本.docx',
          file_name: '测试模板-送审稿_副本.docx',
          original_name: '测试模板-送审稿.docx',
          size: 1024,
          upload_time: '2026-01-01T00:00:00.000Z',
        },
      },
      failed_slots: [],
      partial_success: false,
    });

    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));
    const dialog = await screen.findByTestId('template-candidate-dialog');
    await user.click(within(dialog).getByRole('button', { name: '选择' }));

    expect(mockSelectTemplateCandidate).toHaveBeenCalledWith({
      candidate: {
        tendername: '测试模板',
        year: 2026,
        fsg: null,
        shener: 'http://10.11.1.224/shener',
      },
    });
    await waitFor(() =>
      expect(screen.queryByTestId('template-candidate-dialog')).not.toBeInTheDocument()
    );
    expect(screen.getAllByText('测试模板-送审稿.docx')).toHaveLength(2);
    expect(screen.queryByTestId('template-feedback')).not.toBeInTheDocument();
  });

  it('keeps partial selection result without showing template feedback', async () => {
    const user = userEvent.setup();
    mockSelectTemplateCandidate.mockResolvedValue({
      selected_files: {
        clean_draft: {
          file_path: 'D:/UploadFiles/测试模板-送审稿.docx',
          file_name: '测试模板-送审稿.docx',
          original_name: '测试模板-送审稿.docx',
          size: 1024,
          upload_time: '2026-01-01T00:00:00.000Z',
        },
      },
      failed_slots: [
        {
          slot: 'origin_tender',
          message: '下载模板文件失败',
        },
      ],
      partial_success: true,
    });

    renderSharedForm();

    await user.click(screen.getByRole('button', { name: '智能抽取模板' }));
    const dialog = await screen.findByTestId('template-candidate-dialog');
    await user.click(within(dialog).getByRole('button', { name: '选择' }));

    await waitFor(() =>
      expect(screen.queryByTestId('template-candidate-dialog')).not.toBeInTheDocument()
    );
    expect(screen.getByText('测试模板-送审稿.docx')).toBeInTheDocument();
    expect(screen.queryByTestId('template-feedback')).not.toBeInTheDocument();
  });
});
