import React from 'react';
import { render, screen } from '../../../utils/test-utils';
import { MainLayout } from '@/components/layout/MainLayout';

jest.mock('next/navigation', () => ({
  usePathname: jest.fn(),
}));

jest.mock('@/components/layout/HistorySection', () => ({
  HistorySection: () => <div data-testid="history-section">history</div>,
}));

const mockUsePathname = jest.requireMock('next/navigation').usePathname as jest.Mock;

describe('MainLayout', () => {
  beforeEach(() => {
    mockUsePathname.mockReset();
  });

  it('hides the sidebar on the home page', () => {
    mockUsePathname.mockReturnValue('/');

    const { container } = render(
      <MainLayout>
        <div>home content</div>
      </MainLayout>
    );

    expect(screen.queryByText('招标文件生成')).not.toBeInTheDocument();
    expect(screen.getByText('home content')).toBeInTheDocument();
    expect(container.querySelector('.main-content')).toBeNull();
  });

  it('keeps the sidebar on non-home pages', () => {
    mockUsePathname.mockReturnValue('/workspace');

    const { container } = render(
      <MainLayout>
        <div>workspace content</div>
      </MainLayout>
    );

    expect(screen.getByText('招标文件生成')).toBeInTheDocument();
    expect(screen.getByText('三栏聊天')).toBeInTheDocument();
    expect(screen.getByTestId('history-section')).toBeInTheDocument();
    expect(container.querySelector('.main-content')).not.toBeNull();
  });
});
