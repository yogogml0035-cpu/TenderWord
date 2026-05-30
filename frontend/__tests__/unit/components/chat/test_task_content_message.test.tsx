import { render, screen } from '@testing-library/react';
import { TaskContentMessage } from '@/components/chat/TaskContentMessage';
import type { Message } from '@/types/chat';

function createMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'message-1',
    conversationId: 'conv-1',
    type: 'ai',
    content: '正文内容',
    timestamp: Date.now(),
    status: 'completed',
    ...overrides,
  };
}

describe('TaskContentMessage', () => {
  it('uses agent node and round as the process card title', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'generate',
            agentStepType: 'draft',
            agentStepNode: 'content_generate_agent',
            agentStepRound: 1,
          },
        })}
      />
    );

    expect(screen.getByText('content_generate_agent round-1')).toBeInTheDocument();
    expect(screen.queryByText('AI 初稿内容')).not.toBeInTheDocument();
  });

  it('shows a compact running state for empty agent-step cards', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          content: '',
          status: 'generating',
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'generate',
            agentStepType: 'stream',
            agentStepNode: 'content_verify_agent',
            agentStepRound: 1,
          },
        })}
      />
    );

    expect(screen.getByText('正在调用...')).toBeInTheDocument();
    expect(screen.queryByText('等待生成...')).not.toBeInTheDocument();
  });

  it('uses final title for the main content agent final step', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'generate',
            agentStepType: 'final',
            agentStepNode: 'content_agent',
            agentStepRound: 2,
          },
        })}
      />
    );

    expect(screen.getByText('content_agent final')).toBeInTheDocument();
    expect(screen.queryByText('content_agent round-2')).not.toBeInTheDocument();
  });

  it('uses the exact comment_agent node name as the process card title', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'comment_supplement',
            agentStepType: 'stream',
            agentStepNode: 'comment_agent',
            agentStepRound: 1,
          },
        })}
      />
    );

    expect(screen.getByText('comment_agent')).toBeInTheDocument();
    expect(screen.queryByText('comment_agent round-1')).not.toBeInTheDocument();
  });
});
