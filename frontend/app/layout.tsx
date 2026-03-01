import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TenderWord - 智能招标文件生成系统',
  description: '基于 LangGraph 和 AI 技术的招标文件生成系统',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
