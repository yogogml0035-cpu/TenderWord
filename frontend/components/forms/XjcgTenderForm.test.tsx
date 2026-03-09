import React from 'react';
import { render, screen } from '@testing-library/react';
import { XjcgTenderForm } from './XjcgTenderForm';

describe('XjcgTenderForm Wrapper', () => {
  it('uses xjcg insertion defaults', () => {
    render(<XjcgTenderForm onSubmit={jest.fn()} />);

    expect(screen.getByText('模板文件（可选）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('插入位置前的章节标题')).toHaveValue('第三章  采购需求');
    expect(screen.getByPlaceholderText('插入位置后的章节标题')).toHaveValue('第四章  响应文件有关格式');
  });
});
