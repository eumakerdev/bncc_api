"""
Vector Store Service for semantic search and embeddings
"""

import logging
import asyncio
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
import numpy as np

from app.core.config import settings
from app.models.bncc import Habilidade, CompetenciaEspecifica, DocumentoFonte

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector storage and semantic search"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.bncc_data = None
        
    async def initialize(self):
        """Initialize the vector store service"""
        try:
            # Initialize embedding model
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            
            # Initialize ChromaDB
            await self._initialize_chromadb()
            
            # Load BNCC data
            await self._load_bncc_data()
            
            # Create embeddings if collection is empty
            if self.collection.count() == 0:
                logger.info("Creating initial embeddings...")
                await self._create_embeddings()
            else:
                logger.info(f"Vector store already contains {self.collection.count()} documents")
                
        except Exception as e:
            logger.error(f"Error initializing vector store service: {e}")
            raise
    
    async def _initialize_chromadb(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Create data directory if it doesn't exist
            data_dir = Path(settings.CHROMADB_PATH)
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=str(data_dir),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="bncc_documents",
                metadata={"description": "BNCC habilidades e competências"}
            )
            
            logger.info("ChromaDB initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            raise
    
    async def _load_bncc_data(self):
        """Load BNCC data from JSON file"""
        try:
            data_path = Path(settings.BNCC_DATA_PATH)
            if not data_path.exists():
                logger.warning(f"BNCC data file not found at {data_path}")
                self.bncc_data = {"habilidades": [], "competencias_especificas": []}
                return
            
            with open(data_path, 'r', encoding='utf-8') as f:
                self.bncc_data = json.load(f)
            
            logger.info(f"Loaded BNCC data: {len(self.bncc_data.get('habilidades', []))} habilidades, "
                       f"{len(self.bncc_data.get('competencias_especificas', []))} competências específicas")
                       
        except Exception as e:
            logger.error(f"Error loading BNCC data: {e}")
            self.bncc_data = {"habilidades": [], "competencias_especificas": []}
    
    async def _create_embeddings(self):
        """Create embeddings for all BNCC documents"""
        try:
            documents = []
            metadatas = []
            ids = []
            
            # Process habilidades
            for habilidade in self.bncc_data.get('habilidades', []):
                doc_text = f"{habilidade['codigo']}: {habilidade['descricao']}"
                if habilidade.get('objetos_conhecimento'):
                    doc_text += f" Objetos de conhecimento: {', '.join(habilidade['objetos_conhecimento'])}"
                
                documents.append(doc_text)
                metadatas.append({
                    "tipo": "habilidade",
                    "codigo": habilidade['codigo'],
                    "etapa": habilidade['etapa'],
                    "area_conhecimento": habilidade['area_conhecimento'],
                    "componente": habilidade['componente'],
                    "anos": json.dumps(habilidade.get('anos', [])),
                    "competencias_gerais": json.dumps(habilidade.get('competencias_gerais', [])),
                })
                ids.append(f"hab_{habilidade['codigo']}")
            
            # Process competências específicas
            for competencia in self.bncc_data.get('competencias_especificas', []):
                doc_text = f"{competencia['codigo']}: {competencia['descricao']}"
                
                documents.append(doc_text)
                metadatas.append({
                    "tipo": "competencia_especifica",
                    "codigo": competencia['codigo'],
                    "etapa": competencia['etapa'],
                    "area_conhecimento": competencia['area_conhecimento'],
                    "componente": competencia.get('componente', ''),
                    "numero": str(competencia.get('numero', 0)),
                })
                ids.append(f"comp_{competencia['codigo']}")
            
            if documents:
                # Generate embeddings
                logger.info(f"Generating embeddings for {len(documents)} documents...")
                embeddings = self.embedding_model.encode(documents, show_progress_bar=True)
                
                # Add to ChromaDB
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings.tolist(),
                    ids=ids
                )
                
                logger.info(f"Successfully created embeddings for {len(documents)} documents")
            else:
                logger.warning("No documents found to create embeddings")
                
        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
            raise
    
    async def search_semantic(
        self, 
        query: str, 
        max_results: int = 5,
        similarity_threshold: float = None
    ) -> List[DocumentoFonte]:
        """
        Perform semantic search
        
        Args:
            query: Search query in natural language
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of DocumentoFonte objects with search results
        """
        try:
            if not self.collection or self.collection.count() == 0:
                logger.warning("Vector store is empty")
                return []
            
            # Use default threshold if not provided
            if similarity_threshold is None:
                similarity_threshold = settings.SIMILARITY_THRESHOLD
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=min(max_results, settings.MAX_SEARCH_RESULTS),
                include=['documents', 'metadatas', 'distances']
            )
            
            # Process results
            fontes = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i]
                    # Convert distance to similarity (ChromaDB uses cosine distance)
                    similarity = 1 - distance
                    
                    if similarity >= similarity_threshold:
                        metadata = results['metadatas'][0][i]
                        
                        fonte = DocumentoFonte(
                            codigo=metadata['codigo'],
                            tipo=metadata['tipo'],
                            relevancia=round(similarity, 3),
                            titulo=self._get_document_title(metadata)
                        )
                        fontes.append(fonte)
            
            logger.info(f"Semantic search for '{query}' returned {len(fontes)} results")
            return fontes
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def _get_document_title(self, metadata: Dict[str, Any]) -> str:
        """Generate a title for a document based on its metadata"""
        if metadata['tipo'] == 'habilidade':
            return f"Habilidade {metadata['codigo']} - {metadata['componente'].replace('_', ' ').title()}"
        elif metadata['tipo'] == 'competencia_especifica':
            return f"Competência Específica {metadata['codigo']} - {metadata['area_conhecimento'].replace('_', ' ').title()}"
        return metadata['codigo']
    
    async def get_document_by_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by its codigo"""
        try:
            # Search in habilidades
            for habilidade in self.bncc_data.get('habilidades', []):
                if habilidade['codigo'] == codigo:
                    return habilidade
            
            # Search in competências específicas
            for competencia in self.bncc_data.get('competencias_especificas', []):
                if competencia['codigo'] == codigo:
                    return competencia
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document by codigo {codigo}: {e}")
            return None
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            if not self.collection:
                return {"total_documents": 0, "status": "not_initialized"}
            
            count = self.collection.count()
            
            # Get type distribution
            results = self.collection.get(include=['metadatas'])
            type_counts = {}
            if results['metadatas']:
                for metadata in results['metadatas']:
                    doc_type = metadata.get('tipo', 'unknown')
                    type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            
            return {
                "total_documents": count,
                "type_distribution": type_counts,
                "embedding_model": settings.EMBEDDING_MODEL,
                "status": "initialized"
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"total_documents": 0, "status": "error", "error": str(e)}
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.client:
                # ChromaDB client doesn't need explicit cleanup
                pass
            logger.info("Vector store service cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Singleton instance
_vector_service = None


async def get_vector_service() -> VectorStoreService:
    """Get the global vector service instance"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
        await _vector_service.initialize()
    return _vector_service
