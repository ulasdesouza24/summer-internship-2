from __future__ import annotations

import json
from typing import Any, Dict, List

import google.generativeai as genai
import httpx

from src.config import settings


SYSTEM_PROMPT = (
    "Sen, bir yazılım projesinin kod tabanı hakkında uzman bir asistansın. "
    "Elindeki tek aracın execute_cypher_query olduğunu ve Neo4j bilgi grafiğini Cypher ile sorgulayacağını unutma. "
    "Şema detayları (etiketler ve alan adları KESİN olarak bunlardır): "
    "Düğümler: Gelistirici(isim,email,team), Modul(dosya_yolu,dil), Fonksiyon(id,isim,parametreler,geri_donus_tipi,satir,dosya_yolu), Kutuphane(isim,versiyon). "
    "İlişkiler: YAZDI(Gelistirici->Modul), ICERIR(Modul->Fonksiyon), CAGIRIR(Fonksiyon->Fonksiyon), KULLANIR(Modul->Kutuphane). "
    "ÖNEMLİ: 'dosya_adi' alanı YOKTUR, her zaman 'dosya_yolu' kullan. Başlık/son ekle dosya ararken EŞİTLEME kullanma; dosya adı verilirse ENDS WITH ile eşle. "
    "Örnekler: "
    "1) Belirli bir dosya adı: MATCH (m:Modul) WHERE m.dosya_yolu ENDS WITH 'auth.py' MATCH (g:Gelistirici)-[:YAZDI]->(m) RETURN g.isim, g.email. "
    "2) Modül sayısı: MATCH (m:Modul) RETURN count(m) AS modul_sayisi. "
    "3) Kütüphaneler: MATCH (m:Modul)-[:KULLANIR]->(k:Kutuphane) RETURN k.isim, count(*) AS kullanilma. "
    "Sadece gerekli alanları döndür ve mümkünse kısa yanıt ver."
)


def _build_tool_schema() -> Dict[str, Any]:
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


def _call_bridge(server_url: str, query: str) -> List[Dict[str, Any]]:
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{server_url}/execute_cypher_query", json={"query": query})
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


def ask(question: str, server_url: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=settings.GEMINI_API_KEY)

    def tool_handler(name: str, arguments: Dict[str, Any]):
        if name != "execute_cypher_query":
            return {"error": f"Unknown tool {name}"}
        query = arguments.get("query", "")
        # Guard: common misnaming fix
        query = query.replace("dosya_adi", "dosya_yolu")
        results = _call_bridge(server_url, query)
        return {"results": results}

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        tools=[_build_tool_schema()],
        system_instruction=SYSTEM_PROMPT,
    )

    chat = model.start_chat(enable_automatic_function_calling=True)
    # Newer SDKs handle function calling automatically when enabled; no explicit tool_config needed
    response = chat.send_message(question)

    while True:
        made_call = False
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if getattr(part, "function_call", None):
                    fn = part.function_call
                    name = fn.name
                    args = {k: v for k, v in fn.args.items()} if hasattr(fn, "args") else {}
                    # Pass a JSON object (dict), not a JSON string
                    tool_result = genai.protos.FunctionResponse(name=name, response=tool_handler(name, args))
                    response = chat.send_message(tool_result)
                    made_call = True
                    break
            if made_call:
                break
        if not made_call:
            break

    return response.text or ""


