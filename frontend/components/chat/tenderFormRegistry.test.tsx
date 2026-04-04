import {
  tenderFormComponentMap,
  tenderFormConverterMap,
  tenderTypeDisplayNameMap,
} from './tenderFormRegistry';

describe('tenderFormRegistry', () => {
  it('registers gjgk display name and component', () => {
    expect(tenderTypeDisplayNameMap.gjgk).toBe('国际公开');
    expect(tenderFormComponentMap.gjgk).toBeDefined();
  });

  it('converts gjgk form data to gjgk_tender request', () => {
    const request = tenderFormConverterMap.gjgk({
      tender_no: 'GJ-001',
      tender_lx: 1,
      fund_lx: 1,
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

    expect(request.form_type).toBe('gjgk_tender');
    expect(request.tender_data.tender_lx).toBe(1);
    expect(request.tender_data.fund_source_lx).toBe(1);
  });
});
