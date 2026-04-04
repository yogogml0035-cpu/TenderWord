import { FundLx, TenderLx, TenderType } from '@/types';

/**
 * 招标类型映射规则
 * key格式: purchase_method
 * tender_lx / fund_lx 仅作为按钮态输入，不参与前端判型
 * value: 对应的TenderType
 */
export const TYPE_MAPPING: Record<string, TenderType> = {
  '2': 'gngk',     // 国内公开
  '5': 'xjcg',     // 询价采购
  '0': 'gjgk',     // 国际公开
};

const DEFAULT_URL_PARAMS_BY_TYPE: Record<
  TenderType,
  { tender_lx: TenderLx; purchase_method: number; fund_lx: FundLx }
> = {
  gngk: { tender_lx: 0, purchase_method: 2, fund_lx: 0 },
  xjcg: { tender_lx: 0, purchase_method: 5, fund_lx: 0 },
  gjgk: { tender_lx: 0, purchase_method: 0, fund_lx: 1 },
};

/**
 * URL参数接口
 */
export interface TenderUrlParams {
  tender_lx?: TenderLx;
  purchase_method: number;
  fund_lx?: 0 | 1;
  tenderno?: string;
}

/**
 * 映射结果接口
 */
export interface TenderTypeMappingResult {
  tenderType?: TenderType;
  isValid: boolean;
  errors: string[];
}

/**
 * 从URL参数中获取招标类型
 * 
 * @param params - URL参数对象或URLSearchParams
 * @returns 映射结果，包含tenderType、isValid和errors
 * 
 * @example
 * ```typescript
 * const result = getTenderTypeFromParams({
 *   tender_lx: 1,
 *   fund_lx: 0,
 *   purchase_method: 2
 * });
 * // result: { tenderType: 'gngk', isValid: true, errors: [] }
 * ```
 */
export function getTenderTypeFromParams(
  params: TenderUrlParams | URLSearchParams
): TenderTypeMappingResult {
  const errors: string[] = [];

  // 提取参数值
  let purchase_method: number | undefined;

  if (params instanceof URLSearchParams) {
    purchase_method = parseInt(params.get('purchase_method') || '', 10);
  } else {
    purchase_method = params.purchase_method;
  }

  if (purchase_method === undefined || isNaN(purchase_method)) {
    errors.push('Missing or invalid purchase_method parameter');
  }

  if (errors.length > 0) {
    return {
      tenderType: undefined,
      isValid: false,
      errors,
    };
  }

  // 判型仅依赖 purchase_method
  const mappingKey = `${purchase_method}`;
  const tenderType = TYPE_MAPPING[mappingKey];

  if (!tenderType) {
    return {
      tenderType: undefined,
      isValid: false,
      errors: [
        `Unsupported tender type combination: ${mappingKey}`,
      ],
    };
  }

  return {
    tenderType,
    isValid: true,
    errors: [],
  };
}

/**
 * 获取招标编号
 * 
 * @param params - URL参数对象或URLSearchParams
 * @returns 招标编号或undefined
 * 
 * @example
 * ```typescript
 * const tenderno = getTenderNo({ tenderno: 'TEST001' });
 * // tenderno: 'TEST001'
 * ```
 */
export function getTenderNo(
  params: { tenderno?: string } | URLSearchParams
): string | undefined {
  if (params instanceof URLSearchParams) {
    const tenderno = params.get('tenderno');
    return tenderno || undefined;
  }
  return params.tenderno;
}

/**
 * 解析完整的URL参数
 * 
 * @param searchParams - URLSearchParams对象
 * @returns 完整的参数解析结果
 * 
 * @example
 * ```typescript
 * const url = new URL('http://localhost:8502?tender_lx=1&purchase_method=2&fund_lx=0&tenderno=TEST001');
 * const result = parseTenderUrlParams(url.searchParams);
 * // result: {
 * //   params: { tender_lx: 1, purchase_method: 2, fund_lx: 0, tenderno: 'TEST001' },
 * //   tenderType: 'gngk',
 * //   isValid: true,
 * //   errors: []
 * // }
 * ```
 */
export function parseTenderUrlParams(
  searchParams: URLSearchParams
): {
  params: Partial<TenderUrlParams>;
  tenderType?: TenderType;
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  // 安全解析参数
  const parseParam = (
    key: string,
    options?: { allowInvalid?: boolean }
  ): number | undefined => {
    const value = searchParams.get(key);
    if (value === null || value === '') {
      return undefined;
    }
    const num = parseInt(value, 10);
    if (isNaN(num)) {
      if (!options?.allowInvalid) {
        errors.push(`Invalid ${key}: "${value}" is not a valid number`);
      }
      return undefined;
    }
    return num;
  };

  const rawTenderLx = parseParam('tender_lx', { allowInvalid: true });
  const tender_lx = rawTenderLx === 0 || rawTenderLx === 1 ? rawTenderLx : undefined;
  const purchase_method = parseParam('purchase_method');
  const rawFundLx = parseParam('fund_lx', { allowInvalid: true });
  const fund_lx = rawFundLx === 0 || rawFundLx === 1 ? rawFundLx : undefined;
  const tenderno = searchParams.get('tenderno') || undefined;

  // 构建参数对象
  const params: Partial<TenderUrlParams> = {};
  if (tender_lx !== undefined) params.tender_lx = tender_lx;
  if (purchase_method !== undefined) params.purchase_method = purchase_method;
  if (fund_lx !== undefined) params.fund_lx = fund_lx;
  if (tenderno) params.tenderno = tenderno;

  // 验证并获取招标类型
  let tenderTypeResult: TenderTypeMappingResult = {
    tenderType: undefined,
    isValid: false,
    errors: [],
  };

  if (purchase_method !== undefined) {
    tenderTypeResult = getTenderTypeFromParams({
      tender_lx,
      purchase_method,
      fund_lx,
    });
  } else {
    const missingParams = [];
    if (purchase_method === undefined) missingParams.push('purchase_method');
    if (missingParams.length > 0) {
      errors.push(`Missing required parameters: ${missingParams.join(', ')}`);
    }
  }

  return {
    params,
    tenderType: tenderTypeResult.tenderType,
    isValid: tenderTypeResult.isValid && errors.length === 0,
    errors: [...errors, ...tenderTypeResult.errors],
  };
}

/**
 * 类型守卫：检查是否为有效的招标类型
 * 
 * @param value - 待检查的值
 * @returns 是否为有效的TenderType
 */
export function isValidTenderType(value: unknown): value is TenderType {
  return value === 'xjcg' || value === 'gngk' || value === 'gjgk';
}

/**
 * 生成用于URL的招标类型参数
 * 
 * @param tenderType - 招标类型
 * @returns URL参数对象或null（如果类型无效）
 * 
 * @example
 * ```typescript
 * const params = getUrlParamsForTenderType('gngk');
 * // params: { tender_lx: 0, purchase_method: 2, fund_lx: 0 }
 * ```
 */
export function getUrlParamsForTenderType(
  tenderType: TenderType
): { tender_lx: TenderLx; purchase_method: number; fund_lx: FundLx } | null {
  return DEFAULT_URL_PARAMS_BY_TYPE[tenderType] ?? null;
}
