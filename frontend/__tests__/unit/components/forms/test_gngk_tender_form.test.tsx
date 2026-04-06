import React from 'react';
import { render, screen } from '@testing-library/react';
import { GngkTenderForm } from '@/components/forms/GngkTenderForm';

describe('GngkTenderForm Wrapper', () => {
  it('uses gngk-specific copy and insertion defaults', () => {
    render(<GngkTenderForm onSubmit={jest.fn()} />);

    expect(screen.getByText('模板文件（可选）')).toBeInTheDocument();
    expect(screen.queryByText('清洁稿文件（可选）')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('插入位置前的章节标题')).toHaveValue('第三章 招标内容及要求');
    expect(screen.getByPlaceholderText('插入位置后的章节标题')).toHaveValue('第四章 投标文件有关格式');
  });
});
