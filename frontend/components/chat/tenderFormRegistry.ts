import type { ComponentType } from 'react';
import type { TenderType } from '@/types';
import type { ConversationFormDraft } from '@/stores/chatStore';
import type { GenerateRequest, TenderData } from '@/types/api';
import { XjcgTenderForm, type XjcgTenderFormData } from '@/components/forms/XjcgTenderForm';
import { GngkTenderForm, type GngkTenderFormData } from '@/components/forms/GngkTenderForm';
import { convertGngkFormToApiRequest, convertXjcgFormToApiRequest } from '@/lib/formDataConverter';

export type TenderFormData = XjcgTenderFormData | GngkTenderFormData;

export interface TenderFormComponentProps {
  onSubmit: (data: TenderFormData) => Promise<void> | void;
  className?: string;
  initialTenderNo?: string;
  initialTenderData?: TenderData | null;
  initialDraft?: ConversationFormDraft | null;
  onDraftChange?: (updates: Partial<ConversationFormDraft>) => void;
  isSubmitting?: boolean;
  canCancel?: boolean;
  onCancel?: () => Promise<void> | void;
}

type TenderFormConverter = (formData: TenderFormData) => GenerateRequest;

export const tenderTypeDisplayNameMap: Record<TenderType, string> = {
  xjcg: '询价采购',
  gngk: '国内公开',
};

export const tenderFormComponentMap: Record<TenderType, ComponentType<TenderFormComponentProps>> = {
  xjcg: XjcgTenderForm as ComponentType<TenderFormComponentProps>,
  gngk: GngkTenderForm as ComponentType<TenderFormComponentProps>,
};

export const tenderFormConverterMap: Record<TenderType, TenderFormConverter> = {
  xjcg: (formData) => convertXjcgFormToApiRequest(formData as XjcgTenderFormData),
  gngk: (formData) => convertGngkFormToApiRequest(formData as GngkTenderFormData),
};
