/**
 * Application-wide type definitions
 */

// Tender types
export type TenderType = 'xjcg' | 'gkzb' | 'yqzb'; // 询价采购 | 公开招标 | 邀请招标
export type PurchaseMethod = 0 | 1 | 2 | 5;
export type FundType = 0 | 1; // 0=国内, 1=国际

export interface TenderConfig {
  formId: string;
  tabName: string;
  graphName: string;
  urlParams: {
    tender_lx: number;
    purchase_method: number;
    fund_lx: number;
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
