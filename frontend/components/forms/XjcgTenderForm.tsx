'use client';

import {
  TenderFormShared,
  type BaseTenderFormData,
  type TenderFormSharedProps,
} from './TenderFormShared';
import type { TenderInsertionConfig } from './tenderFormConfig';

export interface XjcgTenderFormData {
  tender_no: string;
  tender_lx: BaseTenderFormData['tender_lx'];
  fund_lx: BaseTenderFormData['fund_lx'];
  generation_style: BaseTenderFormData['generation_style'];
  tender_data: BaseTenderFormData['tender_data'];
  model: BaseTenderFormData['model'];
  files: BaseTenderFormData['files'];
  insertion_config?: TenderInsertionConfig;
}

export interface XjcgTenderFormProps
  extends Omit<TenderFormSharedProps<BaseTenderFormData>, 'tenderType' | 'onSubmit'> {
  onSubmit: (data: XjcgTenderFormData) => Promise<void> | void;
}

export function XjcgTenderForm({ onSubmit, ...props }: XjcgTenderFormProps) {
  return (
    <TenderFormShared<BaseTenderFormData>
      tenderType="xjcg"
      onSubmit={(data) => onSubmit(data)}
      {...props}
    />
  );
}

export default XjcgTenderForm;
