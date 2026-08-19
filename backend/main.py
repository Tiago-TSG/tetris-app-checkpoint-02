import os
import json
import base64
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sophisticated Tetris Backend")

# Caminho para arquivo de scores (usado como fallback local)
SCORES_FILE = os.getenv("SCORES_FILE_PATH", "scores.json")
COLLECTION_NAME = "scores"
TOPIC_NAME = "scores-topic"

class ScoreEntry(BaseModel):
    name: str = Field(..., min_length=1, max_length=15)
    score: int = Field(..., ge=0)
    level: int = Field(..., ge=1)
    lines: int = Field(..., ge=0)

class PubSubPushPayload(BaseModel):
    message: dict
    subscription: str

# Scores padrão para inicializar o placar com estilo arcade retro
DEFAULT_SCORES = [
    {"name": "NEON_MASTER", "score": 100000, "level": 10, "lines": 100},
    {"name": "ARCADE_PRO", "score": 75000, "level": 8, "lines": 80},
    {"name": "RETRO_CHAMP", "score": 50000, "level": 5, "lines": 50},
    {"name": "TETRIS_FAN", "score": 25000, "level": 3, "lines": 30},
    {"name": "NEWBIE", "score": 5000, "level": 1, "lines": 10}
]

# Inicializa o Firestore de forma segura
db = None
try:
    # Se houver um emulador rodando ou se estiver na nuvem (Cloud Run/GCP),
    # o SDK do Google Cloud lida com as credenciais nativamente.
    # Usamos None como padrão para que o SDK autodetecte o ID do projeto atual na nuvem.
    from google.cloud import firestore
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    db = firestore.Client(project=project_id)
    logger.info(f"Firestore client successfully initialized with project: {db.project}")
except Exception as e:
    logger.warning(f"Could not initialize Firestore Client: {e}. Falling back to local JSON storage.")
    db = None

# Inicializa o Pub/Sub de forma segura (Publisher)
publisher = None
topic_path = None
try:
    from google.cloud import pubsub_v1
    pub_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    publisher = pubsub_v1.PublisherClient()
    
    # Se conseguirmos obter o projeto (seja da env ou resolvido pelo cliente)
    if pub_project_id or getattr(publisher, "project", None):
        resolved_project = pub_project_id or publisher.project
        topic_path = publisher.topic_path(resolved_project, TOPIC_NAME)
        logger.info(f"Pub/Sub Publisher client successfully initialized. Topic path: {topic_path}")
    else:
        logger.warning("Could not auto-detect GCP project for Pub/Sub. Falling back to direct database writes.")
        publisher = None
except Exception as e:
    logger.warning(f"Could not initialize Pub/Sub Publisher Client: {e}. Falling back to direct database writes.")
    publisher = None

def load_scores_local() -> List[Dict[str, Any]]:
    if not os.path.exists(SCORES_FILE):
        logger.info("Scores file not found. Pre-populating with default scores.")
        save_scores_local(DEFAULT_SCORES)
        return DEFAULT_SCORES
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading scores file: {e}. Returning default scores.")
        return DEFAULT_SCORES

def save_scores_local(scores: List[Dict[str, Any]]) -> None:
    try:
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving scores file: {e}")

def populate_default_scores_firestore() -> None:
    if not db:
        return
    try:
        col_ref = db.collection(COLLECTION_NAME)
        batch = db.batch()
        for entry in DEFAULT_SCORES:
            doc_ref = col_ref.document()
            batch.set(doc_ref, entry)
        batch.commit()
        logger.info("Successfully populated Firestore with default retro scores.")
    except Exception as e:
        logger.error(f"Failed to populate default scores in Firestore: {e}")

def load_scores_from_firestore() -> List[Dict[str, Any]]:
    if db is None:
        return load_scores_local()
    try:
        col_ref = db.collection(COLLECTION_NAME)
        # Buscar os top 10 ordenados por pontuação decrescente
        query = col_ref.order_by("score", direction=firestore.Query.DESCENDING).limit(10)
        docs = list(query.stream())
        
        if not docs:
            logger.info("Firestore collection empty. Pre-populating with default scores.")
            populate_default_scores_firestore()
            docs = list(query.stream())
            
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Error loading scores from Firestore: {e}. Falling back to local file.")
        return load_scores_local()

def save_score_to_firestore(entry: Dict[str, Any]) -> None:
    if db is None:
        # Se estiver no modo local, adiciona o score na lista local e salva
        local_scores = load_scores_local()
        local_scores.append(entry)
        local_scores = sorted(local_scores, key=lambda x: x["score"], reverse=True)[:10]
        save_scores_local(local_scores)
        return
    try:
        col_ref = db.collection(COLLECTION_NAME)
        col_ref.add(entry)
        logger.info(f"Score for {entry['name']} successfully saved to Firestore.")
    except Exception as e:
        logger.error(f"Error saving score to Firestore: {e}. Saving to local fallback.")
        # Em caso de erro temporário no Firestore, salva local também
        try:
            local_scores = load_scores_local()
            local_scores.append(entry)
            local_scores = sorted(local_scores, key=lambda x: x["score"], reverse=True)[:10]
            save_scores_local(local_scores)
        except Exception as local_err:
            logger.error(f"Failed to save to local fallback: {local_err}")

def publish_score_to_pubsub(entry: Dict[str, Any]) -> bool:
    if publisher is None or topic_path is None:
        logger.info("Pub/Sub client not active. Fallback: direct write to Firestore/local.")
        save_score_to_firestore(entry)
        return False
    try:
        # Serializar dicionário para string JSON e codificar em bytes
        data_bytes = json.dumps(entry).encode("utf-8")
        # Publicar no Pub/Sub
        future = publisher.publish(topic_path, data_bytes)
        message_id = future.result()
        logger.info(f"Score for {entry['name']} successfully published to Pub/Sub. Message ID: {message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to Pub/Sub: {e}. Fallback: direct write.")
        save_score_to_firestore(entry)
        return False

@app.get("/api/scores", response_model=List[Dict[str, Any]])
def get_scores():
    """Recupera os 10 melhores placares."""
    scores = load_scores_from_firestore()
    # Garante a ordenação decrescente e corta nos top 10
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:10]
    return scores

@app.post("/api/scores", response_model=List[Dict[str, Any]])
def add_score(entry: ScoreEntry):
    """Adiciona um novo placar. Publica no Pub/Sub de forma assíncrona se disponível."""
    logger.info(f"Adding score: {entry.name} - {entry.score}")
    entry_dict = entry.model_dump()
    publish_score_to_pubsub(entry_dict)
    return get_scores()

@app.post("/api/internal/scores-worker")
def pubsub_push_receiver(payload: PubSubPushPayload):
    """Gatilho Push do Pub/Sub que recebe mensagens assíncronas e grava no Firestore."""
    try:
        # Extrair dados da mensagem
        message_data = payload.message.get("data")
        if not message_data:
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub message: missing 'data'")
            
        # Decodificar de base64 para string UTF-8
        decoded_bytes = base64.b64decode(message_data)
        decoded_str = decoded_bytes.decode("utf-8")
        
        # Converter a string em dicionário JSON
        entry_dict = json.loads(decoded_str)
        logger.info(f"Pub/Sub Push received message: {entry_dict}")
        
        # Validar dados usando o modelo de entrada
        validated_entry = ScoreEntry(**entry_dict)
        
        # Gravar no Firestore (ou fallback local se db for None)
        save_score_to_firestore(validated_entry.model_dump())
        
        return {"status": "success", "message": "Score successfully persisted via Pub/Sub"}
    except Exception as e:
        logger.error(f"Error processing Pub/Sub Push message: {e}")
        # Retorna erro 500 para o Pub/Sub saber que deve tentar novamente (retry)
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

# Montagem dos arquivos estáticos do frontend.
# Criamos a pasta estática se não existir para evitar erros ao iniciar o FastAPI
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
