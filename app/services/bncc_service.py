"""
BNCC Data Service for managing habilidades and competencias
"""

import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.core.config import settings
from app.models.bncc import (
    Habilidade, CompetenciaGeral, CompetenciaEspecifica, 
    HabilidadeFiltros, EtapaEnsino, AreaConhecimento, ComponenteCurricular
)

logger = logging.getLogger(__name__)


class BNCCDataService:
    """Service for accessing and filtering BNCC data"""
    
    def __init__(self):
        self.data = None
        self._load_data()
    
    def _load_data(self):
        """Load BNCC data from JSON file"""
        try:
            data_path = Path(settings.BNCC_DATA_PATH)
            
            if not data_path.exists():
                logger.warning(f"BNCC data file not found at {data_path}")
                self.data = self._get_empty_data()
                return
            
            with open(data_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            logger.info(f"Loaded BNCC data: {len(self.data.get('habilidades', []))} habilidades, "
                       f"{len(self.data.get('competencias_gerais', []))} competências gerais, "
                       f"{len(self.data.get('competencias_especificas', []))} competências específicas")
                       
        except Exception as e:
            logger.error(f"Error loading BNCC data: {e}")
            self.data = self._get_empty_data()
    
    def _get_empty_data(self) -> Dict[str, List]:
        """Return empty data structure"""
        return {
            "habilidades": [],
            "competencias_gerais": [],
            "competencias_especificas": []
        }
    
    async def get_habilidade_by_codigo(self, codigo: str) -> Optional[Habilidade]:
        """Get a specific habilidade by its codigo"""
        try:
            codigo = codigo.upper().strip()
            
            for hab_data in self.data.get('habilidades', []):
                if hab_data.get('codigo', '').upper() == codigo:
                    return Habilidade(**hab_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting habilidade {codigo}: {e}")
            return None
    
    async def search_habilidades(
        self, 
        filtros: HabilidadeFiltros,
        skip: int = 0,
        limit: int = 100
    ) -> List[Habilidade]:
        """
        Search habilidades with filters
        
        Args:
            filtros: HabilidadeFiltros object with search criteria
            skip: Number of items to skip (pagination)
            limit: Maximum number of items to return
            
        Returns:
            List of matching Habilidade objects
        """
        try:
            resultado = []
            
            for hab_data in self.data.get('habilidades', []):
                if self._match_habilidade_filtros(hab_data, filtros):
                    try:
                        habilidade = Habilidade(**hab_data)
                        resultado.append(habilidade)
                    except Exception as e:
                        logger.warning(f"Error creating Habilidade object: {e}")
                        continue
            
            # Apply pagination
            return resultado[skip:skip + limit]
            
        except Exception as e:
            logger.error(f"Error searching habilidades: {e}")
            return []
    
    def _match_habilidade_filtros(self, hab_data: Dict[str, Any], filtros: HabilidadeFiltros) -> bool:
        """Check if a habilidade matches the given filters"""
        try:
            # Filter by etapa
            if filtros.etapa and hab_data.get('etapa') != filtros.etapa.value:
                return False
            
            # Filter by ano
            if filtros.ano:
                anos = hab_data.get('anos', [])
                if filtros.ano not in anos:
                    return False
            
            # Filter by area_conhecimento
            if filtros.area_conhecimento and hab_data.get('area_conhecimento') != filtros.area_conhecimento.value:
                return False
            
            # Filter by componente
            if filtros.componente and hab_data.get('componente') != filtros.componente.value:
                return False
            
            # Filter by competencia_geral
            if filtros.competencia_geral:
                competencias_gerais = hab_data.get('competencias_gerais', [])
                if filtros.competencia_geral not in competencias_gerais:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error matching filters: {e}")
            return False
    
    async def count_habilidades(self, filtros: HabilidadeFiltros) -> int:
        """Count habilidades matching the filters"""
        try:
            count = 0
            for hab_data in self.data.get('habilidades', []):
                if self._match_habilidade_filtros(hab_data, filtros):
                    count += 1
            return count
            
        except Exception as e:
            logger.error(f"Error counting habilidades: {e}")
            return 0
    
    async def get_competencias_gerais(self) -> List[CompetenciaGeral]:
        """Get all general competencies"""
        try:
            resultado = []
            
            for comp_data in self.data.get('competencias_gerais', []):
                try:
                    competencia = CompetenciaGeral(**comp_data)
                    resultado.append(competencia)
                except Exception as e:
                    logger.warning(f"Error creating CompetenciaGeral object: {e}")
                    continue
            
            # Sort by numero
            resultado.sort(key=lambda x: x.numero)
            return resultado
            
        except Exception as e:
            logger.error(f"Error getting competencias gerais: {e}")
            return []
    
    async def get_competencia_geral_by_numero(self, numero: int) -> Optional[CompetenciaGeral]:
        """Get a specific general competency by its number"""
        try:
            for comp_data in self.data.get('competencias_gerais', []):
                if comp_data.get('numero') == numero:
                    return CompetenciaGeral(**comp_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting competencia geral {numero}: {e}")
            return None
    
    async def get_competencias_especificas(
        self, 
        area: Optional[AreaConhecimento] = None,
        componente: Optional[ComponenteCurricular] = None,
        etapa: Optional[EtapaEnsino] = None
    ) -> List[CompetenciaEspecifica]:
        """
        Get specific competencies with optional filters
        
        Args:
            area: Filter by knowledge area
            componente: Filter by curricular component
            etapa: Filter by education stage
            
        Returns:
            List of matching CompetenciaEspecifica objects
        """
        try:
            resultado = []
            
            for comp_data in self.data.get('competencias_especificas', []):
                # Apply filters
                if area and comp_data.get('area_conhecimento') != area.value:
                    continue
                
                if componente and comp_data.get('componente') != componente.value:
                    continue
                
                if etapa and comp_data.get('etapa') != etapa.value:
                    continue
                
                try:
                    competencia = CompetenciaEspecifica(**comp_data)
                    resultado.append(competencia)
                except Exception as e:
                    logger.warning(f"Error creating CompetenciaEspecifica object: {e}")
                    continue
            
            # Sort by area, then by numero
            resultado.sort(key=lambda x: (x.area_conhecimento.value, x.numero))
            return resultado
            
        except Exception as e:
            logger.error(f"Error getting competencias especificas: {e}")
            return []
    
    async def get_competencia_especifica_by_codigo(self, codigo: str) -> Optional[CompetenciaEspecifica]:
        """Get a specific competency by its codigo"""
        try:
            codigo = codigo.upper().strip()
            
            for comp_data in self.data.get('competencias_especificas', []):
                if comp_data.get('codigo', '').upper() == codigo:
                    return CompetenciaEspecifica(**comp_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting competencia especifica {codigo}: {e}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get BNCC data statistics"""
        try:
            stats = {
                "total_habilidades": len(self.data.get('habilidades', [])),
                "total_competencias_gerais": len(self.data.get('competencias_gerais', [])),
                "total_competencias_especificas": len(self.data.get('competencias_especificas', [])),
                "etapas": {},
                "areas_conhecimento": {},
                "componentes": {}
            }
            
            # Count by etapa
            for hab in self.data.get('habilidades', []):
                etapa = hab.get('etapa', 'unknown')
                stats["etapas"][etapa] = stats["etapas"].get(etapa, 0) + 1
            
            # Count by area de conhecimento
            for hab in self.data.get('habilidades', []):
                area = hab.get('area_conhecimento', 'unknown')
                stats["areas_conhecimento"][area] = stats["areas_conhecimento"].get(area, 0) + 1
            
            # Count by componente
            for hab in self.data.get('habilidades', []):
                componente = hab.get('componente', 'unknown')
                stats["componentes"][componente] = stats["componentes"].get(componente, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity and return report"""
        try:
            report = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "summary": {}
            }
            
            # Check habilidades
            hab_codigos = set()
            for i, hab in enumerate(self.data.get('habilidades', [])):
                try:
                    # Check required fields
                    if not hab.get('codigo'):
                        report["errors"].append(f"Habilidade {i}: Missing codigo")
                        report["valid"] = False
                    
                    if not hab.get('descricao'):
                        report["errors"].append(f"Habilidade {i}: Missing descricao")
                        report["valid"] = False
                    
                    # Check for duplicate codigos
                    codigo = hab.get('codigo', '')
                    if codigo in hab_codigos:
                        report["errors"].append(f"Duplicate habilidade codigo: {codigo}")
                        report["valid"] = False
                    hab_codigos.add(codigo)
                    
                    # Validate Pydantic model
                    Habilidade(**hab)
                    
                except Exception as e:
                    report["errors"].append(f"Habilidade {i} validation error: {str(e)}")
                    report["valid"] = False
            
            # Check competências gerais
            for i, comp in enumerate(self.data.get('competencias_gerais', [])):
                try:
                    CompetenciaGeral(**comp)
                except Exception as e:
                    report["errors"].append(f"Competencia geral {i} validation error: {str(e)}")
                    report["valid"] = False
            
            # Check competências específicas
            comp_codigos = set()
            for i, comp in enumerate(self.data.get('competencias_especificas', [])):
                try:
                    # Check for duplicate codigos
                    codigo = comp.get('codigo', '')
                    if codigo in comp_codigos:
                        report["errors"].append(f"Duplicate competencia especifica codigo: {codigo}")
                        report["valid"] = False
                    comp_codigos.add(codigo)
                    
                    CompetenciaEspecifica(**comp)
                except Exception as e:
                    report["errors"].append(f"Competencia especifica {i} validation error: {str(e)}")
                    report["valid"] = False
            
            report["summary"] = {
                "total_errors": len(report["errors"]),
                "total_warnings": len(report["warnings"]),
                "habilidades_checked": len(self.data.get('habilidades', [])),
                "competencias_gerais_checked": len(self.data.get('competencias_gerais', [])),
                "competencias_especificas_checked": len(self.data.get('competencias_especificas', []))
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error validating data integrity: {e}")
            return {
                "valid": False,
                "errors": [f"Validation process failed: {str(e)}"],
                "warnings": [],
                "summary": {}
            }


# Global service instance
_bncc_service = None


def get_bncc_service() -> BNCCDataService:
    """Get the global BNCC data service instance"""
    global _bncc_service
    if _bncc_service is None:
        _bncc_service = BNCCDataService()
    return _bncc_service
