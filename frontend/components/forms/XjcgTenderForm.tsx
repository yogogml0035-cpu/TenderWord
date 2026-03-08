'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { TenderNoInput, type TenderData } from './TenderNoInput';
import type { ModelType } from './ModelSelector';
import { FileUploader, type UploadedFile } from './FileUploader';
import { FormSection, FormField, ErrorDisplay, InfoCard, type TenderInfoItem } from './shared';
import type { ConversationDraftFile, ConversationFormDraft } from '@/stores/chatStore';

export interface XjcgTenderFormData {
  tender_no: string;
  tender_data: TenderData;
  model: ModelType;
  files: {
    origin_tender?: UploadedFile;
    clean_draft?: UploadedFile;
    tender_params: UploadedFile[];
  };
  insertion_config?: {
    before_text: string;
    after_text: string;
  };
}

export interface XjcgTenderFormProps {
  onSubmit: (data: XjcgTenderFormData) => Promise<void> | void;
  className?: string;
  initialTenderNo?: string;
  initialTenderData?: TenderData | null;
  initialDraft?: ConversationFormDraft | null;
  onDraftChange?: (updates: Partial<ConversationFormDraft>) => void;
  isSubmitting?: boolean;
  canCancel?: boolean;
  onCancel?: () => Promise<void> | void;
}

function toDraftFile(file: UploadedFile | null | undefined): ConversationDraftFile | undefined {
  if (!file) {
    return undefined;
  }
  return {
    id: file.id,
    file_path: file.file_path,
    file_name: file.file_name,
    original_name: file.original_name,
    size: file.size,
    upload_time: file.upload_time,
    ...(file.file_type ? { file_type: file.file_type } : {}),
  };
}

export function XjcgTenderForm({
  onSubmit,
  className,
  initialTenderNo = '',
  initialTenderData,
  initialDraft,
  onDraftChange,
  isSubmitting = false,
  canCancel = false,
  onCancel,
}: XjcgTenderFormProps) {
  const [tenderNo, setTenderNo] = useState(initialDraft?.tender_no || initialTenderNo);
  const [tenderData, setTenderData] = useState<TenderData | null>(
    initialDraft?.tender_data || initialTenderData || null
  );
  const [originFile, setOriginFile] = useState<UploadedFile | null>(
    (initialDraft?.files?.origin_tender as UploadedFile | undefined) || null
  );
  const [cleanDraftFile, setCleanDraftFile] = useState<UploadedFile | null>(
    (initialDraft?.files?.clean_draft as UploadedFile | undefined) || null
  );
  const [paramFiles, setParamFiles] = useState<UploadedFile[]>(
    (initialDraft?.files?.tender_params as UploadedFile[] | undefined) || []
  );
  const [insertionConfig, setInsertionConfig] = useState({
    before_text: initialDraft?.insertion_config?.before_text || '第三章  采购需求',
    after_text: initialDraft?.insertion_config?.after_text || '第四章  响应文件有关格式',
  });
  const [error, setError] = useState<string | null>(null);
  const selectedModel: ModelType = initialDraft?.model || 'deepseek';

  const syncDraftFiles = useCallback(
    (nextOriginFile: UploadedFile | null, nextCleanDraftFile: UploadedFile | null, nextParamFiles: UploadedFile[]) => {
      if (!onDraftChange) {
        return;
      }
      onDraftChange({
        files: {
          ...(toDraftFile(nextOriginFile) ? { origin_tender: toDraftFile(nextOriginFile) } : {}),
          ...(toDraftFile(nextCleanDraftFile)
            ? { clean_draft: toDraftFile(nextCleanDraftFile) }
            : {}),
          tender_params: nextParamFiles
            .map((file) => toDraftFile(file))
            .filter((file): file is ConversationDraftFile => !!file),
        },
      });
    },
    [onDraftChange]
  );

  const handleTenderDataFetched = useCallback((data: TenderData) => {
    setTenderData(data);
    setError(null);
    onDraftChange?.({ tender_data: data });
  }, [onDraftChange]);

  const handleTenderNoChange = useCallback(
    (value: string) => {
      setTenderNo(value);
      onDraftChange?.({ tender_no: value });
    },
    [onDraftChange]
  );

  const handleBeforeTextChange = useCallback(
    (value: string) => {
      setInsertionConfig((prev) => {
        const next = { ...prev, before_text: value };
        onDraftChange?.({ insertion_config: next });
        return next;
      });
    },
    [onDraftChange]
  );

  const handleAfterTextChange = useCallback(
    (value: string) => {
      setInsertionConfig((prev) => {
        const next = { ...prev, after_text: value };
        onDraftChange?.({ insertion_config: next });
        return next;
      });
    },
    [onDraftChange]
  );

  const originUploaderFiles = useMemo(() => (originFile ? [originFile] : []), [originFile]);
  const cleanDraftUploaderFiles = useMemo(
    () => (cleanDraftFile ? [cleanDraftFile] : []),
    [cleanDraftFile]
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      // Validation
      if (!tenderNo.trim()) {
        setError('请输入招标编号');
        return;
      }

      if (!tenderData) {
        setError('请先获取招标信息');
        return;
      }

      // 清洁稿和送审稿至少上传一个
      if (!originFile && !cleanDraftFile) {
        setError('清洁稿和送审稿至少要上传一个文件');
        return;
      }

      if (paramFiles.length === 0) {
        setError('请上传至少一个技术参数文件');
        return;
      }

      const formData: XjcgTenderFormData = {
        tender_no: tenderNo,
        tender_data: tenderData,
        model: selectedModel,
        files: {
          origin_tender: originFile || undefined,
          clean_draft: cleanDraftFile || undefined,
          tender_params: paramFiles,
        },
        insertion_config: insertionConfig,
      };

      await onSubmit(formData);
    },
    [
      tenderNo,
      tenderData,
      selectedModel,
      originFile,
      cleanDraftFile,
      paramFiles,
      insertionConfig,
      onSubmit,
    ]
  );

  // Prepare tender data for InfoCard
  const tenderInfoItems: TenderInfoItem[] = tenderData
    ? [
        { label: '项目名称', value: tenderData.project_name, key: 'project_name' },
        { label: '项目编号', value: tenderData.project_number, key: 'project_number' },
        { label: '项目内容', value: tenderData.project_content, key: 'project_content' },
        { label: '保证金规则', value: tenderData.bzj_rule, key: 'bzj_rule' },
        { label: '采购人', value: tenderData.buyer_name, key: 'buyer_name' },
        { label: '主办人/协办人', value: tenderData.project_zbr_xbr, key: 'project_zbr_xbr' },
        { label: '主办人/协办人电话', value: tenderData.zbr_xbr_tel, key: 'zbr_xbr_tel' },
        { label: '主办人拼音', value: tenderData.zbr_pinyin, key: 'zbr_pinyin' },
        { label: '售标开始时间', value: tenderData.shell_start_date, key: 'shell_start_date' },
        { label: '售标结束时间', value: tenderData.shell_end_date, key: 'shell_end_date' },
        { label: '递交文件截止时间', value: tenderData.submit_date, key: 'submit_date' },
        { label: '发布平台', value: tenderData.platform, key: 'platform' },
        { label: '服务费', value: tenderData.service_fee, key: 'service_fee' },
      ]
    : [];
  const showCancelAction = isSubmitting && canCancel && typeof onCancel === 'function';

  return (
    <form onSubmit={handleSubmit} className={cn('form-section space-y-5', className)}>
      {/* Section 1: Tender Info */}
      <FormSection title="招标信息" index={1}>
        <TenderNoInput
          value={tenderNo}
          onChange={handleTenderNoChange}
          onDataFetched={handleTenderDataFetched}
          disabled={isSubmitting}
          required
        />
        {tenderData && <InfoCard items={tenderInfoItems} columns={2} />}
      </FormSection>

      {/* Section 2: File Upload */}
      <FormSection title="文件上传" index={2}>
        <div className="space-y-5">
          <FileUploader
            label="清洁稿文件（可选）"
            description="上传清洁稿 Word 文件，如上传则优先使用"
            accept=".doc,.docx"
            multiple={false}
            autoUpload={true}
            disabled={isSubmitting}
            fileType="clean_draft"
            initialFiles={cleanDraftUploaderFiles}
            onFilesChange={(files) => {
              const nextCleanDraftFile = files[0] || null;
              setCleanDraftFile(nextCleanDraftFile);
              syncDraftFiles(originFile, nextCleanDraftFile, paramFiles);
            }}
          />

          <FileUploader
            label="送审稿文件（可选）"
            description="上传送审稿 Word 文件"
            accept=".doc,.docx"
            multiple={false}
            autoUpload={true}
            disabled={isSubmitting}
            fileType="origin_tender"
            initialFiles={originUploaderFiles}
            onFilesChange={(files) => {
              const nextOriginFile = files[0] || null;
              setOriginFile(nextOriginFile);
              syncDraftFiles(nextOriginFile, cleanDraftFile, paramFiles);
            }}
          />

          <FileUploader
            label="技术参数文件（必填）"
            description="上传技术参数 Word 文件，支持多个文件"
            accept=".doc,.docx"
            multiple={true}
            maxFiles={5}
            autoUpload={true}
            disabled={isSubmitting}
            fileType="params"
            initialFiles={paramFiles}
            onFilesChange={(files) => {
              setParamFiles(files);
              syncDraftFiles(originFile, cleanDraftFile, files);
            }}
          />
        </div>
      </FormSection>

      {/* Section 3: Advanced Settings */}
      <FormSection title="高级设置（可选）" index={3}>
        <div className="space-y-4">
          <FormField
            label="插入位置前文本"
            name="before_text"
            variant="text"
            value={insertionConfig.before_text}
            onChange={handleBeforeTextChange}
            disabled={isSubmitting}
            placeholder="插入位置前的章节标题"
            helperText="系统将在该文本位置之后插入生成的内容"
          />

          <FormField
            label="插入位置后文本"
            name="after_text"
            variant="text"
            value={insertionConfig.after_text}
            onChange={handleAfterTextChange}
            disabled={isSubmitting}
            placeholder="插入位置后的章节标题"
            helperText="系统将在该文本位置之前插入生成的内容"
          />
        </div>
      </FormSection>

      {/* Error Display */}
      {error && (
        <ErrorDisplay message={error} onDismiss={() => setError(null)} />
      )}

      {/* Submit Button */}
      <button
        type={showCancelAction ? 'button' : 'submit'}
        onClick={showCancelAction ? () => void onCancel?.() : undefined}
        disabled={isSubmitting && !showCancelAction}
        className={cn(
          'group relative w-full transform overflow-hidden rounded-xl px-5 py-2.5 text-[15px] font-semibold text-white transition-all duration-200 ease-out',
          showCancelAction && 'z-40',
          showCancelAction
            ? 'bg-gradient-to-r from-red-500 via-red-500 to-orange-500 shadow-md shadow-red-500/25 hover:-translate-y-0.5 hover:from-red-600 hover:via-red-600 hover:to-orange-600 hover:shadow-lg hover:shadow-red-500/30'
            : 'bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 shadow-md shadow-blue-500/25 hover:-translate-y-0.5 hover:from-blue-700 hover:via-blue-600 hover:to-cyan-600 hover:shadow-lg hover:shadow-blue-500/30 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:transform-none disabled:hover:shadow-md'
        )}
      >
        {/* Shimmer effect */}
        {!showCancelAction && (
          <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-full" />
        )}

        <span className="relative flex items-center justify-center gap-2">
          {showCancelAction ? (
            <>
              <svg
                className="h-4.5 w-4.5 transition-transform duration-200 group-hover:rotate-90"
                width={20}
                height={20}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
              </svg>
              <span>取消生成</span>
            </>
          ) : isSubmitting ? (
            <>
              <svg className="h-4.5 w-4.5 animate-spin" width={20} height={20} viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>提交中...</span>
            </>
          ) : (
            <>
              {/* Sparkles icon */}
              <svg
                className="h-4.5 w-4.5 transition-transform group-hover:scale-110"
                width={20}
                height={20}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
                />
              </svg>
              <span>开始生成</span>
              <svg
                className="h-4.5 w-4.5 transition-transform group-hover:translate-x-1"
                width={20}
                height={20}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </>
          )}
        </span>
      </button>
    </form>
  );
}

export default XjcgTenderForm;
