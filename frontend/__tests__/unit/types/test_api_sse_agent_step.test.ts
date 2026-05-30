import type {
  SSEAgentStepEvent,
  SSEAgentStepFinding,
  SSEEventType,
} from '@/types/api';

describe('SSE agent_step API types', () => {
  it('allows agent_step in the event type union', () => {
    const eventType: SSEEventType = 'agent_step';

    expect(eventType).toBe('agent_step');
  });

  it('models generic agent stream payloads with raw verify JSON', () => {
    const finding: SSEAgentStepFinding = {
      evidence: '缺少交付周期',
      fix_hint: '补充合同签订后的交付时间',
    };
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-27T17:10:00',
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'stream',
      round: 1,
      node: 'content_verify_agent',
      is_complete: true,
      content: '[{"evidence":"缺少交付周期","fix_hint":"补充合同签订后的交付时间"}]',
      findings: [finding],
    };

    expect(event).toMatchObject({
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'stream',
      round: 1,
      node: 'content_verify_agent',
      is_complete: true,
      content: '[{"evidence":"缺少交付周期","fix_hint":"补充合同签订后的交付时间"}]',
      findings: [finding],
    });
  });

  it('models revise subagent content snapshots', () => {
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-27T17:11:00',
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'stream',
      round: 2,
      node: 'content_revise_agent',
      is_complete: true,
      content: '修复后的采购需求正文',
      findings: [],
    };

    expect(event.content).toBe('修复后的采购需求正文');
  });

  it('models final main agent step as 1-based round metadata', () => {
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-27T17:12:00',
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'final',
      round: 2,
      node: 'content_agent',
      is_complete: true,
      content: '智能体生成完成，最终正文已通过文件协议写入 final。',
      findings: [],
    };

    expect(event.step_type).toBe('final');
    expect(event.round).toBe(2);
  });
});
