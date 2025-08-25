from __future__ import annotations

import argparse
from typing import Dict, List, Tuple

from pathlib import Path

from src.config import settings
from src.graph.neo4j_client import Neo4jClient
from src.ingest.parser import collect_graph_data, DeveloperInfo, FunctionInfo, ModuleInfo


def _merge_modul(tx, module: ModuleInfo):
    tx.run(
        """
        MERGE (m:Modul {dosya_yolu: $dosya_yolu})
        ON CREATE SET m.dil = $dil
        ON MATCH SET m.dil = coalesce(m.dil, $dil)
        """,
        dosya_yolu=module.file_path,
        dil=module.language,
    )


def _merge_fonksiyon(tx, func: FunctionInfo):
    tx.run(
        """
        MERGE (f:Fonksiyon {id: $id})
        SET f.isim = $isim,
            f.parametreler = $parametreler,
            f.geri_donus_tipi = $geri_donus_tipi,
            f.dosya_yolu = $dosya_yolu,
            f.satir = $satir
        """,
        id=func.id,
        isim=func.name,
        parametreler=func.parameters,
        geri_donus_tipi=func.returns,
        dosya_yolu=func.file_path,
        satir=func.line,
    )


def _rel_icerir(tx, module: ModuleInfo, func: FunctionInfo):
    tx.run(
        """
        MATCH (m:Modul {dosya_yolu: $dosya_yolu}), (f:Fonksiyon {id: $id})
        MERGE (m)-[:ICERIR]->(f)
        """,
        dosya_yolu=module.file_path,
        id=func.id,
    )


def _merge_kutuphane(tx, name: str, version: str | None = None):
    tx.run(
        """
        MERGE (k:Kutuphane {isim: $isim})
        ON CREATE SET k.versiyon = $versiyon
        ON MATCH SET k.versiyon = coalesce(k.versiyon, $versiyon)
        """,
        isim=name,
        versiyon=version,
    )


def _rel_kullanir_modul(tx, module: ModuleInfo, lib_name: str):
    tx.run(
        """
        MATCH (m:Modul {dosya_yolu: $dosya_yolu}), (k:Kutuphane {isim: $isim})
        MERGE (m)-[:KULLANIR]->(k)
        """,
        dosya_yolu=module.file_path,
        isim=lib_name,
    )


def _merge_gelistirici(tx, dev: DeveloperInfo):
    tx.run(
        """
        MERGE (g:Gelistirici {email: $email})
        ON CREATE SET g.isim = $isim, g.team = $team
        ON MATCH SET g.isim = coalesce(g.isim, $isim), g.team = coalesce(g.team, $team)
        """,
        email=dev.email or dev.name or "unknown",
        isim=dev.name,
        team=dev.team,
    )


def _rel_yazdi_modul(tx, module: ModuleInfo, dev: DeveloperInfo):
    tx.run(
        """
        MATCH (g:Gelistirici {email: $email}), (m:Modul {dosya_yolu: $dosya_yolu})
        MERGE (g)-[:YAZDI]->(m)
        """,
        email=dev.email or dev.name or "unknown",
        dosya_yolu=module.file_path,
    )


def _rel_cagirir(tx, caller: FunctionInfo, callee_name: str):
    # naive: connect by name within same module
    tx.run(
        """
        MATCH (f1:Fonksiyon {id: $caller_id})
        MATCH (f2:Fonksiyon {isim: $callee_name, dosya_yolu: $dosya_yolu})
        MERGE (f1)-[:CAGIRIR]->(f2)
        """,
        caller_id=caller.id,
        callee_name=callee_name,
        dosya_yolu=caller.file_path,
    )


def ingest(root: Path, include_devs: bool = True) -> None:
    client = Neo4jClient(
        settings.NEO4J_URI or "bolt://localhost:7687",
        settings.NEO4J_USERNAME or "neo4j",
        settings.NEO4J_PASSWORD or "",
        database=settings.NEO4J_DATABASE,
    )
    client.ensure_constraints()

    modules, functions, libraries, developers_by_file = collect_graph_data(root, include_devs=include_devs)

    with client._driver.session(database=settings.NEO4J_DATABASE) as session:
        # nodes
        for module in modules.values():
            session.execute_write(_merge_modul, module)
        for func in functions:
            session.execute_write(_merge_fonksiyon, func)
        for lib in libraries:
            session.execute_write(_merge_kutuphane, lib, None)

        # relationships
        for module in modules.values():
            # ICERIR
            for func in [f for f in functions if f.file_path == module.file_path]:
                session.execute_write(_rel_icerir, module, func)
                # CAGIRIR by name
                for callee in func.calls:
                    session.execute_write(_rel_cagirir, func, callee)

            # KULLANIR
            for (lib_name, _lvl) in module.imported_libs:
                session.execute_write(_rel_kullanir_modul, module, lib_name)

            # YAZDI
            if include_devs:
                for dev in developers_by_file.get(module.file_path, []):
                    session.execute_write(_merge_gelistirici, dev)
                    session.execute_write(_rel_yazdi_modul, module, dev)

    client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest codebase into Neo4j graph")
    parser.add_argument("--root", type=str, required=True, help="Path to source code root")
    parser.add_argument("--include-dev", type=str, default="true", help="Use git blame to infer developers")
    args = parser.parse_args()

    include_devs = args.include_dev.lower() in ("1", "true", "yes", "on")
    ingest(Path(args.root), include_devs=include_devs)


if __name__ == "__main__":
    main()


