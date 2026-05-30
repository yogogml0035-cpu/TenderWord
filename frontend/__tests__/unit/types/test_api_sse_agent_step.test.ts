import type {
  CommentWritebackSummary,
  SSEAgentStepEvent,
  SSEAgentStepFinding,
  SSECommentAgentStep,
  SSEDoneEvent,
  SSEEventType,
  TaskKind,
  TaskResult,
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

  it('models structured comment_agent process payloads', () => {
    const commentAgent: SSECommentAgentStep = {
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
          passed: 1,
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
        passed: 1,
        failed: 0,
        skipped: 0,
        highlights: [],
      },
      writeback: {
        attempted: 8,
        added: 7,
        failed: 0,
        skipped: 1,
        issues: [],
      },
    };
    const event: SSEAgentStepEvent = {
      timestamp: '2026-05-30T01:00:00',
      task_id: 'task-comment-1',
      task_kind: 'comment_supplement',
      step_type: 'final',
      round: 1,
      node: 'comment_agent',
      is_complete: true,
      content: 'comment_agent 最终写入统计',
      findings: [],
      comment_agent: commentAgent,
    };

    expect(event.comment_agent?.rounds).toHaveLength(2);
    expect(event.comment_agent?.rounds[1].highlights[0].status).toBe('已修复');
    expect(event.comment_agent?.writeback?.added).toBe(7);
  });

  it('allows comment_supplement task kind and comment_writeback payloads', () => {
    const taskKind: TaskKind = 'comment_supplement';
    const commentWriteback: CommentWritebackSummary = {
      summary: 'AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0',
      generated: 2,
      added: 1,
      failed: 1,
      skipped: 0,
      warning: true,
    };
    const result: TaskResult = {
      output_file: 'D:/UploadFiles/output.docx',
      file_name: 'output.docx',
      file_size: 1024,
      model_used: 'deepseek',
      total_time_seconds: 3.2,
      comment_writeback: commentWriteback,
    };
    const doneEvent: SSEDoneEvent = {
      timestamp: '2026-05-30T00:30:00',
      task_id: 'task-comment-1',
      task_kind: taskKind,
      success: true,
      message: '任务完成',
      output_file: result.output_file,
      file_name: result.file_name,
      comment_writeback: commentWriteback,
    };

    expect(doneEvent.task_kind).toBe('comment_supplement');
    expect(result.comment_writeback?.warning).toBe(true);
    expect(doneEvent.comment_writeback).toEqual(commentWriteback);
  });
});
