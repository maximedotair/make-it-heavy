from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yaml
import json
import asyncio
import time
import sys
import threading
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("openrouter-api")

# Ajouter le répertoire parent pour accéder aux modules existants
sys.path.append(str(Path(__file__).parent.parent))

# Importer les modules existants
from agent import OpenRouterAgent
from orchestrator import TaskOrchestrator

app = FastAPI(title="OpenRouter Agent API", version="1.0.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
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

# Chemin vers le fichier de configuration dans le répertoire parent
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config() -> Dict[str, Any]:
    """Charger la configuration depuis config.yaml"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Adapter la structure pour l'interface web
        openrouter_config = config.get('openrouter', {})
        return {
            'api_key': openrouter_config.get('api_key', ''),
            'base_url': openrouter_config.get('base_url', ''),
            'model': openrouter_config.get('model', ''),
            'temperature': openrouter_config.get('temperature', 0.7),
            'max_tokens': openrouter_config.get('max_tokens', 2000)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du chargement de la configuration: {str(e)}")

def save_config(config_data: Dict[str, Any]) -> None:
    """Sauvegarder la configuration dans config.yaml"""
    try:
        # Charger la config complète existante
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)
        
        # Mettre à jour seulement la section openrouter
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
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde de la configuration: {str(e)}")

@app.get("/")
async def root():
    return {"message": "OpenRouter Agent API", "version": "1.0.0"}

@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Obtenir la configuration actuelle"""
    config = load_config()
    return ConfigResponse(**config)

@app.post("/api/config")
async def update_config(config_update: ConfigUpdate):
    """Mettre à jour la configuration"""
    try:
        config_data = config_update.dict()
        save_config(config_data)
        return {"message": "Configuration mise à jour avec succès"}
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
    """Stream réponse d'un agent simple"""
    
    logger.info(f"🚀 Starting single agent processing")
    
    # Envoyer le message de début
    yield f"data: {json.dumps({'type': 'status', 'data': 'Processing...'})}\n\n"
    
    # Exécuter l'agent dans un thread séparé pour éviter de bloquer
    result_container = {"result": None, "error": None}
    
    def run_agent():
        try:
            logger.info(f"🔧 Initializing OpenRouter agent with config: {CONFIG_PATH}")
            logger.info(f"📁 Config path exists: {CONFIG_PATH.exists()}")
            agent = OpenRouterAgent(config_path=str(CONFIG_PATH.absolute()), silent=True)
            logger.info("📤 Sending message to agent")
            result_container["result"] = agent.run(message)
            logger.info(f"📨 Agent response received - Length: {len(result_container['result']) if result_container['result'] else 0} chars")
        except Exception as e:
            logger.error(f"💥 Agent error: {str(e)}")
            result_container["error"] = str(e)
    
    # Démarrer l'agent dans un thread
    agent_thread = threading.Thread(target=run_agent)
    agent_thread.start()
    
    # Attendre que l'agent termine avec timeout
    timeout = 120  # 2 minutes
    start_time = time.time()
    while agent_thread.is_alive() and (time.time() - start_time) < timeout:
        await asyncio.sleep(0.5)
    
    if agent_thread.is_alive():
        logger.warning("⏰ Agent timeout reached")
        yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 2 minutes'})}\n\n"
        return
    
    agent_thread.join()
    
    # Nettoyer le message de statut
    yield f"data: {json.dumps({'type': 'clear_status'})}\n\n"
    
    # Envoyer le résultat
    if result_container["error"]:
        logger.error(f"🚫 Sending error response: {result_container['error']}")
        yield f"data: {json.dumps({'type': 'error', 'data': result_container['error']})}\n\n"
    elif result_container["result"]:
        # Simuler le streaming en divisant la réponse
        response = result_container["result"]
        words = response.split()
        logger.info(f"📝 Streaming {len(words)} words")
        for i, word in enumerate(words):
            chunk = {
                "type": "content",
                "data": word + (" " if i < len(words) - 1 else "")
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.03)  # Simuler le délai de streaming
    
    logger.info("🏁 Single agent streaming completed")
    # Signal de fin
    yield "data: [DONE]\n\n"

async def stream_orchestrator_response(message: str) -> AsyncGenerator[str, None]:
    """Stream réponse avec orchestrateur multi-agents et progression"""
    
    logger.info(f"🎭 Starting orchestrator processing")
    
    # Initialiser l'orchestrateur
    yield f"data: {json.dumps({'type': 'status', 'data': 'Initializing multi-agent orchestrator...'})}\n\n"
    
    try:
        logger.info(f"🔧 Creating TaskOrchestrator instance with config: {CONFIG_PATH}")
        logger.info(f"📁 Config path exists: {CONFIG_PATH.exists()}")
        logger.info(f"📍 Absolute config path: {CONFIG_PATH.absolute()}")
        orchestrator = TaskOrchestrator(config_path=str(CONFIG_PATH.absolute()), silent=True)
        logger.info(f"✅ Orchestrator initialized with {orchestrator.num_agents} agents")
    except Exception as e:
        logger.error(f"💥 Orchestrator initialization failed: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'data': f'Initialization error: {str(e)}'})}\n\n"
        return
    
    # Décomposer la tâche
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
    
    # Initialiser la progression
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
    
    # Exécuter l'orchestration dans un thread séparé
    result_container = {"result": None, "error": None}
    
    def run_orchestration():
        try:
            logger.info("🚀 Starting orchestration process")
            result_container["result"] = orchestrator.orchestrate(message)
            logger.info(f"📨 Orchestration completed - Result length: {len(result_container['result']) if result_container['result'] else 0} chars")
        except Exception as e:
            logger.error(f"💥 Orchestration error: {str(e)}")
            result_container["error"] = str(e)
    
    # Démarrer l'orchestration
    orchestration_thread = threading.Thread(target=run_orchestration)
    orchestration_thread.start()
    
    # Surveiller la progression avec timeout
    timeout = 300  # 5 minutes pour multi-agents
    start_time = time.time()
    while orchestration_thread.is_alive() and (time.time() - start_time) < timeout:
        # Envoyer la progression de chaque agent
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
        
        await asyncio.sleep(1.0)
    
    if orchestration_thread.is_alive():
        logger.warning("⏰ Orchestrator timeout reached")
        yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 5 minutes'})}\n\n"
        return
    
    # Attendre que le thread se termine
    orchestration_thread.join()
    
    # Nettoyer le message de statut
    yield f"data: {json.dumps({'type': 'clear_status'})}\n\n"
    
    # Envoyer le résultat final
    if result_container["error"]:
        logger.error(f"🚫 Sending orchestrator error: {result_container['error']}")
        yield f"data: {json.dumps({'type': 'error', 'data': result_container['error']})}\n\n"
    elif result_container["result"]:
        # Envoyer le contenu final
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
    # Signal de fin
    yield "data: [DONE]\n\n"

@app.get("/api/health")
async def health_check():
    """Vérifier l'état de l'API"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/api/orchestrator/status")
async def orchestrator_status():
    """Obtenir des informations sur l'orchestrateur"""
    try:
        orchestrator = TaskOrchestrator(config_path=str(CONFIG_PATH), silent=True)
        return {
            "num_agents": orchestrator.num_agents,
            "aggregation_strategy": orchestrator.aggregation_strategy,
            "task_timeout": orchestrator.task_timeout
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)