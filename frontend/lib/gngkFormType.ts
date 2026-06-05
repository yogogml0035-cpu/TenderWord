import type { GenerateRequest } from '@/types/api';
import type { FundLx, TenderLx } from '@/types';

export interface ResolveGngkFormTypeInput {
  tender_lx: TenderLx;
  fund_lx: FundLx;
  ifzgcg?: number;
}

export type GngkFormType = Extract<
  GenerateRequest['form_type'],
  | 'gngk_hw_zc_tender'
  | 'gngk_hw_cz_tender'
  | 'gngk_fw_zc_tender'
  | 'gngk_fw_cz_tender'
>;

export function resolveGngkFormType({
  tender_lx,
  fund_lx,
  ifzgcg,
}: ResolveGngkFormTypeInput): GngkFormType {
  // 工程类当前先复用服务链路，避免因缺少独立 graph 导致无法提交。
  if (tender_lx === 1 || tender_lx === 2) {
    return fund_lx === 1 && ifzgcg !== 2 ? 'gngk_fw_cz_tender' : 'gngk_fw_zc_tender';
  }

  if (fund_lx === 1 && ifzgcg !== 2) {
    return 'gngk_hw_cz_tender';
  }

  return 'gngk_hw_zc_tender';
}
