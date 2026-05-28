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
  it('uses agent node name as the process card title', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'generate',
            agentStepType: 'draft',
            agentStepNode: 'generate_agent',
          },
        })}
      />
    );

    expect(screen.getByText('generate_agent')).toBeInTheDocument();
    expect(screen.queryByText('AI 初稿内容')).not.toBeInTheDocument();
  });
});
