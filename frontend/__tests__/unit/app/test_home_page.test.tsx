const mockRedirect = jest.fn();

jest.mock('next/navigation', () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

import HomePage from '@/app/page';

describe('HomePage', () => {
  beforeEach(() => {
    mockRedirect.mockClear();
  });

  it('redirects to the tender workspace', () => {
    HomePage();

    expect(mockRedirect).toHaveBeenCalledWith('/tender');
  });
});
