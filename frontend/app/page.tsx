import { MainLayout } from '@/components/layout/MainLayout';
import { FileText, ArrowRight, Sparkles } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto">
        {/* Hero Section */}
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-[var(--primary)]/10 rounded-2xl mb-6">
            <Sparkles className="w-10 h-10 text-[var(--primary)]" />
          </div>
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-4">
            欢迎使用 TenderWord
          </h1>
          <p className="text-lg text-[var(--text-muted)] max-w-2xl mx-auto">
            智能招标文件生成系统，基于 LangGraph 和 AI 技术，
            快速生成专业的招标文件
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <QuickActionCard
            href="/tender/xjcg"
            title="询价采购"
            description="快速创建询价采购招标文件"
            icon={<FileText className="w-6 h-6" />}
          />
          <QuickActionCard
            href="/tender/gkzb"
            title="公开招标"
            description="创建标准的公开招标文档"
            icon={<FileText className="w-6 h-6" />}
          />
          <QuickActionCard
            href="/tender/yqzb"
            title="邀请招标"
            description="生成邀请招标相关文档"
            icon={<FileText className="w-6 h-6" />}
          />
        </div>

        {/* Features */}
        <div className="mt-16">
          <h2 className="text-2xl font-semibold text-center mb-8">功能特性</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <FeatureCard
              title="智能生成"
              description="基于 AI 技术，自动分析需求并生成专业招标文件"
            />
            <FeatureCard
              title="多模型支持"
              description="支持 DeepSeek、Qwen、Doubao 等多种大语言模型"
            />
            <FeatureCard
              title="实时进度"
              description="生成过程中实时显示进度和状态更新"
            />
            <FeatureCard
              title="历史记录"
              description="自动保存生成历史，方便查看和管理"
            />
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

function QuickActionCard({
  href,
  title,
  description,
  icon,
}: {
  href: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="st-card group hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[var(--secondary-bg)] rounded-lg text-[var(--primary)]">
            {icon}
          </div>
          <h3 className="font-semibold text-[var(--foreground)]">{title}</h3>
        </div>
        <ArrowRight className="w-5 h-5 text-[var(--text-muted)] group-hover:text-[var(--primary)] group-hover:translate-x-1 transition-all" />
      </div>
      <p className="mt-3 text-sm text-[var(--text-muted)]">{description}</p>
    </Link>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="st-card">
      <h3 className="font-semibold text-[var(--foreground)] mb-2">{title}</h3>
      <p className="text-sm text-[var(--text-muted)]">{description}</p>
    </div>
  );
}
