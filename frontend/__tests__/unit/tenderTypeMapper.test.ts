import {
  getTenderTypeFromParams,
  getUrlParamsForTenderType,
  parseTenderUrlParams,
} from '@/utils/tenderTypeMapper';

describe('tenderTypeMapper', () => {
  it.each([
    { fund_lx: 0, tenderType: 'xjcg' },
    { fund_lx: 1, tenderType: 'xjcg' },
  ])('maps 询价采购 without depending on fund_lx=$fund_lx', ({ fund_lx, tenderType }) => {
    expect(
      getTenderTypeFromParams({
        tender_lx: 0,
        purchase_method: 5,
        fund_lx,
      })
    ).toEqual({
      tenderType,
      isValid: true,
      errors: [],
    });
  });

  it.each([
    { fund_lx: 0, tenderType: 'gngk' },
    { fund_lx: 1, tenderType: 'gngk' },
  ])('maps 国内公开 without depending on fund_lx=$fund_lx', ({ fund_lx, tenderType }) => {
    expect(
      getTenderTypeFromParams({
        tender_lx: 0,
        purchase_method: 2,
        fund_lx,
      })
    ).toEqual({
      tenderType,
      isValid: true,
      errors: [],
    });
  });

  it('parses URL params for 询价采购 when fund_lx=1', () => {
    const result = parseTenderUrlParams(
      new URLSearchParams('tenderno=0811-DSITC260712&tender_lx=0&purchase_method=5&fund_lx=1')
    );

    expect(result).toEqual({
      params: {
        tenderno: '0811-DSITC260712',
        tender_lx: 0,
        purchase_method: 5,
        fund_lx: 1,
      },
      tenderType: 'xjcg',
      isValid: true,
      errors: [],
    });
  });

  it('keeps routing valid when fund_lx is missing or invalid', () => {
    expect(
      parseTenderUrlParams(new URLSearchParams('tenderno=TEST-001&tender_lx=0&purchase_method=5'))
    ).toMatchObject({
      tenderType: 'xjcg',
      isValid: true,
      errors: [],
    });

    expect(
      parseTenderUrlParams(
        new URLSearchParams('tenderno=TEST-002&tender_lx=0&purchase_method=2&fund_lx=abc')
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
  });
});
