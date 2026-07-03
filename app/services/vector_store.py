"""
Servico de armazenamento vetorial e busca semantica (US4 / P4).

Degradacao graciosa (Principio VII / research.md 9): as dependencias pesadas
(ChromaDB + sentence-transformers) sao importadas **preguicosamente** dentro dos
metodos, protegidas por try/except. Se indisponiveis (nao instaladas, sem
snapshot, falha de carga), o servico marca `self.available = False` em vez de
derrubar a aplicacao. Os endpoints deterministicos NAO dependem deste servico.

Vetores e demais derivados sao **nao-oficiais** (FR-004/FR-017): o texto oficial
vive apenas no snapshot versionado `data/bncc_v1.json`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "bncc_documents"


def _coerce_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitiza metadados para o ChromaDB, que aceita apenas str/int/float/bool.

    Campos presentes-porem-None no snapshot (ex.: `etapa`, `area_conhecimento`)
    viram string vazia. `dict.get(k, "")` nao basta: seu default so vale quando a
    chave esta ausente, nao quando o valor e None. Determinismo/fidelidade
    (Principio IV): a coercao e estavel e nao altera o texto oficial.
    """
    return {k: ("" if v is None else v) for k, v in meta.items()}


class VectorStoreService:
    """
    Recuperacao semantica sobre o snapshot da BNCC.

    Ciclo de vida (chamado pelo lifespan em `app/main.py`):
        service = VectorStoreService()
        await service.initialize()   # nunca levanta; seta self.available
        ...
        await service.cleanup()
    """

    def __init__(self) -> None:
        self.available: bool = False
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.bncc_data: dict[str, Any] = {
            "habilidades": [],
            "competencias_especificas": [],
            "competencias_gerais": [],
        }
        self._reason: str | None = None

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    async def initialize(self) -> None:
        """
        Inicializa o modelo de embeddings + ChromaDB e carrega o snapshot.

        NUNCA levanta excecao: qualquer falha marca `available = False` e deixa
        um motivo em `self._reason`. Isso isola a camada de IA (Principio VII).
        """
        try:
            self._load_snapshot()  # dados sao uteis mesmo sem ML (fallback)

            # Imports pesados adiados: se ausentes, degrada.
            from sentence_transformers import SentenceTransformer  # noqa: WPS433

            logger.info("Carregando modelo de embeddings: %s", settings.EMBEDDING_MODEL)
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

            self._init_chromadb()

            count = self.collection.count() if self.collection is not None else 0
            if count == 0:
                logger.info(
                    "Colecao vetorial vazia. Rode scripts/generate_embeddings.py "
                    "para popular. Busca semantica ficara sem correspondencias."
                )
            else:
                logger.info("Colecao vetorial com %d documentos.", count)

            self.available = True
            self._reason = None
        except Exception as exc:  # noqa: BLE001 - degradacao graciosa deliberada
            self.available = False
            self._reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Camada de IA (vector store) indisponivel - degradando: %s",
                self._reason,
            )

    def _load_snapshot(self) -> None:
        """Carrega o snapshot versionado da BNCC (read-only)."""
        data_path = Path(settings.BNCC_DATA_PATH)
        if not data_path.exists():
            logger.warning("Snapshot da BNCC ausente em %s.", data_path)
            return
        with open(data_path, encoding="utf-8") as fh:
            self.bncc_data = json.load(fh)
        logger.info(
            "Snapshot carregado: %d habilidades.",
            len(self.bncc_data.get("habilidades", [])),
        )

    def _init_chromadb(self) -> None:
        """Inicializa o cliente ChromaDB persistente (import adiado)."""
        import chromadb  # noqa: WPS433
        from chromadb.config import Settings as ChromaSettings  # noqa: WPS433

        data_dir = Path(settings.CHROMADB_PATH)
        data_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(data_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            # `hnsw:space=cosine`: search() calcula `similarity = 1 - distance`,
            # valido apenas para distancia coseno. Sem isto o ChromaDB usa L2
            # (padrao) e a similaridade fica incorreta (nada passa no limiar).
            metadata={
                "description": "BNCC habilidades e competencias (derivado nao-oficial)",
                "hnsw:space": "cosine",
            },
        )

    async def cleanup(self) -> None:
        """Libera recursos (ChromaDB nao exige teardown explicito)."""
        self.available = False
        logger.info("Vector store cleanup concluido.")

    # ------------------------------------------------------------------ #
    # Busca
    # ------------------------------------------------------------------ #
    async def search(
        self,
        query: str,
        k: int = 5,
        similarity_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Busca semantica por similaridade coseno.

        Aplica o limiar `settings.SIMILARITY_THRESHOLD` (FR-017): candidatos
        abaixo do limiar NAO sao retornados (nao sao oficiais). Devolve uma lista
        de dicts: {codigo, tipo, relevancia, titulo, descricao}.

        Levanta `RuntimeError` se o servico estiver indisponivel (para que o
        `ai_service` mapeie para 503). Retorna [] quando disponivel mas sem
        correspondencia confiavel.
        """
        if not self.available or self.collection is None or self.embedding_model is None:
            raise RuntimeError(self._reason or "Vector store indisponivel (embeddings/ChromaDB).")

        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.SIMILARITY_THRESHOLD
        )
        n_results = max(1, min(k, settings.MAX_SEARCH_RESULTS))

        query_embedding = self.embedding_model.encode([query])
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        fontes: list[dict[str, Any]] = []
        ids = results.get("ids") or [[]]
        if ids and ids[0]:
            for i, _doc_id in enumerate(ids[0]):
                distance = results["distances"][0][i]
                similarity = 1.0 - float(distance)  # ChromaDB usa distancia coseno
                if similarity < threshold:
                    continue
                metadata = results["metadatas"][0][i] or {}
                document = (results.get("documents") or [[None]])[0][i]
                fontes.append(
                    {
                        "codigo": metadata.get("codigo", ""),
                        "tipo": metadata.get("tipo", "habilidade"),
                        "relevancia": round(similarity, 3),
                        "titulo": self._title(metadata),
                        "descricao": document or "",
                    }
                )

        logger.info("Busca '%s' -> %d fontes acima do limiar.", query, len(fontes))
        return fontes

    def get_document_by_codigo(self, codigo: str) -> dict[str, Any] | None:
        """Recupera o documento oficial completo do snapshot pelo codigo."""
        for key in ("habilidades", "competencias_especificas", "competencias_gerais"):
            for doc in self.bncc_data.get(key, []):
                if isinstance(doc, dict) and doc.get("codigo") == codigo:
                    return doc
        return None

    @staticmethod
    def _title(metadata: dict[str, Any]) -> str:
        codigo = metadata.get("codigo", "")
        tipo = metadata.get("tipo", "")
        componente = str(metadata.get("componente", "")).replace("_", " ").title()
        if tipo == "habilidade" and componente:
            return f"Habilidade {codigo} - {componente}"
        if tipo == "competencia_especifica":
            area = str(metadata.get("area_conhecimento", "")).replace("_", " ").title()
            return f"Competencia Especifica {codigo} - {area}".strip(" -")
        return codigo

    # ------------------------------------------------------------------ #
    # Indexacao (usada por scripts/generate_embeddings.py)
    # ------------------------------------------------------------------ #
    def index_snapshot(self, *, reset: bool = False) -> int:
        """
        (Re)indexa o snapshot no ChromaDB. Requer libs de ML disponiveis e
        `initialize()` bem-sucedido. Retorna o numero de documentos indexados.
        """
        if not self.available or self.collection is None or self.embedding_model is None:
            raise RuntimeError(self._reason or "Vector store indisponivel (embeddings/ChromaDB).")

        if reset and self.client is not None:
            try:
                self.client.delete_collection(COLLECTION_NAME)
            except Exception:  # noqa: BLE001 - colecao pode nao existir
                pass
            self._init_chromadb()

        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        ids: list[str] = []

        for hab in self.bncc_data.get("habilidades", []):
            text = f"{hab['codigo']}: {hab['descricao']}"
            objetos = hab.get("objetos_conhecimento") or []
            if objetos:
                text += " Objetos de conhecimento: " + ", ".join(objetos)
            documents.append(text)
            metadatas.append(
                _coerce_meta(
                    {
                        "tipo": "habilidade",
                        "codigo": hab["codigo"],
                        "etapa": hab.get("etapa", ""),
                        "area_conhecimento": hab.get("area_conhecimento", ""),
                        "componente": hab.get("componente", ""),
                        "oficial": False,
                    }
                )
            )
            ids.append(f"hab_{hab['codigo']}")

        for comp in self.bncc_data.get("competencias_especificas", []):
            documents.append(f"{comp['codigo']}: {comp['descricao']}")
            metadatas.append(
                _coerce_meta(
                    {
                        "tipo": "competencia_especifica",
                        "codigo": comp["codigo"],
                        "etapa": comp.get("etapa", ""),
                        "area_conhecimento": comp.get("area_conhecimento", ""),
                        "componente": comp.get("componente", ""),
                        "oficial": False,
                    }
                )
            )
            ids.append(f"comp_{comp['codigo']}")

        if not documents:
            logger.warning("Nenhum documento no snapshot para indexar.")
            return 0

        embeddings = self.embedding_model.encode(documents)
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings.tolist(),
            ids=ids,
        )
        logger.info("Indexados %d documentos (derivados nao-oficiais).", len(documents))
        return len(documents)


# --------------------------------------------------------------------------- #
# Singleton de modulo (compat.: app.main usa VectorStoreService() diretamente)
# --------------------------------------------------------------------------- #
_vector_service: VectorStoreService | None = None


async def get_vector_service() -> VectorStoreService:
    """Devolve (criando/iniciando sob demanda) a instancia global do servico."""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
        await _vector_service.initialize()
    return _vector_service
