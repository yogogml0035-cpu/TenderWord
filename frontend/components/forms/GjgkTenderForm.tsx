'use client';

import {
  TenderFormShared,
  type BaseTenderFormData,
  type TenderFormSharedProps,
} from './TenderFormShared';

export type GjgkTenderFormData = BaseTenderFormData;

export type GjgkTenderFormProps = Omit<
  TenderFormSharedProps<GjgkTenderFormData>,
  'tenderType'
>;

export function GjgkTenderForm(props: GjgkTenderFormProps) {
  return <TenderFormShared<GjgkTenderFormData> tenderType="gjgk" {...props} />;
}

export default GjgkTenderForm;
