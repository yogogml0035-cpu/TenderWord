import { MainLayout } from '@/components/layout/MainLayout';
import { Sparkles, MessageSquare } from 'lucide-react';
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

          {/* Chat Mode Link */}
          <div className="mt-8">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary)]/90 transition-colors"
            >
              <MessageSquare className="w-5 h-5" />
              进入聊天模式
            </Link>
          </div>
        </div>

        {/* Features */}
        <div className="mt-8">
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

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="card">
      <h3 className="font-semibold text-[var(--foreground)] mb-2">{title}</h3>
      <p className="text-sm text-[var(--text-muted)]">{description}</p>
    </div>
  );
}
