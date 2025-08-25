import os
from dotenv import load_dotenv


load_dotenv()


def _get_env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


class Settings:
    # Neo4j
    NEO4J_URI: str | None = _get_env_str("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str | None = _get_env_str("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str | None = _get_env_str("NEO4J_PASSWORD", "tyFMUlet-VQCED7akjYElNqgy5RAd4XJmpxElg-MkTU")
    NEO4J_DATABASE: str | None = _get_env_str("NEO4J_DATABASE", "neo4j")

    # Bridge server (MCP-like)
    MCP_SERVER_HOST: str | None = _get_env_str("MCP_SERVER_HOST", "0.0.0.0")
    MCP_SERVER_PORT: int = int(_get_env_str("MCP_SERVER_PORT", "8000"))
    MCP_READ_ONLY: bool = _get_env_str("MCP_READ_ONLY", "true").lower() in ("1", "true", "yes", "on")

    # Gemini
    GEMINI_API_KEY: str | None = _get_env_str("GEMINI_API_KEY", None)


settings = Settings()


