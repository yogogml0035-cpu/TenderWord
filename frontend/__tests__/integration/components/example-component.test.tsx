/**
 * Integration test example for components
 * This demonstrates how to test components with providers and mocked APIs
 */

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../utils/test-utils';
import { server } from '../mocks/server';
import { errorHandlers } from '../mocks/handlers';

// Example component for testing
function ExampleForm() {
  const [value, setValue] = React.useState('');
  const [submitted, setSubmitted] = React.useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim()) {
      setSubmitted(true);
    }
  };

  if (submitted) {
    return <div data-testid="success">Submitted: {value}</div>;
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter text"
        data-testid="input"
      />
      <button type="submit" data-testid="submit">
        Submit
      </button>
    </form>
  );
}

describe('ExampleForm Component', () => {
  it('should render form with input and button', () => {
    renderWithProviders(<ExampleForm />);

    expect(screen.getByTestId('input')).toBeInTheDocument();
    expect(screen.getByTestId('submit')).toBeInTheDocument();
  });

  it('should update input value when typing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExampleForm />);

    const input = screen.getByTestId('input');
    await user.type(input, 'Hello World');

    expect(input).toHaveValue('Hello World');
  });

  it('should show success message on submit', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExampleForm />);

    const input = screen.getByTestId('input');
    await user.type(input, 'Test Input');

    const submitButton = screen.getByTestId('submit');
    await user.click(submitButton);

    expect(screen.getByTestId('success')).toBeInTheDocument();
    expect(screen.getByText('Submitted: Test Input')).toBeInTheDocument();
  });

  it('should not submit empty value', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExampleForm />);

    const submitButton = screen.getByTestId('submit');
    await user.click(submitButton);

    expect(screen.queryByTestId('success')).not.toBeInTheDocument();
  });
});

// Example of testing with MSW API mocking
describe('API Integration Example', () => {
  it('should handle API calls', async () => {
    // This is a placeholder for API integration tests
    // You would typically test components that make API calls
    // using MSW handlers

    // Example:
    // renderWithProviders(<ComponentThatFetchesData />);
    // await waitFor(() => {
    //   expect(screen.getByText('Data loaded')).toBeInTheDocument();
    // });
  });

  it('should handle API errors', async () => {
    // Override handlers to return error
    server.use(errorHandlers.badRequest);

    // This is a placeholder for error handling tests
    // You would test how your component handles API errors

    // Example:
    // renderWithProviders(<ComponentThatFetchesData />);
    // await waitFor(() => {
    //   expect(screen.getByText('Error: Invalid request')).toBeInTheDocument();
    // });
  });
});

// Example of testing components with store
describe('Component with Store Integration', () => {
  it('should interact with store', async () => {
    // This is a placeholder for testing components that use Zustand stores
    // You can test store updates and component re-renders

    // Example:
    // const { result } = renderHook(() => useAppStore());
    // renderWithProviders(<ComponentUsingStore />);
    //
    // await user.click(screen.getByText('Toggle'));
    // expect(result.current.someValue).toBe(true);
  });
});
