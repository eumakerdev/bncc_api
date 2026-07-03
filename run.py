#!/usr/bin/env python3
"""
Script para executar a BNCC API
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 11):
        logger.error("Python 3.11 or higher is required")
        return False
    return True


def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import chromadb
        import sentence_transformers
        logger.info("All required dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Please install dependencies: pip install -r requirements.txt")
        return False


def setup_environment():
    """Setup environment variables and data directory"""
    # Create data directory
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    # Copy .env.example to .env if it doesn't exist
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        logger.info("Created .env file from .env.example")
    
    return True


def extract_sample_data():
    """Extract sample BNCC data"""
    try:
        logger.info("Extracting sample BNCC data...")
        result = subprocess.run([
            sys.executable, "scripts/extract_bncc_data.py", 
            "--output", "./data/bncc_completa.json",
            "--validate"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Data extraction failed: {result.stderr}")
            return False
        
        logger.info("Sample data extracted successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        return False


def generate_embeddings():
    """Generate embeddings for the data"""
    try:
        logger.info("Generating embeddings...")
        result = subprocess.run([
            sys.executable, "scripts/generate_embeddings.py"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Embedding generation failed: {result.stderr}")
            return False
        
        logger.info("Embeddings generated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return False


def run_tests():
    """Run the test suite"""
    try:
        logger.info("Running tests...")
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/", "-v"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning("Some tests failed")
            logger.info(result.stdout)
            logger.warning(result.stderr)
        else:
            logger.info("All tests passed")
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return False


def start_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """Start the FastAPI application"""
    try:
        logger.info(f"Starting BNCC API on {host}:{port}")
        logger.info(f"API Documentation: http://{host}:{port}/docs")
        logger.info(f"ReDoc Documentation: http://{host}:{port}/redoc")
        
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app",
            "--host", host,
            "--port", str(port),
            "--reload" if reload else "--no-reload"
        ])
        
    except KeyboardInterrupt:
        logger.info("API stopped by user")
    except Exception as e:
        logger.error(f"Error starting API: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="BNCC API Runner")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--setup-only", action="store_true", help="Only setup data and exit")
    parser.add_argument("--test", action="store_true", help="Run tests before starting")
    parser.add_argument("--skip-setup", action="store_true", help="Skip data setup")
    
    args = parser.parse_args()
    
    logger.info("BNCC API Setup and Runner")
    logger.info("=" * 50)
    
    # Check requirements
    if not check_python_version():
        return 1
    
    if not check_dependencies():
        return 1
    
    # Setup environment
    if not setup_environment():
        return 1
    
    # Setup data (unless skipped)
    if not args.skip_setup:
        # Check if data file exists
        data_file = Path("./data/bncc_completa.json")
        if not data_file.exists():
            if not extract_sample_data():
                return 1
        else:
            logger.info("BNCC data file already exists")
        
        # Generate embeddings if needed
        chromadb_dir = Path("./data/chromadb")
        if not chromadb_dir.exists() or not any(chromadb_dir.iterdir()):
            if not generate_embeddings():
                logger.warning("Failed to generate embeddings, but continuing...")
        else:
            logger.info("ChromaDB embeddings already exist")
    
    # Run tests if requested
    if args.test:
        if not run_tests():
            logger.warning("Tests failed, but continuing...")
    
    # Exit if setup-only
    if args.setup_only:
        logger.info("Setup completed successfully!")
        return 0
    
    # Start the API
    start_api(
        host=args.host,
        port=args.port,
        reload=not args.no_reload
    )
    
    return 0


if __name__ == "__main__":
    exit(main())
