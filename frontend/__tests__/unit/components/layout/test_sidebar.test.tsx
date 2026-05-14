import React from 'react';
import { render, screen } from '../../../utils/test-utils';
import { SidebarWithHistory } from '@/components/layout/Sidebar';
import { useAppStore } from '@/stores/useAppStore';
import { useHistoryStore } from '@/stores/historyStore';

jest.mock('@/lib/api', () => ({
  getDownloadUrl: jest.fn((filePath: string, downloadName?: string) =>
    `http://localhost:8000/api/download/${encodeURIComponent(filePath)}${
      downloadName ? `?download_name=${encodeURIComponent(downloadName)}` : ''
    }`
  ),
}));

describe('SidebarWithHistory', () => {
  beforeEach(() => {
    useAppStore.setState({ sidebarOpen: true });
    useHistoryStore.setState({
      history: [
        {
          id: 'history-1',
          taskId: 'task-1',
          tenderNo: 'TW-001',
          tenderType: 'xjcg',
          tenderTypeName: '询价采购',
          status: 'completed',
          outputFile: 'D:/UploadFiles/output.docx',
          outputFileName: '输出文件.docx',
          model: 'deepseek',
          createdAt: '2026-05-15T00:00:00.000Z',
          progressPercent: 100,
        },
      ],
    });
  });

  it('uses the API download helper for history download links', () => {
    render(<SidebarWithHistory />);

    expect(screen.getByRole('link', { name: '下载文件' })).toHaveAttribute(
      'href',
      'http://localhost:8000/api/download/D%3A%2FUploadFiles%2Foutput.docx?download_name=%E8%BE%93%E5%87%BA%E6%96%87%E4%BB%B6.docx'
    );
  });
});
