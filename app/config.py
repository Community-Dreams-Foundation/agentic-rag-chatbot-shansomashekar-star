from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_json_model: str = "mistral:7b"
    ollama_embed_model: str = "nomic-embed-text"

    # Retrieval
    hyde_enabled: bool = True
    retrieval_k: int = 6
    retrieval_fetch_k: int = 20
    ensemble_bm25_weight: float = 0.35
    ensemble_faiss_weight: float = 0.65

    # Chunking
    parent_chunk_size: int = 1500
    parent_chunk_overlap: int = 100
    child_chunk_size: int = 300
    child_chunk_overlap: int = 30

    # Memory
    memory_confidence_threshold: float = 0.80

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 168  # 7 days

    # Redis (optional)
    redis_url: str = ""

    # DB
    db_path: str = "data/ragbot.db"

    # Limits
    max_upload_mb: int = 10
    supported_types: str = ".pdf,.txt,.md,.html,.htm"

    # CI
    sanity_mock: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
