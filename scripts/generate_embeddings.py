"""
Script para gerar embeddings dos dados da BNCC
"""

import json
import logging
import asyncio
from pathlib import Path
import argparse
import time
import sys
import os

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def generate_embeddings():
    """Generate embeddings for BNCC data"""
    try:
        # Import services (this will install dependencies if needed)
        from app.services.vector_store import VectorStoreService
        from app.core.config import settings
        
        logger.info("Initializing vector store service...")
        vector_service = VectorStoreService()
        
        start_time = time.time()
        await vector_service.initialize()
        
        # Get collection stats
        stats = await vector_service.get_collection_stats()
        logger.info(f"Embedding generation completed!")
        logger.info(f"Total documents: {stats.get('total_documents', 0)}")
        logger.info(f"Type distribution: {stats.get('type_distribution', {})}")
        logger.info(f"Embedding model: {stats.get('embedding_model', 'unknown')}")
        logger.info(f"Processing time: {time.time() - start_time:.2f} seconds")
        
        # Cleanup
        await vector_service.cleanup()
        
        return True
        
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        logger.error("Please install required packages: pip install sentence-transformers chromadb")
        return False
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return False


async def test_semantic_search():
    """Test semantic search functionality"""
    try:
        from app.services.vector_store import VectorStoreService
        
        logger.info("Testing semantic search...")
        
        vector_service = VectorStoreService()
        await vector_service.initialize()
        
        # Test queries
        test_queries = [
            "matemática frações quinto ano",
            "educação física jogos brincadeiras",
            "língua portuguesa leitura",
            "ciências materiais objetos"
        ]
        
        for query in test_queries:
            logger.info(f"\nTesting query: '{query}'")
            results = await vector_service.search_semantic(query, max_results=3)
            
            for i, result in enumerate(results, 1):
                logger.info(f"  {i}. {result.codigo} (relevância: {result.relevancia:.3f})")
        
        await vector_service.cleanup()
        return True
        
    except Exception as e:
        logger.error(f"Error testing semantic search: {e}")
        return False


def check_data_file():
    """Check if BNCC data file exists"""
    from app.core.config import settings
    
    data_path = Path(settings.BNCC_DATA_PATH)
    
    if not data_path.exists():
        logger.error(f"BNCC data file not found: {data_path}")
        logger.info("Please run the data extraction script first:")
        logger.info("python scripts/extract_bncc_data.py")
        return False
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total_habilidades = len(data.get('habilidades', []))
        total_competencias = len(data.get('competencias_gerais', [])) + len(data.get('competencias_especificas', []))
        
        logger.info(f"Found BNCC data file with {total_habilidades} habilidades and {total_competencias} competências")
        return True
        
    except Exception as e:
        logger.error(f"Error reading BNCC data file: {e}")
        return False


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Generate embeddings for BNCC data")
    parser.add_argument("--test", action="store_true", help="Test semantic search after generating embeddings")
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting embedding generation process...")
        
        # Check if data file exists
        if not check_data_file():
            return 1
        
        # Generate embeddings
        success = await generate_embeddings()
        if not success:
            return 1
        
        # Test semantic search if requested
        if args.test:
            success = await test_semantic_search()
            if not success:
                logger.warning("Semantic search test failed, but embeddings were generated successfully")
        
        logger.info("Embedding generation process completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
