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

  it('models audit findings with evidence and fix hints', () => {
    const finding: SSEAgentStepFinding = {
      evidence: '缺少交付周期',
      fix_hint: '补充合同签订后的交付时间',
    };
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-27T17:10:00',
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'audit',
      round: 1,
      node: 'verify_agent',
      is_complete: true,
      findings: [finding],
    };

    expect(event).toMatchObject({
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'audit',
      round: 1,
      node: 'verify_agent',
      is_complete: true,
      findings: [finding],
    });
  });

  it('models revision content snapshots', () => {
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-27T17:11:00',
      task_id: 'task-agent-1',
      task_kind: 'generate',
      step_type: 'revision',
      round: 2,
      node: 'host_agent',
      is_complete: true,
      content: '修复后的采购需求正文',
      findings: [],
    };

    expect(event.content).toBe('修复后的采购需求正文');
  });
});
