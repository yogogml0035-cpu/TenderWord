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
  TemplateCandidate,
  TemplateCandidateRanking,
  TemplateSelectedFile,
  TenderTypeInfo,
} from '@/types/api';
import { generateConversationTitle, shouldAutoUpdateConversationTitle } from '@/lib/chat-utils';
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
  tender_data: TenderData;
  model: ModelType;
  files: {
    origin_tender?: UploadedFile;
    clean_draft?: UploadedFile;
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
  cleanDraftUpload: {
    label: '模板文件（可选）',
    description: '上传则优先使用，若未上传则使用送审稿文件作为模板',
  },
  originUpload: {
    label: '送审稿文件（可选）',
    description: '若上传则最终文件将生成批注',
  },
} as const;

const oldTemplateSelectionMessage = '该模板过旧不能选择，仅供下载参考';
const missingInsertionAnchorMessage = '请先补全当前页面的插入锚点';
const segmentedControlClassName =
  'inline-flex items-center rounded-2xl border border-slate-200 bg-slate-100/85 p-1 shadow-sm';
const segmentedToggleButtonClassName =
  'relative min-w-[72px] rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50';
const gngkFiscalInsertionConfigDefaults: TenderInsertionConfig = {
  before_text: '第四章  招标需求',
  after_text: '第五章  评标方法与程序',
};

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

function resolveDefaultInsertionConfig(
  tenderType: TenderType,
  fundLx: FundLx,
  variantDefaults: TenderInsertionConfig
): TenderInsertionConfig {
  if (tenderType === 'gngk' && fundLx === 1) {
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
    { label: '保证金规则', value: tenderData.bzj_rule, key: 'bzj_rule' },
    { label: '采购人', value: tenderData.buyer_name, key: 'buyer_name' },
    { label: '主办人/协办人', value: tenderData.project_zbr_xbr, key: 'project_zbr_xbr' },
    { label: '主办人/协办人电话', value: tenderData.zbr_xbr_tel, key: 'zbr_xbr_tel' },
    { label: '主办人拼音', value: tenderData.zbr_pinyin, key: 'zbr_pinyin' },
    { label: '售标开始时间', value: tenderData.shell_start_date, key: 'shell_start_date' },
    { label: '售标结束时间', value: tenderData.shell_end_date, key: 'shell_end_date' },
    { label: '递交文件截止时间', value: tenderData.submit_date, key: 'submit_date' },
  ];

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
  const [originFile, setOriginFile] = useState<UploadedFile | null>(
    (initialDraft?.files?.origin_tender as UploadedFile | undefined) || null
  );
  const [cleanDraftFile, setCleanDraftFile] = useState<UploadedFile | null>(
    (initialDraft?.files?.clean_draft as UploadedFile | undefined) || null
  );
  const [paramFiles, setParamFiles] = useState<UploadedFile[]>(
    (initialDraft?.files?.tender_params as UploadedFile[] | undefined) || []
  );
  const draftTenderLx: TenderLx | undefined =
    initialDraft?.tender_lx === 0 || initialDraft?.tender_lx === 1
      ? initialDraft.tender_lx
      : undefined;
  const initialTenderLx: TenderLx =
    urlTenderLx === 0 || urlTenderLx === 1
      ? urlTenderLx
      : draftTenderLx === 0 || draftTenderLx === 1
        ? draftTenderLx
        : 0;
  const [localTenderLx, setLocalTenderLx] = useState<TenderLx>(initialTenderLx);
  const draftFundLx: FundLx | undefined =
    initialDraft?.fund_lx === 0 || initialDraft?.fund_lx === 1 ? initialDraft.fund_lx : undefined;
  const initialFundLx: FundLx =
    urlFundLx === 0 || urlFundLx === 1
      ? urlFundLx
      : draftFundLx === 0 || draftFundLx === 1
        ? draftFundLx
        : 0;
  const [localFundLx, setLocalFundLx] = useState<FundLx>(initialFundLx);
  const [insertionConfig, setInsertionConfig] = useState<TenderInsertionConfig>(() => {
    const gngkScopedInsertion =
      initialDraft?.gngk_insertion_configs?.[initialFundLx] ?? initialDraft?.insertion_config;
    return resolveInsertionConfig(
      gngkScopedInsertion,
      resolveDefaultInsertionConfig(
        tenderType,
        initialFundLx,
        variantConfig.insertionConfigDefaults
      )
    );
  });
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
  const renderControlsInHeader = headerControlsTarget !== undefined;
  const selectedModel: ModelType = initialDraft?.model || 'deepseek';
  const tenderNo = onDraftChange ? initialDraft?.tender_no || initialTenderNo : localTenderNo;
  const tenderLx: TenderLx =
    onDraftChange && (initialDraft?.tender_lx === 0 || initialDraft?.tender_lx === 1)
      ? initialDraft.tender_lx
      : localTenderLx;
  const fundLx: FundLx =
    onDraftChange && (initialDraft?.fund_lx === 0 || initialDraft?.fund_lx === 1)
      ? initialDraft.fund_lx
      : localFundLx;
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

    if (tenderType === 'gngk' && shouldUpdateFund) {
      const scopedConfig = initialDraft?.gngk_insertion_configs?.[initialFundLx];
      const nextInsertion = resolveInsertionConfig(
        scopedConfig,
        resolveDefaultInsertionConfig(
          tenderType,
          initialFundLx,
          variantConfig.insertionConfigDefaults
        )
      );
      updates.insertion_config = nextInsertion;
      setInsertionConfig(nextInsertion);
    }

    setLocalTenderLx(initialTenderLx);
    setLocalFundLx(initialFundLx);

    if (Object.keys(updates).length > 0) {
      onDraftChange(updates);
    }
  }, [
    initialDraft?.tender_lx,
    initialDraft?.fund_lx,
    initialDraft?.gngk_insertion_configs,
    initialTenderLx,
    initialFundLx,
    onDraftChange,
    tenderType,
    variantConfig.insertionConfigDefaults,
    variantConfig.insertionConfigDefaults.after_text,
    variantConfig.insertionConfigDefaults.before_text,
  ]);

  useEffect(() => {
    if (!onDraftChange) {
      return;
    }

    const updates: Partial<ConversationFormDraft> = {};

    if (!areInsertionConfigsEqual(initialDraft?.insertion_config, insertionConfig)) {
      updates.insertion_config = insertionConfig;
    }

    if (tenderType === 'gngk') {
      const currentScopedConfig = initialDraft?.gngk_insertion_configs?.[fundLx];
      if (!areInsertionConfigsEqual(currentScopedConfig, insertionConfig)) {
        updates.gngk_insertion_configs = {
          ...(initialDraft?.gngk_insertion_configs || {}),
          [fundLx]: insertionConfig,
        };
      }
    }

    if (Object.keys(updates).length > 0) {
      onDraftChange(updates);
    }
  }, [
    fundLx,
    initialDraft?.gngk_insertion_configs,
    initialDraft?.insertion_config,
    insertionConfig,
    onDraftChange,
    tenderType,
  ]);

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
    (
      nextOriginFile: UploadedFile | null,
      nextCleanDraftFile: UploadedFile | null,
      nextParamFiles: UploadedFile[]
    ) => {
      if (!onDraftChange) {
        return;
      }

      const nextOriginTender = toDraftFile(nextOriginFile);
      const nextCleanDraft = toDraftFile(nextCleanDraftFile);
      onDraftChange({
        files: {
          ...(nextOriginTender ? { origin_tender: nextOriginTender } : {}),
          ...(nextCleanDraft ? { clean_draft: nextCleanDraft } : {}),
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
      if (fundLx === nextFundLx) {
        return;
      }

      setLocalFundLx(nextFundLx);

      const nextUpdates: Partial<ConversationFormDraft> = {
        fund_lx: nextFundLx,
      };

      if (tenderType === 'gngk') {
        const currentScopedConfigs = initialDraft?.gngk_insertion_configs || {};
        const nextScopedConfigs = {
          ...currentScopedConfigs,
          [fundLx]: insertionConfig,
        };
        const targetScoped = nextScopedConfigs[nextFundLx];
        const nextInsertion = resolveInsertionConfig(
          targetScoped,
          resolveDefaultInsertionConfig(
            tenderType,
            nextFundLx,
            variantConfig.insertionConfigDefaults
          )
        );

        nextUpdates.gngk_insertion_configs = nextScopedConfigs;
        nextUpdates.insertion_config = nextInsertion;
        setInsertionConfig(nextInsertion);
      }

      onDraftChange?.(nextUpdates);

      const url = new URL(window.location.href);
      url.searchParams.set('fund_lx', String(nextFundLx));
      window.history.replaceState(window.history.state, '', url.toString());
    },
    [
      fundLx,
      initialDraft?.gngk_insertion_configs,
      insertionConfig,
      onDraftChange,
      tenderType,
      variantConfig.insertionConfigDefaults,
    ]
  );

  const handleTenderLxChange = useCallback(
    (nextTenderLx: TenderLx) => {
      if (tenderLx === nextTenderLx) {
        return;
      }

      setLocalTenderLx(nextTenderLx);
      onDraftChange?.({
        tender_lx: nextTenderLx,
      });

      const url = new URL(window.location.href);
      url.searchParams.set('tender_lx', String(nextTenderLx));
      window.history.replaceState(window.history.state, '', url.toString());
    },
    [onDraftChange, tenderLx]
  );

  const handleBeforeTextChange = useCallback(
    (value: string) => {
      const next = { ...insertionConfig, before_text: value };
      setInsertionConfig(next);
      if (tenderType === 'gngk') {
        onDraftChange?.({
          insertion_config: next,
          gngk_insertion_configs: {
            ...(initialDraft?.gngk_insertion_configs || {}),
            [fundLx]: next,
          },
        });
      } else {
        onDraftChange?.({ insertion_config: next });
      }
    },
    [fundLx, initialDraft?.gngk_insertion_configs, insertionConfig, onDraftChange, tenderType]
  );

  const handleAfterTextChange = useCallback(
    (value: string) => {
      const next = { ...insertionConfig, after_text: value };
      setInsertionConfig(next);
      if (tenderType === 'gngk') {
        onDraftChange?.({
          insertion_config: next,
          gngk_insertion_configs: {
            ...(initialDraft?.gngk_insertion_configs || {}),
            [fundLx]: next,
          },
        });
      } else {
        onDraftChange?.({ insertion_config: next });
      }
    },
    [fundLx, initialDraft?.gngk_insertion_configs, insertionConfig, onDraftChange, tenderType]
  );

  const originUploaderFiles = useMemo(() => (originFile ? [originFile] : []), [originFile]);
  const cleanDraftUploaderFiles = useMemo(
    () => (cleanDraftFile ? [cleanDraftFile] : []),
    [cleanDraftFile]
  );
  const tenderInfoItems = useMemo(
    () => toTenderInfoItems(tenderType, tenderData, tenderTypeInfo),
    [tenderData, tenderType, tenderTypeInfo]
  );
  const showCancelAction = isSubmitting && canCancel && typeof onCancel === 'function';

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

        const nextCleanDraftFile = response.selected_files.clean_draft
          ? toSelectedUploadedFile(response.selected_files.clean_draft)
          : cleanDraftFile;
        const nextOriginFile = response.selected_files.origin_tender
          ? toSelectedUploadedFile(response.selected_files.origin_tender)
          : originFile;

        if (response.selected_files.clean_draft) {
          setCleanDraftFile(nextCleanDraftFile);
        }
        if (response.selected_files.origin_tender) {
          setOriginFile(nextOriginFile);
        }

        syncDraftFiles(nextOriginFile, nextCleanDraftFile, paramFiles);
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
    [cleanDraftFile, originFile, paramFiles, syncDraftFiles]
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

      if (!originFile && !cleanDraftFile) {
        setError('清洁稿和送审稿至少要上传一个文件');
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
        tender_data: {
          ...tenderData,
          tender_lx: tenderLx,
          fund_source_lx: fundLx,
        },
        model: selectedModel,
        files: {
          origin_tender: originFile || undefined,
          clean_draft: cleanDraftFile || undefined,
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
      originFile,
      cleanDraftFile,
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
              label={sharedUploadCopy.cleanDraftUpload.label}
              description={sharedUploadCopy.cleanDraftUpload.description}
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
              label={sharedUploadCopy.originUpload.label}
              description={sharedUploadCopy.originUpload.description}
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
              maxFiles={10}
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
