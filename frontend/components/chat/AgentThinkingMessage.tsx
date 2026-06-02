'use client';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
  Wrench,
} from 'lucide-react';
import type { AgentThinkingViewStage } from '@/types/chat';
import type { Message } from '@/types/chat';

interface AgentThinkingMessageProps {
  message: Message;
}

function getCardBorderColor(status: Message['status']): string {
  switch (status) {
    case 'completed':
      return 'border-emerald-200';
    case 'error':
      return 'border-rose-200';
    case 'cancelled':
      return 'border-slate-200';
    default:
      return 'border-blue-200';
  }
}

function getStageStatusIcon(stage: AgentThinkingViewStage) {
  switch (stage.status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-rose-500" />;
    case 'in_progress':
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    default:
      if (stage.key === 'tool') {
        return <Wrench className="h-4 w-4 text-slate-300" />;
      }
      if (stage.key === 'retry') {
        return <RefreshCw className="h-4 w-4 text-slate-300" />;
      }
      return <Sparkles className="h-4 w-4 text-slate-300" />;
  }
}

function getStageStatusBadge(stage: AgentThinkingViewStage): { label: string; className: string } {
  switch (stage.status) {
    case 'completed':
      return {
        label: '已完成',
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      };
    case 'error':
      return {
        label: '异常',
        className: 'border-rose-200 bg-rose-50 text-rose-700',
      };
    case 'in_progress':
      return {
        label: '进行中',
        className: 'border-blue-200 bg-blue-50 text-blue-700',
      };
    default:
      return {
        label: '待触发',
        className: 'border-slate-200 bg-slate-50 text-slate-500',
      };
  }
}

function getCardStatusCopy(status: Message['status']): string {
  switch (status) {
    case 'completed':
      return '本轮处理已收敛';
    case 'error':
      return '本轮处理失败';
    case 'cancelled':
      return '本轮处理已取消';
    default:
      return '正在分析并准备下一步动作';
  }
}

function getGuardResultBadge(guardResult: AgentThinkingViewStage['guardResult']): {
  label: string;
  className: string;
} | null {
  if (guardResult === 'passed') {
    return {
      label: '条件满足',
      className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    };
  }
  if (guardResult === 'needs_input') {
    return {
      label: '需补充信息',
      className: 'border-amber-200 bg-amber-50 text-amber-700',
    };
  }
  return null;
}

export function AgentThinkingMessage({ message }: AgentThinkingMessageProps) {
  const thinkingState = message.metadata?.agentThinking;
  if (!thinkingState) {
    return null;
  }

  return (
    <div
      data-testid="agent-thinking-card"
      className={`overflow-hidden rounded-2xl border bg-white shadow-sm ${getCardBorderColor(message.status)}`}
    >
      <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-blue-600">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-800">任务上下文助手</h3>
              {thinkingState.selectedSkill ? (
                <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-semibold tracking-[0.12em] text-blue-700">
                  {thinkingState.selectedSkill}
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-slate-500">{getCardStatusCopy(message.status)}</p>
          </div>
        </div>
      </div>

      <div className="space-y-3 px-4 py-3">
        {thinkingState.stages.map((stage) => {
          const stageStatus = getStageStatusBadge(stage);
          const guardBadge = getGuardResultBadge(stage.guardResult);

          return (
            <section
              key={stage.key}
              data-testid={`agent-thinking-stage-${stage.key}`}
              className="rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2">
                  <div className="mt-0.5 flex-shrink-0">{getStageStatusIcon(stage)}</div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-sm font-medium text-slate-800">{stage.label}</h4>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${stageStatus.className}`}
                      >
                        {stageStatus.label}
                      </span>
                      {guardBadge ? (
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${guardBadge.className}`}
                        >
                          {guardBadge.label}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">
                      {stage.summary}
                    </p>
                  </div>
                </div>

                {stage.toolName ? (
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-mono text-[11px] text-slate-600">
                    {stage.toolName}
                  </span>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export default AgentThinkingMessage;
