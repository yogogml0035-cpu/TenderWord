import {
  convertGjgkFormToApiRequest,
  convertGngkFormToApiRequest,
  convertXjcgFormToApiRequest,
} from '@/lib/formDataConverter';

const baseTenderData = {
  project_name: '测试项目',
  project_number: 'TEST-001',
  project_content: '测试内容',
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
};

const baseFiles = {
  template: {
    id: 'template',
    file_path: '/uploads/template.docx',
    file_name: 'template.docx',
    original_name: 'template.docx',
    size: 100,
    upload_time: '2026-03-01T00:00:00.000Z',
  },
  tender_params: [
    {
      id: 'params',
      file_path: '/uploads/params.docx',
      file_name: 'params.docx',
      original_name: 'params.docx',
      size: 100,
      upload_time: '2026-03-01T00:00:00.000Z',
    },
  ],
};

describe('formDataConverter', () => {
  it.each([
    ['xjcg', () =>
      convertXjcgFormToApiRequest({
        tender_no: 'XJCG-001',
        tender_lx: 1,
        fund_lx: 0,
        generation_mode: 'agent',
        comment_generation_mode: 'off',
        generation_style: 'param',
        style_writeback_mode: 'bold_only',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章  采购需求',
          after_text: '第四章  响应文件有关格式',
        },
      })],
    ['gngk', () =>
      convertGngkFormToApiRequest({
        tender_no: 'GNGK-001',
        tender_lx: 2,
        fund_lx: 1,
        generation_mode: 'agent',
        comment_generation_mode: 'off',
        generation_style: 'param',
        style_writeback_mode: 'bold_only',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章 招标内容及要求',
          after_text: '第四章 投标文件有关格式',
        },
      })],
    ['gjgk', () =>
      convertGjgkFormToApiRequest({
        tender_no: 'GJGK-001',
        tender_lx: 1,
        fund_lx: 1,
        generation_mode: 'agent',
        comment_generation_mode: 'off',
        generation_style: 'param',
        style_writeback_mode: 'bold_only',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '技术规格及要求',
          after_text: '附件1：投标文件封面（格式）',
        },
      })],
  ] as const)(
    'forwards generation settings and template payload for %s converters',
    (_tenderType, buildRequest) => {
      const request = buildRequest();
      expect(request.generation_mode).toBe('agent');
      expect(request.comment_generation_mode).toBe('off');
      expect(request.generation_style).toBe('param');
      expect(request.style_writeback_mode).toBe('bold_only');
      expect(request.file_paths).toEqual({
        template: '/uploads/template.docx',
        tender_params: [{ file_path: '/uploads/params.docx', original_name: 'params.docx' }],
      });
      expect(Object.keys(request.file_paths).sort()).toEqual(['template', 'tender_params']);
    }
  );

  it.each([
    ['xjcg', () =>
      convertXjcgFormToApiRequest({
        tender_no: 'XJCG-001',
        tender_lx: 0,
        fund_lx: 0,
        generation_style: 'template',
        style_writeback_mode: 'full',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章  采购需求',
          after_text: '第四章  响应文件有关格式',
        },
      })],
    ['gngk', () =>
      convertGngkFormToApiRequest({
        tender_no: 'GNGK-001',
        tender_lx: 0,
        fund_lx: 0,
        generation_style: 'template',
        style_writeback_mode: 'full',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章 招标内容及要求',
          after_text: '第四章 投标文件有关格式',
        },
      })],
    ['gjgk', () =>
      convertGjgkFormToApiRequest({
        tender_no: 'GJGK-001',
        tender_lx: 0,
        fund_lx: 1,
        generation_style: 'template',
        style_writeback_mode: 'full',
        tender_data: baseTenderData,
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '技术规格及要求',
          after_text: '附件1：投标文件封面（格式）',
        },
      })],
  ] as const)(
    'defaults generation_mode to workflow for %s converters',
    (_tenderType, buildRequest) => {
      expect(buildRequest().generation_mode).toBe('workflow');
      expect(buildRequest().comment_generation_mode).toBe('on');
    }
  );

  it.each([
    { tender_lx: 0 as const, fund_lx: 0 as const, expected: 'gngk_hw_zc_tender' },
    { tender_lx: 0 as const, fund_lx: 1 as const, expected: 'gngk_hw_cz_tender' },
    { tender_lx: 1 as const, fund_lx: 0 as const, expected: 'gngk_fw_zc_tender' },
    { tender_lx: 1 as const, fund_lx: 1 as const, expected: 'gngk_fw_cz_tender' },
    { tender_lx: 2 as const, fund_lx: 0 as const, expected: 'gngk_fw_zc_tender' },
    { tender_lx: 2 as const, fund_lx: 1 as const, expected: 'gngk_fw_cz_tender' },
  ])('maps gngk tender_lx=$tender_lx fund_lx=$fund_lx to $expected', ({ tender_lx, fund_lx, expected }) => {
    const request = convertGngkFormToApiRequest({
      tender_no: 'GNGK-001',
      tender_lx,
      fund_lx,
      generation_style: 'template',
      style_writeback_mode: 'full',
      tender_data: baseTenderData,
      model: 'deepseek',
      files: baseFiles,
      insertion_config: {
        before_text: '第三章 招标内容及要求',
        after_text: '第四章 投标文件有关格式',
      },
    });

    expect(request.form_type).toBe(expected);
    expect(request.tender_data.tender_lx).toBe(tender_lx);
    expect(request.tender_data.fund_source_lx).toBe(fund_lx);
  });

  it.each([
    { ifzgcg: 2, expected: 'gngk_hw_zc_tender' },
    { ifzgcg: 1, expected: 'gngk_hw_cz_tender' },
    { ifzgcg: undefined, expected: 'gngk_hw_cz_tender' },
  ])(
    'maps gngk goods fiscal ifzgcg=$ifzgcg to $expected while keeping fiscal tender data',
    ({ ifzgcg, expected }) => {
      const request = convertGngkFormToApiRequest({
        tender_no: 'GNGK-001',
        tender_lx: 0,
        fund_lx: 1,
        generation_style: 'template',
        style_writeback_mode: 'full',
        tender_data: {
          ...baseTenderData,
          ...(ifzgcg === undefined ? {} : { ifzgcg }),
        },
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章 招标内容及要求',
          after_text: '第四章 投标文件有关格式',
        },
      });

      expect(request.form_type).toBe(expected);
      expect(request.tender_data.tender_lx).toBe(0);
      expect(request.tender_data.fund_source_lx).toBe(1);
    }
  );

  it.each([
    { ifzgcg: 2, expected: 'gngk_fw_zc_tender' },
    { ifzgcg: 1, expected: 'gngk_fw_cz_tender' },
    { ifzgcg: undefined, expected: 'gngk_fw_cz_tender' },
  ])(
    'maps gngk service fiscal ifzgcg=$ifzgcg to $expected while keeping fiscal tender data',
    ({ ifzgcg, expected }) => {
      const request = convertGngkFormToApiRequest({
        tender_no: 'GNGK-001',
        tender_lx: 2,
        fund_lx: 1,
        generation_style: 'template',
        style_writeback_mode: 'full',
        tender_data: {
          ...baseTenderData,
          ...(ifzgcg === undefined ? {} : { ifzgcg }),
        },
        model: 'deepseek',
        files: baseFiles,
        insertion_config: {
          before_text: '第三章 招标内容及要求',
          after_text: '第四章 投标文件有关格式',
        },
      });

      expect(request.form_type).toBe(expected);
      expect(request.tender_data.tender_lx).toBe(2);
      expect(request.tender_data.fund_source_lx).toBe(1);
    }
  );

  it('keeps xjcg graph selection stable while forwarding tender_lx', () => {
    const request = convertXjcgFormToApiRequest({
      tender_no: 'XJCG-001',
      tender_lx: 2,
      fund_lx: 0,
      generation_style: 'template',
      style_writeback_mode: 'full',
      tender_data: baseTenderData,
      model: 'deepseek',
      files: baseFiles,
      insertion_config: {
        before_text: '第三章  采购需求',
        after_text: '第四章  响应文件有关格式',
      },
    });

    expect(request.form_type).toBe('xjcg_tender');
    expect(request.tender_data.tender_lx).toBe(2);
  });

  it('keeps gjgk graph selection stable while forwarding tender_lx', () => {
    const request = convertGjgkFormToApiRequest({
      tender_no: 'GJGK-001',
      tender_lx: 1,
      fund_lx: 1,
      generation_style: 'template',
      style_writeback_mode: 'full',
      tender_data: baseTenderData,
      model: 'deepseek',
      files: baseFiles,
      insertion_config: {
        before_text: '技术规格及要求',
        after_text: '附件1：投标文件封面（格式）',
      },
    });

    expect(request.form_type).toBe('gjgk_tender');
    expect(request.tender_data.tender_lx).toBe(1);
    expect(request.tender_data.fund_source_lx).toBe(1);
  });

  it('forwards tender_params as ordered { file_path, original_name } objects', () => {
    const multiFiles = {
      template: baseFiles.template,
      tender_params: [
        {
          id: 'params-1',
          file_path: '/uploads/uuid-1.docx',
          file_name: 'uuid-1.docx',
          original_name: '第一包技术参数.docx',
          size: 100,
          upload_time: '2026-03-01T00:00:00.000Z',
        },
        {
          id: 'params-2',
          file_path: '/uploads/uuid-2.docx',
          file_name: 'uuid-2.docx',
          original_name: '第二包技术参数.docx',
          size: 100,
          upload_time: '2026-03-01T00:00:00.000Z',
        },
        {
          id: 'params-3',
          file_path: '/uploads/uuid-3.docx',
          file_name: 'uuid-3.docx',
          original_name: '第三包技术参数.docx',
          size: 100,
          upload_time: '2026-03-01T00:00:00.000Z',
        },
      ],
    };

    const request = convertXjcgFormToApiRequest({
      tender_no: 'XJCG-001',
      tender_lx: 0,
      fund_lx: 0,
      generation_style: 'template',
      style_writeback_mode: 'full',
      tender_data: baseTenderData,
      model: 'deepseek',
      files: multiFiles,
      insertion_config: {
        before_text: '第三章  采购需求',
        after_text: '第四章  响应文件有关格式',
      },
    });

    // 按界面显示顺序发送对象形式；original_name 用上传原名（非后端保存文件名）。
    expect(request.file_paths.tender_params).toEqual([
      { file_path: '/uploads/uuid-1.docx', original_name: '第一包技术参数.docx' },
      { file_path: '/uploads/uuid-2.docx', original_name: '第二包技术参数.docx' },
      { file_path: '/uploads/uuid-3.docx', original_name: '第三包技术参数.docx' },
    ]);
  });
});
