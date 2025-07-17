export interface Config {
  api_key: string;
  base_url: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
}

export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  use_orchestrator?: boolean;
}

export interface ChatResponse {
  response: string;
  error?: string;
}

export interface StreamChunk {
  type: 'content' | 'status' | 'clear_status' | 'progress' | 'error' | 'tool_usage' | 'clear_tool_usage';
  data: any;
}

export interface ProgressData {
  agent_id: number;
  status: string;
  total_agents: number;
}

export interface OrchestratorStatus {
  num_agents: number;
  aggregation_strategy: string;
  task_timeout: number;
}