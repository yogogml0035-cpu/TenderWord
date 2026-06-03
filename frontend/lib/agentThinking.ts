import type { AgentRunEvent, AgentSkill, AgentThinkingGuardResult, TaskKind } from '@/types/api';
import type {
  AgentThinkingCardState,
  AgentThinkingViewStage,
  AgentThinkingViewStageKey,
  Message,
} from '@/types/chat';

const DEFAULT_RETRY_SUMMARY = '本次运行未触发异常重试';

const STAGE_LABELS: Record<AgentThinkingViewStageKey, string> = {
  understand: '理解需求',
  execute: '执行任务',
  tool: '调用工具',
  retry: '异常与重试',
  summary: '汇总结论',
};

const INITIAL_STAGE_SUMMARIES: Record<AgentThinkingViewStageKey, string> = {
  understand: '正在理解你的需求',
  execute: '等待上下文检查与前置条件判断',
  tool: '等待决定是否调用任务创建工具',
  retry: DEFAULT_RETRY_SUMMARY,
  summary: '等待本轮结论',
};

function createStage(
  key: AgentThinkingViewStageKey,
  status: AgentThinkingViewStage['status']
): AgentThinkingViewStage {
  return {
    key,
    label: STAGE_LABELS[key],
    status,
    summary: INITIAL_STAGE_SUMMARIES[key],
  };
}

function getSelectedSkillFromRunStarted(event: Extract<AgentRunEvent, { event: 'run_started' }>): AgentSkill | undefined {
  return event.data.selected_skills[0];
}

function getStage(
  state: AgentThinkingCardState,
  key: AgentThinkingViewStageKey
): AgentThinkingViewStage | undefined {
  return state.stages.find((stage) => stage.key === key);
}

function setStage(
  state: AgentThinkingCardState,
  key: AgentThinkingViewStageKey,
  updates: Partial<AgentThinkingViewStage>
): AgentThinkingCardState {
  return {
    ...state,
    stages: state.stages.map((stage) => (stage.key === key ? { ...stage, ...updates } : stage)),
  };
}

function setIfPending(
  state: AgentThinkingCardState,
  key: AgentThinkingViewStageKey,
  updates: Partial<AgentThinkingViewStage>
): AgentThinkingCardState {
  const stage = getStage(state, key);
  if (!stage || stage.status !== 'pending') {
    return state;
  }
  return setStage(state, key, updates);
}

function completeRetryStage(state: AgentThinkingCardState): AgentThinkingCardState {
  const retryStage = getStage(state, 'retry');
  if (!retryStage || retryStage.status === 'error') {
    return state;
  }
  return setStage(state, 'retry', {
    status: 'completed',
    summary: retryStage.summary || DEFAULT_RETRY_SUMMARY,
  });
}

function settleRunningStages(state: AgentThinkingCardState): AgentThinkingCardState {
  return {
    ...state,
    stages: state.stages.map((stage) =>
      stage.status === 'in_progress' ? { ...stage, status: 'completed' } : stage
    ),
  };
}

function finalizeWithoutToolCall(
  state: AgentThinkingCardState,
  summary: string
): AgentThinkingCardState {
  const toolStage = getStage(state, 'tool');
  if (!toolStage || toolStage.status !== 'pending') {
    return state;
  }
  return setStage(state, 'tool', {
    status: 'completed',
    summary,
  });
}

function taskKindLabel(taskKind: TaskKind): string {
  if (taskKind === 'rewrite') {
    return 'rewrite';
  }
  return taskKind;
}

export function createAgentThinkingState(options?: {
  runId?: string;
  selectedSkill?: AgentSkill;
}): AgentThinkingCardState {
  return {
    ...(options?.runId ? { runId: options.runId } : {}),
    ...(options?.selectedSkill ? { selectedSkill: options.selectedSkill } : {}),
    stages: [
      createStage('understand', 'in_progress'),
      createStage('execute', 'pending'),
      createStage('tool', 'pending'),
      createStage('retry', 'pending'),
      createStage('summary', 'pending'),
    ],
  };
}

export function finalizeCancelledAgentThinkingState(
  currentState: AgentThinkingCardState
): AgentThinkingCardState {
  let nextState = currentState;
  nextState = setStage(nextState, 'summary', {
    status: 'completed',
    summary: '已取消本次任务助手运行',
  });
  nextState = completeRetryStage(nextState);
  nextState = {
    ...nextState,
    terminalState: 'cancelled',
  };
  return settleRunningStages(nextState);
}

export function applyAgentThinkingEvent(
  currentState: AgentThinkingCardState | null | undefined,
  event: AgentRunEvent
): AgentThinkingCardState | null {
  if (event.event === 'needs_input' || event.event === 'done' || event.event === 'error') {
    if (!currentState) {
      return null;
    }
  }

  const baseState =
    currentState ||
    (event.event === 'run_started'
      ? createAgentThinkingState({
          runId: event.data.run_id,
          selectedSkill: getSelectedSkillFromRunStarted(event),
        })
      : event.event === 'thinking_stage' || event.event === 'tool_call' || event.event === 'task_accepted'
        ? createAgentThinkingState({
            runId: event.data.run_id,
            selectedSkill:
              event.event === 'thinking_stage'
                ? event.data.selected_skill || undefined
                : undefined,
          })
        : null);

  if (!baseState) {
    return null;
  }

  let nextState: AgentThinkingCardState = baseState;

  if (event.event === 'run_started') {
    return {
      ...nextState,
      runId: event.data.run_id,
      selectedSkill: getSelectedSkillFromRunStarted(event),
    };
  }

  if (event.event === 'thinking_stage') {
    nextState = {
      ...nextState,
      runId: event.data.run_id,
      ...(event.data.selected_skill ? { selectedSkill: event.data.selected_skill } : {}),
    };

    if (event.data.stage === 'understand') {
      nextState = setStage(nextState, 'understand', {
        status: event.data.status,
        summary: event.data.summary,
      });
      nextState = setIfPending(nextState, 'execute', {
        status: 'in_progress',
        summary: '正在检查当前会话上下文与前置条件',
      });
      return nextState;
    }

    if (event.data.stage === 'guard') {
      const guardResult: AgentThinkingGuardResult | undefined = event.data.guard_result || undefined;
      nextState = setStage(nextState, 'execute', {
        status: event.data.status,
        summary: event.data.summary,
        ...(guardResult ? { guardResult } : {}),
      });
      if (guardResult === 'passed') {
        nextState = setIfPending(nextState, 'tool', {
          status: 'in_progress',
          summary: '正在准备调用任务创建工具',
        });
      }
      if (guardResult === 'needs_input') {
        nextState = finalizeWithoutToolCall(nextState, '当前条件不足，未调用任务创建工具');
        nextState = completeRetryStage(nextState);
        nextState = setIfPending(nextState, 'summary', {
          status: 'in_progress',
          summary: '正在整理需要你补充的信息',
        });
      }
      return nextState;
    }

    if (event.data.stage === 'tool') {
      nextState = setStage(nextState, 'tool', {
        status: event.data.status,
        summary: event.data.summary,
        ...(event.data.tool_name ? { toolName: event.data.tool_name } : {}),
      });
      return nextState;
    }

    nextState = setStage(nextState, 'summary', {
      status: event.data.status,
      summary: event.data.summary,
    });
    return nextState;
  }

  if (event.event === 'tool_call') {
    nextState = {
      ...nextState,
      runId: event.data.run_id,
    };
    nextState = setStage(nextState, 'tool', {
      status: 'completed',
      summary: event.data.summary,
      toolName: event.data.tool_name,
    });
    nextState = setIfPending(nextState, 'summary', {
      status: 'in_progress',
      summary: '等待任务创建结果',
    });
    return nextState;
  }

  if (event.event === 'task_accepted') {
    nextState = {
      ...nextState,
      runId: event.data.run_id,
      terminalState: 'task_accepted',
    };
    nextState = completeRetryStage(nextState);
    nextState = finalizeWithoutToolCall(
      nextState,
      '任务已被系统接收，未返回额外工具调用阶段'
    );
    nextState = setStage(nextState, 'summary', {
      status: 'completed',
      summary: `已创建 ${taskKindLabel(event.data.task_kind)} 任务，后续进度由任务卡继续展示。`,
    });
    return settleRunningStages(nextState);
  }

  if (event.event === 'needs_input') {
    nextState = {
      ...nextState,
      runId: event.data.run_id,
      terminalState: 'needs_input',
      ...(event.data.selected_skill ? { selectedSkill: event.data.selected_skill } : {}),
    };
    nextState = completeRetryStage(nextState);
    nextState = finalizeWithoutToolCall(nextState, '当前条件不足，未调用任务创建工具');
    nextState = setStage(nextState, 'summary', {
      status: 'completed',
      summary: event.data.message,
    });
    return settleRunningStages(nextState);
  }

  if (event.event === 'done') {
    if (nextState.terminalState === 'task_accepted') {
      return nextState;
    }
    nextState = {
      ...nextState,
      runId: event.data.run_id,
      terminalState: 'done',
      ...(event.data.selected_skill ? { selectedSkill: event.data.selected_skill } : {}),
    };
    nextState = completeRetryStage(nextState);
    nextState = finalizeWithoutToolCall(nextState, '本次无需调用任务创建工具');
    nextState = setStage(nextState, 'summary', {
      status: 'completed',
      summary: event.data.message,
    });
    return settleRunningStages(nextState);
  }

  nextState = settleRunningStages(nextState);
  nextState = {
    ...nextState,
    runId: event.data.run_id,
    terminalState: 'error',
  };
  nextState = setStage(nextState, 'retry', {
    status: 'error',
    summary: event.data.message,
  });
  nextState = setStage(nextState, 'summary', {
    status: 'error',
    summary: '本次运行失败，请检查错误信息后重试。',
  });
  return nextState;
}

export function isAgentThinkingMessage(message: Message): boolean {
  return message.type === 'ai' && !!message.metadata?.agentThinking;
}
