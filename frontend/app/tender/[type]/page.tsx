'use client';

import { useParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { cn } from '@/lib/utils';

const tenderTypeMap: Record<string, { title: string; description: string }> = {
  xjcg: {
    title: '询价采购',
    description: '创建询价采购招标文件',
  },
  gkzb: {
    title: '公开招标',
    description: '创建公开招标招标文件',
  },
  yqzb: {
    title: '邀请招标',
    description: '创建邀请招标招标文件',
  },
};

export default function TenderPage() {
  const params = useParams();
  const type = params.type as string;
  const config = tenderTypeMap[type] || {
    title: '未知类型',
    description: '不支持的招标类型',
  };

  return (
    <MainLayout title={config.title} subtitle={config.description}>
      <div className="form-section">
        {/* Form placeholder - will be implemented in next task */}
        <div className="card">
          <div className="flex items-center justify-center h-64 text-[var(--text-muted)]">
            <div className="text-center">
              <p className="text-lg font-medium mb-2">{config.title} 表单</p>
              <p className="text-sm">此页面将在后续任务中实现</p>
              <div className="mt-4 flex justify-center gap-2">
                <span className="badge badge-info">招标类型: {type}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
