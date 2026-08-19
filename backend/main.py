import os
import json
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sophisticated Tetris Backend")

# Caminho para arquivo de scores
SCORES_FILE = os.getenv("SCORES_FILE_PATH", "scores.json")

class ScoreEntry(BaseModel):
    name: str = Field(..., min_length=1, max_length=15)
    score: int = Field(..., ge=0)
    level: int = Field(..., ge=1)
    lines: int = Field(..., ge=0)

# Scores padrão para inicializar o placar com estilo arcade retro
DEFAULT_SCORES = [
    {"name": "NEON_MASTER", "score": 100000, "level": 10, "lines": 100},
    {"name": "ARCADE_PRO", "score": 75000, "level": 8, "lines": 80},
    {"name": "RETRO_CHAMP", "score": 50000, "level": 5, "lines": 50},
    {"name": "TETRIS_FAN", "score": 25000, "level": 3, "lines": 30},
    {"name": "NEWBIE", "score": 5000, "level": 1, "lines": 10}
]

def load_scores() -> List[Dict[str, Any]]:
    if not os.path.exists(SCORES_FILE):
        logger.info("Scores file not found. Pre-populating with default scores.")
        save_scores(DEFAULT_SCORES)
        return DEFAULT_SCORES
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading scores file: {e}. Returning default scores.")
        return DEFAULT_SCORES

def save_scores(scores: List[Dict[str, Any]]) -> None:
    try:
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving scores file: {e}")

@app.get("/api/scores", response_model=List[Dict[str, Any]])
def get_scores():
    """Recupera os 10 melhores placares."""
    scores = load_scores()
    # Ordenar por garantia e cortar nos top 10
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:10]
    return scores

@app.post("/api/scores", response_model=List[Dict[str, Any]])
def add_score(entry: ScoreEntry):
    """Adiciona um novo placar e retorna o top 10 atualizado."""
    logger.info(f"Adding score: {entry.name} - {entry.score}")
    scores = load_scores()
    
    # Adiciona o novo registro
    scores.append(entry.model_dump())
    
    # Ordena decrescente e filtra os top 10
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:10]
    
    # Grava no JSON
    save_scores(scores)
    
    return scores

# Montagem dos arquivos estáticos do frontend.
# Criamos a pasta estática se não existir para evitar erros ao iniciar o FastAPI
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
