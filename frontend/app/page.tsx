import { MainLayout } from '@/components/layout/MainLayout';
import { Sparkles, MessageSquare } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  return (
    <MainLayout>
      <div className="mx-auto max-w-4xl">
        {/* Hero Section */}
        <div className="py-16 text-center">
          <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-2xl bg-[var(--primary)]/10">
            <Sparkles className="h-10 w-10 text-[var(--primary)]" />
          </div>
          <h1 className="mb-4 text-4xl font-bold text-[var(--foreground)]">欢迎使用 TenderWord</h1>
          <p className="mx-auto max-w-2xl text-lg text-[var(--text-muted)]">
            智能招标文件生成系统，基于 LangGraph 和 AI 技术， 快速生成专业的招标文件
          </p>

          {/* Chat Mode Link */}
          <div className="mt-8">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--primary)] px-6 py-3 text-white transition-colors hover:bg-[var(--primary)]/90"
            >
              <MessageSquare className="h-5 w-5" />
              进入聊天模式
            </Link>
          </div>
        </div>

        {/* Features */}
        <div className="mt-8">
          <h2 className="mb-8 text-center text-2xl font-semibold">功能特性</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <FeatureCard
              title="智能生成"
              description="基于 AI 技术，自动分析需求并生成专业招标文件"
            />
            <FeatureCard
              title="多模型支持"
              description="支持 DeepSeek、Qwen、Doubao 等多种大语言模型"
            />
            <FeatureCard title="实时进度" description="生成过程中实时显示进度和状态更新" />
            <FeatureCard title="历史记录" description="自动保存生成历史，方便查看和管理" />
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="card">
      <h3 className="mb-2 font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="text-sm text-[var(--text-muted)]">{description}</p>
    </div>
  );
}
