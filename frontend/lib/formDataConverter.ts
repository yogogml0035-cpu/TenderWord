/**
 * Form Data Converter
 * 将表单数据转换为 API 请求格式
 *
 * @module formDataConverter
 * @description 提供 XJCG 和 GNGK 表单数据到 API 请求数据的转换函数
 */

import type { XjcgTenderFormData } from '@/components/forms/XjcgTenderForm';
import type { GngkTenderFormData } from '@/components/forms/GngkTenderForm';
import type { UploadedFile } from '@/components/forms/FileUploader';
import type { GenerateRequest, FilesConfig } from '@/types/api';

// ============================================
// Type Exports
// ============================================

export type { XjcgTenderFormData, GngkTenderFormData };

// ============================================
// Helper Functions
// ============================================

/**
 * 从 UploadedFile 中提取 file_path
 * @param file - 上传的文件对象
 * @returns 文件路径，如果文件不存在则返回 undefined
 */
function extractFilePath(file: UploadedFile | undefined | null): string | undefined {
  if (!file) {
    return undefined;
  }
  return file.file_path;
}

/**
 * 从 UploadedFile 数组中提取 file_path 数组
 * @param files - 上传的文件对象数组
 * @returns 文件路径数组，如果输入为空则返回空数组
 */
function extractFilePaths(files: UploadedFile[] | undefined | null): string[] {
  if (!files || files.length === 0) {
    return [];
  }
  return files.map((file) => file.file_path);
}

/**
 * 构建 FilesConfig 对象
 * @param originTender - 原始招标文件
 * @param cleanDraft - 清稿文件
 * @param tenderParams - 技术参数文件数组
 * @returns FilesConfig 对象
 */
function buildFilesConfig(
  originTender: UploadedFile | undefined | null,
  cleanDraft: UploadedFile | undefined | null,
  tenderParams: UploadedFile[] | undefined | null
): FilesConfig {
  const paramPaths = extractFilePaths(tenderParams);

  return {
    origin_tender: extractFilePath(originTender),
    clean_draft: extractFilePath(cleanDraft),
    tender_params: paramPaths,
  };
}

// ============================================
// XJCG Converter
// ============================================

/**
 * 将 XJCG 表单数据转换为 API 请求格式
 *
 * @param formData - XJCG 表单数据
 * @returns GenerateRequest API 请求对象
 *
 * @example
 * ```typescript
 * const formData: XjcgTenderFormData = {
 *   tender_no: 'ZBGG-2024-001',
 *   tender_data: { project_name: '测试项目', ... },
 *   model: 'deepseek',
 *   files: {
 *     origin_tender: { file_path: '/uploads/template.docx', ... },
 *     tender_params: [{ file_path: '/uploads/params.xlsx', ... }],
 *   },
 *   insertion_config: { before_text: '第三章', after_text: '第四章' },
 * };
 *
 * const apiRequest = convertXjcgFormToApiRequest(formData);
 * // {
 * //   tender_no: 'ZBGG-2024-001',
 * //   tender_data: { ... },
 * //   files: {
 * //     origin_tender_path: '/uploads/template.docx',
 * //     clean_draft_path: undefined,
 * //     tender_param_paths: ['/uploads/params.xlsx'],
 * //   },
 * //   model: 'deepseek',
 * //   insertion_config: { before_text: '第三章', after_text: '第四章' },
 * // }
 * ```
 */
export function convertXjcgFormToApiRequest(formData: XjcgTenderFormData): GenerateRequest {
  const filesConfig = buildFilesConfig(
    formData.files.origin_tender,
    formData.files.clean_draft,
    formData.files.tender_params
  );

  return {
    form_type: 'xjcg_tender',
    tender_data: formData.tender_data,
    file_paths: filesConfig,
    insertion_config: formData.insertion_config,
    model: formData.model,
  };
}

// ============================================
// GNGK Converter
// ============================================

/**
 * 扩展的 GNGK API 请求类型（包含资质文件）
 */
export interface GngkGenerateRequest extends GenerateRequest {
  qualification_files?: string[];
  bid_sections?: {
    technical: boolean;
    business: boolean;
    price: boolean;
  };
}

/**
 * 将 GNGK 表单数据转换为 API 请求格式
 *
 * @param formData - GNGK 表单数据
 * @param options - 转换选项
 * @returns GenerateRequest API 请求对象（可能包含扩展字段）
 *
 * @example
 * ```typescript
 * const formData: GngkTenderFormData = {
 *   tender_no: 'ZBGG-2024-001',
 *   tender_data: { project_name: '测试项目', ... },
 *   model: 'deepseek',
 *   files: {
 *     origin_tender: { file_path: '/uploads/template.docx', ... },
 *     tender_params: [{ file_path: '/uploads/params.xlsx', ... }],
 *     qualification: [{ file_path: '/uploads/qual.pdf', ... }],
 *   },
 *   insertion_config: { before_text: '第三章', after_text: '第四章' },
 *   bid_sections: { technical: true, business: true, price: false },
 * };
 *
 * const apiRequest = convertGngkFormToApiRequest(formData);
 * // {
 * //   tender_no: 'ZBGG-2024-001',
 * //   tender_data: { ... },
 * //   files: {
 * //     origin_tender_path: '/uploads/template.docx',
 * //     tender_param_paths: ['/uploads/params.xlsx'],
 * //   },
 * //   model: 'deepseek',
 * //   insertion_config: { before_text: '第三章', after_text: '第四章' },
 * //   qualification_files: ['/uploads/qual.pdf'],
 * //   bid_sections: { technical: true, business: true, price: false },
 * // }
 * ```
 */
export function convertGngkFormToApiRequest(
  formData: GngkTenderFormData
): GngkGenerateRequest {
  const filesConfig = buildFilesConfig(
    formData.files.origin_tender,
    formData.files.clean_draft,
    formData.files.tender_params
  );

  const request: GngkGenerateRequest = {
    form_type: 'gngk_tender',
    tender_data: formData.tender_data,
    file_paths: filesConfig,
    insertion_config: formData.insertion_config,
    model: formData.model,
};
  // No longer processing qualification files - removed from GNGK form

  return request;
}

// ============================================
// Generic Converter
// ============================================

/**
 * 招标类型枚举
 */
export type TenderType = 'xjcg' | 'gngk';

/**
 * 通用表单数据类型
 */
export type TenderFormData = XjcgTenderFormData | GngkTenderFormData;

/**
 * 根据招标类型自动选择转换函数
 *
 * @param type - 招标类型 ('xjcg' | 'gngk')
 * @param formData - 表单数据
 * @returns GenerateRequest API 请求对象
 *
 * @example
 * ```typescript
 * const formData = getFormData(); // XjcgTenderFormData 或 GngkTenderFormData
 * const apiRequest = convertFormToApiRequest('xjcg', formData);
 * ```
 */
export function convertFormToApiRequest(
  type: 'xjcg',
  formData: XjcgTenderFormData
): GenerateRequest;
export function convertFormToApiRequest(
  type: 'gngk',
  formData: GngkTenderFormData
): GngkGenerateRequest;
export function convertFormToApiRequest(
  type: TenderType,
  formData: TenderFormData
): GenerateRequest | GngkGenerateRequest {
  switch (type) {
    case 'xjcg':
      return convertXjcgFormToApiRequest(formData as XjcgTenderFormData);
    case 'gngk':
      return convertGngkFormToApiRequest(formData as GngkTenderFormData);
    default:
      // Type guard ensures this shouldn't happen, but just in case
      throw new Error(`Unsupported tender type: ${type}`);
  }
}
