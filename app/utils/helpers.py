"""
Utility functions for data validation and processing
"""

import re
from typing import List, Dict, Any, Optional
from enum import Enum


def validate_codigo_habilidade(codigo: str) -> bool:
    """
    Validate BNCC habilidade code format
    
    Valid formats:
    - EF05MA03 (Ensino Fundamental, 5º ano, Matemática, habilidade 03)
    - EI03EO04 (Educação Infantil, 3 anos, ...)
    - EM13MAT104 (Ensino Médio, 1º-3º ano, Matemática, habilidade 104)
    """
    if not codigo or not isinstance(codigo, str):
        return False
    
    # Basic pattern for BNCC codes
    patterns = [
        r'^EF\d{2}[A-Z]{2}\d{2}$',  # Ensino Fundamental: EF05MA03
        r'^EI\d{2}[A-Z]{2}\d{2}$',  # Educação Infantil: EI03EO04
        r'^EM\d{2}[A-Z]{3}\d{3}$'  # Ensino Médio: EM13MAT104
    ]
    
    return any(re.match(pattern, codigo.upper()) for pattern in patterns)


def validate_codigo_competencia(codigo: str) -> bool:
    """
    Validate BNCC competência específica code format
    
    Valid formats:
    - EFMAT01 (Ensino Fundamental, Matemática, competência 01)
    - EMLP02 (Ensino Médio, Língua Portuguesa, competência 02)
    """
    if not codigo or not isinstance(codigo, str):
        return False
    
    # Pattern for competência específica codes
    pattern = r'^[A-Z]{2,4}\d{2}$'
    return bool(re.match(pattern, codigo.upper()))


def normalize_codigo(codigo: str) -> str:
    """Normalize BNCC code format"""
    if not codigo:
        return ""
    
    return codigo.upper().strip()


def extract_ano_from_codigo(codigo: str) -> Optional[str]:
    """Extract year information from BNCC habilidade code"""
    if not validate_codigo_habilidade(codigo):
        return None
    
    codigo = codigo.upper()
    
    if codigo.startswith('EF'):
        # Ensino Fundamental: EF05MA03 -> anos 0 e 5
        year_part = codigo[2:4]
        if year_part.isdigit():
            year1 = year_part[0]
            year2 = year_part[1]
            if year1 == '0':
                return year2
            else:
                return f"{year1}-{year2}"
    
    elif codigo.startswith('EI'):
        # Educação Infantil: EI03EO04 -> 3 anos
        year_part = codigo[2:4]
        if year_part.isdigit():
            return year_part.lstrip('0') or '0'
    
    elif codigo.startswith('EM'):
        # Ensino Médio: EM13MAT104 -> 1º-3º ano
        year_part = codigo[2:4]
        if year_part == '13':
            return "1-3"
    
    return None


def extract_componente_from_codigo(codigo: str) -> Optional[str]:
    """Extract component information from BNCC habilidade code"""
    if not validate_codigo_habilidade(codigo):
        return None
    
    codigo = codigo.upper()
    
    # Component mapping
    component_map = {
        'LP': 'lingua_portuguesa',
        'MA': 'matematica',
        'CI': 'ciencias',
        'GE': 'geografia',
        'HI': 'historia',
        'AR': 'arte',
        'EF': 'educacao_fisica',
        'LI': 'lingua_inglesa',
        'ER': 'ensino_religioso',
        'EO': 'eu_outro_nos',  # Educação Infantil
        'CG': 'corpo_gestos_movimentos',  # Educação Infantil
        'TS': 'tracos_sons_cores_formas',  # Educação Infantil
        'EF': 'escuta_fala_pensamento_linguagem',  # Educação Infantil
        'ET': 'espacos_tempos_quantidades'  # Educação Infantil
    }
    
    if codigo.startswith(('EF', 'EI')):
        component_code = codigo[4:6]
    elif codigo.startswith('EM'):
        component_code = codigo[4:7]
    else:
        return None
    
    return component_map.get(component_code)


def get_etapa_from_codigo(codigo: str) -> Optional[str]:
    """Get education stage from BNCC code"""
    if not codigo:
        return None
    
    codigo = codigo.upper()
    
    if codigo.startswith('EF'):
        return 'ensino_fundamental'
    elif codigo.startswith('EI'):
        return 'educacao_infantil'
    elif codigo.startswith('EM'):
        return 'ensino_medio'
    
    return None


def format_competencias_display(competencias_gerais: List[int]) -> str:
    """Format competências gerais list for display"""
    if not competencias_gerais:
        return "Nenhuma"
    
    return ", ".join(f"CG{num:02d}" for num in sorted(competencias_gerais))


def create_search_text(habilidade: Dict[str, Any]) -> str:
    """Create searchable text from habilidade data"""
    parts = []
    
    # Add codigo
    if habilidade.get('codigo'):
        parts.append(habilidade['codigo'])
    
    # Add description
    if habilidade.get('descricao'):
        parts.append(habilidade['descricao'])
    
    # Add objetos de conhecimento
    if habilidade.get('objetos_conhecimento'):
        parts.extend(habilidade['objetos_conhecimento'])
    
    # Add metadata
    if habilidade.get('componente'):
        parts.append(habilidade['componente'].replace('_', ' '))
    
    if habilidade.get('area_conhecimento'):
        parts.append(habilidade['area_conhecimento'].replace('_', ' '))
    
    return ' '.join(parts)


def calculate_relevance_score(
    query: str, 
    document: Dict[str, Any], 
    base_score: float = 1.0
) -> float:
    """Calculate relevance score for a document based on query"""
    score = base_score
    query_lower = query.lower()
    
    # Boost score for exact code matches
    if document.get('codigo') and document['codigo'].lower() in query_lower:
        score *= 2.0
    
    # Boost score for component matches
    if document.get('componente'):
        component = document['componente'].replace('_', ' ')
        if component in query_lower:
            score *= 1.5
    
    # Boost score for year matches
    if document.get('anos'):
        for ano in document['anos']:
            if ano in query_lower:
                score *= 1.3
                break
    
    # Boost score for area matches
    if document.get('area_conhecimento'):
        area = document['area_conhecimento'].replace('_', ' ')
        if area in query_lower:
            score *= 1.2
    
    return score


def clean_text(text: str) -> str:
    """Clean and normalize text for processing"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Normalize common characters
    replacements = {
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '–': '-',
        '—': '-',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text.strip()


def generate_summary(text: str, max_length: int = 200) -> str:
    """Generate a summary of text with maximum length"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Try to cut at sentence boundary
    sentences = text.split('.')
    summary = ""
    
    for sentence in sentences:
        if len(summary + sentence + '.') <= max_length:
            summary += sentence + '.'
        else:
            break
    
    # If no complete sentence fits, cut at word boundary
    if not summary:
        words = text.split()
        summary = ""
        for word in words:
            if len(summary + ' ' + word) <= max_length - 3:
                summary += ' ' + word if summary else word
            else:
                break
        summary += "..."
    
    return summary.strip()


class BNCCConstants:
    """Constants for BNCC data processing"""
    
    ETAPAS = {
        'educacao_infantil': 'Educação Infantil',
        'ensino_fundamental': 'Ensino Fundamental',
        'ensino_medio': 'Ensino Médio'
    }
    
    AREAS_CONHECIMENTO = {
        'linguagens': 'Linguagens',
        'matematica': 'Matemática',
        'ciencias_natureza': 'Ciências da Natureza',
        'ciencias_humanas': 'Ciências Humanas',
        'ensino_religioso': 'Ensino Religioso'
    }
    
    COMPONENTES = {
        'lingua_portuguesa': 'Língua Portuguesa',
        'arte': 'Arte',
        'educacao_fisica': 'Educação Física',
        'lingua_inglesa': 'Língua Inglesa',
        'matematica': 'Matemática',
        'ciencias': 'Ciências',
        'geografia': 'Geografia',
        'historia': 'História',
        'ensino_religioso': 'Ensino Religioso'
    }
    
    COMPETENCIAS_GERAIS_TITULOS = {
        1: "Conhecimento",
        2: "Pensamento científico, crítico e criativo",
        3: "Repertório cultural",
        4: "Comunicação",
        5: "Cultura digital",
        6: "Trabalho e projeto de vida",
        7: "Argumentação",
        8: "Autoconhecimento e autocuidado",
        9: "Empatia e cooperação",
        10: "Responsabilidade e cidadania"
    }
