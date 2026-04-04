import {
  getTenderTypeFromParams,
  getUrlParamsForTenderType,
  isValidTenderType,
  parseTenderUrlParams,
} from './tenderTypeMapper';

describe('tenderTypeMapper', () => {
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

  it('returns canonical gjgk url params', () => {
    expect(getUrlParamsForTenderType('gjgk')).toEqual({
      tender_lx: 0,
      purchase_method: 0,
      fund_lx: 1,
    });
  });

  it('accepts gjgk as a valid tender type', () => {
    expect(isValidTenderType('gjgk')).toBe(true);
  });

  it('treats invalid fund_lx as undefined while keeping tender type resolution', () => {
    const result = parseTenderUrlParams(
      new URLSearchParams('tender_lx=1&purchase_method=0&fund_lx=2&tenderno=GJGK001')
    );

    expect(result.tenderType).toBe('gjgk');
    expect(result.params.fund_lx).toBeUndefined();
  });

  it('treats invalid tender_lx as undefined while keeping tender type resolution', () => {
    const result = parseTenderUrlParams(
      new URLSearchParams('tender_lx=9&purchase_method=2&fund_lx=0&tenderno=GNGK001')
    );

    expect(result.tenderType).toBe('gngk');
    expect(result.params.tender_lx).toBeUndefined();
  });
});
