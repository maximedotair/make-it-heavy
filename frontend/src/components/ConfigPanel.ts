import { Config } from '../types/index.js';

export class ConfigPanel {
  private container: HTMLElement;
  private config: Config | null = null;

  constructor(containerId: string) {
    const element = document.getElementById(containerId);
    if (!element) {
      throw new Error(`Container with id ${containerId} not found`);
    }
    this.container = element;
    this.loadConfig();
  }

  private async loadConfig(): Promise<void> {
    try {
      const response = await fetch('/api/config');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      this.config = data;
      this.render();
    } catch (error) {
      console.error('Error loading configuration:', error);
      this.showError('Unable to load configuration');
    }
  }

  private async saveConfig(): Promise<void> {
    if (!this.config) return;

    try {
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(this.config),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      this.showSuccess('Configuration saved successfully');
    } catch (error) {
      console.error('Error saving configuration:', error);
      this.showError('Error saving configuration');
    }
  }

  private render(): void {
    if (!this.config) return;

    this.container.innerHTML = `
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Model</label>
          <input type="text" id="model" value="${this.config.model || ''}"
                 placeholder="e.g., openai/gpt-4"
                 class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
          <input type="text" id="base_url" value="${this.config.base_url || ''}"
                 placeholder="https://openrouter.ai/api/v1"
                 class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
          <input type="password" id="api_key" value="${this.config.api_key || ''}"
                 placeholder="Enter your OpenRouter API key"
                 class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
          <input type="number" id="temperature" value="${this.config.temperature || 0.7}"
                 min="0" max="2" step="0.1"
                 class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          <p class="text-xs text-gray-500 mt-1">Controls randomness (0-2)</p>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Max Tokens</label>
          <input type="number" id="max_tokens" value="${this.config.max_tokens || 2000}"
                 min="1" max="4000"
                 class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          <p class="text-xs text-gray-500 mt-1">Maximum response length</p>
        </div>
        
        <button id="save-config"
                class="w-full bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 transition duration-200">
          Save Configuration
        </button>
        
        <div id="config-message" class="hidden p-3 rounded-md text-sm"></div>
      </div>
    `;

    this.attachEventListeners();
  }

  private attachEventListeners(): void {
    const saveButton = document.getElementById('save-config');
    saveButton?.addEventListener('click', () => this.handleSave());

    // Auto-save on input change
    const inputs = ['model', 'base_url', 'api_key', 'temperature', 'max_tokens'];
    inputs.forEach(id => {
      const input = document.getElementById(id) as HTMLInputElement;
      if (input && this.config) {
        input.addEventListener('input', (e) => {
          const target = e.target as HTMLInputElement;
          this.updateConfigValue(id, target.value);
        });
      }
    });
  }

  private updateConfigValue(id: string, value: string): void {
    if (!this.config) return;
    
    switch (id) {
      case 'temperature':
        this.config.temperature = parseFloat(value);
        break;
      case 'max_tokens':
        this.config.max_tokens = parseInt(value);
        break;
      case 'model':
        this.config.model = value;
        break;
      case 'base_url':
        this.config.base_url = value;
        break;
      case 'api_key':
        this.config.api_key = value;
        break;
    }
  }

  private async handleSave(): Promise<void> {
    await this.saveConfig();
  }

  private showError(message: string): void {
    const messageDiv = document.getElementById('config-message');
    if (messageDiv) {
      messageDiv.className = 'p-3 rounded-md text-sm bg-red-100 text-red-700';
      messageDiv.textContent = message;
      messageDiv.classList.remove('hidden');
      setTimeout(() => messageDiv.classList.add('hidden'), 5000);
    }
  }

  private showSuccess(message: string): void {
    const messageDiv = document.getElementById('config-message');
    if (messageDiv) {
      messageDiv.className = 'p-3 rounded-md text-sm bg-green-100 text-green-700';
      messageDiv.textContent = message;
      messageDiv.classList.remove('hidden');
      setTimeout(() => messageDiv.classList.add('hidden'), 3000);
    }
  }
}