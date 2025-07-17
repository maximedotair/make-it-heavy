import './style.css';
import { ChatInterface } from './components/ChatInterface.js';
import { ConfigPanel } from './components/ConfigPanel.js';

class App {
  private chatInterface!: ChatInterface;
  private configPanel!: ConfigPanel;

  constructor() {
    this.initApp();
  }

  private initApp() {
    const app = document.getElementById('app');
    if (!app) {
      console.error('App container not found');
      return;
    }

    app.innerHTML = `
      <div class="min-h-screen bg-gray-50">
        <header class="bg-white shadow-sm border-b">
          <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center py-4">
              <h1 class="text-2xl font-bold text-gray-900">OpenRouter Agent</h1>
              <button 
                id="toggle-config"
                class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                ⚙️ Configuration
              </button>
            </div>
          </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="lg:col-span-2">
              <div class="bg-white rounded-lg shadow-lg h-[600px]">
                <div id="chat-container" class="h-full"></div>
              </div>
            </div>
            
            <div class="lg:col-span-1">
              <div id="config-container" class="hidden">
                <div id="config-panel"></div>
              </div>
            </div>
          </div>
        </main>
      </div>
    `;

    this.initializeComponents();
    this.setupEventListeners();
  }

  private initializeComponents() {
    try {
      this.chatInterface = new ChatInterface('chat-container');
      this.configPanel = new ConfigPanel('config-panel');
    } catch (error) {
      console.error('Error during initialization:', error);
    }
  }

  private setupEventListeners() {
    const toggleButton = document.getElementById('toggle-config');
    const configContainer = document.getElementById('config-container');

    if (toggleButton && configContainer) {
      toggleButton.addEventListener('click', () => {
        const isHidden = configContainer.classList.contains('hidden');
        configContainer.classList.toggle('hidden');
        toggleButton.textContent = isHidden ? '✕ Close' : '⚙️ Configuration';
      });
    }
  }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
  new App();
});