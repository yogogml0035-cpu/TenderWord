/**
 * Application-wide type definitions
 */

// Tender types
export type TenderType = 'xjcg' | 'gngk' | 'gjgk'; // 询价采购 | 国内公开 | 国际公开
export type PurchaseMethod = 0 | 1 | 2 | 5;
export type FundLx = 0 | 1;
export type FundType = FundLx; // 兼容旧命名

export interface TenderConfig {
  formId: string;
  tabName: string;
  graphName: string;
  urlParams: {
    tender_lx: number;
    purchase_method: number;
    fund_lx: FundLx;
  };
}

// Form data types
export interface TenderFormData {
  tenderNo: string;
  templateFile?: File;
  paramFiles?: File[];
  model: string;
}

// Task types
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: string;
  status: TaskStatus;
  progress: number;
  message?: string;
  result?: string;
  error?: string;
  createdAt: Date;
  updatedAt: Date;
}

// History types
export interface GenerationHistory {
  id: string;
  tenderNo: string;
  type: TenderType;
  status: TaskStatus;
  createdAt: Date;
  completedAt?: Date;
  outputFile?: string;
}

// API Response types
export interface ApiError {
  message: string;
  code?: string;
}

// User session
export interface UserSession {
  id: string;
  createdAt: Date;
}

// Re-export API types
export * from './api';
