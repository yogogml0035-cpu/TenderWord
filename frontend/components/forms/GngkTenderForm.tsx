'use client';

import {
  TenderFormShared,
  type BaseTenderFormData,
  type TenderFormSharedProps,
} from './TenderFormShared';

export type GngkTenderFormData = BaseTenderFormData;

export type GngkTenderFormProps = Omit<
  TenderFormSharedProps<GngkTenderFormData>,
  'tenderType'
>;

export function GngkTenderForm(props: GngkTenderFormProps) {
  return <TenderFormShared<GngkTenderFormData> tenderType="gngk" {...props} />;
}

export default GngkTenderForm;
