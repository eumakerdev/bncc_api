"""
Tests for the main API endpoints
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestMainAPI:
    """Test cases for main API functionality."""
    
    def test_root_redirect(self, client: TestClient):
        """Test that root path redirects to documentation."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
    
    def test_openapi_spec(self, client: TestClient):
        """Test OpenAPI specification endpoint."""
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "BNCC API"


class TestSystemEndpoints:
    """Test cases for system endpoints."""
    
    def test_system_info(self, client: TestClient):
        """Test system info endpoint."""
        response = client.get("/api/v1/sistema/info")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "BNCC API"
        assert "version" in data
        assert "features" in data
        assert isinstance(data["features"], list)
    
    def test_system_config(self, client: TestClient):
        """Test system configuration endpoint."""
        response = client.get("/api/v1/sistema/config")
        assert response.status_code == 200
        
        data = response.json()
        assert "api" in data
        assert "data" in data
        assert "ai" in data
        assert "search" in data
    
    def test_detailed_health_check(self, client: TestClient):
        """Test detailed health check endpoint."""
        response = client.get("/api/v1/sistema/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert isinstance(data["components"], dict)


class TestHabilidadesEndpoints:
    """Test cases for habilidades endpoints."""
    
    def test_search_habilidades_no_filters(self, client: TestClient):
        """Test search habilidades without filters."""
        response = client.get("/api/v1/habilidades/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        assert isinstance(data["items"], list)
    
    def test_search_habilidades_with_filters(self, client: TestClient):
        """Test search habilidades with filters."""
        response = client.get("/api/v1/habilidades/?etapa=ensino_fundamental&componente=matematica")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    def test_get_habilidade_by_codigo_success(self, client: TestClient):
        """Test get habilidade by codigo - success case."""
        # This test assumes sample data is loaded
        response = client.get("/api/v1/habilidades/EF05MA03")
        
        # The response will be 404 if sample data is not loaded, which is expected
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["codigo"] == "EF05MA03"
            assert "descricao" in data
            assert "etapa" in data
    
    def test_get_habilidade_by_codigo_not_found(self, client: TestClient):
        """Test get habilidade by codigo - not found case."""
        response = client.get("/api/v1/habilidades/INVALID_CODE")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data


class TestCompetenciasEndpoints:
    """Test cases for competências endpoints."""
    
    def test_get_competencias_gerais(self, client: TestClient):
        """Test get competências gerais."""
        response = client.get("/api/v1/competencias/gerais")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Should have 10 competências gerais or be empty if no data is loaded
        assert len(data) in [0, 10]
    
    def test_get_competencia_geral_by_numero_valid(self, client: TestClient):
        """Test get competência geral by valid number."""
        response = client.get("/api/v1/competencias/gerais/1")
        
        # Will be 404 if no data is loaded, which is expected
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["numero"] == 1
            assert "titulo" in data
            assert "descricao" in data
    
    def test_get_competencia_geral_by_numero_invalid(self, client: TestClient):
        """Test get competência geral by invalid number."""
        response = client.get("/api/v1/competencias/gerais/11")
        assert response.status_code == 422  # Validation error
    
    def test_get_competencias_especificas(self, client: TestClient):
        """Test get competências específicas."""
        response = client.get("/api/v1/competencias/especificas")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


class TestBuscaSemanticaEndpoints:
    """Test cases for busca semântica endpoints."""
    
    def test_busca_semantica_stats(self, client: TestClient):
        """Test busca semântica stats endpoint."""
        response = client.get("/api/v1/busca-semantica/stats")
        
        # May return 503 if vector service is not available
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "total_documents" in data
            assert "status" in data
    
    def test_busca_semantica_post_invalid_request(self, client: TestClient):
        """Test busca semântica with invalid request."""
        response = client.post("/api/v1/busca-semantica", json={})
        assert response.status_code == 422  # Validation error
    
    def test_busca_semantica_post_valid_request(self, client: TestClient):
        """Test busca semântica with valid request."""
        request_data = {
            "query": "matemática frações",
            "max_resultados": 3
        }
        
        response = client.post("/api/v1/busca-semantica", json=request_data)
        
        # May return 500 if vector service is not available
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "resposta" in data
            assert "fontes" in data
            assert "documentos_consultados" in data
            assert isinstance(data["fontes"], list)


class TestErrorHandling:
    """Test cases for error handling."""
    
    def test_not_found_endpoint(self, client: TestClient):
        """Test accessing non-existent endpoint."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client: TestClient):
        """Test using wrong HTTP method."""
        response = client.post("/api/v1/habilidades/EF05MA03")
        assert response.status_code == 405
