'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { TenderNoInput, type TenderData } from './TenderNoInput';
import { ModelSelector, type ModelType } from './ModelSelector';
import { FileUploader, type UploadedFile } from './FileUploader';
import { AlertCircle } from 'lucide-react';

export interface GngkTenderFormData {
  tender_no: string;
  tender_data: TenderData;
  model: ModelType;
  files: {
    origin_tender?: UploadedFile;
    clean_draft?: UploadedFile;
    tender_params: UploadedFile[];
    qualification?: UploadedFile[];
  };
  insertion_config: {
    before_text: string;
    after_text: string;
  };
}

export interface GngkTenderFormProps {
  onSubmit: (data: GngkTenderFormData) => Promise<void> | void;
  className?: string;
  initialTenderNo?: string;
  initialTenderData?: TenderData;
  isSubmitting?: boolean;
}
export function GngkTenderForm({
  onSubmit,
  className,
  initialTenderNo = '',
  initialTenderData,
  isSubmitting = false,
}: GngkTenderFormProps) {
  const [tenderNo, setTenderNo] = useState(initialTenderNo);
  const [tenderData, setTenderData] = useState<TenderData | null>(initialTenderData || null);
  const [model, setModel] = useState<ModelType>('deepseek');
  const [originFile, setOriginFile] = useState<UploadedFile | null>(null);
  const [cleanDraftFile, setCleanDraftFile] = useState<UploadedFile | null>(null);
  const [paramFiles, setParamFiles] = useState<UploadedFile[]>([]);
  const [qualificationFiles, setQualificationFiles] = useState<UploadedFile[]>([]);
  const [insertionConfig, setInsertionConfig] = useState({
    before_text: '第三章  采购需求',
    after_text: '第四章  投标文件有关格式',
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

      const formData: GngkTenderFormData = {
        tender_no: tenderNo,
        tender_data: tenderData,
        model,
        files: {
          origin_tender: originFile || undefined,
          clean_draft: cleanDraftFile || undefined,
          tender_params: paramFiles,
          qualification: qualificationFiles.length > 0 ? qualificationFiles : undefined,
        },
        insertion_config: insertionConfig,
      };
      await onSubmit(formData);
    },
    [
      tenderNo,
      tenderData,
      model,
      originFile,
      cleanDraftFile,
      paramFiles,
      qualificationFiles,
      insertionConfig,
      onSubmit,
    ]
  );

  return (
    <form onSubmit={handleSubmit} className={cn('form-section space-y-6', className)}>
      {/* Section 1: Tender Info */}
      <div className="relative overflow-hidden rounded-2xl bg-white border border-gray-200/60 shadow-sm hover:shadow-md transition-shadow duration-300">
        <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-blue-500 to-cyan-500" />
        
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-blue-500/25">
              1
            </div>
            <h3 className="text-xl font-bold text-gray-900">招标信息</h3>
          </div>

          <TenderNoInput
            value={tenderNo}
            onChange={setTenderNo}
            onDataFetched={handleTenderDataFetched}
            required
          />

          {tenderData && (
            <div className="mt-6 p-5 bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl border border-gray-100">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">项目名称</p>
                  <p className="text-sm font-semibold text-gray-900">{tenderData.project_name}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">采购人</p>
                  <p className="text-sm font-semibold text-gray-900">{tenderData.buyer_name}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">负责人</p>
                  <p className="text-sm font-semibold text-gray-900">{tenderData.project_zbr_xbr}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">投标截止</p>
                  <p className="text-sm font-semibold text-gray-900">{tenderData.submit_date}</p>
                </div>
              </div>
            </div>
          )}
        </div>
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

          <FileUploader
            label="资格条件文件（可选）"
            description="上传投标人资格条件要求文件"
            accept=".doc,.docx"
            multiple={true}
            maxFiles={3}
            autoUpload={true}
            fileType="qualification"
            onUpload={(files) => setQualificationFiles((prev) => [...prev, ...files])}
          />
        </div>
      </div>

      {/* Section 3: Model Selection */}
      <div className="relative overflow-hidden rounded-2xl bg-white border border-gray-200/60 shadow-sm hover:shadow-md transition-shadow duration-300">
        <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-blue-500 to-cyan-500" />
        
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-blue-500/25">
              3
            </div>
            <h3 className="text-xl font-bold text-gray-900">模型选择</h3>
          </div>

          <ModelSelector value={model} onChange={setModel} />
        </div>
      </div>

      {/* Section 4: Advanced Settings */}
      <div className="relative overflow-hidden rounded-2xl bg-white border border-gray-200/60 shadow-sm hover:shadow-md transition-shadow duration-300">
        <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-amber-400 to-orange-500" />
        
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-orange-500/25">
              4
            </div>
            <h3 className="text-xl font-bold text-gray-900">高级设置</h3>
            <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">必填</span>
          </div>

          <div className="space-y-6">
            <div className="relative">
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                插入位置前文本
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                value={insertionConfig.before_text}
                onChange={(e) =>
                  setInsertionConfig((prev) => ({ ...prev, before_text: e.target.value }))
                }
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                placeholder="插入位置前的章节标题"
              />
              <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                系统将在该文本位置之后插入生成的内容
              </p>
            </div>

            <div className="relative">
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                插入位置后文本
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                value={insertionConfig.after_text}
                onChange={(e) =>
                  setInsertionConfig((prev) => ({ ...prev, after_text: e.target.value }))
                }
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                placeholder="插入位置后的章节标题"
              />
              <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                系统将在该文本位置之前插入生成的内容
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 animate-pulse">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
            <AlertCircle className="w-5 h-5 text-red-600" />
          </div>
          <p className="text-sm font-medium text-red-700">{error}</p>
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

export default GngkTenderForm;
