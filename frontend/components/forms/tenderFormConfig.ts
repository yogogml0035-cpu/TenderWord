import type { TenderType } from '@/types';

export interface TenderInsertionConfig {
  before_text: string;
  after_text: string;
}

export interface TenderFormVariantConfig {
  insertionConfigDefaults: TenderInsertionConfig;
}

export const tenderFormVariantConfigMap: Record<TenderType, TenderFormVariantConfig> = {
  xjcg: {
    insertionConfigDefaults: {
      before_text: '第三章  采购需求',
      after_text: '第四章  响应文件有关格式',
    },
  },
  gngk: {
    insertionConfigDefaults: {
      before_text: '第三章 招标内容及要求',
      after_text: '第四章 投标文件有关格式',
    },
  },
};
