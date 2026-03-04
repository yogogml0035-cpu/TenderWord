'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { BaseForm, type FormField } from './BaseForm';
import { TenderNoInput, type TenderData } from './TenderNoInput';
import { ModelSelector, type ModelType } from './ModelSelector';
import { FileUploader, type UploadedFile } from './FileUploader';
import { AlertCircle } from 'lucide-react';

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
  initialTenderData?: TenderData;
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

      if (paramFiles.length === 0) {
        setError('请上传至少一个技术参数文件');
        return;
      }

      // Ensure files are uploaded
      const unuploadedParams = paramFiles.filter((f) => !f.file_path);
      if (unuploadedParams.length > 0) {
        setError(`请先上传技术参数文件: ${unuploadedParams.map((f) => f.original_name).join(', ')}`);
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

  return (
    <form onSubmit={handleSubmit} className={cn('form-section space-y-6', className)}>
      {/* Section 1: Tender Info */}
      <div className="card">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">1. 招标信息</h3>
        
        <TenderNoInput
          value={tenderNo}
          onChange={setTenderNo}
          onDataFetched={handleTenderDataFetched}
          required
        />

        {tenderData && (
          <div className="mt-4 p-4 bg-[var(--secondary-bg)] rounded-lg space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-[var(--text-muted)]">项目名称</p>
                <p className="text-sm font-medium text-[var(--foreground)]">{tenderData.project_name}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)]">采购人</p>
                <p className="text-sm font-medium text-[var(--foreground)]">{tenderData.buyer_name}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)]">负责人</p>
                <p className="text-sm font-medium text-[var(--foreground)]">{tenderData.project_zbr_xbr}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)]">投标截止</p>
                <p className="text-sm font-medium text-[var(--foreground)]">{tenderData.submit_date}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Section 2: File Upload */}
      <div className="card">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">2. 文件上传</h3>
        
        <div className="space-y-5">
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
            label="清洁稿文件（可选）"
            description="上传清洁稿 Word 文件，如上传则优先使用"
            accept=".doc,.docx"
            multiple={false}
            autoUpload={true}
            fileType="clean_draft"
            onUpload={(files) => setCleanDraftFile(files[0] || null)}
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
      </div>

      {/* Section 3: Model Selection */}
      <div className="card">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">3. 模型选择</h3>
        
        <ModelSelector value={model} onChange={setModel} />
      </div>

      {/* Section 4: Advanced Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">4. 高级设置（可选）</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              插入位置前文本
            </label>
            <input
              type="text"
              value={insertionConfig.before_text}
              onChange={(e) =>
                setInsertionConfig((prev) => ({ ...prev, before_text: e.target.value }))
              }
              className="input-field"
              placeholder="插入位置前的章节标题"
            />
            <p className="text-xs text-[var(--text-muted)] mt-1">
              系统将在该文本位置之后插入生成的内容
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              插入位置后文本
            </label>
            <input
              type="text"
              value={insertionConfig.after_text}
              onChange={(e) =>
                setInsertionConfig((prev) => ({ ...prev, after_text: e.target.value }))
              }
              className="input-field"
              placeholder="插入位置后的章节标题"
            />
            <p className="text-xs text-[var(--text-muted)] mt-1">
              系统将在该文本位置之前插入生成的内容
            </p>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-[var(--error)]" />
          <p className="text-sm text-[var(--error)]">{error}</p>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isSubmitting}
        className="
          group relative w-full py-3.5 px-6
          bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500
          hover:from-blue-700 hover:via-blue-600 hover:to-cyan-600
          text-white font-semibold text-lg
          rounded-xl shadow-lg shadow-blue-500/30
          hover:shadow-xl hover:shadow-blue-500/40
          transform hover:-translate-y-0.5
          transition-all duration-200 ease-out
          disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:transform-none
          disabled:hover:shadow-lg
          overflow-hidden
        "
      >
        {/* Shimmer effect */}
        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000 ease-out" />
        
        <span className="relative flex items-center justify-center gap-3">
          {isSubmitting ? (
            <>
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>提交中...</span>
            </>
          ) : (
            <>
              {/* Sparkles icon */}
              <svg className="h-5 w-5 transition-transform group-hover:scale-110" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
              <span>开始生成</span>
              <svg className="h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
