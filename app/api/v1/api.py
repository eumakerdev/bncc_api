"""
API v1 router configuration
"""

from fastapi import APIRouter

from app.api.v1.endpoints import habilidades, competencias, busca, sistema

api_router = APIRouter()

api_router.include_router(
    habilidades.router, 
    prefix="/habilidades", 
    tags=["Habilidades"]
)

api_router.include_router(
    competencias.router, 
    prefix="/competencias", 
    tags=["Competências"]
)

api_router.include_router(
    busca.router, 
    prefix="/busca-semantica", 
    tags=["Busca Semântica"]
)

api_router.include_router(
    sistema.router, 
    prefix="/sistema", 
    tags=["Sistema"]
)
