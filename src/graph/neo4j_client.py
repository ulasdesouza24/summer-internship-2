from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, basic_auth


WRITE_TOKENS = re.compile(r"\\b(CREATE|MERGE|DELETE|SET|DROP|LOAD\\s+CSV|CALL\\s+dbms|CALL\\s+db\\.)\\b", re.IGNORECASE)


class Neo4jClient:
    def __init__(self, uri: str, username: str, password: str, database: Optional[str] = None) -> None:
        self._driver = GraphDatabase.driver(uri, auth=basic_auth(username, password))
        self._database = database

    def close(self) -> None:
        self._driver.close()

    def run_query(self, query: str, params: Optional[Dict[str, Any]] = None, *, readonly: bool = False) -> List[Dict[str, Any]]:
        if readonly and WRITE_TOKENS.search(query or ""):
            raise ValueError("Write operations are not allowed in read-only mode.")

        def _work(tx):
            return list(tx.run(query, params or {}).data())

        with self._driver.session(database=self._database) as session:
            if readonly:
                return session.execute_read(_work)
            return session.execute_write(_work)

    def ensure_constraints(self) -> None:
        statements = [
            "CREATE CONSTRAINT modul_dosya_yolu_unique IF NOT EXISTS FOR (m:Modul) REQUIRE m.dosya_yolu IS UNIQUE",
            "CREATE CONSTRAINT fonksiyon_id_unique IF NOT EXISTS FOR (f:Fonksiyon) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT gelistirici_email_unique IF NOT EXISTS FOR (g:Gelistirici) REQUIRE g.email IS UNIQUE",
            "CREATE CONSTRAINT kutuphane_isim_unique IF NOT EXISTS FOR (k:Kutuphane) REQUIRE k.isim IS UNIQUE",
        ]
        with self._driver.session(database=self._database) as session:
            for stmt in statements:
                session.execute_write(lambda tx, q=stmt: tx.run(q))


