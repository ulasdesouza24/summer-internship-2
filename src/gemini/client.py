from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from src.gemini.service import ask


SYSTEM_PROMPT = (
    "Sen, bir yazılım projesinin kod tabanı hakkında uzman bir asistansın. "
    "Sana sorulan soruları yanıtlamak için elinde bulunan execute_cypher_query aracını kullanarak "
    "Neo4j bilgi grafiğini sorgulamalısın. Kullanıcının sorusunu analiz et, uygun Cypher sorgusunu oluştur "
    "ve bu aracı çağırarak sonucu elde et. Şema düğümleri: Gelistirici, Modul, Fonksiyon, Kutuphane. "
    "İlişkiler: YAZDI, ICERIR, CAGIRIR, KULLANIR. Sadece gerekli alanları döndür." 
)


def build_tool_schema(server_url: str) -> Dict[str, Any]:
    # Gemini function calling via tools: provide a tool with one function
    return {
        "function_declarations": [
            {
                "name": "execute_cypher_query",
                "description": "Cypher sorgusunu MCP köprüsüne gönderir ve sonucu döndürür",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Cypher query"},
                    },
                    "required": ["query"],
                },
            }
        ]
    }


def run_question(question: str, server_url: str) -> None:
    print(ask(question, server_url))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question to the Gemini graph assistant")
    parser.add_argument("--question", type=str, required=True)
    parser.add_argument("--server", type=str, default="http://localhost:8000")
    args = parser.parse_args()
    run_question(args.question, args.server)


if __name__ == "__main__":
    main()


