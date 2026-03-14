import { Sparkles, MessageSquare } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <main className="min-h-screen">
        <div className="container-wide py-6">
          <div className="mx-auto max-w-4xl">
            <div className="pt-10 pb-8 text-center">
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-2xl bg-[var(--primary)]/10">
                <Sparkles className="h-10 w-10 text-[var(--primary)]" />
              </div>
              <h1 className="mb-4 text-4xl font-bold text-[var(--foreground)]">
                欢迎使用智能招标文件生成助手！
              </h1>
              <p className="mx-auto max-w-2xl text-lg text-[var(--text-muted)]">
                基于大模型快速生成专业的招标文件
              </p>

              <div className="mt-6">
                <Link
                  href="/tender"
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--primary)] px-6 py-3 text-white transition-colors hover:bg-[var(--primary)]/90"
                >
                  <MessageSquare className="h-5 w-5" />
                  进入使用
                </Link>
              </div>
            </div>

            <div className="mt-4">
              <h2 className="mb-6 text-center text-2xl font-semibold">功能特性</h2>
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
        </div>
      </main>
    </div>
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
