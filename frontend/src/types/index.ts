export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isReflection?: boolean;
}

export interface StreamChunk {
  type: 'content' | 'status' | 'clear_status' | 'progress' | 'tool_usage' | 'clear_tool_usage' | 'error';
  data: string | ProgressData | any;
}

export interface ProgressData {
  agent_id: string;
  status: string;
  progress?: number;
  message?: string;
}

export interface AgentStatus {
  id: string;
  name: string;
  status: 'idle' | 'processing' | 'completed' | 'error';
  progress?: number;
  result?: string;
  error?: string;
}

export interface OrchestratorConfig {
  num_agents: number;
  task_timeout: number;
  aggregation_strategy: string;
  agents: string[];
}

export interface ToolUsage {
  tool_name: string;
  event: 'tool_start' | 'tool_complete' | 'tool_error';
  query?: string;
  expression?: string;
  filename?: string;
  path?: string;
  error?: string;
}

export interface Config {
  openrouter_api_key: string;
  model: string;
  max_tokens: number;
  temperature: number;
  num_agents: number;
  task_timeout: number;
  aggregation_strategy: string;
  base_url?: string;
  api_key?: string;
}