import {
  getTenderTypeFromParams,
  getUrlParamsForTenderType,
  isValidTenderType,
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
        tender_lx: 0,
        purchase_method: 0,
        fund_lx: 1,
      })
    ).toMatchObject({ tenderType: 'gjgk', isValid: true });

    expect(
      getTenderTypeFromParams({
        tender_lx: 0,
        purchase_method: 0,
        fund_lx: 2,
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
});
