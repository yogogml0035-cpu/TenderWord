import { render, screen } from '@testing-library/react';
import { AgentThinkingMessage } from '@/components/chat/AgentThinkingMessage';
import type { Message } from '@/types/chat';

function createMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'thinking-1',
    conversationId: 'conv-1',
    type: 'ai',
    content: '',
    timestamp: Date.now(),
    status: 'completed',
    metadata: {
      agentThinking: {
        runId: 'run-1',
        selectedSkill: 'rewrite',
        terminalState: 'task_accepted',
        stages: [
          {
            key: 'understand',
            label: '理解需求',
            status: 'completed',
            summary: '已识别为 rewrite 请求：请帮我改写第三包',
          },
          {
            key: 'execute',
            label: '执行任务',
            status: 'completed',
            summary: '检测到当前会话已有可改写文档。',
            guardResult: 'passed',
          },
          {
            key: 'tool',
            label: '调用工具',
            status: 'completed',
            summary: 'fake runtime 已调用 create_rewrite_task_tool。',
            toolName: 'create_rewrite_task_tool',
          },
          {
            key: 'retry',
            label: '异常与重试',
            status: 'completed',
            summary: '本次运行未触发异常重试',
          },
          {
            key: 'summary',
            label: '汇总结论',
            status: 'completed',
            summary: '已创建 rewrite 任务，后续进度由任务卡继续展示。',
          },
        ],
      },
    },
    ...overrides,
  };
}

describe('AgentThinkingMessage', () => {
  it('renders the selected skill, structured stages, and safe tool metadata', () => {
    render(<AgentThinkingMessage message={createMessage()} />);

    expect(screen.getByText('任务上下文助手')).toBeInTheDocument();
    expect(screen.getByText('rewrite')).toBeInTheDocument();
    expect(screen.getByText('理解需求')).toBeInTheDocument();
    expect(screen.getByText('执行任务')).toBeInTheDocument();
    expect(screen.getByText('调用工具')).toBeInTheDocument();
    expect(screen.getByText('异常与重试')).toBeInTheDocument();
    expect(screen.getByText('汇总结论')).toBeInTheDocument();
    expect(screen.getByText('条件满足')).toBeInTheDocument();
    expect(screen.getByText('create_rewrite_task_tool')).toBeInTheDocument();
    expect(screen.queryByText('reasoning_content')).not.toBeInTheDocument();
  });

  it('shows error status on the retry stage when the run fails', () => {
    render(
      <AgentThinkingMessage
        message={createMessage({
          status: 'error',
          metadata: {
            agentThinking: {
              runId: 'run-1',
              terminalState: 'error',
              stages: [
                {
                  key: 'understand',
                  label: '理解需求',
                  status: 'completed',
                  summary: '已识别为 rewrite 请求',
                },
                {
                  key: 'execute',
                  label: '执行任务',
                  status: 'completed',
                  summary: '检测到上下文异常',
                },
                {
                  key: 'tool',
                  label: '调用工具',
                  status: 'completed',
                  summary: '当前未实际创建任务',
                },
                {
                  key: 'retry',
                  label: '异常与重试',
                  status: 'error',
                  summary: 'agent run 执行失败，请稍后重试',
                },
                {
                  key: 'summary',
                  label: '汇总结论',
                  status: 'error',
                  summary: '本次运行失败，请检查错误信息后重试。',
                },
              ],
            },
          },
        })}
      />
    );

    expect(screen.getAllByText('异常')).not.toHaveLength(0);
    expect(screen.getByText('agent run 执行失败，请稍后重试')).toBeInTheDocument();
  });
});
