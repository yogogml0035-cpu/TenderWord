import {
  tenderFormComponentMap,
  tenderFormConverterMap,
  tenderTypeDisplayNameMap,
} from '@/components/chat/tenderFormRegistry';

describe('tenderFormRegistry', () => {
  it('registers gjgk display name and component', () => {
    expect(tenderTypeDisplayNameMap.gjgk).toBe('国际公开');
    expect(tenderFormComponentMap.gjgk).toBeDefined();
  });

  it.each([
    ['xjcg', 'xjcg_tender'],
    ['gngk', 'gngk_fw_cz_tender'],
    ['gjgk', 'gjgk_tender'],
  ] as const)(
    'preserves generation_mode, generation_style and style_writeback_mode for %s converter',
    (tenderType, formType) => {
      const request = tenderFormConverterMap[tenderType]({
        tender_no: 'GJ-001',
        tender_lx: 1,
        fund_lx: 1,
        generation_mode: 'agent',
        generation_style: 'param',
        style_writeback_mode: 'bold_only',
        tender_data: {
          project_name: '国际项目',
          project_number: 'GJ-001',
          project_content: '国际采购内容',
          bzj_rule: '规则',
          buyer_name: '采购人',
          project_zbr_xbr: '张三',
          zbr_xbr_tel: '13800138000',
          zbr_pinyin: 'zhangsan',
          shell_start_date: '2026-03-01',
          shell_end_date: '2026-03-08',
          submit_date: '2026-03-09',
          platform: '平台A',
          service_fee: '1000',
          tender_lx: 1,
          fund_source_lx: 1,
        },
        model: 'deepseek',
        files: {
          tender_params: [],
        },
        insertion_config: {
          before_text: '技术规格及要求',
          after_text: '附件1：投标文件封面（格式）',
        },
      });

      expect(request.form_type).toBe(formType);
      expect(request.generation_mode).toBe('agent');
      expect(request.generation_style).toBe('param');
      expect(request.style_writeback_mode).toBe('bold_only');
      expect(request.tender_data.tender_lx).toBe(1);
      expect(request.tender_data.fund_source_lx).toBe(1);
    }
  );
});
