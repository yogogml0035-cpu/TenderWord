import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';
import type { TenderType, FundLx, TenderLx } from '@/types';
import type {
  CommentGenerationMode,
  GenerationMode,
  GenerationStyle,
  CommentWritebackSummary,
  SSEAgentStepEvent,
  SSEContentAgentStep,
  StyleWritebackMode,
  StyleWritebackSummary,
  TaskKind,
  TaskStatus,
  TenderData,
  TenderTypeInfo,
  AgentSkill,
} from '@/types/api';
import type { TenderFetchState } from '@/lib/tenderFetch';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import {
  isDualColumnContent,
  type AgentAuditRound,
  type AgentStepFinding,
  type Conversation,
  type LocalTaskReason,
  type LogEntry,
  type Message,
  type TaskMessageKind,
} from '@/types/chat';
import {
  createConversation as createConvUtil,
  generateMessageId,
  inferTenderNoFromConversationTitle,
  normalizeTenderNo,
} from '@/lib/chat-utils';
import { syncBrowserUrlToConversation } from '@/utils/tenderTypeMapper';

const TASK_LOG_KIND: TaskMessageKind = 'task-log';
const TASK_CONTENT_KIND: TaskMessageKind = 'task-content';
const TASK_DOWNLOAD_KIND: TaskMessageKind = 'task-download';
const TASK_AGENT_STEP_KIND: TaskMessageKind = 'agent-step';
const BACKEND_RESTART_LOCAL_REASON: LocalTaskReason = 'backend_restart';
const BACKEND_RESTART_TASK_MESSAGE = '服务已重启，任务已中断，可重试';

export interface TaskMessageGroupIds {
  logMessageId?: string;
  contentMessageId?: string;
  downloadMessageId?: string;
}

export interface TaskMessageSnapshot {
  logs?: LogEntry[];
  aiText?: string;
  aiComplete?: boolean;
}

interface TaskRuntimeSnapshot extends TaskMessageSnapshot {
  progressPercent?: number;
  progressText?: string;
  currentNode?: string;
  currentNodeDisplay?: string;
}

export interface LocatedTaskMessageGroup {
  conversationId: string;
  group: TaskMessageGroupIds;
  logMessage?: Message;
  contentMessage?: Message;
  downloadMessage?: Message;
}

export interface ConversationDraftFile {
  id: string;
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time: string;
  file_type?: string;
}

export interface ConversationFormDraft {
  tender_no?: string;
  tender_data?: TenderData | null;
  tender_type_info?: TenderTypeInfo | null;
  tender_fetch?: TenderFetchState;
  tender_lx?: TenderLx;
  fund_lx?: FundLx;
  model?: 'deepseek' | 'qwen' | 'doubao';
  generation_mode?: GenerationMode;
  comment_generation_mode?: CommentGenerationMode;
  generation_style?: GenerationStyle;
  gngk_generation_styles?: {
    0?: GenerationStyle;
    1?: GenerationStyle;
    2?: GenerationStyle;
  };
  style_writeback_mode?: StyleWritebackMode;
  input_mode?: 'normal' | 'edit';
  edit_file?: ConversationDraftFile | null;
  insertion_config?: {
    before_text: string;
    after_text: string;
  };
  gngk_insertion_configs?: {
    0?: {
      before_text: string;
      after_text: string;
    };
    1?: {
      before_text: string;
      after_text: string;
    };
  };
  gngk_engineering_insertion_configs?: {
    0?: {
      before_text: string;
      after_text: string;
    };
    1?: {
      before_text: string;
      after_text: string;
    };
  };
  gngk_service_insertion_configs?: {
    0?: {
      before_text: string;
      after_text: string;
    };
    1?: {
      before_text: string;
      after_text: string;
    };
  };
  gngk_service_insertion_config?: {
    before_text: string;
    after_text: string;
  };
  manual_insertion_config_scope_keys?: string[];
  chat_input?: string;
  selected_skills?: AgentSkill[];
  pending_rewrite_prompt?: string;
  pending_rewrite_task_id?: string;
  pending_edit_prompt?: string;
  pending_edit_task_id?: string;
  files?: {
    template?: ConversationDraftFile;
    tender_params: ConversationDraftFile[];
  };
}

export interface TaskSummarySnapshot {
  task_id: string;
  task_kind?: TaskKind;
  status: TaskStatus;
  queue_position?: number;
  waiting_count?: number;
  progress_percent?: number;
  progress_text?: string;
  current_node?: string;
  current_node_display?: string;
  localReason?: LocalTaskReason;
  updated_at: number;
}

interface TaskScopeState {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskSummaries: Record<string, TaskSummarySnapshot>;
}

const TERMINAL_TASK_STATUSES = new Set<TaskStatus>(['completed', 'failed', 'cancelled']);
const TERMINAL_MESSAGE_STATUSES = new Set<Message['status']>(['completed', 'error', 'cancelled']);

function isTerminalTaskStatus(status?: TaskStatus): boolean {
  if (!status) {
    return false;
  }
  return TERMINAL_TASK_STATUSES.has(status);
}

function isTerminalMessageStatus(status?: Message['status']): boolean {
  if (!status) {
    return false;
  }
  return TERMINAL_MESSAGE_STATUSES.has(status);
}

function normalizeDraftFile(file: ConversationDraftFile | undefined): ConversationDraftFile | undefined {
  if (!file) {
    return undefined;
  }

  return {
    id: file.id,
    file_path: file.file_path,
    file_name: file.file_name,
    original_name: file.original_name,
    size: file.size,
    upload_time: file.upload_time,
    ...(file.file_type ? { file_type: file.file_type } : {}),
  };
}

function isAgentSkill(value: unknown): value is AgentSkill {
  return value === 'rewrite' || value === 'edit';
}

function normalizeDraftSelectedSkills(skills: AgentSkill[] | undefined): AgentSkill[] | undefined {
  if (!Array.isArray(skills)) {
    return undefined;
  }

  const normalized = skills.filter(isAgentSkill).slice(0, 1);
  return normalized.length > 0 ? normalized : undefined;
}

function mergeConversationDraft(
  base: ConversationFormDraft,
  updates: Partial<ConversationFormDraft>
): ConversationFormDraft {
  const nextDraft: ConversationFormDraft = {
    ...base,
    ...updates,
  };

  if (Object.prototype.hasOwnProperty.call(updates, 'edit_file')) {
    nextDraft.edit_file = normalizeDraftFile(updates.edit_file || undefined) || undefined;
  }

  if (Object.prototype.hasOwnProperty.call(updates, 'selected_skills')) {
    nextDraft.selected_skills = normalizeDraftSelectedSkills(updates.selected_skills);
  }

  if (updates.insertion_config) {
    nextDraft.insertion_config = {
      ...(base.insertion_config || {}),
      ...updates.insertion_config,
    };
  }

  if (updates.gngk_insertion_configs) {
    nextDraft.gngk_insertion_configs = {
      ...(base.gngk_insertion_configs || {}),
      ...updates.gngk_insertion_configs,
    };
  }

  if (updates.gngk_generation_styles) {
    nextDraft.gngk_generation_styles = {
      ...(base.gngk_generation_styles || {}),
      ...updates.gngk_generation_styles,
    };
  }

  if (updates.gngk_engineering_insertion_configs) {
    nextDraft.gngk_engineering_insertion_configs = {
      ...(base.gngk_engineering_insertion_configs || {}),
      ...updates.gngk_engineering_insertion_configs,
    };
  }

  if (updates.gngk_service_insertion_configs) {
    nextDraft.gngk_service_insertion_configs = {
      ...(base.gngk_service_insertion_configs || {}),
      ...updates.gngk_service_insertion_configs,
    };
  }

  if (updates.gngk_service_insertion_config) {
    nextDraft.gngk_service_insertion_config = {
      ...(base.gngk_service_insertion_config || {}),
      ...updates.gngk_service_insertion_config,
    };
  }

  if (updates.files) {
    nextDraft.files = {
      ...(base.files || { tender_params: [] }),
      ...updates.files,
      tender_params: updates.files.tender_params || base.files?.tender_params || [],
    };
  }

  if (nextDraft.files) {
    nextDraft.files = {
      ...(nextDraft.files.template
        ? { template: normalizeDraftFile(nextDraft.files.template) }
        : {}),
      tender_params: (nextDraft.files.tender_params || [])
        .map((file) => normalizeDraftFile(file))
        .filter((file): file is ConversationDraftFile => !!file),
    };
  }

  nextDraft.selected_skills = normalizeDraftSelectedSkills(nextDraft.selected_skills);

  return nextDraft;
}

function getConversationTenderNo(
  conversation: Conversation,
  draft?: ConversationFormDraft
): string | null {
  return (
    normalizeTenderNo(draft?.tender_no) ||
    normalizeTenderNo(inferTenderNoFromConversationTitle(conversation.title))
  );
}

function normalizeLogEntries(logs: unknown): LogEntry[] {
  if (!Array.isArray(logs)) {
    return [];
  }

  return logs.filter((item): item is LogEntry => {
    return (
      typeof item === 'object' &&
      item !== null &&
      typeof (item as LogEntry).id === 'string' &&
      typeof (item as LogEntry).message === 'string' &&
      typeof (item as LogEntry).timestamp === 'number'
    );
  });
}

function isTrackedTaskInFlight(status?: TaskStatus): boolean {
  return status === 'queued' || status === 'running';
}

function getTaskRuntimeSnapshot(taskId: string): TaskRuntimeSnapshot | undefined {
  const stream = useChatStreamStore.getState().streams[taskId];
  if (!stream) {
    return undefined;
  }

  return {
    logs: stream.logs,
    aiText: stream.aiText,
    aiComplete: stream.aiComplete,
    progressPercent: stream.progressPercent,
    progressText: stream.progressText,
    currentNode: stream.currentNode,
    currentNodeDisplay: stream.currentNodeDisplay,
  };
}

function buildInterruptedLogs(
  existingLogs: unknown,
  runtimeLogs?: LogEntry[]
): LogEntry[] {
  const baseLogs = runtimeLogs && runtimeLogs.length > 0 ? runtimeLogs : normalizeLogEntries(existingLogs);
  const interruptedLogExists = baseLogs.some(
    (log) =>
      log.level === 'error' &&
      log.message === BACKEND_RESTART_TASK_MESSAGE
  );
  if (interruptedLogExists) {
    return baseLogs;
  }

  return [
    ...baseLogs,
    {
      id: generateMessageId(),
      timestamp: Date.now(),
      level: 'error',
      message: BACKEND_RESTART_TASK_MESSAGE,
    },
  ];
}

function buildTaskFailureLogs(
  existingLogs: unknown,
  runtimeLogs: LogEntry[] | undefined,
  errorMessage: string
): LogEntry[] {
  const baseLogs =
    runtimeLogs && runtimeLogs.length > 0 ? runtimeLogs : normalizeLogEntries(existingLogs);
  if (
    !errorMessage ||
    baseLogs.some((log) => log.level === 'error' && log.message === errorMessage)
  ) {
    return baseLogs;
  }

  return [
    ...baseLogs,
    {
      id: generateMessageId(),
      timestamp: Date.now(),
      level: 'error',
      message: errorMessage,
    },
  ];
}

function collectBackendRestartTaskIds(state: Pick<
  ChatStore,
  'conversations' | 'activeTaskIds' | 'taskSummaries' | 'conversationDrafts'
>): string[] {
  const taskIds = new Set<string>();

  for (const taskId of state.activeTaskIds) {
    taskIds.add(taskId);
  }

  for (const [taskId, summary] of Object.entries(state.taskSummaries)) {
    if (isTrackedTaskInFlight(summary.status)) {
      taskIds.add(taskId);
    }
  }

  for (const conversation of state.conversations) {
    if (conversation.currentTaskId) {
      taskIds.add(conversation.currentTaskId);
    }

    for (const message of conversation.messages) {
      if (message.taskId && message.status === 'generating') {
        taskIds.add(message.taskId);
      }
    }
  }

  for (const draft of Object.values(state.conversationDrafts)) {
    if (draft.pending_rewrite_task_id) {
      taskIds.add(draft.pending_rewrite_task_id);
    }
  }

  return [...taskIds];
}

function shouldInterruptTaskForBackendRestart(
  state: Pick<ChatStore, 'conversations' | 'activeTaskIds' | 'taskSummaries'>,
  taskId: string
): boolean {
  if (state.activeTaskIds.includes(taskId)) {
    return true;
  }

  const summary = state.taskSummaries[taskId];
  if (summary && isTrackedTaskInFlight(summary.status)) {
    return true;
  }

  return state.conversations.some((conversation) => {
    if (conversation.currentTaskId === taskId) {
      return true;
    }

    return conversation.messages.some(
      (message) => message.taskId === taskId && message.status === 'generating'
    );
  });
}

function getActiveTaskIdsFromState(state: TaskScopeState): string[] {
  const orderedIds = [...state.activeTaskIds];
  const activeTaskIds = new Set(orderedIds);

  for (const conversation of state.conversations) {
    const taskId = conversation.currentTaskId;
    if (!taskId || activeTaskIds.has(taskId)) {
      continue;
    }

    const summary = state.taskSummaries[taskId];
    if (summary && isTerminalTaskStatus(summary.status)) {
      continue;
    }

    activeTaskIds.add(taskId);
    orderedIds.push(taskId);
  }

  return orderedIds.filter((taskId) => {
    const summary = state.taskSummaries[taskId];
    if (!summary) {
      return true;
    }
    return !isTerminalTaskStatus(summary.status);
  });
}

function getCurrentConversationActiveTaskFromState(state: TaskScopeState): string | null {
  if (!state.currentConversationId) {
    return null;
  }

  const currentConversation = state.conversations.find(
    (conversation) => conversation.id === state.currentConversationId
  );
  if (!currentConversation) {
    return null;
  }

  const taskId = currentConversation.currentTaskId;
  if (!taskId) {
    return null;
  }

  const summary = state.taskSummaries[taskId];
  if (summary && isTerminalTaskStatus(summary.status)) {
    return null;
  }

  return taskId;
}

function getLatestActiveTaskIdFromState(state: TaskScopeState): string | null {
  const activeTaskIds = getActiveTaskIdsFromState(state);
  return activeTaskIds[activeTaskIds.length - 1] || null;
}

function getTaskMessageKind(message: Message): TaskMessageKind | undefined {
  const kind = message.metadata?.messageKind;
  if (
    kind === TASK_LOG_KIND ||
    kind === TASK_CONTENT_KIND ||
    kind === TASK_DOWNLOAD_KIND ||
    kind === TASK_AGENT_STEP_KIND
  ) {
    return kind;
  }
  return undefined;
}

function normalizeAgentStepFindings(findings: unknown): AgentStepFinding[] {
  if (!Array.isArray(findings)) {
    return [];
  }

  return findings
    .map((item) => {
      if (typeof item !== 'object' || item === null) {
        return null;
      }
      const finding = item as Partial<AgentStepFinding>;
      return {
        evidence: String(finding.evidence || ''),
        fix_hint: String(finding.fix_hint || ''),
      };
    })
    .filter((finding): finding is AgentStepFinding => {
      return !!finding && (!!finding.evidence || !!finding.fix_hint);
    });
}

function normalizeAgentAuditRounds(rounds: unknown): AgentAuditRound[] {
  if (!Array.isArray(rounds)) {
    return [];
  }

  return rounds
    .map((item) => {
      if (typeof item !== 'object' || item === null) {
        return null;
      }
      const round = (item as Partial<AgentAuditRound>).round;
      if (typeof round !== 'number') {
        return null;
      }
      return {
        round,
        findings: normalizeAgentStepFindings((item as Partial<AgentAuditRound>).findings),
      };
    })
    .filter((round): round is AgentAuditRound => !!round)
    .sort((a, b) => a.round - b.round);
}

function formatAgentFindingsJson(findings: AgentStepFinding[]): string {
  return JSON.stringify(findings, null, 2);
}

function normalizeCommentAgentStep(value: unknown): SSEAgentStepEvent['comment_agent'] {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const payload = value as SSEAgentStepEvent['comment_agent'];
  if (!payload || (payload.phase !== 'validation_round' && payload.phase !== 'final')) {
    return undefined;
  }
  return payload;
}

function normalizeContentAgentStep(value: unknown): SSEContentAgentStep | undefined {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const payload = value as Partial<SSEContentAgentStep> & {
    rounds?: unknown;
    highlights?: unknown;
    final_result?: unknown;
  };
  if (
    payload.phase !== 'draft' &&
    payload.phase !== 'audit' &&
    payload.phase !== 'revision' &&
    payload.phase !== 'final'
  ) {
    return undefined;
  }

  const normalizeRound = (roundValue: unknown) => {
    if (!roundValue || typeof roundValue !== 'object') {
      return null;
    }
    const round = roundValue as Record<string, unknown>;
    const roundIndex = typeof round.round === 'number' ? round.round : Number(round.round || 0);
    if (!Number.isFinite(roundIndex) || roundIndex < 1) {
      return null;
    }
    const findings = normalizeAgentStepFindings(round.findings);
    const roundPhase =
      round.phase === 'draft' || round.phase === 'audit' || round.phase === 'revision'
        ? round.phase
        : payload.phase === 'draft' || payload.phase === 'audit' || payload.phase === 'revision'
          ? payload.phase
          : 'audit';
    return {
      round: roundIndex,
      phase: roundPhase,
      label: typeof round.label === 'string' ? round.label : '',
      summary: typeof round.summary === 'string' ? round.summary : '',
      issue_count: Number.isFinite(Number(round.issue_count)) ? Number(round.issue_count) : findings.length,
      fix_count: Number.isFinite(Number(round.fix_count)) ? Number(round.fix_count) : 0,
      content: typeof round.content === 'string' ? round.content : undefined,
      findings,
    };
  };

  const rounds = Array.isArray(payload.rounds)
    ? payload.rounds.map(normalizeRound).filter((item): item is NonNullable<ReturnType<typeof normalizeRound>> => !!item)
    : [];

  const highlights = normalizeAgentStepFindings(payload.highlights);
  const finalResult =
    payload.final_result && typeof payload.final_result === 'object'
      ? (() => {
          const result = payload.final_result as unknown as Record<string, unknown>;
          return {
            summary: typeof result.summary === 'string' ? result.summary : '',
            revision_rounds: Number.isFinite(Number(result.revision_rounds))
              ? Number(result.revision_rounds)
              : 0,
            final_chars: Number.isFinite(Number(result.final_chars)) ? Number(result.final_chars) : 0,
            issue_count: Number.isFinite(Number(result.issue_count)) ? Number(result.issue_count) : 0,
            content: typeof result.content === 'string' ? result.content : undefined,
          };
        })()
      : undefined;

  return {
    phase: payload.phase,
    summary: typeof payload.summary === 'string' ? payload.summary : '',
    rounds,
    highlights,
    ...(finalResult ? { final_result: finalResult } : {}),
  };
}

function getAgentStepMessageKey(node: string, round: number, hasContentAgent: boolean): string {
  if (hasContentAgent || node === 'content_agent') {
    return 'content_agent';
  }
  return `${node}:${round || 1}`;
}

function shouldShowVerifyFindingsJson(
  step: { content?: unknown; is_complete?: boolean },
  findings: AgentStepFinding[]
): boolean {
  if (typeof step.content === 'string' && step.content.length > 0) {
    return true;
  }
  return !!step.is_complete || findings.length > 0;
}

function getMessageAgentStepKey(message: Message): string | undefined {
  if (typeof message.metadata?.agentStepKey === 'string') {
    return message.metadata.agentStepKey;
  }
  const node = message.metadata?.agentStepNode;
  const round = message.metadata?.agentStepRound;
  if (node === 'content_agent') {
    return 'content_agent';
  }
  if (typeof node === 'string' && typeof round === 'number') {
    return `${node}:${round}`;
  }
  return undefined;
}

function findAgentStepMessage(messages: Message[], taskId: string, key: string): Message | undefined {
  return messages.find((message) => {
    if (message.taskId !== taskId || message.metadata?.messageKind !== TASK_AGENT_STEP_KIND) {
      return false;
    }
    return getMessageAgentStepKey(message) === key;
  });
}

function hasAgentStepMessages(messages: Message[], taskId: string): boolean {
  return messages.some(
    (message) => message.taskId === taskId && message.metadata?.messageKind === TASK_AGENT_STEP_KIND
  );
}

function isAgentProcessTaskKind(taskKind?: TaskKind): boolean {
  return taskKind === 'generate' || taskKind === 'comment_supplement';
}

function shouldUseAgentProcessCards(
  state: Pick<ChatStore, 'conversations' | 'conversationDrafts' | 'taskSummaries'>,
  taskId: string,
  conversationId?: string | null
): boolean {
  const conversation =
    (conversationId ? state.conversations.find((item) => item.id === conversationId) : null) ||
    findConversationByTaskIdFromState(state, taskId);
  const summary = state.taskSummaries[taskId];

  if (summary?.task_kind && !isAgentProcessTaskKind(summary.task_kind)) {
    return false;
  }
  if (conversation && hasAgentStepMessages(conversation.messages, taskId)) {
    return true;
  }
  if (summary?.current_node === 'content_agent' || summary?.current_node === 'comment_agent') {
    return true;
  }
  if (summary?.task_kind === 'comment_supplement') {
    return true;
  }
  return conversation
    ? state.conversationDrafts[conversation.id]?.generation_mode === 'agent'
    : false;
}

function completeGeneratingAgentStepMessages(
  conversation: Conversation,
  taskId: string,
  terminalStatus: Extract<Message['status'], 'completed' | 'error' | 'cancelled'>
): Conversation {
  let changed = false;
  const messages = conversation.messages.map((message) => {
    if (
      message.taskId === taskId &&
      message.status === 'generating' &&
      message.metadata?.messageKind === TASK_AGENT_STEP_KIND
    ) {
      changed = true;
      return { ...message, status: terminalStatus };
    }
    return message;
  });
  return changed ? { ...conversation, messages } : conversation;
}

function getMessageById(messages: Message[], messageId?: string): Message | undefined {
  if (!messageId) {
    return undefined;
  }
  return messages.find((message) => message.id === messageId);
}

function buildGroupFromMessages(messages: Message[]): TaskMessageGroupIds {
  const logMessage = messages.find((message) => getTaskMessageKind(message) === TASK_LOG_KIND);
  const contentMessage = messages.find((message) => getTaskMessageKind(message) === TASK_CONTENT_KIND);
  const downloadMessage = messages.find(
    (message) => getTaskMessageKind(message) === TASK_DOWNLOAD_KIND
  );

  if (logMessage || contentMessage || downloadMessage) {
    return {
      ...(logMessage ? { logMessageId: logMessage.id } : {}),
      ...(contentMessage ? { contentMessageId: contentMessage.id } : {}),
      ...(downloadMessage ? { downloadMessageId: downloadMessage.id } : {}),
    };
  }

  const legacyMessage = messages.find(
    (message) => message.type === 'ai' && isDualColumnContent(message.content)
  );

  return legacyMessage ? { contentMessageId: legacyMessage.id } : {};
}

function mergeTaskMessageGroup(
  base: TaskMessageGroupIds,
  next?: TaskMessageGroupIds
): TaskMessageGroupIds {
  if (!next) {
    return base;
  }
  return {
    ...base,
    ...next,
  };
}

function hasTaskMessageGroupIds(group?: TaskMessageGroupIds): boolean {
  if (!group) {
    return false;
  }
  return !!(group.logMessageId || group.contentMessageId || group.downloadMessageId);
}

function findConversationByTaskIdFromState(
  state: Pick<ChatStore, 'conversations'>,
  taskId: string
): Conversation | null {
  const byBinding = state.conversations.find((conversation) => conversation.currentTaskId === taskId);
  if (byBinding) {
    return byBinding;
  }

  const byMessage = state.conversations.find((conversation) =>
    conversation.messages.some((message) => message.taskId === taskId)
  );
  return byMessage || null;
}

function sortConversationsByUpdatedAtDesc<T extends Pick<Conversation, 'updatedAt'>>(
  conversations: T[]
): T[] {
  return [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
}

function getMostRecentConversationByTypeFromState(
  state: Pick<ChatStore, 'conversations'>,
  type: TenderType
): Conversation | null {
  return (
    sortConversationsByUpdatedAtDesc(
      state.conversations.filter((conversation) => conversation.tenderType === type)
    )[0] || null
  );
}

/**
 * 从会话和草稿中提取 canonical URL 同步所需的参数。
 */
function resolveConversationUrlParams(
  conversation: Conversation,
  draft: ConversationFormDraft | undefined
): { tenderno?: string | null; tender_lx?: TenderLx; fund_lx?: FundLx } {
  const tenderno =
    getConversationTenderNo(conversation, draft);
  const tender_lx: TenderLx | undefined =
    draft?.tender_lx === 0 || draft?.tender_lx === 1 || draft?.tender_lx === 2
      ? draft.tender_lx
      : undefined;
  const fund_lx: FundLx | undefined =
    draft?.fund_lx === 0 || draft?.fund_lx === 1 ? draft.fund_lx : undefined;
  return { tenderno, tender_lx, fund_lx };
}

/**
 * 按 gngk 子类型精确匹配已有会话。
 * 匹配维度：tenderType=gngk + tenderno + tender_lx + fund_lx，
 * 若有多条完全同身份则复用 updatedAt 最新的一条。
 */
function findGngkConversationByIdentity(
  state: Pick<ChatStore, 'conversations' | 'conversationDrafts'>,
  tenderno: string,
  tenderLx: TenderLx,
  fundLx: FundLx
): Conversation | null {
  const normalizedTenderNo = normalizeTenderNo(tenderno);
  if (!normalizedTenderNo) {
    return null;
  }

  const candidates = state.conversations
    .filter((conversation) => {
      if (conversation.tenderType !== 'gngk') {
        return false;
      }
      const draft = state.conversationDrafts[conversation.id];
      const convTenderNo = getConversationTenderNo(conversation, draft);
      if (convTenderNo !== normalizedTenderNo) {
        return false;
      }
      const convTenderLx: TenderLx =
        draft?.tender_lx === 0 || draft?.tender_lx === 1 || draft?.tender_lx === 2
          ? draft.tender_lx
          : 0;
      const convFundLx: FundLx =
        draft?.fund_lx === 0 || draft?.fund_lx === 1 ? draft.fund_lx : 0;
      return convTenderLx === tenderLx && convFundLx === fundLx;
    });

  return sortConversationsByUpdatedAtDesc(candidates)[0] || null;
}

interface ChatStore {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskMessageMap: Record<string, TaskMessageGroupIds>;
  conversationDrafts: Record<string, ConversationFormDraft>;
  taskSummaries: Record<string, TaskSummarySnapshot>;
  unreadConversationResults: Record<string, boolean>;
  isLoading: boolean;
  error: string | null;
  selectedTenderType: TenderType | null;

  createConversation: (tenderno: string, tenderType: TenderType, title?: string) => string;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string | null) => void;
  updateConversationDraft: (conversationId: string, updates: Partial<ConversationFormDraft>) => void;
  clearConversationDraft: (conversationId: string) => void;
  getConversationDraft: (conversationId: string | null) => ConversationFormDraft | null;

  addMessage: (
    conversationId: string,
    message: Omit<Message, 'id' | 'timestamp' | 'conversationId'>
  ) => string;
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;

  startTask: (
    conversationId: string,
    taskId: string,
    initialSummary?: Partial<Omit<TaskSummarySnapshot, 'task_id' | 'updated_at'>>,
    initialGroup?: TaskMessageGroupIds
  ) => TaskMessageGroupIds;
  ensureTaskLogMessage: (taskId: string, options?: { status?: Message['status'] }) => string | null;
  ensureTaskContentMessage: (
    taskId: string,
    options?: {
      status?: Message['status'];
      content?: string;
      error?: string;
      suppressForAgentStep?: boolean;
    }
  ) => string | null;
  markTaskContentReady: (taskId: string, aiText?: string) => void;
  upsertAgentStepMessage: (taskId: string, step: SSEAgentStepEvent) => string | null;
  completeTask: (
    taskId: string,
    outputFile?: string,
    fileName?: string,
    content?: TaskMessageSnapshot,
    styleWriteback?: StyleWritebackSummary,
    commentWriteback?: CommentWritebackSummary
  ) => void;
  failTask: (taskId: string, error: string, content?: TaskMessageSnapshot) => void;
  cancelTask: (taskId: string, content?: TaskMessageSnapshot) => void;
  interruptTaskForBackendRestart: (taskId: string) => void;
  handleBackendRestart: () => void;
  discardStaleTask: (taskId: string) => void;
  detachTaskTracking: (taskId: string) => void;
  upsertTaskSummary: (
    taskId: string,
    summary: Omit<TaskSummarySnapshot, 'task_id' | 'updated_at'>
  ) => void;
  removeTaskSummary: (taskId: string) => void;
  getTaskSummary: (taskId: string) => TaskSummarySnapshot | null;
  markConversationUnreadResult: (conversationId: string) => void;
  clearConversationUnreadResult: (conversationId: string) => void;
  isConversationUnreadResult: (conversationId: string) => boolean;

  getCurrentConversation: () => Conversation | null;
  currentConversationActiveTask: () => string | null;
  currentConversationIsBusy: () => boolean;
  latestActiveTaskId: () => string | null;
  otherActiveTaskCount: () => number;
  hasActiveTasks: () => boolean;
  clearError: () => void;
  setSelectedTenderType: (type: TenderType | null) => void;
  findConversationByTenderNo: (tenderno: string, tenderType: TenderType) => Conversation | null;
  findGngkConversationByIdentity: (
    tenderno: string,
    tenderLx: TenderLx,
    fundLx: FundLx
  ) => Conversation | null;
  findTaskMessageGroup: (taskId: string) => LocatedTaskMessageGroup | null;
  findMessageByTaskId: (taskId: string) => { conversationId: string; message: Message } | null;
  getSortedConversations: () => Conversation[];
  getMostRecentConversationByType: (type: TenderType) => Conversation | null;
  syncUrlToCurrentConversation: () => void;
  resetSessionState: () => void;
}

export const useChatStore = create<ChatStore>()(
  devtools(
    persist(
      (set, get) => ({
        // State
        conversations: [],
        currentConversationId: null,
        activeTaskIds: [],
        taskMessageMap: {},
        conversationDrafts: {},
        taskSummaries: {},
        unreadConversationResults: {},
        isLoading: false,
        error: null,
        selectedTenderType: null,

        createConversation: (tenderno, tenderType, title) => {
          const conversation = createConvUtil(title || tenderno, tenderType);
          set((state) => ({
            conversations: [conversation, ...state.conversations],
            currentConversationId: conversation.id,
            selectedTenderType: tenderType,
            conversationDrafts: {
              ...state.conversationDrafts,
              [conversation.id]: {
                generation_mode: 'workflow',
                comment_generation_mode: 'on',
                generation_style: 'template',
                style_writeback_mode: 'full',
                model: 'deepseek',
              },
            },
          }));
          return conversation.id;
        },

        updateConversation: (id, updates) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === id ? { ...conv, ...updates, updatedAt: Date.now() } : conv
            ),
          }));
        },

        deleteConversation: (id) => {
          set((state) => {
            const conversationToDelete = state.conversations.find((conv) => conv.id === id);
            const deletedTaskIds = new Set<string>();

            if (conversationToDelete?.currentTaskId) {
              deletedTaskIds.add(conversationToDelete.currentTaskId);
            }
            for (const message of conversationToDelete?.messages || []) {
              if (typeof message.taskId === 'string') {
                deletedTaskIds.add(message.taskId);
              }
            }
            const newConversations = state.conversations.filter((conv) => conv.id !== id);

            let newCurrentId = state.currentConversationId;
            let nextSelectedTenderType = state.selectedTenderType;
            if (state.currentConversationId === id) {
              if (conversationToDelete) {
                const sameTypeConversations = sortConversationsByUpdatedAtDesc(
                  newConversations.filter((conv) => conv.tenderType === conversationToDelete.tenderType)
                );
                newCurrentId = sameTypeConversations[0]?.id || null;
                nextSelectedTenderType =
                  sameTypeConversations[0]?.tenderType || conversationToDelete.tenderType;
              } else {
                newCurrentId = sortConversationsByUpdatedAtDesc(newConversations)[0]?.id || null;
                nextSelectedTenderType =
                  newConversations.find((conversation) => conversation.id === newCurrentId)?.tenderType ||
                  nextSelectedTenderType;
              }
            }

            return {
              conversations: newConversations,
              currentConversationId: newCurrentId,
              selectedTenderType: nextSelectedTenderType,
              activeTaskIds: state.activeTaskIds.filter((taskId) => !deletedTaskIds.has(taskId)),
              taskMessageMap: Object.fromEntries(
                Object.entries(state.taskMessageMap).filter(([taskId]) => !deletedTaskIds.has(taskId))
              ),
              conversationDrafts: Object.fromEntries(
                Object.entries(state.conversationDrafts).filter(
                  ([conversationId]) => conversationId !== id
                )
              ),
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([taskId]) => !deletedTaskIds.has(taskId))
              ),
              unreadConversationResults: Object.fromEntries(
                Object.entries(state.unreadConversationResults).filter(
                  ([conversationId]) => conversationId !== id
                )
              ),
            };
          });
        },

        setCurrentConversation: (id) => {
          set((state) => {
            const nextConversation = id
              ? state.conversations.find((conversation) => conversation.id === id) || null
              : null;

            return {
              currentConversationId: id,
              selectedTenderType: nextConversation?.tenderType || state.selectedTenderType,
              unreadConversationResults: id
                ? Object.fromEntries(
                    Object.entries(state.unreadConversationResults).filter(
                      ([conversationId]) => conversationId !== id
                    )
                  )
                : state.unreadConversationResults,
            };
          });

          // Sync browser URL to reflect the newly selected conversation's state
          if (id) {
            get().syncUrlToCurrentConversation();
          }
        },

        updateConversationDraft: (conversationId, updates) => {
          set((state) => ({
            conversationDrafts: {
              ...state.conversationDrafts,
              [conversationId]: mergeConversationDraft(
                state.conversationDrafts[conversationId] || {},
                updates
              ),
            },
          }));
        },

        clearConversationDraft: (conversationId) =>
          set((state) => ({
            conversationDrafts: Object.fromEntries(
              Object.entries(state.conversationDrafts).filter(([id]) => id !== conversationId)
            ),
          })),

        getConversationDraft: (conversationId) => {
          if (!conversationId) {
            return null;
          }
          return get().conversationDrafts[conversationId] || null;
        },

        addMessage: (conversationId, message) => {
          const newMessage = {
            ...message,
            conversationId,
            id: generateMessageId(),
            timestamp: Date.now(),
          };
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? { ...conv, messages: [...conv.messages, newMessage], updatedAt: Date.now() }
                : conv
            ),
          }));
          return newMessage.id;
        },

        updateMessage: (conversationId, messageId, updates) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? {
                    ...conv,
                    messages: conv.messages.map((msg) =>
                      msg.id === messageId
                        ? {
                            ...msg,
                            ...updates,
                            ...(updates.metadata
                              ? { metadata: { ...(msg.metadata || {}), ...updates.metadata } }
                              : {}),
                          }
                        : msg
                    ),
                    updatedAt: Date.now(),
                  }
                : conv
            ),
          }));
        },

        deleteMessage: (conversationId, messageId) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? {
                    ...conv,
                    messages: conv.messages.filter((msg) => msg.id !== messageId),
                    updatedAt: Date.now(),
                  }
                : conv
            ),
          }));
        },

        startTask: (conversationId, taskId, initialSummary, initialGroup) => {
          let nextGroup: TaskMessageGroupIds = {};
          set((state) => {
            const summarySeed = initialSummary?.status
              ? {
                  [taskId]: {
                    ...(state.taskSummaries[taskId] || {}),
                    task_id: taskId,
                    status: initialSummary.status,
                    ...(typeof initialSummary.task_kind === 'string'
                      ? { task_kind: initialSummary.task_kind }
                      : {}),
                    ...(typeof initialSummary.queue_position === 'number'
                      ? { queue_position: initialSummary.queue_position }
                      : {}),
                    ...(typeof initialSummary.waiting_count === 'number'
                      ? { waiting_count: initialSummary.waiting_count }
                      : {}),
                    ...(typeof initialSummary.progress_percent === 'number'
                      ? { progress_percent: initialSummary.progress_percent }
                      : {}),
                    ...(typeof initialSummary.progress_text === 'string'
                      ? { progress_text: initialSummary.progress_text }
                      : {}),
                    ...(typeof initialSummary.current_node_display === 'string'
                      ? { current_node_display: initialSummary.current_node_display }
                      : {}),
                    ...(typeof initialSummary.current_node === 'string'
                      ? { current_node: initialSummary.current_node }
                      : {}),
                    updated_at: Date.now(),
                  },
                }
              : {};
            nextGroup = mergeTaskMessageGroup(state.taskMessageMap[taskId] || {}, initialGroup);

            return {
              conversations: state.conversations.map((conv) =>
                conv.id === conversationId
                  ? { ...conv, currentTaskId: taskId, updatedAt: Date.now() }
                  : conv
              ),
              activeTaskIds: state.activeTaskIds.includes(taskId)
                ? state.activeTaskIds
                : [...state.activeTaskIds, taskId],
              taskMessageMap: hasTaskMessageGroupIds(nextGroup)
                ? {
                    ...state.taskMessageMap,
                    [taskId]: nextGroup,
                  }
                : state.taskMessageMap,
              taskSummaries: {
                ...state.taskSummaries,
                ...summarySeed,
              },
            };
          });

          return nextGroup;
        },

        ensureTaskLogMessage: (taskId, options) => {
          const existing = get().findTaskMessageGroup(taskId);
          if (existing?.logMessage) {
            const existingKind = getTaskMessageKind(existing.logMessage);
            const shouldPromoteToTaskLog =
              existingKind !== TASK_LOG_KIND || existing.logMessage.taskId !== taskId;
            const requestedStatus = options?.status || existing.logMessage.status;
            const nextStatus =
              !shouldPromoteToTaskLog &&
              isTerminalMessageStatus(existing.logMessage.status) &&
              requestedStatus === 'generating'
                ? existing.logMessage.status
                : requestedStatus;
            const nextTaskKind = get().taskSummaries[taskId]?.task_kind;
            const existingLogs = normalizeLogEntries(existing.logMessage.metadata?.logs);
            const shouldUpdateStatus = existing.logMessage.status !== nextStatus;
            const shouldUpdateTaskKind = existing.logMessage.metadata?.taskKind !== nextTaskKind;

            if (shouldPromoteToTaskLog || shouldUpdateStatus || shouldUpdateTaskKind) {
              get().updateMessage(existing.conversationId, existing.logMessage.id, {
                taskId,
                ...(shouldPromoteToTaskLog ? { content: '' } : {}),
                status: nextStatus,
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(nextTaskKind ? { taskKind: nextTaskKind } : {}),
                  logs: existingLogs,
                },
              });
            }
            return existing.logMessage.id;
          }

          const conversation = findConversationByTaskIdFromState(get(), taskId);
          if (!conversation) {
            return null;
          }

          const logMessageId = get().addMessage(conversation.id, {
            type: 'ai',
            content: '',
            status: options?.status || 'generating',
            taskId,
            metadata: {
              messageKind: TASK_LOG_KIND,
              taskKind: get().taskSummaries[taskId]?.task_kind,
              logs: [],
            },
          });

          const currentGroup = get().taskMessageMap[taskId] || {};
          const nextGroup = mergeTaskMessageGroup(currentGroup, { logMessageId });

          set((state) => ({
            taskMessageMap: {
              ...state.taskMessageMap,
              [taskId]: nextGroup,
            },
          }));

          return logMessageId;
        },

        ensureTaskContentMessage: (taskId, options) => {
          let locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            get().ensureTaskLogMessage(taskId, { status: options?.status || 'generating' });
            locatedTaskGroup = get().findTaskMessageGroup(taskId);
          }
          if (!locatedTaskGroup) {
            return null;
          }

          if (locatedTaskGroup.contentMessage) {
            return locatedTaskGroup.contentMessage.id;
          }
          const conversation = get().conversations.find(
            (item) => item.id === locatedTaskGroup.conversationId
          );
          if (
            options?.suppressForAgentStep &&
            conversation &&
            hasAgentStepMessages(conversation.messages, taskId)
          ) {
            return null;
          }

          const contentMessageId = get().addMessage(locatedTaskGroup.conversationId, {
            type: 'ai',
            content: options?.content || '',
            status: options?.status || 'generating',
            ...(typeof options?.error === 'string' ? { error: options.error } : {}),
            taskId,
            metadata: {
              messageKind: TASK_CONTENT_KIND,
              taskKind: get().taskSummaries[taskId]?.task_kind,
            },
          });

          const nextGroup = mergeTaskMessageGroup(locatedTaskGroup.group, { contentMessageId });
          set((state) => ({
            taskMessageMap: {
              ...state.taskMessageMap,
              [taskId]: nextGroup,
            },
          }));

          return contentMessageId;
        },

        markTaskContentReady: (taskId, aiText) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            return;
          }

          const nextText = typeof aiText === 'string' ? aiText : undefined;
          const { conversationId, contentMessage } = locatedTaskGroup;

          if (!contentMessage) {
            get().ensureTaskContentMessage(taskId, {
              status: 'completed',
              ...(typeof nextText === 'string' ? { content: nextText } : {}),
            });
            return;
          }

          const shouldRefreshCompletedContent =
            contentMessage.status === 'completed' &&
            typeof nextText === 'string' &&
            nextText !== contentMessage.content;

          if (contentMessage.status !== 'generating' && !shouldRefreshCompletedContent) {
            return;
          }

          get().updateMessage(conversationId, contentMessage.id, {
            status: 'completed',
            error: undefined,
            ...(typeof nextText === 'string' ? { content: nextText } : {}),
            metadata: {
              messageKind: TASK_CONTENT_KIND,
              taskKind: get().taskSummaries[taskId]?.task_kind,
            },
          });
        },

        upsertAgentStepMessage: (taskId, step) => {
          get().ensureTaskLogMessage(taskId, { status: 'generating' });
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (
            locatedTaskGroup?.contentMessage &&
            getTaskMessageKind(locatedTaskGroup.contentMessage) === TASK_CONTENT_KIND
          ) {
            get().deleteMessage(locatedTaskGroup.conversationId, locatedTaskGroup.contentMessage.id);
            const nextGroup = { ...locatedTaskGroup.group };
            delete nextGroup.contentMessageId;
            set((state) => ({
              taskMessageMap: {
                ...state.taskMessageMap,
                [taskId]: nextGroup,
              },
            }));
          }

          const conversation = findConversationByTaskIdFromState(get(), taskId);
          if (!conversation) {
            return null;
          }

          const stepType = step.step_type || 'stream';
          const stepRound = step.round;
          const findings = normalizeAgentStepFindings(step.findings);
          const contentAgent = normalizeContentAgentStep(step.content_agent);
          const commentAgent = normalizeCommentAgentStep(step.comment_agent);
          const taskKind = step.task_kind || get().taskSummaries[taskId]?.task_kind;
          const sourceNode = step.node || 'content_agent';
          const stepKey = getAgentStepMessageKey(sourceNode, stepRound, !!contentAgent);
          const node = contentAgent ? 'content_agent' : sourceNode;
          const incomingStatus: Message['status'] = contentAgent
            ? contentAgent.phase === 'final' && step.is_complete
              ? 'completed'
              : 'generating'
            : step.is_complete
              ? 'completed'
              : 'generating';
          const existing = findAgentStepMessage(conversation.messages, taskId, stepKey);
          if (existing && isTerminalMessageStatus(existing.status) && incomingStatus === 'generating') {
            return existing.id;
          }
          const status = incomingStatus;

          conversation.messages.forEach((message) => {
            if (
              message.taskId !== taskId ||
              message.status !== 'generating' ||
              message.metadata?.messageKind !== TASK_AGENT_STEP_KIND ||
              getMessageAgentStepKey(message) === stepKey
            ) {
              return;
            }
            get().updateMessage(conversation.id, message.id, { status: 'completed' });
          });

          let content = typeof step.content === 'string' ? step.content : '';
          let auditRounds: AgentAuditRound[] | undefined;

          if (contentAgent) {
            content = contentAgent.final_result?.content || content || contentAgent.summary;
          } else if (node === 'content_verify_agent') {
            const existingRounds = normalizeAgentAuditRounds(existing?.metadata?.agentStepAuditRounds);
            const nextRound: AgentAuditRound = { round: stepRound, findings };
            auditRounds = [
              ...existingRounds.filter((round) => round.round !== stepRound),
              nextRound,
            ].sort((a, b) => a.round - b.round);
            content = shouldShowVerifyFindingsJson(step, findings)
              ? typeof step.content === 'string' && step.content.length > 0
                ? step.content
                : formatAgentFindingsJson(findings)
              : typeof existing?.content === 'string'
                ? existing.content
                : '';
          }

          const metadata = {
            messageKind: TASK_AGENT_STEP_KIND,
            ...(taskKind ? { taskKind } : {}),
            agentStepType: stepType,
            agentStepRound: stepRound,
            agentStepKey: stepKey,
            agentStepNode: node,
            ...(sourceNode !== node ? { agentStepSourceNode: sourceNode } : {}),
            agentStepFindings: findings,
            ...(contentAgent ? { contentAgent } : {}),
            ...(commentAgent ? { commentAgent } : {}),
            ...(auditRounds ? { agentStepAuditRounds: auditRounds } : {}),
          };

          const existingContent = typeof existing?.content === 'string' ? existing.content : '';
          const persistedContent = contentAgent
            ? content || existingContent
            : step.is_complete
              ? content
              : existingContent;

          if (existing) {
            if (
              !contentAgent &&
              !step.is_complete &&
              typeof step.content === 'string' &&
              step.content.length > 0
            ) {
              return existing.id;
            }
            get().updateMessage(conversation.id, existing.id, {
              content: persistedContent,
              status,
              error: undefined,
              metadata,
            });
            return existing.id;
          }

          return get().addMessage(conversation.id, {
            type: 'ai',
            content: persistedContent,
            status,
            taskId,
            metadata,
          });
        },

        completeTask: (taskId, outputFile, fileName, content, styleWriteback, commentWriteback) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;
          const terminalConversationId: string | null = locatedTaskGroup?.conversationId || null;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, downloadMessage, group } =
              locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;
            const usesAgentStepCards = shouldUseAgentProcessCards(get(), taskId, conversationId);

            if (
              usesAgentStepCards &&
              contentMessage &&
              getTaskMessageKind(contentMessage) === TASK_CONTENT_KIND
            ) {
              get().deleteMessage(conversationId, contentMessage.id);
            }

            if (logMessage) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'completed',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  taskKind: get().taskSummaries[taskId]?.task_kind,
                  ...(hasLogs ? { logs: content?.logs } : {}),
                },
              });
            }

            let contentMessageId: string | undefined = usesAgentStepCards
              ? undefined
              : contentMessage?.id;
            if (!usesAgentStepCards && !contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'completed',
                  content: content?.aiText || '',
                }) || undefined;
            } else if (!usesAgentStepCards && contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'completed',
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                error: undefined,
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                  taskKind: get().taskSummaries[taskId]?.task_kind,
                },
              });
            }

            let downloadMessageId = group.downloadMessageId;
            if (typeof outputFile === 'string' && outputFile.length > 0) {
              const resolvedFileName =
                typeof fileName === 'string' && fileName.length > 0
                  ? fileName
                  : outputFile.split(/[\\/]/).pop();

              if (downloadMessage) {
                get().updateMessage(conversationId, downloadMessage.id, {
                  status: 'completed',
                  content: resolvedFileName || '下载生成文件',
                  metadata: {
                    messageKind: TASK_DOWNLOAD_KIND,
                    taskKind: get().taskSummaries[taskId]?.task_kind,
                    outputFile,
                    fileName: resolvedFileName,
                    ...(styleWriteback ? { styleWriteback } : {}),
                    ...(commentWriteback ? { commentWriteback } : {}),
                  },
                });
                downloadMessageId = downloadMessage.id;
              } else {
                downloadMessageId = get().addMessage(conversationId, {
                  type: 'ai',
                  content: resolvedFileName || '下载生成文件',
                  status: 'completed',
                  taskId,
                  metadata: {
                    messageKind: TASK_DOWNLOAD_KIND,
                    taskKind: get().taskSummaries[taskId]?.task_kind,
                    outputFile,
                    fileName: resolvedFileName,
                    ...(styleWriteback ? { styleWriteback } : {}),
                    ...(commentWriteback ? { commentWriteback } : {}),
                  },
                });
              }
            }

            const baseGroup = usesAgentStepCards
              ? (() => {
                  const nextBaseGroup = { ...group };
                  delete nextBaseGroup.contentMessageId;
                  return nextBaseGroup;
                })()
              : group;
            nextGroup = mergeTaskMessageGroup(baseGroup, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
              ...(downloadMessageId ? { downloadMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            const shouldMarkUnread =
              terminalConversationId &&
              terminalConversationId !== state.currentConversationId;
            const nextUnreadResults = shouldMarkUnread
              ? {
                  ...state.unreadConversationResults,
                  [terminalConversationId]: true,
                }
              : state.unreadConversationResults;

            return {
              conversations: state.conversations.map((conversation) =>
                completeGeneratingAgentStepMessages(
                  conversation.currentTaskId === taskId
                    ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                    : conversation,
                  taskId,
                  'completed'
                )
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
              conversationDrafts: state.conversationDrafts,
              unreadConversationResults: nextUnreadResults,
            };
          });
        },

        failTask: (taskId, error, content) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;
          const terminalConversationId: string | null = locatedTaskGroup?.conversationId || null;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, group } = locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;
            const nextLogs = buildTaskFailureLogs(
              logMessage?.metadata?.logs,
              hasLogs ? content?.logs : undefined,
              error
            );
            const usesAgentStepCards = shouldUseAgentProcessCards(get(), taskId, conversationId);

            if (logMessage && getTaskMessageKind(logMessage) === TASK_LOG_KIND) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'error',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  taskKind: get().taskSummaries[taskId]?.task_kind,
                  logs: nextLogs,
                },
              });
            }

            if (
              usesAgentStepCards &&
              contentMessage &&
              getTaskMessageKind(contentMessage) === TASK_CONTENT_KIND
            ) {
              get().deleteMessage(conversationId, contentMessage.id);
            }

            let contentMessageId: string | undefined = usesAgentStepCards
              ? undefined
              : contentMessage?.id;
            if (!usesAgentStepCards && !contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'error',
                  content: content?.aiText || '',
                  error,
                }) || undefined;
            } else if (!usesAgentStepCards && contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'error',
                error,
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                  taskKind: get().taskSummaries[taskId]?.task_kind,
                },
              });
            }

            const baseGroup = usesAgentStepCards
              ? (() => {
                  const nextBaseGroup = { ...group };
                  delete nextBaseGroup.contentMessageId;
                  return nextBaseGroup;
                })()
              : group;
            nextGroup = mergeTaskMessageGroup(baseGroup, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            const shouldMarkUnread =
              terminalConversationId &&
              terminalConversationId !== state.currentConversationId;
            const nextUnreadResults = shouldMarkUnread
              ? {
                  ...state.unreadConversationResults,
                  [terminalConversationId]: true,
                }
              : state.unreadConversationResults;

            return {
              conversations: state.conversations.map((conversation) =>
                completeGeneratingAgentStepMessages(
                  conversation.currentTaskId === taskId
                    ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                    : conversation,
                  taskId,
                  'error'
                )
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
              unreadConversationResults: nextUnreadResults,
            };
          });
        },

        cancelTask: (taskId, content) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;
          const terminalConversationId: string | null = locatedTaskGroup?.conversationId || null;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, group } = locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;
            const usesAgentStepCards = shouldUseAgentProcessCards(get(), taskId, conversationId);

            if (logMessage && getTaskMessageKind(logMessage) === TASK_LOG_KIND) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'cancelled',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(hasLogs ? { logs: content?.logs } : {}),
                },
              });
            }

            if (
              usesAgentStepCards &&
              contentMessage &&
              getTaskMessageKind(contentMessage) === TASK_CONTENT_KIND
            ) {
              get().deleteMessage(conversationId, contentMessage.id);
            }

            let contentMessageId: string | undefined = usesAgentStepCards
              ? undefined
              : contentMessage?.id;
            if (!usesAgentStepCards && !contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'cancelled',
                  content: content?.aiText || '',
                }) || undefined;
            } else if (!usesAgentStepCards && contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'cancelled',
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                error: undefined,
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                },
              });
            }

            const baseGroup = usesAgentStepCards
              ? (() => {
                  const nextBaseGroup = { ...group };
                  delete nextBaseGroup.contentMessageId;
                  return nextBaseGroup;
                })()
              : group;
            nextGroup = mergeTaskMessageGroup(baseGroup, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            const shouldMarkUnread =
              terminalConversationId &&
              terminalConversationId !== state.currentConversationId;
            const nextUnreadResults = shouldMarkUnread
              ? {
                  ...state.unreadConversationResults,
                  [terminalConversationId]: true,
                }
              : state.unreadConversationResults;

            return {
              conversations: state.conversations.map((conversation) =>
                completeGeneratingAgentStepMessages(
                  conversation.currentTaskId === taskId
                    ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                    : conversation,
                  taskId,
                  'cancelled'
                )
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
              unreadConversationResults: nextUnreadResults,
            };
          });
        },

        interruptTaskForBackendRestart: (taskId) => {
          const taskSummary = get().taskSummaries[taskId];
          const runtimeSnapshot = getTaskRuntimeSnapshot(taskId);

          let locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            get().ensureTaskLogMessage(taskId, { status: 'error' });
            locatedTaskGroup = get().findTaskMessageGroup(taskId);
          }

          const taskKind =
            taskSummary?.task_kind ||
            locatedTaskGroup?.contentMessage?.metadata?.taskKind ||
            locatedTaskGroup?.logMessage?.metadata?.taskKind ||
            locatedTaskGroup?.downloadMessage?.metadata?.taskKind;

          let nextGroup: TaskMessageGroupIds | undefined;
          const terminalConversationId: string | null = locatedTaskGroup?.conversationId || null;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, group } = locatedTaskGroup;
            const usesAgentStepCards = shouldUseAgentProcessCards(get(), taskId, conversationId);
            const nextLogs = buildInterruptedLogs(
              logMessage?.metadata?.logs,
              runtimeSnapshot?.logs
            );
            const nextProgressText =
              runtimeSnapshot?.progressText ||
              taskSummary?.progress_text ||
              logMessage?.metadata?.progressText;
            const nextProgressPercent =
              runtimeSnapshot?.progressPercent ??
              taskSummary?.progress_percent ??
              (typeof logMessage?.metadata?.progressPercent === 'number'
                ? logMessage.metadata.progressPercent
                : undefined);
            const nextCurrentNode =
              runtimeSnapshot?.currentNode ||
              taskSummary?.current_node ||
              (typeof logMessage?.metadata?.currentNode === 'string'
                ? logMessage.metadata.currentNode
                : undefined);
            const nextCurrentNodeDisplay =
              runtimeSnapshot?.currentNodeDisplay ||
              taskSummary?.current_node_display ||
              (typeof logMessage?.metadata?.currentNodeDisplay === 'string'
                ? logMessage.metadata.currentNodeDisplay
                : undefined);

            if (logMessage && getTaskMessageKind(logMessage) === TASK_LOG_KIND) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'error',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(taskKind ? { taskKind } : {}),
                  logs: nextLogs,
                  ...(typeof nextProgressText === 'string'
                    ? { progressText: nextProgressText }
                    : {}),
                  ...(typeof nextProgressPercent === 'number'
                    ? { progressPercent: nextProgressPercent }
                    : {}),
                  ...(typeof nextCurrentNode === 'string'
                    ? { currentNode: nextCurrentNode }
                    : {}),
                  ...(typeof nextCurrentNodeDisplay === 'string'
                    ? { currentNodeDisplay: nextCurrentNodeDisplay }
                    : {}),
                  localTaskReason: BACKEND_RESTART_LOCAL_REASON,
                },
              });
            }

            const nextAiText =
              typeof runtimeSnapshot?.aiText === 'string' && runtimeSnapshot.aiText.length > 0
                ? runtimeSnapshot.aiText
                : typeof contentMessage?.content === 'string'
                  ? contentMessage.content
                  : '';
            const hasNonEmptyAiText = nextAiText.length > 0;

            if (
              usesAgentStepCards &&
              contentMessage &&
              getTaskMessageKind(contentMessage) === TASK_CONTENT_KIND
            ) {
              get().deleteMessage(conversationId, contentMessage.id);
            }

            let contentMessageId: string | undefined = usesAgentStepCards
              ? undefined
              : contentMessage?.id;
            if (!usesAgentStepCards && !contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'error',
                  content: nextAiText,
                  error: BACKEND_RESTART_TASK_MESSAGE,
                }) || undefined;

              if (contentMessageId) {
                get().updateMessage(conversationId, contentMessageId, {
                  status: 'error',
                  error: BACKEND_RESTART_TASK_MESSAGE,
                  metadata: {
                    messageKind: TASK_CONTENT_KIND,
                    ...(taskKind ? { taskKind } : {}),
                    ...(typeof nextProgressText === 'string'
                      ? { progressText: nextProgressText }
                      : {}),
                    ...(typeof nextProgressPercent === 'number'
                      ? { progressPercent: nextProgressPercent }
                      : {}),
                    ...(typeof nextCurrentNode === 'string'
                      ? { currentNode: nextCurrentNode }
                      : {}),
                    ...(typeof nextCurrentNodeDisplay === 'string'
                      ? { currentNodeDisplay: nextCurrentNodeDisplay }
                      : {}),
                    localTaskReason: BACKEND_RESTART_LOCAL_REASON,
                  },
                });
              }
            } else if (!usesAgentStepCards && contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'error',
                ...(hasNonEmptyAiText ? { content: nextAiText } : {}),
                error: BACKEND_RESTART_TASK_MESSAGE,
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                  ...(taskKind ? { taskKind } : {}),
                  ...(typeof nextProgressText === 'string'
                    ? { progressText: nextProgressText }
                    : {}),
                  ...(typeof nextProgressPercent === 'number'
                    ? { progressPercent: nextProgressPercent }
                    : {}),
                  ...(typeof nextCurrentNode === 'string'
                    ? { currentNode: nextCurrentNode }
                    : {}),
                  ...(typeof nextCurrentNodeDisplay === 'string'
                    ? { currentNodeDisplay: nextCurrentNodeDisplay }
                    : {}),
                  localTaskReason: BACKEND_RESTART_LOCAL_REASON,
                },
              });
            }

            const baseGroup = usesAgentStepCards
              ? (() => {
                  const nextBaseGroup = { ...group };
                  delete nextBaseGroup.contentMessageId;
                  return nextBaseGroup;
                })()
              : group;
            nextGroup = mergeTaskMessageGroup(baseGroup, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            const shouldMarkUnread =
              terminalConversationId &&
              terminalConversationId !== state.currentConversationId;
            const nextUnreadResults = shouldMarkUnread
              ? {
                  ...state.unreadConversationResults,
                  [terminalConversationId]: true,
                }
              : state.unreadConversationResults;

            return {
              conversations: state.conversations.map((conversation) => ({
                ...conversation,
                currentTaskId:
                  conversation.currentTaskId === taskId ? undefined : conversation.currentTaskId,
                updatedAt:
                  conversation.currentTaskId === taskId ? Date.now() : conversation.updatedAt,
                messages: conversation.messages.map((message) =>
                  message.taskId === taskId && message.status === 'generating'
                    ? {
                        ...message,
                        status: 'error',
                        error: BACKEND_RESTART_TASK_MESSAGE,
                        metadata: {
                          ...message.metadata,
                          localTaskReason: BACKEND_RESTART_LOCAL_REASON,
                        },
                      }
                    : message
                ),
              })),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
              unreadConversationResults: nextUnreadResults,
            };
          });

          useChatStreamStore.getState().clearStream(taskId);
          useChatTaskSessionStore.getState().removeSession(taskId);
        },

        handleBackendRestart: () => {
          const state = get();
          const interruptedTaskIds = collectBackendRestartTaskIds(state);

          for (const taskId of interruptedTaskIds) {
            get().interruptTaskForBackendRestart(taskId);
          }

          set((currentState) => ({
            conversationDrafts: Object.fromEntries(
              Object.entries(currentState.conversationDrafts).map(([conversationId, draft]) => [
                conversationId,
                mergeConversationDraft(draft, {
                  chat_input:
                    typeof draft.chat_input === 'string' && draft.chat_input.length > 0
                      ? draft.chat_input
                      : draft.pending_rewrite_prompt || draft.pending_edit_prompt,
                  pending_rewrite_prompt: undefined,
                  pending_rewrite_task_id: undefined,
                  pending_edit_prompt: undefined,
                  pending_edit_task_id: undefined,
                }),
              ])
            ),
          }));

          useChatStreamStore.setState({ streams: {} });
          useChatTaskSessionStore.getState().clearSessions();
        },

        discardStaleTask: (taskId) => {
          if (shouldInterruptTaskForBackendRestart(get(), taskId)) {
            get().interruptTaskForBackendRestart(taskId);
            return;
          }

          set((state) => ({
            conversations: state.conversations.map((conv) => ({
              ...conv,
              currentTaskId: conv.currentTaskId === taskId ? undefined : conv.currentTaskId,
              messages: conv.messages.filter((msg) => {
                if (msg.taskId !== taskId || msg.status !== 'generating') {
                  return true;
                }

                const kind = getTaskMessageKind(msg);
                if (kind === TASK_DOWNLOAD_KIND) {
                  return true;
                }

                return false;
              }),
            })),
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
            taskSummaries: Object.fromEntries(
              Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
            ),
          }));
        },

        detachTaskTracking: (taskId) =>
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.currentTaskId === taskId
                ? { ...conv, currentTaskId: undefined, updatedAt: Date.now() }
                : conv
            ),
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskSummaries: Object.fromEntries(
              Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
            ),
          })),

        upsertTaskSummary: (taskId, summary) =>
          set((state) => ({
            taskSummaries: {
              ...state.taskSummaries,
              [taskId]: {
                ...(state.taskSummaries[taskId] || {}),
                ...summary,
                task_id: taskId,
                updated_at: Date.now(),
              },
            },
          })),

        removeTaskSummary: (taskId) =>
          set((state) => ({
            taskSummaries: Object.fromEntries(
              Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
            ),
          })),

        getTaskSummary: (taskId) => get().taskSummaries[taskId] || null,

        markConversationUnreadResult: (conversationId) =>
          set((state) => ({
            unreadConversationResults: {
              ...state.unreadConversationResults,
              [conversationId]: true,
            },
          })),

        clearConversationUnreadResult: (conversationId) =>
          set((state) => ({
            unreadConversationResults: Object.fromEntries(
              Object.entries(state.unreadConversationResults).filter(
                ([id]) => id !== conversationId
              )
            ),
          })),

        isConversationUnreadResult: (conversationId) =>
          !!get().unreadConversationResults[conversationId],

        getCurrentConversation: () => {
          const state = get();
          return (
            state.conversations.find((conv) => conv.id === state.currentConversationId) || null
          );
        },

        currentConversationActiveTask: () => {
          const state = get();
          return getCurrentConversationActiveTaskFromState(state);
        },

        currentConversationIsBusy: () => {
          const state = get();
          return getCurrentConversationActiveTaskFromState(state) !== null;
        },

        latestActiveTaskId: () => {
          const state = get();
          return getLatestActiveTaskIdFromState(state);
        },

        otherActiveTaskCount: () => {
          const state = get();
          const latestTaskId = getLatestActiveTaskIdFromState(state);
          if (!latestTaskId) {
            return 0;
          }

          return getActiveTaskIdsFromState(state).filter((taskId) => taskId !== latestTaskId).length;
        },

        hasActiveTasks: () => getActiveTaskIdsFromState(get()).length > 0,
        clearError: () => set({ error: null }),
        setSelectedTenderType: (type) => set({ selectedTenderType: type }),

        findConversationByTenderNo: (tenderno, tenderType) => {
          const state = get();
          const normalizedTenderNo = normalizeTenderNo(tenderno);
          if (!normalizedTenderNo) {
            return null;
          }

          return (
            [...state.conversations]
              .filter((conversation) => conversation.tenderType === tenderType)
              .sort((a, b) => b.updatedAt - a.updatedAt)
              .find(
                (conversation) =>
                  getConversationTenderNo(
                    conversation,
                    state.conversationDrafts[conversation.id]
                  ) === normalizedTenderNo
              ) || null
          );
        },

        findGngkConversationByIdentity: (tenderno, tenderLx, fundLx) => {
          return findGngkConversationByIdentity(get(), tenderno, tenderLx, fundLx);
        },

        findTaskMessageGroup: (taskId) => {
          const state = get();
          const mappedGroup = state.taskMessageMap[taskId];

          if (mappedGroup) {
            for (const conversation of state.conversations) {
              const logMessage = getMessageById(conversation.messages, mappedGroup.logMessageId);
              const contentMessage = getMessageById(
                conversation.messages,
                mappedGroup.contentMessageId
              );
              const downloadMessage = getMessageById(
                conversation.messages,
                mappedGroup.downloadMessageId
              );

              if (logMessage || contentMessage || downloadMessage) {
                return {
                  conversationId: conversation.id,
                  group: mappedGroup,
                  logMessage,
                  contentMessage,
                  downloadMessage,
                };
              }
            }
          }

          for (const conversation of state.conversations) {
            const taskMessages = conversation.messages.filter((item) => item.taskId === taskId);
            if (taskMessages.length === 0) {
              continue;
            }

            const builtGroup = buildGroupFromMessages(taskMessages);
            const logMessage = getMessageById(conversation.messages, builtGroup.logMessageId);
            const contentMessage = getMessageById(conversation.messages, builtGroup.contentMessageId);
            const downloadMessage = getMessageById(
              conversation.messages,
              builtGroup.downloadMessageId
            );

            if (logMessage || contentMessage || downloadMessage) {
              return {
                conversationId: conversation.id,
                group: builtGroup,
                logMessage,
                contentMessage,
                downloadMessage,
              };
            }

            const legacyMessage = taskMessages.find((message) => message.type === 'ai');
            if (legacyMessage) {
              return {
                conversationId: conversation.id,
                group: { contentMessageId: legacyMessage.id },
                contentMessage: legacyMessage,
              };
            }
          }

          return null;
        },

        findMessageByTaskId: (taskId) => {
          const group = get().findTaskMessageGroup(taskId);
          if (group) {
            const message = group.contentMessage || group.logMessage || group.downloadMessage;
            if (message) {
              return { conversationId: group.conversationId, message };
            }
          }

          const state = get();
          for (const conversation of state.conversations) {
            const message = conversation.messages.find((item) => item.taskId === taskId);
            if (message) {
              return { conversationId: conversation.id, message };
            }
          }
          return null;
        },

        getSortedConversations: () => {
          const state = get();
          return sortConversationsByUpdatedAtDesc(state.conversations);
        },

        getMostRecentConversationByType: (type: TenderType) => {
          const state = get();
          return getMostRecentConversationByTypeFromState(state, type);
        },

        syncUrlToCurrentConversation: () => {
          const state = get();
          const conversation = state.conversations.find(
            (conv) => conv.id === state.currentConversationId
          );
          if (!conversation) {
            return;
          }
          const draft = state.conversationDrafts[conversation.id];
          const urlParams = resolveConversationUrlParams(conversation, draft);
          syncBrowserUrlToConversation({
            tenderType: conversation.tenderType,
            tenderno: urlParams.tenderno,
            tender_lx: urlParams.tender_lx,
            fund_lx: urlParams.fund_lx,
          });
        },

        resetSessionState: () =>
          set({
            conversations: [],
            currentConversationId: null,
            activeTaskIds: [],
            taskMessageMap: {},
            conversationDrafts: {},
            taskSummaries: {},
            unreadConversationResults: {},
            isLoading: false,
            error: null,
            selectedTenderType: null,
          }),
      }),
      {
        name: 'chat-storage',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          conversations: state.conversations,
          currentConversationId: state.currentConversationId,
          selectedTenderType: state.selectedTenderType,
          conversationDrafts: state.conversationDrafts,
          taskSummaries: state.taskSummaries,
          unreadConversationResults: state.unreadConversationResults,
        }),
      }
    )
  )
);

export default useChatStore;
