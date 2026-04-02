'use client';

import { useSearchParams } from 'next/navigation';
import { useMemo } from 'react';
import { TenderType } from '@/types';
import { parseTenderUrlParams, getTenderNo } from '@/utils/tenderTypeMapper';

/**
 * URL参数解析Hook的返回类型
 */
export interface UseUrlParamsReturn {
  /** 招标编号 */
  tenderno: string | undefined;
  /** 资金类型（仅 0|1） */
  fund_lx: 0 | 1 | undefined;
  /** 招标类型 */
  tenderType: TenderType | undefined;
  /** 参数是否有效 */
  isValid: boolean;
  /** 错误信息列表 */
  errors: string[];
  /** 原始URLSearchParams对象 */
  searchParams: URLSearchParams | null;
  /** 是否存在URL参数 */
  hasParams: boolean;
}

/**
 * 解析URL参数的React Hook
 * 
 * 该Hook使用Next.js的useSearchParams来安全地读取URL参数，
 * 并解析出招标编号、招标类型等信息。
 * 
 * @returns URL参数解析结果
 * 
 * @example
 * ```typescript
 * // 完整URL: /tender?tender_lx=0&purchase_method=2&fund_lx=0&tenderno=TEST001
 * function MyComponent() {
 *   const { tenderno, tenderType, isValid, errors } = useUrlParams();
 *   
 *   if (!isValid) {
 *     return <div>错误: {errors.join(', ')}</div>;
 *   }
 *   
 *   return <div>招标编号: {tenderno}, 类型: {tenderType}</div>;
 * }
 * ```
 * 
 * @example
 * ```typescript
 * // 缺少tenderno
 * // URL: /tender?tender_lx=0&purchase_method=2&fund_lx=0
 * function MyComponent() {
 *   const { tenderno, tenderType, isValid, errors } = useUrlParams();
 *   // tenderno: undefined
 *   // tenderType: 'gngk'
 *   // isValid: true
 *   // errors: []
 * }
 * ```
 */
export function useUrlParams(): UseUrlParamsReturn {
  const searchParams = useSearchParams();

  return useMemo((): UseUrlParamsReturn => {
    // 处理searchParams为null的情况（SSR期间）
    if (!searchParams) {
      return {
        tenderno: undefined,
        fund_lx: undefined,
        tenderType: undefined,
        isValid: false,
        errors: ['Search params not available'],
        searchParams: null,
        hasParams: false,
      };
    }

    // 检查是否有任何参数
    const hasParams = searchParams.toString().length > 0;

    // 解析招标编号（可选参数）
    const tenderno = getTenderNo(searchParams);

    // 解析招标类型参数
    const result = parseTenderUrlParams(searchParams);
    const fund_lx = result.params.fund_lx === 0 || result.params.fund_lx === 1
      ? result.params.fund_lx
      : undefined;

    // 如果没有参数，返回空状态但不标记为错误
    if (!hasParams) {
      return {
        tenderno: undefined,
        fund_lx: undefined,
        tenderType: undefined,
        isValid: true,
        errors: [],
        searchParams,
        hasParams: false,
      };
    }

    return {
      tenderno,
      fund_lx,
      tenderType: result.tenderType,
      isValid: result.isValid,
      errors: result.errors,
      searchParams,
      hasParams,
    };
  }, [searchParams]);
}

/**
 * 仅获取招标编号的简化Hook
 * 
 * @returns 招标编号或undefined
 * 
 * @example
 * ```typescript
 * function MyComponent() {
 *   const tenderno = useTenderNo();
 *   return <div>招标编号: {tenderno || '未提供'}</div>;
 * }
 * ```
 */
export function useTenderNo(): string | undefined {
  const searchParams = useSearchParams();
  
  return useMemo(() => {
    if (!searchParams) return undefined;
    return getTenderNo(searchParams);
  }, [searchParams]);
}

/**
 * 仅获取招标类型的简化Hook
 * 
 * @returns 招标类型及验证结果
 * 
 * @example
 * ```typescript
 * function MyComponent() {
 *   const { tenderType, isValid, errors } = useTenderType();
 *   
 *   if (!isValid) {
 *     return <div>无效的类型参数</div>;
 *   }
 *   
 *   return <div>当前类型: {tenderType}</div>;
 * }
 * ```
 */
export function useTenderType(): {
  tenderType: TenderType | undefined;
  isValid: boolean;
  errors: string[];
} {
  const { tenderType, isValid, errors } = useUrlParams();
  
  return useMemo(() => ({
    tenderType,
    isValid,
    errors,
  }), [tenderType, isValid, errors]);
}

export default useUrlParams;
