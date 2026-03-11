import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TenderNoInput } from './TenderNoInput';

describe('TenderNoInput', () => {
  it('renders controlled success state and triggers fetch actions', async () => {
    const user = userEvent.setup();
    const onFetch = jest.fn();

    render(
      <TenderNoInput
        value="0811-DSITC253505"
        onChange={jest.fn()}
        onFetch={onFetch}
        isSuccess
      />
    );

    expect(screen.getByTestId('tender-no-success-icon')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '获取信息' }));
    expect(onFetch).toHaveBeenCalledTimes(1);

    await user.type(screen.getByDisplayValue('0811-DSITC253505'), '{enter}');
    expect(onFetch).toHaveBeenCalledTimes(2);
  });

  it('renders controlled loading and error states from props', () => {
    render(
      <TenderNoInput
        value="0811-DSITC251534"
        onChange={jest.fn()}
        onFetch={jest.fn()}
        isLoading
        error="自动获取失败"
      />
    );

    expect(screen.getByTestId('tender-no-loading-icon')).toBeInTheDocument();
    expect(screen.getByText('自动获取失败')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
