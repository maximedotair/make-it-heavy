import sys
import argparse
import json
import asyncio
import time
import threading
import logging
from typing import AsyncGenerator, Optional
from pathlib import Path

from agent import OpenRouterAgent
from orchestrator import TaskOrchestrator

def cli_main():
    """Original CLI interface"""
    print("OpenRouter Agent with DuckDuckGo Search")
    print("Type 'quit', 'exit', or 'bye' to exit")
    print("-" * 50)
    
    try:
        agent = OpenRouterAgent()
        print("Agent initialized successfully!")
        print(f"Using model: {agent.config['openrouter']['model']}")
        print("Note: Make sure to set your OpenRouter API key in config.yaml")
        print("-" * 50)
    except Exception as e:
        print(f"Error initializing agent: {e}")
        print("Make sure you have:")
        print("1. Set your OpenRouter API key in config.yaml")
        print("2. Installed all dependencies with: pip install -r requirements.txt")
        return
    
    while True:
        try:
            user_input = input("\nUser: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye!")
                break
            
            if not user_input:
                print("Please enter a question or command.")
                continue
            
            print("Agent: Thinking...")
            response = agent.run(user_input)
            print(f"Agent: {response}")
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again or type 'quit' to exit.")

def web_main(port=8000):
    """Web interface using FastAPI"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel
        import yaml
        import uvicorn
    except ImportError as e:
        print(f"Missing dependencies for web mode: {e}")
        print("Install with: pip install fastapi uvicorn pydantic")
        return

    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("openrouter-web")

    # FastAPI Web Interface
    app = FastAPI(title="OpenRouter Agent Web Interface", version="1.0.0")

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pydantic models
    class ChatRequest(BaseModel):
        message: str
        use_orchestrator: Optional[bool] = False

    class ConfigUpdate(BaseModel):
        api_key: str
        base_url: str
        model: str
        temperature: Optional[float] = 0.7
        max_tokens: Optional[int] = 2000

    class ConfigResponse(BaseModel):
        api_key: str
        base_url: str
        model: str
        temperature: float
        max_tokens: int

    CONFIG_PATH = Path("config.yaml")

    def load_config():
        """Load configuration from config.yaml"""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            openrouter_config = config.get('openrouter', {})
            return {
                'api_key': openrouter_config.get('api_key', ''),
                'base_url': openrouter_config.get('base_url', ''),
                'model': openrouter_config.get('model', ''),
                'temperature': openrouter_config.get('temperature', 0.7),
                'max_tokens': openrouter_config.get('max_tokens', 2000)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")

    def save_config(config_data):
        """Save configuration to config.yaml"""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
            
            if 'openrouter' not in full_config:
                full_config['openrouter'] = {}
            
            full_config['openrouter'].update({
                'api_key': config_data['api_key'],
                'base_url': config_data['base_url'],
                'model': config_data['model'],
                'temperature': config_data['temperature'],
                'max_tokens': config_data['max_tokens']
            })
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(full_config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")

    @app.get("/")
    async def root():
        return {"message": "OpenRouter Agent Web Interface", "version": "1.0.0"}

    @app.get("/api/config", response_model=ConfigResponse)
    async def get_config():
        config = load_config()
        return ConfigResponse(**config)

    @app.post("/api/config")
    async def update_config(config_update: ConfigUpdate):
        try:
            config_data = config_update.dict()
            save_config(config_data)
            return {"message": "Configuration saved successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/stream")
    async def stream_chat(request: ChatRequest):
        """Endpoint pour le streaming des réponses"""
        logger.info(f"📨 New chat request - Message length: {len(request.message)} chars, Orchestrator: {request.use_orchestrator}")
        
        async def generate_stream() -> AsyncGenerator[str, None]:
            start_time = time.time()
            try:
                if request.use_orchestrator:
                    logger.info("🔄 Using orchestrator mode")
                    async for chunk in stream_orchestrator_response(request.message):
                        yield chunk
                else:
                    logger.info("🤖 Using single agent mode")
                    async for chunk in stream_agent_response(request.message):
                        yield chunk
                
                duration = time.time() - start_time
                logger.info(f"✅ Request completed in {duration:.2f}s")
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ Request failed after {duration:.2f}s: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    async def stream_agent_response(message: str) -> AsyncGenerator[str, None]:
        """Stream response from a single agent"""
        logger.info(f"🚀 Starting single agent processing")
        
        yield f"data: {json.dumps({'type': 'status', 'data': 'Processing...'})}\n\n"
        
        result_container = {"result": None, "error": None}
        tool_events = []
        
        def tool_callback(event):
            """Callback to capture tool usage events"""
            logger.info(f"🔍 Tool callback received: {event}")
            tool_events.append(event)
        
        def run_agent():
            try:
                logger.info("🔧 Initializing OpenRouter agent")
                agent = OpenRouterAgent(silent=True, tool_callback=tool_callback)
                logger.info("📤 Sending message to agent")
                result_container["result"] = agent.run(message)
                logger.info(f"📨 Agent response received - Length: {len(result_container['result']) if result_container['result'] else 0} chars")
            except Exception as e:
                logger.error(f"💥 Agent error: {str(e)}")
                result_container["error"] = str(e)
        
        agent_thread = threading.Thread(target=run_agent)
        agent_thread.start()
        
        timeout = 120  # 2 minutes
        start_time = time.time()
        last_tool_event_count = 0
        
        while agent_thread.is_alive() and (time.time() - start_time) < timeout:
            # Check for new tool events and stream them
            if len(tool_events) > last_tool_event_count:
                logger.info(f"🎯 Processing {len(tool_events) - last_tool_event_count} new tool events")
                for event in tool_events[last_tool_event_count:]:
                    try:
                        if event.get('type') == 'tool_start':
                            tool_info = f"🔧 Using {event.get('tool_name', 'unknown tool')}"
                            tool_args = event.get('tool_args', {})
                            if 'query' in tool_args:
                                tool_info += f" (searching: {tool_args['query'][:50]}...)"
                            elif 'expression' in tool_args:
                                tool_info += f" (calculating: {tool_args['expression']})"
                            elif 'path' in tool_args:
                                tool_info += f" (file: {tool_args['path']})"
                            
                            # Convertir la structure pour correspondre à l'attente du frontend
                            tool_event = {
                                'event': 'tool_start',
                                'tool_name': event.get('tool_name', 'unknown'),
                                'tool_args': event.get('tool_args', {})
                            }
                            
                            # Extraire les arguments spécifiques pour l'affichage
                            tool_args = event.get('tool_args', {})
                            if 'query' in tool_args:
                                tool_event['query'] = tool_args['query']
                            elif 'expression' in tool_args:
                                tool_event['expression'] = tool_args['expression']
                            elif 'path' in tool_args:
                                tool_event['filename'] = tool_args['path']
                            
                            tool_data = {
                                'type': 'tool_usage',
                                'data': tool_event
                            }
                            yield f"data: {json.dumps(tool_data)}\n\n"
                            logger.info(f"🚀 Streamed tool_usage event: {event.get('tool_name')}")
                        elif event.get('type') == 'tool_complete':
                            clear_data = {'type': 'clear_tool_usage'}
                            yield f"data: {json.dumps(clear_data)}\n\n"
                            logger.info(f"🚀 Streamed clear_tool_usage event")
                    except Exception as e:
                        logger.error(f"Error processing tool event: {e}, event: {event}")
                
                last_tool_event_count = len(tool_events)
            
            await asyncio.sleep(0.5)
        
        if agent_thread.is_alive():
            logger.warning("⏰ Agent timeout reached")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 2 minutes'})}\n\n"
            return
        
        agent_thread.join()
        
        # Clear status message
        yield f"data: {json.dumps({'type': 'clear_status'})}\n\n"
        
        if result_container["error"]:
            logger.error(f"🚫 Sending error response: {result_container['error']}")
            yield f"data: {json.dumps({'type': 'error', 'data': result_container['error']})}\n\n"
        elif result_container["result"]:
            response = result_container["result"]
            words = response.split()
            logger.info(f"📝 Streaming {len(words)} words")
            for i, word in enumerate(words):
                chunk = {
                    "type": "content",
                    "data": word + (" " if i < len(words) - 1 else "")
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.03)
        
        logger.info("🏁 Single agent streaming completed")
        yield "data: [DONE]\n\n"

    async def stream_orchestrator_response(message: str) -> AsyncGenerator[str, None]:
        """Stream response with multi-agent orchestrator"""
        logger.info(f"🎭 Starting orchestrator processing")
        
        yield f"data: {json.dumps({'type': 'status', 'data': 'Initializing multi-agent orchestrator...'})}\n\n"
        
        try:
            logger.info("🔧 Creating TaskOrchestrator instance")
            orchestrator = TaskOrchestrator(silent=True)
            logger.info(f"✅ Orchestrator initialized with {orchestrator.num_agents} agents")
        except Exception as e:
            logger.error(f"💥 Orchestrator initialization failed: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'data': f'Initialization error: {str(e)}'})}\n\n"
            return
        
        yield f"data: {json.dumps({'type': 'status', 'data': 'Decomposing task...'})}\n\n"
        
        try:
            logger.info("📋 Decomposing task into subtasks")
            subtasks = orchestrator.decompose_task(message, orchestrator.num_agents)
            logger.info(f"✂️ Task decomposed into {len(subtasks)} subtasks")
            yield f"data: {json.dumps({'type': 'status', 'data': f'Task decomposed into {len(subtasks)} subtasks'})}\n\n"
        except Exception as e:
            logger.error(f"💥 Task decomposition failed: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'data': f'Decomposition error: {str(e)}'})}\n\n"
            return
        
        # Initialize progress
        for i in range(orchestrator.num_agents):
            orchestrator.agent_progress[i] = "QUEUED"
            progress_data = {
                "type": "progress",
                "data": {
                    "agent_id": i + 1,
                    "status": "QUEUED",
                    "total_agents": orchestrator.num_agents
                }
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
        
        result_container = {"result": None, "error": None}
        
        tool_events = []
        
        def tool_callback(event):
            """Callback to capture tool usage events from orchestrator agents"""
            logger.info(f"🔍 Orchestrator tool callback received: {event}")
            tool_events.append(event)
        
        def run_orchestration():
            try:
                logger.info("🚀 Starting orchestration process")
                # Pass tool callback to orchestrator
                result_container["result"] = orchestrator.orchestrate(message, tool_callback=tool_callback)
                logger.info(f"📨 Orchestration completed - Result length: {len(result_container['result']) if result_container['result'] else 0} chars")
            except Exception as e:
                logger.error(f"💥 Orchestration error: {str(e)}")
                result_container["error"] = str(e)
        
        orchestration_thread = threading.Thread(target=run_orchestration)
        orchestration_thread.start()
        
        timeout = 300  # 5 minutes for multi-agents
        start_time = time.time()
        last_tool_event_count = 0
        
        while orchestration_thread.is_alive() and (time.time() - start_time) < timeout:
            # Stream progress updates
            progress = orchestrator.get_progress_status()
            for agent_id, status in progress.items():
                progress_data = {
                    "type": "progress",
                    "data": {
                        "agent_id": agent_id + 1,
                        "status": status,
                        "total_agents": orchestrator.num_agents
                    }
                }
                yield f"data: {json.dumps(progress_data)}\n\n"
            
            # Check for new tool events and stream them
            if len(tool_events) > last_tool_event_count:
                for event in tool_events[last_tool_event_count:]:
                    try:
                        if event.get('type') == 'tool_start':
                            tool_info = f"🔧 Agent using {event.get('tool_name', 'unknown tool')}"
                            tool_args = event.get('tool_args', {})
                            if 'query' in tool_args:
                                tool_info += f" (searching: {tool_args['query'][:50]}...)"
                            elif 'expression' in tool_args:
                                tool_info += f" (calculating: {tool_args['expression']})"
                            elif 'path' in tool_args:
                                tool_info += f" (file: {tool_args['path']})"
                            
                            # Convertir la structure pour correspondre à l'attente du frontend
                            tool_event = {
                                'event': 'tool_start',
                                'tool_name': event.get('tool_name', 'unknown'),
                                'tool_args': event.get('tool_args', {})
                            }
                            
                            # Extraire les arguments spécifiques pour l'affichage
                            tool_args = event.get('tool_args', {})
                            if 'query' in tool_args:
                                tool_event['query'] = tool_args['query']
                            elif 'expression' in tool_args:
                                tool_event['expression'] = tool_args['expression']
                            elif 'path' in tool_args:
                                tool_event['filename'] = tool_args['path']
                            
                            yield f"data: {json.dumps({'type': 'tool_usage', 'data': tool_event})}\n\n"
                            logger.info(f"🔧 Orchestrator tool used: {event.get('tool_name')} with args: {tool_args}")
                        elif event.get('type') == 'tool_complete':
                            yield f"data: {json.dumps({'type': 'clear_tool_usage'})}\n\n"
                    except Exception as e:
                        logger.error(f"Error processing orchestrator tool event: {e}, event: {event}")
                
                last_tool_event_count = len(tool_events)
            
            await asyncio.sleep(1.0)
        
        if orchestration_thread.is_alive():
            logger.warning("⏰ Orchestrator timeout reached")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 5 minutes'})}\n\n"
            return
        
        orchestration_thread.join()
        
        if result_container["error"]:
            logger.error(f"🚫 Sending orchestrator error: {result_container['error']}")
            yield f"data: {json.dumps({'type': 'error', 'data': result_container['error']})}\n\n"
        elif result_container["result"]:
            # Indiquer le début de la consolidation finale
            yield f"data: {json.dumps({'type': 'status', 'data': 'All agents completed! Consolidating results...'})}\n\n"
            await asyncio.sleep(0.5)  # Petite pause pour que l'utilisateur voie le message
            
            # Clear status message avant le streaming
            yield f"data: {json.dumps({'type': 'clear_status'})}\n\n"
            
            # Indiquer le début du streaming des résultats
            yield f"data: {json.dumps({'type': 'status', 'data': 'Delivering consolidated results...'})}\n\n"
            await asyncio.sleep(0.3)
            
            # Clear status message final avant le contenu
            yield f"data: {json.dumps({'type': 'clear_status'})}\n\n"
            
            response = result_container["result"]
            words = response.split()
            logger.info(f"📝 Streaming {len(words)} words from orchestrator result")
            for i, word in enumerate(words):
                chunk = {
                    "type": "content",
                    "data": word + (" " if i < len(words) - 1 else "")
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.02)
        
        logger.info("🏁 Orchestrator streaming completed")
        yield "data: [DONE]\n\n"

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "timestamp": time.time()}

    @app.get("/api/orchestrator/status")
    async def orchestrator_status():
        try:
            orchestrator = TaskOrchestrator(silent=True)
            return {
                "num_agents": orchestrator.num_agents,
                "aggregation_strategy": orchestrator.aggregation_strategy,
                "task_timeout": orchestrator.task_timeout
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Start the server
    print("🚀 Starting OpenRouter Agent Web Interface...")
    print(f"📱 Web interface available at: http://localhost:{port}")
    print("🔧 API documentation at: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)

def main():
    """Main entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(description="OpenRouter Agent")
    parser.add_argument("--web", action="store_true", help="Start web interface")
    parser.add_argument("--port", type=int, default=8000, help="Port for web interface")
    
    args = parser.parse_args()
    
    if args.web:
        web_main(args.port)
    else:
        cli_main()

if __name__ == "__main__":
    main()