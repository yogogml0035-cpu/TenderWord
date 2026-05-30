'use client';

import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TenderType, FundLx, TenderLx } from '@/types';
import { useUrlParams } from '@/hooks/useUrlParams';
import type { ConversationDraftFile, ConversationFormDraft } from '@/stores/chatStore';
import { useChatStore } from '@/stores/chatStore';
import {
  createTenderFetchState,
  resolveTenderFetchState,
  syncTenderDataDraft,
  type TenderDraftUpdates,
  type TenderFetchState,
} from '@/lib/tenderFetch';
import {
  ApiError,
  fetchTemplateCandidates,
  getTemplateCandidateDownloadUrl,
  selectTemplateCandidate,
} from '@/lib/api';
import type {
  GenerationMode,
  GenerationStyle,
  StyleWritebackMode,
  TemplateCandidate,
  TemplateCandidateRanking,
  TemplateSelectedFile,
  TenderTypeInfo,
} from '@/types/api';
import { generateConversationTitle, shouldAutoUpdateConversationTitle } from '@/lib/chat-utils';
import { getTenderTypeFromParams, syncBrowserUrlToConversation } from '@/utils/tenderTypeMapper';
import { TenderNoInput, type TenderData } from './TenderNoInput';
import { FileUploader, type UploadedFile } from './FileUploader';
import { TemplateCandidateDialog } from './TemplateCandidateDialog';
import type { ModelType } from './ModelSelector';
import {
  FormSection,
  FormField,
  ErrorDisplay,
  InfoCard,
  secondaryActionButtonClassName,
  type TenderInfoItem,
} from './shared';
import { tenderFormVariantConfigMap, type TenderInsertionConfig } from './tenderFormConfig';

export interface BaseTenderFormData {
  tender_no: string;
  tender_lx: TenderLx;
  fund_lx: FundLx;
  generation_mode?: GenerationMode;
  generation_style: GenerationStyle;
  style_writeback_mode: StyleWritebackMode;
  tender_data: TenderData;
  model: ModelType;
  files: {
    template?: UploadedFile;
    tender_params: UploadedFile[];
  };
  insertion_config: TenderInsertionConfig;
}

export interface TenderFormSharedProps<TFormData extends BaseTenderFormData = BaseTenderFormData> {
  tenderType: TenderType;
  onSubmit: (data: TFormData) => Promise<void> | void;
  className?: string;
  headerTitle?: string;
  headerControlsTarget?: Element | null;
  initialTenderNo?: string;
  initialTenderData?: TenderData | null;
  initialDraft?: ConversationFormDraft | null;
  onDraftChange?: (updates: Partial<ConversationFormDraft>) => void;
  isSubmitting?: boolean;
  canCancel?: boolean;
  onCancel?: () => Promise<void> | void;
}

const sharedUploadCopy = {
  templateUpload: {
    label: '模板文件（必填）',
    description: '上传模板 Word 文件，作为生成正文的格式与内容参考',
  },
} as const;

const oldTemplateSelectionMessage = '该模板过旧不能选择，仅供下载参考';
const missingInsertionAnchorMessage = '请先补全当前页面的插入锚点';
const segmentedControlClassName =
  'inline-flex items-center rounded-2xl border border-slate-200 bg-slate-100/85 p-1 shadow-sm';
const segmentedToggleButtonClassName =
  'relative min-w-[72px] rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50';
const advancedSettingsGridClassName =
  'grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(14rem,1fr))]';
const defaultGenerationMode: GenerationMode = 'workflow';
const defaultStyleWritebackMode: StyleWritebackMode = 'full';
const gngkSharedContentBeforeText = '第三章 招标内容及要求';
const gngkLegacyFormatAfterText = '第四章 投标文件有关格式';
const gngkContractTermsAfterText = '第四章 合同条款';
const gngkFiscalInsertionConfigDefaults: TenderInsertionConfig = {
  before_text: '第四章  招标需求',
  after_text: '第五章  评标方法与程序',
};
const gngkServiceInsertionConfigDefaults: TenderInsertionConfig = {
  before_text: gngkSharedContentBeforeText,
  after_text: gngkLegacyFormatAfterText,
};
const gngkEngineeringInsertionConfigDefaults: TenderInsertionConfig = {
  before_text: gngkSharedContentBeforeText,
  after_text: gngkLegacyFormatAfterText,
};
const gngkSelfFundedContractInsertionConfigDefaults: TenderInsertionConfig = {
  before_text: gngkSharedContentBeforeText,
  after_text: gngkContractTermsAfterText,
};
function resolveDefaultGenerationStyle(): GenerationStyle {
  return 'template';
}

function shouldUseGngkContractTermsAfterText(
  tenderType: TenderType,
  tenderLx: TenderLx,
  fundLx: FundLx,
  ifdzpt2: number | undefined
): boolean {
  return tenderType === 'gngk' && tenderLx === 2 && fundLx === 0 && ifdzpt2 === 2;
}

function shouldUseGngkFiscalInsertionConfig(
  tenderType: TenderType,
  tenderLx: TenderLx,
  fundLx: FundLx,
  ifzgcg: number | undefined
): boolean {
  return tenderType === 'gngk' && tenderLx === 0 && fundLx === 1 && ifzgcg !== 2;
}

function resolveFetchedTenderType(tenderTypeInfo: TenderTypeInfo | null): TenderType | null {
  if (!tenderTypeInfo) {
    return null;
  }

  const result = getTenderTypeFromParams(tenderTypeInfo);
  return result.isValid ? result.tenderType || null : null;
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

function normalizeTemplateTenderNo(value: string | null | undefined): string | null {
  const normalizedValue = value?.trim();
  return normalizedValue ? normalizedValue : null;
}

function normalizeTemplateProjectName(value: string | null | undefined): string | null {
  const normalizedValue = value?.trim();
  return normalizedValue ? normalizedValue : null;
}

function areInsertionConfigsEqual(
  current: Partial<TenderInsertionConfig> | null | undefined,
  next: TenderInsertionConfig
): boolean {
  return current?.before_text === next.before_text && current?.after_text === next.after_text;
}

function buildInsertionConfigScopeKey(
  tenderType: TenderType,
  tenderLx: TenderLx,
  fundLx: FundLx
): string {
  return tenderType === 'gngk' ? `${tenderType}:${tenderLx}:${fundLx}` : tenderType;
}

function buildFetchedInsertionApplyKey(
  tenderType: TenderType,
  tenderTypeInfo: TenderTypeInfo,
  tenderData: TenderData | null
): string {
  return [
    tenderType,
    tenderTypeInfo.purchase_method,
    tenderTypeInfo.tender_lx,
    tenderTypeInfo.fund_lx,
    tenderData?.project_number || '',
    tenderData?.ifdzpt2 ?? '',
    tenderData?.ifzgcg ?? '',
  ].join(':');
}

function buildManualInsertionScopeKeys(
  draft: ConversationFormDraft | null | undefined,
  scopeKey: string
): string[] {
  const scopeKeys = new Set(draft?.manual_insertion_config_scope_keys || []);
  scopeKeys.add(scopeKey);
  return Array.from(scopeKeys);
}

function isManualInsertionScope(
  draft: ConversationFormDraft | null | undefined,
  manualScopeKeysRef: React.MutableRefObject<Set<string>>,
  scopeKey: string
): boolean {
  return (
    manualScopeKeysRef.current.has(scopeKey) ||
    !!draft?.manual_insertion_config_scope_keys?.includes(scopeKey)
  );
}

function resolveDefaultInsertionConfig(
  tenderType: TenderType,
  tenderLx: TenderLx,
  fundLx: FundLx,
  variantDefaults: TenderInsertionConfig,
  tenderData?: TenderData | null
): TenderInsertionConfig {
  if (shouldUseGngkContractTermsAfterText(tenderType, tenderLx, fundLx, tenderData?.ifdzpt2)) {
    return gngkSelfFundedContractInsertionConfigDefaults;
  }

  if (tenderType === 'gngk' && tenderLx === 2) {
    return gngkServiceInsertionConfigDefaults;
  }

  if (tenderType === 'gngk' && tenderLx === 1) {
    return gngkEngineeringInsertionConfigDefaults;
  }

  if (shouldUseGngkFiscalInsertionConfig(tenderType, tenderLx, fundLx, tenderData?.ifzgcg)) {
    return gngkFiscalInsertionConfigDefaults;
  }

  return variantDefaults;
}

function resolveInsertionConfig(
  current: Partial<TenderInsertionConfig> | null | undefined,
  fallback: TenderInsertionConfig
): TenderInsertionConfig {
  return {
    before_text: current?.before_text ?? fallback.before_text,
    after_text: current?.after_text ?? fallback.after_text,
  };
}

function mergeDraftStateLike(
  draft: ConversationFormDraft | null | undefined,
  updates: Partial<ConversationFormDraft>
): ConversationFormDraft {
  return {
    ...(draft || {}),
    ...updates,
    ...(updates.insertion_config
      ? {
          insertion_config: {
            ...(draft?.insertion_config || {}),
            ...updates.insertion_config,
          },
        }
      : {}),
    ...(updates.gngk_insertion_configs
      ? {
          gngk_insertion_configs: {
            ...(draft?.gngk_insertion_configs || {}),
            ...updates.gngk_insertion_configs,
          },
        }
      : {}),
    ...(updates.gngk_generation_styles
      ? {
          gngk_generation_styles: {
            ...(draft?.gngk_generation_styles || {}),
            ...updates.gngk_generation_styles,
          },
        }
      : {}),
    ...(updates.gngk_engineering_insertion_configs
      ? {
          gngk_engineering_insertion_configs: {
            ...(draft?.gngk_engineering_insertion_configs || {}),
            ...updates.gngk_engineering_insertion_configs,
          },
        }
      : {}),
    ...(updates.gngk_service_insertion_configs
      ? {
          gngk_service_insertion_configs: {
            ...(draft?.gngk_service_insertion_configs || {}),
            ...updates.gngk_service_insertion_configs,
          },
        }
      : {}),
    ...(updates.gngk_service_insertion_config
      ? {
          gngk_service_insertion_config: {
            ...(draft?.gngk_service_insertion_config || {}),
            ...updates.gngk_service_insertion_config,
          },
        }
      : {}),
  };
}

function resolveGngkScopedInsertionConfig(
  draft: ConversationFormDraft | null | undefined,
  tenderLx: TenderLx,
  fundLx: FundLx,
  useLegacyServiceDraftFallback = false
): Partial<TenderInsertionConfig> | null | undefined {
  if (tenderLx === 2) {
    const scopedServiceInsertion = draft?.gngk_service_insertion_configs?.[fundLx];
    if (scopedServiceInsertion) {
      return scopedServiceInsertion;
    }

    if (useLegacyServiceDraftFallback) {
      return draft?.gngk_service_insertion_config ?? draft?.insertion_config;
    }

    return undefined;
  }

  if (tenderLx === 1) {
    return draft?.gngk_engineering_insertion_configs?.[fundLx];
  }

  return draft?.gngk_insertion_configs?.[fundLx];
}

function resolveVisibleInsertionConfig(
  tenderType: TenderType,
  draft: ConversationFormDraft | null | undefined,
  tenderLx: TenderLx,
  fundLx: FundLx,
  variantDefaults: TenderInsertionConfig,
  useLegacyServiceDraftFallback = false,
  tenderData?: TenderData | null
): TenderInsertionConfig {
  const fallback = resolveDefaultInsertionConfig(
    tenderType,
    tenderLx,
    fundLx,
    variantDefaults,
    tenderData
  );
  const scopedInsertion =
    tenderType === 'gngk'
      ? resolveGngkScopedInsertionConfig(
          draft,
          tenderLx,
          fundLx,
          useLegacyServiceDraftFallback
        )
      : draft?.insertion_config;

  return resolveInsertionConfig(scopedInsertion, fallback);
}

function resolveModeChangeInsertionConfig(
  tenderType: TenderType,
  draft: ConversationFormDraft | null | undefined,
  manualScopeKeysRef: React.MutableRefObject<Set<string>>,
  tenderLx: TenderLx,
  fundLx: FundLx,
  variantDefaults: TenderInsertionConfig,
  tenderData?: TenderData | null
): TenderInsertionConfig {
  const fallback = resolveDefaultInsertionConfig(
    tenderType,
    tenderLx,
    fundLx,
    variantDefaults,
    tenderData
  );

  if (tenderType !== 'gngk') {
    return resolveInsertionConfig(draft?.insertion_config, fallback);
  }

  const scopedInsertion = resolveGngkScopedInsertionConfig(draft, tenderLx, fundLx, false);
  if (!scopedInsertion) {
    return fallback;
  }

  const resolvedScopedInsertion = resolveInsertionConfig(scopedInsertion, fallback);
  const insertionScopeKey = buildInsertionConfigScopeKey(tenderType, tenderLx, fundLx);

  if (
    isManualInsertionScope(draft, manualScopeKeysRef, insertionScopeKey) ||
    !isKnownAutoInsertionConfig(resolvedScopedInsertion)
  ) {
    return resolvedScopedInsertion;
  }

  return fallback;
}

function buildGngkModeCacheUpdates(
  draft: ConversationFormDraft | null | undefined,
  tenderLx: TenderLx,
  fundLx: FundLx,
  insertionConfig: TenderInsertionConfig
): Partial<ConversationFormDraft> {
  if (tenderLx === 2) {
    if (areInsertionConfigsEqual(draft?.gngk_service_insertion_configs?.[fundLx], insertionConfig)) {
      return {};
    }

    return {
      gngk_service_insertion_configs: {
        ...(draft?.gngk_service_insertion_configs || {}),
        [fundLx]: insertionConfig,
      },
    };
  }

  if (tenderLx === 1) {
    if (
      areInsertionConfigsEqual(draft?.gngk_engineering_insertion_configs?.[fundLx], insertionConfig)
    ) {
      return {};
    }

    return {
      gngk_engineering_insertion_configs: {
        ...(draft?.gngk_engineering_insertion_configs || {}),
        [fundLx]: insertionConfig,
      },
    };
  }

  if (areInsertionConfigsEqual(draft?.gngk_insertion_configs?.[fundLx], insertionConfig)) {
    return {};
  }

  return {
    gngk_insertion_configs: {
      ...(draft?.gngk_insertion_configs || {}),
      [fundLx]: insertionConfig,
    },
  };
}

function resolveVisibleGenerationStyle(
  tenderType: TenderType,
  draft: ConversationFormDraft | null | undefined,
  tenderLx: TenderLx,
  useLegacyGngkFallback = false
): GenerationStyle {
  if (tenderType !== 'gngk') {
    return draft?.generation_style ?? resolveDefaultGenerationStyle();
  }

  const scopedGenerationStyle = draft?.gngk_generation_styles?.[tenderLx];
  if (scopedGenerationStyle) {
    return scopedGenerationStyle;
  }

  if (useLegacyGngkFallback && draft?.generation_style) {
    return draft.generation_style;
  }

  return resolveDefaultGenerationStyle();
}

function buildGngkGenerationStyleCacheUpdates(
  draft: ConversationFormDraft | null | undefined,
  tenderLx: TenderLx,
  generationStyle: GenerationStyle
): Partial<ConversationFormDraft> {
  if (areGenerationStylesEqual(draft?.gngk_generation_styles?.[tenderLx], generationStyle)) {
    return {};
  }

  return {
    gngk_generation_styles: {
      ...(draft?.gngk_generation_styles || {}),
      [tenderLx]: generationStyle,
    },
  };
}

function areGenerationStylesEqual(
  current: GenerationStyle | null | undefined,
  next: GenerationStyle
): boolean {
  return current === next;
}

function buildVisibleInsertionDraftUpdates(
  draft: ConversationFormDraft | null | undefined,
  tenderType: TenderType,
  tenderLx: TenderLx,
  fundLx: FundLx,
  insertionConfig: TenderInsertionConfig
): Partial<ConversationFormDraft> {
  const updates: Partial<ConversationFormDraft> = {};

  if (!areInsertionConfigsEqual(draft?.insertion_config, insertionConfig)) {
    updates.insertion_config = insertionConfig;
  }

  if (tenderType === 'gngk') {
    Object.assign(updates, buildGngkModeCacheUpdates(draft, tenderLx, fundLx, insertionConfig));
  }

  return updates;
}

function isKnownAutoInsertionConfig(config: TenderInsertionConfig): boolean {
  return [
    tenderFormVariantConfigMap.xjcg.insertionConfigDefaults,
    tenderFormVariantConfigMap.gngk.insertionConfigDefaults,
    tenderFormVariantConfigMap.gjgk.insertionConfigDefaults,
    gngkFiscalInsertionConfigDefaults,
    gngkEngineeringInsertionConfigDefaults,
    gngkServiceInsertionConfigDefaults,
    gngkSelfFundedContractInsertionConfigDefaults,
  ].some((candidate) => areInsertionConfigsEqual(config, candidate));
}

function resolveInitialTenderData(
  draft: ConversationFormDraft | null | undefined,
  initialTenderData?: TenderData | null
): TenderData | null {
  return draft?.tender_data || initialTenderData || null;
}

function buildTemplateCandidateCacheKey(tenderNo: string, projectName: string | null): string {
  return `${tenderNo}::${projectName || '__no_project_name__'}`;
}

function toSelectedUploadedFile(file: TemplateSelectedFile): UploadedFile {
  return {
    id: Math.random().toString(36).slice(2),
    file_path: file.file_path,
    file_name: file.file_name,
    original_name: file.original_name,
    size: file.size,
    upload_time: file.upload_time || new Date().toISOString(),
  };
}

function toGjgkFundLabel(fundLx: TenderTypeInfo['fund_lx'] | undefined): string | undefined {
  if (fundLx === 0) {
    return '自筹资金';
  }
  if (fundLx === 1) {
    return '财政资金';
  }
  return undefined;
}

function toTenderLxLabel(tenderLx: TenderTypeInfo['tender_lx'] | undefined): string | undefined {
  if (tenderLx === 0) {
    return '货物';
  }
  if (tenderLx === 1) {
    return '工程';
  }
  if (tenderLx === 2) {
    return '服务';
  }
  return undefined;
}

function toTenderInfoItems(
  tenderType: TenderType,
  tenderData: TenderData | null,
  tenderTypeInfo: TenderTypeInfo | null
): TenderInfoItem[] {
  if (!tenderData) {
    return [];
  }

  const items: TenderInfoItem[] = [
    { label: '项目名称', value: tenderData.project_name, key: 'project_name' },
    { label: '项目编号', value: tenderData.project_number, key: 'project_number' },
    { label: '项目内容', value: tenderData.project_content, key: 'project_content' },
    {
      label: '总投资',
      value: tenderData.investment ? `${tenderData.investment}万元` : tenderData.investment,
      key: 'investment',
    },
    { label: '保证金规则', value: tenderData.bzj_rule, key: 'bzj_rule' },
    { label: '采购人', value: tenderData.buyer_name, key: 'buyer_name' },
    { label: '主办人/协办人', value: tenderData.project_zbr_xbr, key: 'project_zbr_xbr' },
    { label: '主办人/协办人电话', value: tenderData.zbr_xbr_tel, key: 'zbr_xbr_tel' },
    { label: '主办人拼音', value: tenderData.zbr_pinyin, key: 'zbr_pinyin' },
    { label: '售标开始时间', value: tenderData.shell_start_date, key: 'shell_start_date' },
    { label: '售标结束时间', value: tenderData.shell_end_date, key: 'shell_end_date' },
    { label: '递交文件截止时间', value: tenderData.submit_date, key: 'submit_date' },
  ];

  items.push({
    label: '标的类型',
    value: toTenderLxLabel(tenderTypeInfo?.tender_lx),
    key: 'tender_lx',
  });

  if (tenderType === 'gjgk') {
    items.push({
      label: '资金性质',
      value: toGjgkFundLabel(tenderTypeInfo?.fund_lx),
      key: 'fund_lx',
    });
  } else {
    items.push({ label: '发布平台', value: tenderData.platform, key: 'platform' });
  }

  items.push({ label: '服务费', value: tenderData.service_fee, key: 'service_fee' });

  return items;
}

export function TenderFormShared<TFormData extends BaseTenderFormData = BaseTenderFormData>({
  tenderType,
  onSubmit,
  className,
  headerTitle,
  headerControlsTarget,
  initialTenderNo = '',
  initialTenderData,
  initialDraft,
  onDraftChange,
  isSubmitting = false,
  canCancel = false,
  onCancel,
}: TenderFormSharedProps<TFormData>) {
  const variantConfig = tenderFormVariantConfigMap[tenderType];
  const { tenderno: urlTenderNo, tender_lx: urlTenderLx, fund_lx: urlFundLx } = useUrlParams();
  const updateConversation = useChatStore((state) => state.updateConversation);
  const setSelectedTenderType = useChatStore((state) => state.setSelectedTenderType);
  const currentConversation = useChatStore(
    (state) =>
      state.conversations.find((conversation) => conversation.id === state.currentConversationId) ||
      null
  );
  const [localTenderNo, setLocalTenderNo] = useState(initialDraft?.tender_no || initialTenderNo);
  const [localTenderData, setLocalTenderData] = useState<TenderData | null>(
    initialDraft?.tender_data || initialTenderData || null
  );
  const [localTenderTypeInfo, setLocalTenderTypeInfo] = useState<TenderTypeInfo | null>(
    initialDraft?.tender_type_info || null
  );
  const [localTenderFetchState, setLocalTenderFetchState] = useState<TenderFetchState>(
    resolveTenderFetchState(
      initialDraft?.tender_fetch,
      initialDraft?.tender_data || initialTenderData
    )
  );
  const [templateFile, setTemplateFile] = useState<UploadedFile | null>(
    (initialDraft?.files?.template as UploadedFile | undefined) || null
  );
  const [paramFiles, setParamFiles] = useState<UploadedFile[]>(
    (initialDraft?.files?.tender_params as UploadedFile[] | undefined) || []
  );
  const initialResolvedTenderData = resolveInitialTenderData(initialDraft, initialTenderData);
  const draftTenderLx: TenderLx | undefined =
    initialDraft?.tender_lx === 0 || initialDraft?.tender_lx === 1 || initialDraft?.tender_lx === 2
      ? initialDraft.tender_lx
      : undefined;
  // Priority: draft > URL > default (0=货物)
  // Draft is authoritative for existing conversations; URL only wins when
  // page.tsx explicitly wrote the deep-link values into the draft first.
  const initialTenderLx: TenderLx =
    draftTenderLx === 0 || draftTenderLx === 1 || draftTenderLx === 2
      ? draftTenderLx
      : urlTenderLx === 0 || urlTenderLx === 1 || urlTenderLx === 2
        ? urlTenderLx
        : 0;
  const [localTenderLx, setLocalTenderLx] = useState<TenderLx>(initialTenderLx);
  const draftFundLx: FundLx | undefined =
    initialDraft?.fund_lx === 0 || initialDraft?.fund_lx === 1 ? initialDraft.fund_lx : undefined;
  // Priority: draft > URL > default (0=自筹)
  const initialFundLx: FundLx =
    draftFundLx === 0 || draftFundLx === 1
      ? draftFundLx
      : urlFundLx === 0 || urlFundLx === 1
        ? urlFundLx
        : 0;
  const [localFundLx, setLocalFundLx] = useState<FundLx>(initialFundLx);
  const [localGenerationStyle, setLocalGenerationStyle] = useState<GenerationStyle>(
    resolveVisibleGenerationStyle(
      tenderType,
      initialDraft,
      initialTenderLx,
      tenderType === 'gngk'
    )
  );
  const [localGenerationMode, setLocalGenerationMode] = useState<GenerationMode>(
    initialDraft?.generation_mode || defaultGenerationMode
  );
  const [localStyleWritebackMode, setLocalStyleWritebackMode] = useState<StyleWritebackMode>(
    initialDraft?.style_writeback_mode || defaultStyleWritebackMode
  );
  const [insertionConfig, setInsertionConfig] = useState<TenderInsertionConfig>(() => {
    return resolveVisibleInsertionConfig(
      tenderType,
      initialDraft,
      initialTenderLx,
      initialFundLx,
      variantConfig.insertionConfigDefaults,
      tenderType === 'gngk' && initialTenderLx === 2,
      initialResolvedTenderData
    );
  });
  const manualInsertionScopeKeysRef = useRef<Set<string>>(
    new Set(initialDraft?.manual_insertion_config_scope_keys || [])
  );
  const optimisticTenderLxRef = useRef<TenderLx>(initialTenderLx);
  const optimisticFundLxRef = useRef<FundLx>(initialFundLx);
  const [error, setError] = useState<string | null>(null);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [templateCandidates, setTemplateCandidates] = useState<TemplateCandidate[]>([]);
  const [templateCandidateCache, setTemplateCandidateCache] = useState<
    Record<
      string,
      {
        candidates: TemplateCandidate[];
        ranking: TemplateCandidateRanking | null;
      }
    >
  >({});
  const [templateCandidateRanking, setTemplateCandidateRanking] =
    useState<TemplateCandidateRanking | null>(null);
  const [templateDialogError, setTemplateDialogError] = useState<string | null>(null);
  const [templateDialogNotice, setTemplateDialogNotice] = useState<string | null>(null);
  const [templateCandidatesLoading, setTemplateCandidatesLoading] = useState(false);
  const [templateCandidatesRefreshing, setTemplateCandidatesRefreshing] = useState(false);
  const [selectingTemplateRowKey, setSelectingTemplateRowKey] = useState<string | null>(null);
  const didSyncInitialRouteStateRef = useRef(false);
  const shouldApplyFetchedTypeRef = useRef(false);
  const fetchedInsertionApplyKeyRef = useRef<string | null>(null);
  const renderControlsInHeader = headerControlsTarget !== undefined;
  const selectedModel: ModelType = initialDraft?.model || 'deepseek';
  const tenderNo = onDraftChange ? initialDraft?.tender_no || initialTenderNo : localTenderNo;
  const tenderLx: TenderLx =
    onDraftChange &&
    (initialDraft?.tender_lx === 0 || initialDraft?.tender_lx === 1 || initialDraft?.tender_lx === 2)
      ? initialDraft.tender_lx
      : localTenderLx;
  const fundLx: FundLx =
    onDraftChange && (initialDraft?.fund_lx === 0 || initialDraft?.fund_lx === 1)
      ? initialDraft.fund_lx
      : localFundLx;
  const generationStyle: GenerationStyle =
    onDraftChange
      ? resolveVisibleGenerationStyle(tenderType, initialDraft, tenderLx, tenderType === 'gngk')
      : localGenerationStyle;
  const generationMode: GenerationMode = onDraftChange
    ? initialDraft?.generation_mode || defaultGenerationMode
    : localGenerationMode;
  const styleWritebackMode: StyleWritebackMode = onDraftChange
    ? initialDraft?.style_writeback_mode || defaultStyleWritebackMode
    : localStyleWritebackMode;
  const tenderData = onDraftChange
    ? initialDraft?.tender_data || initialTenderData || null
    : localTenderData;
  const tenderTypeInfo = onDraftChange
    ? initialDraft?.tender_type_info || null
    : localTenderTypeInfo;
  const tenderFetchState = onDraftChange
    ? resolveTenderFetchState(
        initialDraft?.tender_fetch,
        initialDraft?.tender_data || initialTenderData
      )
    : localTenderFetchState;
  const effectiveTemplateTenderNo = useMemo(
    () => normalizeTemplateTenderNo(tenderNo) || normalizeTemplateTenderNo(urlTenderNo),
    [tenderNo, urlTenderNo]
  );
  const effectiveTemplateProjectName = useMemo(
    () => normalizeTemplateProjectName(tenderData?.project_name),
    [tenderData]
  );

  useEffect(() => {
    optimisticTenderLxRef.current = tenderLx;
    optimisticFundLxRef.current = fundLx;
  }, [fundLx, tenderLx]);

  useEffect(() => {
    if (!onDraftChange || didSyncInitialRouteStateRef.current) {
      return;
    }
    didSyncInitialRouteStateRef.current = true;

    const shouldUpdateTenderLx = initialDraft?.tender_lx !== initialTenderLx;
    const shouldUpdateFund = initialDraft?.fund_lx !== initialFundLx;
    const updates: Partial<ConversationFormDraft> = {};

    if (shouldUpdateTenderLx) {
      updates.tender_lx = initialTenderLx;
    }
    if (shouldUpdateFund) {
      updates.fund_lx = initialFundLx;
    }

    setLocalTenderLx(initialTenderLx);
    setLocalFundLx(initialFundLx);

    if (Object.keys(updates).length > 0) {
      onDraftChange(updates);
    }
  }, [
    initialDraft?.tender_lx,
    initialDraft?.fund_lx,
    initialTenderLx,
    initialFundLx,
    onDraftChange,
  ]);

  useEffect(() => {
    if (!onDraftChange) {
      return;
    }

    const updates: Partial<ConversationFormDraft> = {};

    Object.assign(
      updates,
      buildVisibleInsertionDraftUpdates(initialDraft, tenderType, tenderLx, fundLx, insertionConfig)
    );

    if (Object.keys(updates).length > 0) {
      onDraftChange(updates);
    }
  }, [
    initialDraft,
    tenderLx,
    fundLx,
    initialDraft?.gngk_insertion_configs,
    initialDraft?.gngk_engineering_insertion_configs,
    initialDraft?.gngk_service_insertion_configs,
    initialDraft?.gngk_service_insertion_config,
    initialDraft?.insertion_config,
    insertionConfig,
    onDraftChange,
    tenderType,
  ]);

  useEffect(() => {
    if (!onDraftChange || initialDraft?.style_writeback_mode) {
      return;
    }

    onDraftChange({
      style_writeback_mode: defaultStyleWritebackMode,
    });
  }, [initialDraft?.style_writeback_mode, onDraftChange]);

  useEffect(() => {
    if (!onDraftChange || initialDraft?.generation_mode) {
      return;
    }

    onDraftChange({
      generation_mode: defaultGenerationMode,
    });
  }, [initialDraft?.generation_mode, onDraftChange]);

  const applyTenderDraftUpdates = useCallback(
    (updates: TenderDraftUpdates) => {
      if (Object.prototype.hasOwnProperty.call(updates, 'tender_no')) {
        setLocalTenderNo(updates.tender_no || '');
      }
      if (Object.prototype.hasOwnProperty.call(updates, 'tender_data')) {
        setLocalTenderData(updates.tender_data || null);
      }
      if (Object.prototype.hasOwnProperty.call(updates, 'tender_type_info')) {
        setLocalTenderTypeInfo(updates.tender_type_info || null);
      }
      if (updates.tender_fetch) {
        setLocalTenderFetchState(updates.tender_fetch);
      }
      onDraftChange?.(updates);
    },
    [onDraftChange]
  );

  const syncDraftFiles = useCallback(
    (nextTemplateFile: UploadedFile | null, nextParamFiles: UploadedFile[]) => {
      if (!onDraftChange) {
        return;
      }

      const nextTemplate = toDraftFile(nextTemplateFile);
      onDraftChange({
        files: {
          template: nextTemplate || undefined,
          tender_params: nextParamFiles
            .map((file) => toDraftFile(file))
            .filter((file): file is ConversationDraftFile => !!file),
        },
      });
    },
    [onDraftChange]
  );

  const handleTenderNoChange = useCallback(
    (value: string) => {
      setError(null);
      setLocalTenderNo(value);
      const nextFetchState = createTenderFetchState('idle');
      setLocalTenderFetchState(nextFetchState);
      setLocalTenderTypeInfo(null);
      onDraftChange?.({
        tender_no: value,
        tender_type_info: null,
        tender_fetch: nextFetchState,
      });
    },
    [onDraftChange]
  );

  const handleFetchTenderData = useCallback(async () => {
    setError(null);

    const data = await syncTenderDataDraft({
      tenderNo,
      updateDraft: applyTenderDraftUpdates,
      onSuccess: () => {
        if (
          currentConversation &&
          shouldAutoUpdateConversationTitle(currentConversation.title, tenderNo)
        ) {
          updateConversation(currentConversation.id, {
            title: generateConversationTitle(tenderNo.trim()),
          });
        }
      },
    });

    return data;
  }, [applyTenderDraftUpdates, currentConversation, tenderNo, updateConversation]);

  const handleFundLxChange = useCallback(
    (nextFundLx: FundLx) => {
      const currentTenderLx = optimisticTenderLxRef.current;
      const currentFundLx = optimisticFundLxRef.current;

      if (currentFundLx === nextFundLx) {
        return;
      }

      optimisticFundLxRef.current = nextFundLx;
      setLocalFundLx(nextFundLx);

      const nextUpdates: Partial<ConversationFormDraft> = {
        fund_lx: nextFundLx,
      };

      if (tenderType === 'gngk') {
        const currentModeCacheUpdates = buildGngkModeCacheUpdates(
          initialDraft,
          currentTenderLx,
          currentFundLx,
          insertionConfig
        );
        const nextDraft = mergeDraftStateLike(initialDraft, currentModeCacheUpdates);
        const nextInsertion = resolveModeChangeInsertionConfig(
          tenderType,
          nextDraft,
          manualInsertionScopeKeysRef,
          currentTenderLx,
          nextFundLx,
          variantConfig.insertionConfigDefaults
        );

        Object.assign(nextUpdates, currentModeCacheUpdates);
        Object.assign(
          nextUpdates,
          buildVisibleInsertionDraftUpdates(
            nextDraft,
            tenderType,
            currentTenderLx,
            nextFundLx,
            nextInsertion
          )
        );

        if (!areInsertionConfigsEqual(insertionConfig, nextInsertion)) {
          setInsertionConfig(nextInsertion);
        }
      }

      onDraftChange?.(nextUpdates);

      syncBrowserUrlToConversation({
        tenderType,
        tenderno: tenderNo || urlTenderNo,
        tender_lx: currentTenderLx,
        fund_lx: nextFundLx,
      });
    },
    [
      initialDraft,
      insertionConfig,
      onDraftChange,
      tenderNo,
      tenderType,
      urlTenderNo,
      variantConfig.insertionConfigDefaults,
    ]
  );

  const handleTenderLxChange = useCallback(
    (nextTenderLx: TenderLx) => {
      const currentTenderLx = optimisticTenderLxRef.current;
      const currentFundLx = optimisticFundLxRef.current;

      if (currentTenderLx === nextTenderLx) {
        return;
      }

      optimisticTenderLxRef.current = nextTenderLx;
      setLocalTenderLx(nextTenderLx);
      const nextUpdates: Partial<ConversationFormDraft> = {
        tender_lx: nextTenderLx,
      };

      const currentGenerationStyleCacheUpdates =
        tenderType === 'gngk'
          ? buildGngkGenerationStyleCacheUpdates(initialDraft, currentTenderLx, generationStyle)
          : {};
      const nextDraftWithGenerationStyleCache = mergeDraftStateLike(
        initialDraft,
        currentGenerationStyleCacheUpdates
      );
      const nextGenerationStyle = resolveVisibleGenerationStyle(
        tenderType,
        nextDraftWithGenerationStyleCache,
        nextTenderLx
      );
      setLocalGenerationStyle(nextGenerationStyle);
      nextUpdates.generation_style = nextGenerationStyle;
      Object.assign(nextUpdates, currentGenerationStyleCacheUpdates);

      if (tenderType === 'gngk') {
        const currentModeCacheUpdates = buildGngkModeCacheUpdates(
          initialDraft,
          currentTenderLx,
          currentFundLx,
          insertionConfig
        );
        const nextDraft = mergeDraftStateLike(
          nextDraftWithGenerationStyleCache,
          currentModeCacheUpdates
        );
        const nextInsertion = resolveModeChangeInsertionConfig(
          tenderType,
          nextDraft,
          manualInsertionScopeKeysRef,
          nextTenderLx,
          currentFundLx,
          variantConfig.insertionConfigDefaults
        );

        Object.assign(nextUpdates, currentModeCacheUpdates);
        Object.assign(
          nextUpdates,
          buildVisibleInsertionDraftUpdates(
            nextDraft,
            tenderType,
            nextTenderLx,
            currentFundLx,
            nextInsertion
          )
        );

        if (!areInsertionConfigsEqual(insertionConfig, nextInsertion)) {
          setInsertionConfig(nextInsertion);
        }
      }

      onDraftChange?.(nextUpdates);

      syncBrowserUrlToConversation({
        tenderType,
        tenderno: tenderNo || urlTenderNo,
        tender_lx: nextTenderLx,
        fund_lx: currentFundLx,
      });
    },
    [
      generationStyle,
      initialDraft,
      insertionConfig,
      onDraftChange,
      tenderNo,
      tenderType,
      urlTenderNo,
      variantConfig.insertionConfigDefaults,
    ]
  );

  const handleGenerationStyleChange = useCallback(
    (nextGenerationStyle: GenerationStyle) => {
      if (generationStyle === nextGenerationStyle) {
        return;
      }

      setLocalGenerationStyle(nextGenerationStyle);
      const nextUpdates: Partial<ConversationFormDraft> = {
        generation_style: nextGenerationStyle,
      };

      if (tenderType === 'gngk') {
        Object.assign(
          nextUpdates,
          buildGngkGenerationStyleCacheUpdates(initialDraft, tenderLx, nextGenerationStyle)
        );
      }

      onDraftChange?.(nextUpdates);
    },
    [generationStyle, initialDraft, onDraftChange, tenderLx, tenderType]
  );

  const handleGenerationModeChange = useCallback(
    (nextGenerationMode: GenerationMode) => {
      if (generationMode === nextGenerationMode) {
        return;
      }

      setLocalGenerationMode(nextGenerationMode);
      onDraftChange?.({
        generation_mode: nextGenerationMode,
      });
    },
    [generationMode, onDraftChange]
  );

  const handleStyleWritebackModeChange = useCallback(
    (nextStyleWritebackMode: StyleWritebackMode) => {
      if (styleWritebackMode === nextStyleWritebackMode) {
        return;
      }

      setLocalStyleWritebackMode(nextStyleWritebackMode);
      onDraftChange?.({
        style_writeback_mode: nextStyleWritebackMode,
      });
    },
    [onDraftChange, styleWritebackMode]
  );

  const handleBeforeTextChange = useCallback(
    (value: string) => {
      const next = { ...insertionConfig, before_text: value };
      const insertionScopeKey = buildInsertionConfigScopeKey(tenderType, tenderLx, fundLx);
      manualInsertionScopeKeysRef.current.add(insertionScopeKey);
      setInsertionConfig(next);
      onDraftChange?.({
        ...buildVisibleInsertionDraftUpdates(initialDraft, tenderType, tenderLx, fundLx, next),
        manual_insertion_config_scope_keys: buildManualInsertionScopeKeys(
          initialDraft,
          insertionScopeKey
        ),
      });
    },
    [fundLx, initialDraft, insertionConfig, onDraftChange, tenderLx, tenderType]
  );

  const handleAfterTextChange = useCallback(
    (value: string) => {
      const next = { ...insertionConfig, after_text: value };
      const insertionScopeKey = buildInsertionConfigScopeKey(tenderType, tenderLx, fundLx);
      manualInsertionScopeKeysRef.current.add(insertionScopeKey);
      setInsertionConfig(next);
      onDraftChange?.({
        ...buildVisibleInsertionDraftUpdates(initialDraft, tenderType, tenderLx, fundLx, next),
        manual_insertion_config_scope_keys: buildManualInsertionScopeKeys(
          initialDraft,
          insertionScopeKey
        ),
      });
    },
    [fundLx, initialDraft, insertionConfig, onDraftChange, tenderLx, tenderType]
  );

  const templateUploaderFiles = useMemo(
    () => (templateFile ? [templateFile] : []),
    [templateFile]
  );
  const tenderInfoItems = useMemo(
    () => toTenderInfoItems(tenderType, tenderData, tenderTypeInfo),
    [tenderData, tenderType, tenderTypeInfo]
  );
  const showCancelAction = isSubmitting && canCancel && typeof onCancel === 'function';

  useEffect(() => {
    if (tenderFetchState.status === 'loading') {
      shouldApplyFetchedTypeRef.current = true;
      fetchedInsertionApplyKeyRef.current = null;
      return;
    }

    if (tenderFetchState.status === 'idle' || tenderFetchState.status === 'error') {
      shouldApplyFetchedTypeRef.current = false;
    }
  }, [tenderFetchState.status]);

  useEffect(() => {
    if (
      !tenderTypeInfo ||
      tenderFetchState.status !== 'success' ||
      !shouldApplyFetchedTypeRef.current
    ) {
      return;
    }
    shouldApplyFetchedTypeRef.current = false;

    const nextTenderType = resolveFetchedTenderType(tenderTypeInfo);
    const nextTenderLx = tenderTypeInfo.tender_lx;
    const nextFundLx = tenderTypeInfo.fund_lx;
    const draftUpdates: Partial<ConversationFormDraft> = {};

    if (tenderLx !== nextTenderLx) {
      setLocalTenderLx(nextTenderLx);
      draftUpdates.tender_lx = nextTenderLx;
    }

    if (fundLx !== nextFundLx) {
      setLocalFundLx(nextFundLx);
      draftUpdates.fund_lx = nextFundLx;
    }

    if (Object.keys(draftUpdates).length > 0) {
      onDraftChange?.(draftUpdates);
    }

    if (nextTenderType && tenderType !== nextTenderType) {
      if (currentConversation) {
        updateConversation(currentConversation.id, { tenderType: nextTenderType });
      }
      setSelectedTenderType(nextTenderType);
    }

    if (
      nextTenderType ||
      draftUpdates.tender_lx !== undefined ||
      draftUpdates.fund_lx !== undefined
    ) {
      syncBrowserUrlToConversation({
        tenderType: nextTenderType || tenderType,
        tenderno: tenderNo || urlTenderNo,
        tender_lx: nextTenderLx,
        fund_lx: nextFundLx,
      });
    }
  }, [
    currentConversation,
    fundLx,
    onDraftChange,
    setSelectedTenderType,
    tenderLx,
    tenderNo,
    tenderFetchState.status,
    tenderType,
    tenderTypeInfo,
    updateConversation,
    urlTenderNo,
  ]);

  useEffect(() => {
    if (!tenderTypeInfo) {
      return;
    }

    const nextTenderType = resolveFetchedTenderType(tenderTypeInfo);
    if (nextTenderType && nextTenderType !== tenderType) {
      return;
    }

    if (tenderLx !== tenderTypeInfo.tender_lx || fundLx !== tenderTypeInfo.fund_lx) {
      return;
    }

    const fetchedInsertionApplyKey = buildFetchedInsertionApplyKey(
      tenderType,
      tenderTypeInfo,
      tenderData
    );
    if (fetchedInsertionApplyKeyRef.current === fetchedInsertionApplyKey) {
      return;
    }
    fetchedInsertionApplyKeyRef.current = fetchedInsertionApplyKey;

    const insertionScopeKey = buildInsertionConfigScopeKey(tenderType, tenderLx, fundLx);
    if (isManualInsertionScope(initialDraft, manualInsertionScopeKeysRef, insertionScopeKey)) {
      return;
    }

    if (!isKnownAutoInsertionConfig(insertionConfig)) {
      return;
    }

    const nextInsertion = resolveDefaultInsertionConfig(
      tenderType,
      tenderTypeInfo.tender_lx,
      tenderTypeInfo.fund_lx,
      variantConfig.insertionConfigDefaults,
      tenderData
    );
    if (areInsertionConfigsEqual(insertionConfig, nextInsertion)) {
      return;
    }

    setInsertionConfig(nextInsertion);
    onDraftChange?.(
      buildVisibleInsertionDraftUpdates(initialDraft, tenderType, tenderLx, fundLx, nextInsertion)
    );
  }, [
    fundLx,
    initialDraft,
    insertionConfig,
    onDraftChange,
    tenderData,
    tenderLx,
    tenderType,
    tenderTypeInfo,
    variantConfig.insertionConfigDefaults,
  ]);

  const loadTemplateCandidates = useCallback(
    async (
      forceRefresh = false,
      tenderNoOverride?: string | null,
      projectNameOverride?: string | null
    ) => {
      const activeTemplateTenderNo =
        normalizeTemplateTenderNo(tenderNoOverride) || effectiveTemplateTenderNo;
      const activeTemplateProjectName =
        normalizeTemplateProjectName(projectNameOverride) ?? effectiveTemplateProjectName;
      if (!activeTemplateTenderNo) {
        return;
      }

      const cacheKey = buildTemplateCandidateCacheKey(
        activeTemplateTenderNo,
        activeTemplateProjectName
      );
      const cachedEntry = templateCandidateCache[cacheKey];
      if (!forceRefresh && cachedEntry) {
        setTemplateCandidates(cachedEntry.candidates);
        setTemplateCandidateRanking(cachedEntry.ranking);
        return;
      }

      if (!cachedEntry) {
        setTemplateCandidates([]);
      }

      setTemplateDialogError(null);
      setTemplateDialogNotice(null);
      setTemplateCandidateRanking(null);
      if (forceRefresh) {
        setTemplateCandidatesRefreshing(true);
      } else {
        setTemplateCandidatesLoading(true);
      }

      try {
        const response = await fetchTemplateCandidates({
          tenderno: activeTemplateTenderNo,
          project_name: activeTemplateProjectName || undefined,
        });
        setTemplateCandidates(response.candidates);
        setTemplateCandidateRanking(response.ranking || null);
        setTemplateCandidateCache((prev) => ({
          ...prev,
          [cacheKey]: {
            candidates: response.candidates,
            ranking: response.ranking || null,
          },
        }));
      } catch (templateError) {
        const message =
          templateError instanceof ApiError
            ? templateError.message
            : '模板候选获取失败，请稍后重试';
        setTemplateDialogError(message);
        if (!cachedEntry) {
          setTemplateCandidates([]);
          setTemplateCandidateRanking(null);
        }
      } finally {
        setTemplateCandidatesLoading(false);
        setTemplateCandidatesRefreshing(false);
      }
    },
    [effectiveTemplateProjectName, effectiveTemplateTenderNo, templateCandidateCache]
  );

  const resolveAndLoadTemplateCandidates = useCallback(
    async (forceRefresh = false) => {
      setTemplateDialogOpen(true);
      setTemplateDialogError(null);
      setTemplateDialogNotice(null);

      if (!effectiveTemplateTenderNo) {
        setTemplateCandidates([]);
        setTemplateCandidateRanking(null);
        setTemplateDialogError('请先输入招标编号，再智能抽取模板');
        return;
      }

      await loadTemplateCandidates(
        forceRefresh,
        effectiveTemplateTenderNo,
        effectiveTemplateProjectName
      );
    },
    [effectiveTemplateProjectName, effectiveTemplateTenderNo, loadTemplateCandidates]
  );

  const handleOpenTemplateDialog = useCallback(() => {
    void resolveAndLoadTemplateCandidates(false);
  }, [resolveAndLoadTemplateCandidates]);

  const handleCloseTemplateDialog = useCallback(() => {
    setTemplateDialogOpen(false);
    setTemplateDialogError(null);
    setTemplateDialogNotice(null);
    setSelectingTemplateRowKey(null);
  }, []);

  const handleRefreshTemplateDialog = useCallback(() => {
    void resolveAndLoadTemplateCandidates(true);
  }, [resolveAndLoadTemplateCandidates]);

  const handleTemplateSelect = useCallback(
    async (candidate: TemplateCandidate, rowKey: string) => {
      setTemplateDialogError(null);
      setTemplateDialogNotice(null);

      if (!candidate.selectable) {
        setTemplateDialogNotice(candidate.blocked_reason || oldTemplateSelectionMessage);
        return;
      }

      setSelectingTemplateRowKey(rowKey);

      try {
        const response = await selectTemplateCandidate({
          candidate: {
            tendername: candidate.tendername,
            year: candidate.year ?? null,
            fsg: null,
            shener: candidate.shener ?? null,
          },
        });

        const selectedFile =
          response.selected_files.clean_draft || response.selected_files.origin_tender || null;
        const nextTemplateFile = selectedFile
          ? toSelectedUploadedFile(selectedFile)
          : templateFile;

        if (selectedFile) {
          setTemplateFile(nextTemplateFile);
        }

        syncDraftFiles(nextTemplateFile, paramFiles);
        setTemplateDialogOpen(false);
        setTemplateDialogError(null);
        setTemplateDialogNotice(null);
      } catch (templateError) {
        const message =
          templateError instanceof ApiError
            ? templateError.message
            : '模板文件选择失败，请稍后重试';

        if (templateError instanceof ApiError && templateError.code === 'TEMPLATE_TOO_OLD') {
          setTemplateDialogNotice(message);
        } else {
          setTemplateDialogError(message);
        }
      } finally {
        setSelectingTemplateRowKey(null);
      }
    },
    [paramFiles, syncDraftFiles, templateFile]
  );

  const uploadSectionAction = (
    <button
      type="button"
      onClick={handleOpenTemplateDialog}
      disabled={isSubmitting}
      className={secondaryActionButtonClassName}
    >
      <Search className="h-4 w-4" />
      智能抽取模板
    </button>
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      if (!tenderNo.trim()) {
        setError('请输入招标编号');
        return;
      }

      if (!tenderData) {
        setError('请先获取招标信息');
        return;
      }

      if (!templateFile) {
        setError('请上传模板文件');
        return;
      }

      if (paramFiles.length === 0) {
        setError('请上传至少一个技术参数文件');
        return;
      }

      const unuploadedParams = paramFiles.filter((file) => !file.file_path);
      if (unuploadedParams.length > 0) {
        setError(
          `请先上传技术参数文件: ${unuploadedParams.map((file) => file.original_name).join(', ')}`
        );
        return;
      }

      if (!insertionConfig.before_text.trim() || !insertionConfig.after_text.trim()) {
        setError(missingInsertionAnchorMessage);
        return;
      }

      const formData: BaseTenderFormData = {
        tender_no: tenderNo,
        tender_lx: tenderLx,
        fund_lx: fundLx,
        generation_mode: generationMode,
        generation_style: generationStyle,
        style_writeback_mode: styleWritebackMode,
        tender_data: {
          ...tenderData,
          tender_lx: tenderLx,
          fund_source_lx: fundLx,
        },
        model: selectedModel,
        files: {
          template: templateFile || undefined,
          tender_params: paramFiles,
        },
        insertion_config: insertionConfig,
      };

      await onSubmit(formData as TFormData);
    },
    [
      tenderNo,
      tenderLx,
      fundLx,
      tenderData,
      selectedModel,
      generationMode,
      generationStyle,
      styleWritebackMode,
      templateFile,
      paramFiles,
      insertionConfig,
      onSubmit,
    ]
  );

  const variantControls = (
    <div
      data-testid="tender-form-variant-controls"
      className="flex flex-wrap items-center justify-start gap-2 md:justify-end"
    >
      <div role="group" aria-label="标的类型" className={segmentedControlClassName}>
        <button
          type="button"
          onClick={() => handleTenderLxChange(0)}
          disabled={isSubmitting}
          className={cn(
            segmentedToggleButtonClassName,
            tenderLx === 0
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-transparent text-slate-700 hover:bg-white/80'
          )}
        >
          货物
        </button>
        <span aria-hidden className="h-6 w-px bg-slate-200" />
        <button
          type="button"
          onClick={() => handleTenderLxChange(1)}
          disabled={isSubmitting}
          className={cn(
            segmentedToggleButtonClassName,
            tenderLx === 1
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-transparent text-slate-700 hover:bg-white/80'
          )}
        >
          工程
        </button>
        <span aria-hidden className="h-6 w-px bg-slate-200" />
        <button
          type="button"
          onClick={() => handleTenderLxChange(2)}
          disabled={isSubmitting}
          className={cn(
            segmentedToggleButtonClassName,
            tenderLx === 2
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-transparent text-slate-700 hover:bg-white/80'
          )}
        >
          服务
        </button>
      </div>
      <div role="group" aria-label="资金类型" className={segmentedControlClassName}>
        <button
          type="button"
          onClick={() => handleFundLxChange(0)}
          disabled={isSubmitting}
          className={cn(
            segmentedToggleButtonClassName,
            fundLx === 0
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-transparent text-slate-700 hover:bg-white/80'
          )}
        >
          自筹
        </button>
        <span aria-hidden className="h-6 w-px bg-slate-200" />
        <button
          type="button"
          onClick={() => handleFundLxChange(1)}
          disabled={isSubmitting}
          className={cn(
            segmentedToggleButtonClassName,
            fundLx === 1
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-transparent text-slate-700 hover:bg-white/80'
          )}
        >
          财政
        </button>
      </div>
    </div>
  );

  return (
    <>
      {renderControlsInHeader && headerControlsTarget
        ? createPortal(variantControls, headerControlsTarget)
        : null}
      <form onSubmit={handleSubmit} className={cn('form-section space-y-5', className)}>
        {!renderControlsInHeader ? (
          <div
            data-testid="tender-form-header"
            className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
          >
            {headerTitle ? (
              <h2 className="text-2xl font-medium text-gray-900">{headerTitle}</h2>
            ) : null}
            {variantControls}
          </div>
        ) : null}

        <FormSection title="招标信息" index={1}>
          <TenderNoInput
            value={tenderNo}
            onChange={handleTenderNoChange}
            onFetch={handleFetchTenderData}
            disabled={isSubmitting}
            required
            isLoading={tenderFetchState.status === 'loading'}
            isSuccess={tenderFetchState.status === 'success'}
            error={tenderFetchState.status === 'error' ? tenderFetchState.error || null : null}
          />
          {tenderData && <InfoCard items={tenderInfoItems} columns={2} />}
        </FormSection>

        <FormSection title="文件上传" index={2} headerAction={uploadSectionAction}>
          <div className="space-y-5">
            <FileUploader
              label={sharedUploadCopy.templateUpload.label}
              description={sharedUploadCopy.templateUpload.description}
              accept=".doc,.docx"
              multiple={false}
              autoUpload={true}
              disabled={isSubmitting}
              fileType="template"
              initialFiles={templateUploaderFiles}
              onFilesChange={(files) => {
                const nextTemplateFile = files[0] || null;
                setTemplateFile(nextTemplateFile);
                syncDraftFiles(nextTemplateFile, paramFiles);
              }}
            />

            <FileUploader
              label="技术参数文件（必填）"
              description="上传技术参数 Word 文件，支持多个文件"
              accept=".doc,.docx"
              multiple={true}
              maxFiles={10}
              autoUpload={true}
              disabled={isSubmitting}
              fileType="params"
              initialFiles={paramFiles}
              onFilesChange={(files) => {
                setParamFiles(files);
                syncDraftFiles(templateFile, files);
              }}
            />
          </div>
        </FormSection>

        <FormSection title="高级设置（可选）" index={3}>
          <div className="space-y-4">
            <div className={advancedSettingsGridClassName}>
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

            <div className={advancedSettingsGridClassName}>
              <div className="space-y-1.5">
                <p className="block text-sm font-semibold text-[var(--foreground)]">生成方式</p>
                <div role="group" aria-label="生成方式" className={segmentedControlClassName}>
                  <button
                    type="button"
                    onClick={() => handleGenerationModeChange('workflow')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      generationMode === 'workflow'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    工作流
                  </button>
                  <span aria-hidden className="h-6 w-px bg-slate-200" />
                  <button
                    type="button"
                    onClick={() => handleGenerationModeChange('agent')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      generationMode === 'agent'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    智能体
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <p className="block text-sm font-semibold text-[var(--foreground)]">生成风格</p>
                <div role="group" aria-label="生成风格" className={segmentedControlClassName}>
                  <button
                    type="button"
                    onClick={() => handleGenerationStyleChange('template')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      generationStyle === 'template'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    按模板优先
                  </button>
                  <span aria-hidden className="h-6 w-px bg-slate-200" />
                  <button
                    type="button"
                    onClick={() => handleGenerationStyleChange('param')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      generationStyle === 'param'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    按参数优先
                  </button>
                </div>
              </div>
            </div>

            <div className={advancedSettingsGridClassName}>
              <div className="space-y-1.5">
                <p className="block text-sm font-semibold text-[var(--foreground)]">样式修订</p>
                <div role="group" aria-label="样式修订" className={segmentedControlClassName}>
                  <button
                    type="button"
                    onClick={() => handleStyleWritebackModeChange('full')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      styleWritebackMode === 'full'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    开
                  </button>
                  <span aria-hidden className="h-6 w-px bg-slate-200" />
                  <button
                    type="button"
                    onClick={() => handleStyleWritebackModeChange('bold_only')}
                    disabled={isSubmitting}
                    className={cn(
                      segmentedToggleButtonClassName,
                      styleWritebackMode === 'bold_only'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-transparent text-slate-700 hover:bg-white/80'
                    )}
                  >
                    关
                  </button>
                </div>
              </div>
            </div>
          </div>
        </FormSection>

        {error && <ErrorDisplay message={error} onDismiss={() => setError(null)} />}

        <TemplateCandidateDialog
          open={templateDialogOpen}
          candidates={templateCandidates}
          loading={templateCandidatesLoading}
          refreshing={templateCandidatesRefreshing}
          selectingRowKey={selectingTemplateRowKey}
          error={templateDialogError}
          notice={templateDialogNotice}
          rankingMessage={templateCandidateRanking?.message || null}
          onClose={handleCloseTemplateDialog}
          onRefresh={handleRefreshTemplateDialog}
          onSelect={handleTemplateSelect}
          getDownloadUrl={(fileUrl, downloadName) =>
            getTemplateCandidateDownloadUrl(fileUrl, downloadName)
          }
        />

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
                <svg
                  className="h-4.5 w-4.5 animate-spin"
                  width={20}
                  height={20}
                  viewBox="0 0 24 24"
                >
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
    </>
  );
}
