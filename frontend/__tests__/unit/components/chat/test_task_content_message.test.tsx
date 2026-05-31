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

  it('uses the Chinese content_agent process card title', () => {
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

    expect(screen.getByText('参数生成智能体')).toBeInTheDocument();
    expect(screen.queryByText('content_agent final')).not.toBeInTheDocument();
    expect(screen.queryByText('content_agent round-2')).not.toBeInTheDocument();
  });

  it('renders structured content_agent stages and collapsed raw outputs', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          content: '最终正文',
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'generate',
            agentStepType: 'final',
            agentStepNode: 'content_agent',
            agentStepRound: 2,
            contentAgent: {
              phase: 'final',
              summary: '最终完成，修复 1 轮，最终正文约 4 字。',
              rounds: [
                {
                  round: 1,
                  phase: 'draft',
                  label: '初稿生成',
                  summary: '初稿生成完成，约 4 字。',
                  issue_count: 0,
                  fix_count: 0,
                  content: '初稿正文',
                  findings: [],
                },
                {
                  round: 1,
                  phase: 'audit',
                  label: '第 1 轮审核发现',
                  summary: '第 1 轮审核发现 1 个问题。',
                  issue_count: 1,
                  fix_count: 0,
                  content: '[{"evidence":"缺少交付地点","fix_hint":"补充交付地点"}]',
                  findings: [
                    {
                      evidence: '缺少交付地点',
                      fix_hint: '补充交付地点',
                    },
                  ],
                },
                {
                  round: 1,
                  phase: 'revision',
                  label: '第 1 轮修复',
                  summary: '第 1 轮修复完成，已处理 1 个问题。',
                  issue_count: 1,
                  fix_count: 1,
                  content: '修复正文',
                  findings: [
                    {
                      evidence: '缺少交付地点',
                      fix_hint: '补充交付地点',
                    },
                  ],
                },
              ],
              highlights: [],
              final_result: {
                summary: '最终完成，修复 1 轮，最终正文约 4 字。',
                revision_rounds: 1,
                final_chars: 4,
                issue_count: 0,
                content: '最终正文',
              },
            },
          },
        })}
      />
    );

    expect(screen.getByText('参数生成智能体')).toBeInTheDocument();
    expect(screen.getByText('初稿生成')).toBeInTheDocument();
    expect(screen.getByText('第 1 轮审核发现')).toBeInTheDocument();
    expect(screen.getByText('第 1 轮修复')).toBeInTheDocument();
    expect(screen.getAllByText('依据：')).toHaveLength(2);
    expect(screen.getAllByText('缺少交付地点')).toHaveLength(2);
    expect(screen.getAllByText('修复建议：')).toHaveLength(2);
    expect(screen.getAllByText('补充交付地点')).toHaveLength(2);
    expect(screen.getAllByText('最终完成，修复 1 轮，最终正文约 4 字。').length).toBeGreaterThan(0);
    const draftDetails = screen.getByText('查看初稿正文').closest('details');
    expect(draftDetails).not.toHaveAttribute('open');
  });

  it('uses the Chinese comment_agent process card title', () => {
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

    expect(screen.getByText('批注生成智能体')).toBeInTheDocument();
    expect(screen.queryByText('comment_agent round-1')).not.toBeInTheDocument();
  });

  it('renders structured comment_agent rounds and writeback stats', () => {
    render(
      <TaskContentMessage
        message={createMessage({
          content: 'fallback text should not be primary',
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'comment_supplement',
            agentStepType: 'final',
            agentStepNode: 'comment_agent',
            agentStepRound: 1,
            commentAgent: {
              phase: 'final',
              rounds: [
                {
                  round: 1,
                  label: '第 1 轮锚点校验',
                  passed: 0,
                  failed: 1,
                  skipped: 0,
                  highlights: [
                    {
                      index: 1,
                      status: '需修复',
                      reason: '当前锚点未在最终正文中精确匹配',
                      original_reference_text: '★7.投标人须提供售后服务承诺',
                      reference_text: '★7.投标人须提供售后服务承诺',
                      candidate_fragments: ['7.投标人须提供售后服务承诺'],
                    },
                  ],
                },
                {
                  round: 2,
                  label: '第 2 轮修复复核',
                  passed: 7,
                  failed: 0,
                  skipped: 0,
                  highlights: [
                    {
                      index: 1,
                      status: '已修复',
                      reason: '锚点已通过校验',
                      original_reference_text: '★7.投标人须提供售后服务承诺',
                      reference_text: '7.投标人须提供售后服务承诺',
                      candidate_fragments: [],
                    },
                  ],
                },
              ],
              highlights: [],
              final_validation: {
                round: 0,
                label: '最终静默复校验',
                passed: 7,
                failed: 0,
                skipped: 0,
                highlights: [],
              },
              writeback: {
                attempted: 8,
                added: 7,
                failed: 0,
                skipped: 1,
                issues: [
                  {
                    index: 8,
                    status: '已跳过',
                    reason: '目标位置已有批注，已跳过',
                    original_reference_text: '',
                    reference_text: '售后服务承诺',
                    candidate_fragments: [],
                  },
                ],
              },
            },
          },
        })}
      />
    );

    expect(screen.getByText('批注生成智能体')).toBeInTheDocument();
    expect(screen.getByText('第 1 轮锚点校验')).toBeInTheDocument();
    expect(screen.getByText('第 2 轮修复复核')).toBeInTheDocument();
    expect(screen.getByText('需修复')).toBeInTheDocument();
    expect(screen.getByText('已修复')).toBeInTheDocument();
    expect(screen.getByText('当前锚点未在最终正文中精确匹配')).toBeInTheDocument();
    expect(screen.getByText('成功 7 条 / 跳过 1 条 / 失败 0 条')).toBeInTheDocument();
    expect(screen.getByText('1 条目标位置已有批注，已跳过')).toBeInTheDocument();
    expect(screen.getByText('最终静默复校验')).toBeInTheDocument();
    expect(screen.queryByText('fallback text should not be primary')).not.toBeInTheDocument();
  });

  it('uses paragraph wrapping for agent-step content', () => {
    const { container } = render(
      <TaskContentMessage
        message={createMessage({
          content: '工具轮次 1：批注锚点校验快照\n当前锚点：投标人须提供原厂授权函',
          metadata: {
            messageKind: 'agent-step',
            taskKind: 'comment_supplement',
            agentStepType: 'tool_snapshot',
            agentStepNode: 'comment_agent',
            agentStepRound: 1,
          },
        })}
      />
    );

    const pre = container.querySelector('pre');
    expect(pre).toHaveClass('break-words', 'whitespace-pre-wrap');
    expect(pre).not.toHaveClass('break-all');
    expect(pre).not.toHaveClass('font-mono');
  });
});
