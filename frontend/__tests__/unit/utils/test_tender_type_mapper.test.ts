import {
  getTenderTypeFromParams,
  getUrlParamsForTenderType,
  isValidTenderType,
  parseTenderUrlParams,
} from '@/utils/tenderTypeMapper';

describe('tenderTypeMapper', () => {
  it.each([
    { tender_lx: 0 as const, fund_lx: 0 as const, tenderType: 'xjcg' as const },
    { tender_lx: 1 as const, fund_lx: 1 as const, tenderType: 'xjcg' as const },
  ])(
    'maps 询价采购 without depending on tender_lx=$tender_lx or fund_lx=$fund_lx',
    ({ tender_lx, fund_lx, tenderType }) => {
    expect(
      getTenderTypeFromParams({
        tender_lx,
        purchase_method: 5,
        fund_lx,
      })
    ).toEqual({
      tenderType,
      isValid: true,
      errors: [],
    });
    }
  );

  it.each([
    { tender_lx: 0 as const, fund_lx: 0 as const, tenderType: 'gngk' as const },
    { tender_lx: 1 as const, fund_lx: 1 as const, tenderType: 'gngk' as const },
  ])(
    'maps 国内公开 without depending on tender_lx=$tender_lx or fund_lx=$fund_lx',
    ({ tender_lx, fund_lx, tenderType }) => {
    expect(
      getTenderTypeFromParams({
        tender_lx,
        purchase_method: 2,
        fund_lx,
      })
    ).toEqual({
      tenderType,
      isValid: true,
      errors: [],
    });
    }
  );

  it('parses URL params for 询价采购 when tender_lx=1 and fund_lx=1', () => {
    const result = parseTenderUrlParams(
      new URLSearchParams('tenderno=0811-DSITC260712&tender_lx=1&purchase_method=5&fund_lx=1')
    );

    expect(result).toEqual({
      params: {
        tenderno: '0811-DSITC260712',
        tender_lx: 1,
        purchase_method: 5,
        fund_lx: 1,
      },
      tenderType: 'xjcg',
      isValid: true,
      errors: [],
    });
  });

  it('keeps routing valid when tender_lx or fund_lx is missing or invalid', () => {
    expect(
      parseTenderUrlParams(new URLSearchParams('tenderno=TEST-001&purchase_method=5'))
    ).toMatchObject({
      tenderType: 'xjcg',
      isValid: true,
      errors: [],
    });

    expect(
      parseTenderUrlParams(
        new URLSearchParams('tenderno=TEST-002&tender_lx=9&purchase_method=2&fund_lx=abc')
      )
    ).toMatchObject({
      tenderType: 'gngk',
      isValid: true,
      errors: [],
    });
  });

  it('returns canonical outbound URL params for known types', () => {
    expect(getUrlParamsForTenderType('xjcg')).toEqual({
      tender_lx: 0,
      purchase_method: 5,
      fund_lx: 0,
    });
    expect(getUrlParamsForTenderType('gngk')).toEqual({
      tender_lx: 0,
      purchase_method: 2,
      fund_lx: 0,
    });
    expect(getUrlParamsForTenderType('gjgk')).toEqual({
      tender_lx: 0,
      purchase_method: 0,
      fund_lx: 1,
    });
  });

  it('maps all gjgk route variants to gjgk', () => {
    expect(
      getTenderTypeFromParams({
        tender_lx: 0,
        purchase_method: 0,
        fund_lx: 0,
      })
    ).toMatchObject({ tenderType: 'gjgk', isValid: true });

    expect(
      getTenderTypeFromParams({
        tender_lx: 1,
        purchase_method: 0,
        fund_lx: 1,
      })
    ).toMatchObject({ tenderType: 'gjgk', isValid: true });
  });

  it('accepts gjgk as a valid tender type', () => {
    expect(isValidTenderType('gjgk')).toBe(true);
  });

  it('treats invalid fund_lx as undefined while keeping gjgk resolution', () => {
    const result = parseTenderUrlParams(
      new URLSearchParams('tender_lx=1&purchase_method=0&fund_lx=2&tenderno=GJGK001')
    );

    expect(result.tenderType).toBe('gjgk');
    expect(result.params.fund_lx).toBeUndefined();
  });
});
