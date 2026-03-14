import { act, renderHook, waitFor } from '@testing-library/react';
import { useTaskHeartbeat } from '@/hooks/useTaskHeartbeat';
import { sendTaskHeartbeat } from '@/lib/api';

jest.mock('@/lib/api', () => ({
  sendTaskHeartbeat: jest.fn(),
}));

const mockSendTaskHeartbeat = sendTaskHeartbeat as jest.MockedFunction<typeof sendTaskHeartbeat>;

describe('useTaskHeartbeat', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockSendTaskHeartbeat.mockResolvedValue({
      task_id: 'task-1',
      alive: true,
      task_kind: 'generate',
      status: 'running',
    });
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  it('sends heartbeat for every active task immediately, on interval, and when focus resumes', async () => {
    renderHook(() => useTaskHeartbeat(['task-1', 'task-2']));

    await waitFor(() => {
      expect(mockSendTaskHeartbeat).toHaveBeenCalledTimes(2);
    });
    expect(mockSendTaskHeartbeat).toHaveBeenNthCalledWith(1, 'task-1');
    expect(mockSendTaskHeartbeat).toHaveBeenNthCalledWith(2, 'task-2');

    await act(async () => {
      jest.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(mockSendTaskHeartbeat).toHaveBeenCalledTimes(4);

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
      await Promise.resolve();
    });

    expect(mockSendTaskHeartbeat).toHaveBeenCalledTimes(6);
  });

  it('notifies the caller when a heartbeat response reports a terminal task status', async () => {
    const onTerminalState = jest.fn();
    mockSendTaskHeartbeat.mockResolvedValue({
      task_id: 'task-2',
      alive: false,
      task_kind: 'generate',
      status: 'cancelled',
    });

    renderHook(() =>
      useTaskHeartbeat(['task-2'], {
        onTerminalState,
      })
    );

    await waitFor(() => {
      expect(onTerminalState).toHaveBeenCalledWith('task-2', 'cancelled');
    });
  });

  it('notifies the caller when heartbeat reports TASK_NOT_FOUND after backend restart', async () => {
    const onMissingTask = jest.fn();
    mockSendTaskHeartbeat.mockRejectedValue(
      Object.assign(new Error('任务不存在'), { code: 'TASK_NOT_FOUND', status: 404 })
    );

    renderHook(() =>
      useTaskHeartbeat(['task-3'], {
        onMissingTask,
      })
    );

    await waitFor(() => {
      expect(onMissingTask).toHaveBeenCalledWith('task-3');
    });
  });
});
