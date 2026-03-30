import { ApiError, fetchTenderDataWithType } from '@/lib/api';
import type { TenderData, TenderTypeInfo } from '@/types/api';

export type TenderFetchStatus = 'idle' | 'loading' | 'success' | 'error';

export interface TenderFetchState {
  status: TenderFetchStatus;
  error?: string;
}

export interface TenderDraftUpdates {
  tender_no?: string;
  tender_data?: TenderData | null;
  tender_type_info?: TenderTypeInfo | null;
  tender_fetch?: TenderFetchState;
}

export interface SyncTenderDataDraftOptions {
  tenderNo: string;
  updateDraft: (updates: TenderDraftUpdates) => void;
  onSuccess?: (data: TenderData) => void;
  onError?: (message: string) => void;
}

export function createTenderFetchState(
  status: TenderFetchStatus,
  error?: string
): TenderFetchState {
  return error ? { status, error } : { status };
}

export function resolveTenderFetchState(
  state: TenderFetchState | undefined,
  data: TenderData | null | undefined
): TenderFetchState {
  if (state) {
    return state;
  }

  return data ? createTenderFetchState('success') : createTenderFetchState('idle');
}

export function getTenderFetchErrorMessage(error: unknown): string {
  if (typeof ApiError === 'function' && error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return '获取招标数据失败';
}

export async function syncTenderDataDraft({
  tenderNo,
  updateDraft,
  onSuccess,
  onError,
}: SyncTenderDataDraftOptions): Promise<TenderData | null> {
  const normalizedTenderNo = tenderNo.trim();

  if (!normalizedTenderNo) {
    const errorMessage = '请输入招标编号';
    updateDraft({
      tender_fetch: createTenderFetchState('error', errorMessage),
    });
    onError?.(errorMessage);
    return null;
  }

  updateDraft({
    tender_no: normalizedTenderNo,
    tender_fetch: createTenderFetchState('loading'),
  });

  try {
    const result = await fetchTenderDataWithType(normalizedTenderNo);
    const data = result.data;
    updateDraft({
      tender_no: normalizedTenderNo,
      tender_data: data,
      tender_type_info: result.type,
      tender_fetch: createTenderFetchState('success'),
    });
    onSuccess?.(data);
    return data;
  } catch (error) {
    const errorMessage = getTenderFetchErrorMessage(error);
    updateDraft({
      tender_no: normalizedTenderNo,
      tender_type_info: null,
      tender_fetch: createTenderFetchState('error', errorMessage),
    });
    onError?.(errorMessage);
    return null;
  }
}
