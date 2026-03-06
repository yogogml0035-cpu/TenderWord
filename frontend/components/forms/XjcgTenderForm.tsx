'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { TenderNoInput, type TenderData } from './TenderNoInput';
import { ModelSelector, type ModelType } from './ModelSelector';
import { FileUploader, type UploadedFile } from './FileUploader';
import { FormSection, FormField, ErrorDisplay, InfoCard, type TenderInfoItem } from './shared';

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
  isSubmitting?: boolean;
}
export function XjcgTenderForm({
  onSubmit,
  className,
  initialTenderNo = '',
  initialTenderData,
  isSubmitting = false,
}: XjcgTenderFormProps) {
  const [tenderNo, setTenderNo] = useState(initialTenderNo);
  const [tenderData, setTenderData] = useState<TenderData | null>(initialTenderData || null);
  const [model, setModel] = useState<ModelType>('deepseek');
  const [originFile, setOriginFile] = useState<UploadedFile | null>(null);
  const [cleanDraftFile, setCleanDraftFile] = useState<UploadedFile | null>(null);
  const [paramFiles, setParamFiles] = useState<UploadedFile[]>([]);
  const [insertionConfig, setInsertionConfig] = useState({
    before_text: '第三章  采购需求',
    after_text: '第四章  响应文件有关格式',
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTenderNo(initialTenderNo || '');
  }, [initialTenderNo]);

  useEffect(() => {
    setTenderData(initialTenderData || null);
  }, [initialTenderData]);

  const handleTenderDataFetched = useCallback((data: TenderData) => {
    setTenderData(data);
    setError(null);
  }, []);

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
        model,
        files: {
          origin_tender: originFile || undefined,
          clean_draft: cleanDraftFile || undefined,
          tender_params: paramFiles,
        },
        insertion_config: insertionConfig,
      };

      await onSubmit(formData);
    },
    [tenderNo, tenderData, model, originFile, cleanDraftFile, paramFiles, insertionConfig, onSubmit]
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

  return (
    <form onSubmit={handleSubmit} className={cn('form-section space-y-6', className)}>
      {/* Section 1: Tender Info */}
      <FormSection title="招标信息" index={1}>
        <TenderNoInput
          value={tenderNo}
          onChange={setTenderNo}
          onDataFetched={handleTenderDataFetched}
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
            fileType="clean_draft"
            onUpload={(files) => setCleanDraftFile(files[0] || null)}
          />

          <FileUploader
            label="送审稿文件（可选）"
            description="上传送审稿 Word 文件"
            accept=".doc,.docx"
            multiple={false}
            autoUpload={true}
            fileType="origin_tender"
            onUpload={(files) => setOriginFile(files[0] || null)}
          />

          <FileUploader
            label="技术参数文件（必填）"
            description="上传技术参数 Word 文件，支持多个文件"
            accept=".doc,.docx"
            multiple={true}
            maxFiles={5}
            autoUpload={true}
            fileType="params"
            onUpload={(files) => setParamFiles((prev) => [...prev, ...files])}
          />
        </div>
      </FormSection>

      {/* Section 3: Model Selection */}
      <FormSection title="模型选择" index={3}>
        <ModelSelector value={model} onChange={setModel} />
      </FormSection>

      {/* Section 4: Advanced Settings */}
      <FormSection title="高级设置（可选）" index={4} badge="可选" badgeVariant="optional">
        <div className="space-y-4">
          <FormField
            label="插入位置前文本"
            name="before_text"
            variant="text"
            value={insertionConfig.before_text}
            onChange={(value) =>
              setInsertionConfig((prev) => ({ ...prev, before_text: value }))
            }
            placeholder="插入位置前的章节标题"
            helperText="系统将在该文本位置之后插入生成的内容"
          />

          <FormField
            label="插入位置后文本"
            name="after_text"
            variant="text"
            value={insertionConfig.after_text}
            onChange={(value) =>
              setInsertionConfig((prev) => ({ ...prev, after_text: value }))
            }
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
        type="submit"
        disabled={isSubmitting}
        className="group relative w-full transform overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 px-6 py-3.5 text-lg font-semibold text-white shadow-lg shadow-blue-500/30 transition-all duration-200 ease-out hover:-translate-y-0.5 hover:from-blue-700 hover:via-blue-600 hover:to-cyan-600 hover:shadow-xl hover:shadow-blue-500/40 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:transform-none disabled:hover:shadow-lg"
      >
        {/* Shimmer effect */}
        <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-full" />

        <span className="relative flex items-center justify-center gap-3">
          {isSubmitting ? (
            <>
              <svg className="h-5 w-5 animate-spin" width={20} height={20} viewBox="0 0 24 24">
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
                className="h-5 w-5 transition-transform group-hover:scale-110"
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
                className="h-5 w-5 transition-transform group-hover:translate-x-1"
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
