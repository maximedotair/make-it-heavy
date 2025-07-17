import { ChatMessage, StreamChunk, ProgressData } from '../types/index.js';
import { marked } from 'marked';
import hljs from 'highlight.js';

export class ChatInterface {
  private container: HTMLElement;
  private messages: ChatMessage[] = [];
  private isStreaming = false;
  private useOrchestrator = false;
  private progressContainer: HTMLElement | null = null;
  private orchestrationInProgress = false;
  private allAgentsCompleted = false;

  constructor(containerId: string) {
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Container with id "${containerId}" not found`);
    }
    this.container = container;
    this.setupMarked();
    this.render();
  }

  private setupMarked() {
    marked.setOptions({
      breaks: true,
      gfm: true
    });
  }

  private render() {
    this.container.innerHTML = `
      <div class="flex flex-col h-full">
        <div class="border-b border-gray-200 p-4">
          <div class="flex items-center justify-between">
            <h2 class="text-xl font-semibold">Agent Chat Interface</h2>
            <div class="flex items-center space-x-2">
              <label class="flex items-center space-x-2 text-sm">
                <input
                  type="checkbox"
                  id="orchestrator-toggle"
                  class="rounded border-gray-300 text-blue-600 focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                />
                <span>Multi-Agent Mode</span>
              </label>
              <button
                id="clear-button"
                class="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
        
        <div id="messages-container" class="flex-1 overflow-y-auto p-4 space-y-4">
          <div class="text-center text-gray-500 py-8">
            <div class="text-2xl mb-2">🤖</div>
            <p class="text-lg">Welcome to OpenRouter Agent Interface</p>
            <p class="text-sm">Ask your question below</p>
          </div>
        </div>
        
        <div id="progress-container" class="hidden border-t border-gray-200 bg-gray-50 p-4">
          <h3 class="text-sm font-medium text-gray-700 mb-2">Multi-Agent Progress</h3>
          <div id="progress-bars" class="space-y-2"></div>
          <div id="tool-usage-container" class="hidden mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div class="flex items-center space-x-2">
              <div class="w-4 h-4 bg-blue-500 rounded-full animate-pulse"></div>
              <div id="tool-usage-text" class="text-sm text-blue-800 font-medium"></div>
            </div>
          </div>
          <div id="orchestration-progress" class="hidden mt-4 pt-4 border-t border-gray-300">
            <div class="flex items-center space-x-3">
              <div class="text-2xl">🧠</div>
              <div class="flex-1">
                <div class="text-sm font-medium text-gray-700 mb-1">Final Orchestration</div>
                <div class="bg-gray-200 rounded-full h-2">
                  <div id="orchestration-bar" class="h-2 rounded-full bg-purple-500 transition-all duration-500" style="width: 0%"></div>
                </div>
              </div>
              <div id="orchestration-status" class="text-xs text-gray-600">Waiting...</div>
            </div>
            <div class="text-xs text-gray-500 mt-2">Consolidating results from all agents...</div>
          </div>
        </div>
        
        <div class="border-t border-gray-200 p-4">
          <div class="flex space-x-2">
            <textarea
              id="message-input"
              class="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
              placeholder="Type your message here..."
              rows="1"
            ></textarea>
            <button
              id="send-button"
              class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span id="send-icon">📤</span>
              <span id="loading-spinner" class="hidden">⏳</span>
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupEventListeners();
  }

  private setupEventListeners() {
    const input = document.getElementById('message-input') as HTMLTextAreaElement;
    const button = document.getElementById('send-button') as HTMLButtonElement;
    const clearButton = document.getElementById('clear-button') as HTMLButtonElement;
    const orchestratorToggle = document.getElementById('orchestrator-toggle') as HTMLInputElement;

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    button.addEventListener('click', () => this.sendMessage());
    clearButton.addEventListener('click', () => this.clear());
    
    orchestratorToggle.addEventListener('change', (e) => {
      this.useOrchestrator = (e.target as HTMLInputElement).checked;
      if (this.useOrchestrator) {
        this.showOrchestratorInfo();
      }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = input.scrollHeight + 'px';
    });
  }

  private async showOrchestratorInfo() {
    try {
      const response = await fetch('http://localhost:8000/api/orchestrator/status');
      const status = await response.json();
      
      const container = document.getElementById('messages-container');
      if (container) {
        const infoDiv = document.createElement('div');
        infoDiv.className = 'bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4';
        infoDiv.innerHTML = `
          <div class="flex items-center space-x-2 mb-2">
            <span class="text-blue-600">🔧</span>
            <span class="font-medium text-blue-800">Multi-Agent Mode Enabled</span>
          </div>
          <p class="text-sm text-blue-700">
            Using ${status.num_agents} agents in parallel with "${status.aggregation_strategy}" strategy.
            Timeout: ${status.task_timeout}s per agent.
          </p>
        `;
        container.appendChild(infoDiv);
        this.scrollToBottom();
      }
    } catch (error) {
      console.error('Error fetching orchestrator status:', error);
    }
  }

  private async sendMessage() {
    const input = document.getElementById('message-input') as HTMLTextAreaElement;
    const button = document.getElementById('send-button') as HTMLButtonElement;
    const sendIcon = document.getElementById('send-icon') as HTMLElement;
    const loadingSpinner = document.getElementById('loading-spinner') as HTMLElement;

    const message = input.value.trim();
    if (!message || this.isStreaming) return;

    // Ajouter le message de l'utilisateur
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date()
    };
    this.addMessage(userMessage);

    // Effacer l'input
    input.value = '';
    input.style.height = 'auto';

    // Afficher l'indicateur de chargement
    button.disabled = true;
    sendIcon.classList.add('hidden');
    loadingSpinner.classList.remove('hidden');

    // Afficher le conteneur de progression si mode orchestrateur
    if (this.useOrchestrator) {
      this.showProgressContainer();
    }

    try {
      await this.streamResponse(message);
    } catch (error) {
      console.error('Error:', error);
      this.addErrorMessage('An error occurred. Please try again.');
    } finally {
      button.disabled = false;
      sendIcon.classList.remove('hidden');
      loadingSpinner.classList.add('hidden');
      this.hideProgressContainer();
      this.resetOrchestratorState();
    }
  }

  private showProgressContainer() {
    const container = document.getElementById('progress-container');
    if (container) {
      container.classList.remove('hidden');
      this.progressContainer = container;
    }
  }

  private hideProgressContainer() {
    const container = document.getElementById('progress-container');
    if (container) {
      container.classList.add('hidden');
      // Nettoyer les barres de progression
      const progressBars = document.getElementById('progress-bars');
      if (progressBars) {
        progressBars.innerHTML = '';
      }
      // Cacher la progression d'orchestration
      const orchestrationProgress = document.getElementById('orchestration-progress');
      if (orchestrationProgress) {
        orchestrationProgress.classList.add('hidden');
      }
    }
  }

  private resetOrchestratorState() {
    this.orchestrationInProgress = false;
    this.allAgentsCompleted = false;
  }

  private updateProgress(progressData: ProgressData) {
    const progressBars = document.getElementById('progress-bars');
    if (!progressBars) return;

    let agentBar = document.getElementById(`agent-${progressData.agent_id}`);
    if (!agentBar) {
      agentBar = document.createElement('div');
      agentBar.id = `agent-${progressData.agent_id}`;
      agentBar.className = 'flex items-center space-x-2 text-sm';
      progressBars.appendChild(agentBar);
    }

    const statusColor = this.getStatusColor(progressData.status);
    const statusIcon = this.getStatusIcon(progressData.status);

    agentBar.innerHTML = `
      <div class="w-16 text-gray-600">Agent ${progressData.agent_id}</div>
      <div class="flex-1 bg-gray-200 rounded-full h-2">
        <div class="h-2 rounded-full transition-all duration-300 ${statusColor}"
             style="width: ${this.getProgressWidth(progressData.status)}%"></div>
      </div>
      <div class="w-6 text-center">${statusIcon}</div>
      <div class="w-24 text-xs text-gray-600">${progressData.status}</div>
    `;

    // Vérifier si tous les agents sont terminés
    this.checkAllAgentsCompleted();
  }

  private checkAllAgentsCompleted() {
    const progressBars = document.getElementById('progress-bars');
    if (!progressBars) return;

    const agentBars = progressBars.querySelectorAll('[id^="agent-"]');
    if (agentBars.length === 0) return;

    const completedAgents = Array.from(agentBars).filter(bar =>
      bar.textContent?.includes('COMPLETED')
    );

    if (completedAgents.length === agentBars.length && !this.allAgentsCompleted) {
      this.allAgentsCompleted = true;
      this.showOrchestrationProgress();
    }
  }

  private showOrchestrationProgress() {
    const orchestrationProgress = document.getElementById('orchestration-progress');
    const orchestrationBar = document.getElementById('orchestration-bar');
    const orchestrationStatus = document.getElementById('orchestration-status');
    
    if (orchestrationProgress && orchestrationBar && orchestrationStatus) {
      orchestrationProgress.classList.remove('hidden');
      orchestrationBar.style.width = '25%';
      orchestrationStatus.textContent = 'Starting...';
      
      // Simuler une progression pendant que l'orchestration se prépare
      setTimeout(() => {
        if (orchestrationBar && orchestrationStatus) {
          orchestrationBar.style.width = '50%';
          orchestrationStatus.textContent = 'Processing...';
        }
      }, 1000);
    }
  }

  private updateOrchestrationProgress(phase: 'consolidating' | 'streaming' | 'completed') {
    const orchestrationBar = document.getElementById('orchestration-bar');
    const orchestrationStatus = document.getElementById('orchestration-status');
    
    if (!orchestrationBar || !orchestrationStatus) return;

    switch (phase) {
      case 'consolidating':
        orchestrationBar.style.width = '75%';
        orchestrationStatus.textContent = 'Consolidating...';
        this.orchestrationInProgress = true;
        break;
      case 'streaming':
        orchestrationBar.style.width = '90%';
        orchestrationStatus.textContent = 'Delivering...';
        break;
      case 'completed':
        orchestrationBar.style.width = '100%';
        orchestrationStatus.textContent = 'Completed ✅';
        this.orchestrationInProgress = false;
        break;
    }
  }

  private getStatusColor(status: string): string {
    switch (status) {
      case 'QUEUED': return 'bg-gray-300';
      case 'PROCESSING...': return 'bg-blue-500';
      case 'COMPLETED': return 'bg-green-500';
      default: return 'bg-red-500';
    }
  }

  private getStatusIcon(status: string): string {
    switch (status) {
      case 'QUEUED': return '⏳';
      case 'PROCESSING...': return '🔄';
      case 'COMPLETED': return '✅';
      default: return '❌';
    }
  }

  private getProgressWidth(status: string): number {
    switch (status) {
      case 'QUEUED': return 25;
      case 'PROCESSING...': return 75;
      case 'COMPLETED': return 100;
      default: return 0;
    }
  }

  private async streamResponse(message: string) {
    this.isStreaming = true;
    
    const assistantMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    
    const messageElement = this.createMessageElement(assistantMessage);
    const contentElement = messageElement.querySelector('.message-content') as HTMLElement;
    
    // Ajouter l'élément de message au DOM
    const container = document.getElementById('messages-container');
    if (container) {
      container.appendChild(messageElement);
      this.scrollToBottom();
    }
    
    const response = await fetch('http://localhost:8000/api/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        message,
        use_orchestrator: this.useOrchestrator 
      }),
    });

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') {
            this.isStreaming = false;
            // Marquer l'orchestration comme terminée si elle était en cours
            if (this.allAgentsCompleted) {
              this.updateOrchestrationProgress('completed');
            }
            return;
          }

          try {
            const chunk: StreamChunk = JSON.parse(data);
            
            switch (chunk.type) {
              case 'content':
                assistantMessage.content += chunk.data;
                contentElement.innerHTML = this.renderMarkdown(assistantMessage.content);
                this.scrollToBottom();
                break;
                
              case 'status':
                this.showStatusMessage(chunk.data);
                // Détecter les phases d'orchestration
                if (chunk.data.includes('Orchestration') || chunk.data.includes('consolidat')) {
                  this.updateOrchestrationProgress('consolidating');
                } else if (chunk.data.includes('Streaming') || chunk.data.includes('words')) {
                  this.updateOrchestrationProgress('streaming');
                }
                break;
                
              case 'clear_status':
                this.clearStatusMessage();
                break;
                
              case 'progress':
                if (this.useOrchestrator) {
                  this.updateProgress(chunk.data as ProgressData);
                }
                break;
                
              case 'tool_usage':
                this.showToolUsage(chunk.data);
                break;
                
              case 'clear_tool_usage':
                this.clearToolUsage();
                break;
                
              case 'error':
                this.addErrorMessage(chunk.data);
                break;
            }
          } catch (e) {
            console.error('Error parsing chunk:', e, 'Raw data:', data);
          }
        }
      }
    }

    this.isStreaming = false;
  }

  private showStatusMessage(status: string) {
    const container = document.getElementById('messages-container');
    if (container) {
      const existingStatus = container.querySelector('.status-message');
      if (existingStatus) {
        existingStatus.remove();
      }

      const statusDiv = document.createElement('div');
      statusDiv.className = 'status-message bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-yellow-800 text-sm animate-pulse';
      statusDiv.innerHTML = `
        <div class="flex items-center space-x-2">
          <span>⚡</span>
          <span>${status}</span>
        </div>
      `;
      container.appendChild(statusDiv);
      this.scrollToBottom();
    }
  }

  private clearStatusMessage() {
    const container = document.getElementById('messages-container');
    if (container) {
      const existingStatus = container.querySelector('.status-message');
      if (existingStatus) {
        existingStatus.remove();
      }
    }
  }

  private showToolUsage(toolData: any) {
    const container = document.getElementById('tool-usage-container');
    const textElement = document.getElementById('tool-usage-text');
    
    if (container && textElement) {
      container.classList.remove('hidden');
      
      // Formater le message selon le type d'outil
      let message = '';
      if (toolData.event === 'tool_start') {
        const toolIcon = this.getToolIcon(toolData.tool_name);
        message = `${toolIcon} Utilisation de ${toolData.tool_name}`;
        
        // Ajouter des détails spécifiques selon l'outil
        if (toolData.tool_name === 'search_web' && toolData.query) {
          message += ` : "${toolData.query}"`;
        } else if (toolData.tool_name === 'calculate' && toolData.expression) {
          message += ` : ${toolData.expression}`;
        } else if ((toolData.tool_name === 'read_file' || toolData.tool_name === 'write_file') && toolData.filename) {
          message += ` : ${toolData.filename}`;
        }
      } else if (toolData.event === 'tool_complete') {
        message = `✅ ${toolData.tool_name} terminé`;
      }
      
      textElement.textContent = message;
    }
  }

  private clearToolUsage() {
    const container = document.getElementById('tool-usage-container');
    if (container) {
      container.classList.add('hidden');
    }
  }

  private getToolIcon(toolName: string): string {
    switch (toolName) {
      case 'search_web': return '🔍';
      case 'calculate': return '🧮';
      case 'read_file': return '📖';
      case 'write_file': return '✍️';
      case 'list_files': return '📁';
      default: return '🔧';
    }
  }

  private addMessage(message: ChatMessage) {
    this.messages.push(message);
    const container = document.getElementById('messages-container');
    if (container) {
      const messageElement = this.createMessageElement(message);
      container.appendChild(messageElement);
      this.scrollToBottom();
    }
  }

  private addErrorMessage(error: string) {
    // Nettoyer le message de statut
    this.clearStatusMessage();
    
    const errorMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'assistant',
      content: `**Error:** ${error}`,
      timestamp: new Date()
    };
    this.addMessage(errorMessage);
  }

  private createMessageElement(message: ChatMessage): HTMLElement {
    const div = document.createElement('div');
    div.className = `flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`;
    
    const contentClass = message.role === 'user' 
      ? 'bg-blue-500 text-white' 
      : 'bg-gray-100 text-gray-800';
    
    div.innerHTML = `
      <div class="max-w-xs lg:max-w-md xl:max-w-lg">
        <div class="${contentClass} rounded-lg px-4 py-2">
          <div class="message-content">${this.renderMarkdown(message.content)}</div>
          <div class="text-xs opacity-75 mt-1">
            ${message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      </div>
    `;
    
    return div;
  }

  private renderMarkdown(content: string): string {
    try {
      const result = marked.parse(content);
      return typeof result === 'string' ? result : content;
    } catch (error) {
      console.error('Markdown rendering error:', error);
      return content;
    }
  }

  private scrollToBottom() {
    const container = document.getElementById('messages-container');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  public clear() {
    this.messages = [];
    const container = document.getElementById('messages-container');
    if (container) {
      container.innerHTML = `
        <div class="text-center text-gray-500 py-8">
          <div class="text-2xl mb-2">🤖</div>
          <p class="text-lg">Conversation cleared</p>
          <p class="text-sm">Ask a new question</p>
        </div>
      `;
    }
    this.hideProgressContainer();
  }
}