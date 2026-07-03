"""
(Re)gera os vetores da BNCC a partir do snapshot versionado
(`data/bncc_v1.json`) para dentro do ChromaDB.

Principio IV/VII: os vetores sao **derivados nao-oficiais** do snapshot oficial.
O script degrada graciosamente: se o snapshot ou as libs de ML
(sentence-transformers, chromadb) estiverem ausentes, encerra com mensagem
clara e codigo de saida != 0 (sem stack trace ruidoso).

Uso:
    python scripts/generate_embeddings.py            # (re)indexa
    python scripts/generate_embeddings.py --reset    # zera a colecao antes
    python scripts/generate_embeddings.py --test     # testa buscas apos indexar
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Raiz do projeto no sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("generate_embeddings")


def _check_snapshot() -> bool:
    from app.core.config import settings

    data_path = Path(settings.BNCC_DATA_PATH)
    if not data_path.exists():
        logger.error("Snapshot da BNCC nao encontrado: %s", data_path)
        logger.error("Gere-o primeiro: python scripts/extract_bncc_data.py --validate")
        return False
    return True


async def _run(reset: bool, test: bool) -> int:
    from app.services.vector_store import VectorStoreService

    service = VectorStoreService()
    await service.initialize()

    if not service.available:
        logger.error(
            "Camada de IA indisponivel (embeddings/ChromaDB nao instalados ou "
            "falha de carga). Instale: pip install sentence-transformers chromadb"
        )
        return 1

    try:
        total = service.index_snapshot(reset=reset)
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao indexar: %s", exc)
        return 1

    logger.info("Indexacao concluida: %d documentos (derivados nao-oficiais).", total)

    if test:
        await _smoke_test(service)

    await service.cleanup()
    return 0


async def _smoke_test(service) -> None:
    queries = [
        "matematica fracoes quinto ano",
        "lingua portuguesa leitura",
        "ciencias meio ambiente",
    ]
    for q in queries:
        try:
            fontes = await service.search(q, k=3)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha no teste de busca '%s': %s", q, exc)
            continue
        logger.info("Query '%s' -> %d fontes", q, len(fontes))
        for f in fontes:
            logger.info("   %s (relevancia %.3f)", f["codigo"], f["relevancia"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera embeddings da BNCC.")
    parser.add_argument("--reset", action="store_true", help="Zera a colecao antes de indexar.")
    parser.add_argument("--test", action="store_true", help="Testa buscas apos indexar.")
    args = parser.parse_args()

    if not _check_snapshot():
        return 1

    try:
        return asyncio.run(_run(reset=args.reset, test=args.test))
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Interrompido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
