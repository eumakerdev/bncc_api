# BNCC API - Base Nacional Comum Curricular API

Uma API RESTful inteligente e moderna para a Base Nacional Comum Curricular (BNCC) do Brasil, com capacidades de busca semântica e integração de IA.

## 🎯 Visão Geral

Esta API não é apenas um repositório de dados, mas uma plataforma inteligente que permite aos desenvolvedores, educadores e pesquisadores "conversar" com o documento da BNCC, realizar buscas semânticas complexas e integrar facilmente os dados em suas aplicações educacionais.

## 🚀 Funcionalidades

### Fase 1: API Core (MVP)

- ✅ Endpoints RESTful para habilidades e competências
- ✅ Busca parametrizada com filtros
- ✅ Documentação automática (Swagger UI/ReDoc)
- ✅ Validação rigorosa com Pydantic

### Fase 2: Busca Semântica e IA

- ✅ Arquitetura RAG (Retrieval-Augmented Generation)
- ✅ Busca semântica em linguagem natural
- ✅ Integração com LLMs via LangChain
- ✅ Banco de dados vetorial (ChromaDB)

### Fase 3: Model Context Protocol (MCP)

- ✅ Servidor MCP integrado
- ✅ Interoperabilidade com outras IAs
- ✅ Padronização futura

## 🛠️ Stack Tecnológica

- **Backend**: Python 3.11+ + FastAPI
- **IA/ML**: LangChain + ChromaDB + sentence-transformers
- **Containerização**: Docker + Docker Compose
- **Testes**: pytest (cobertura 80%+)
- **CI/CD**: GitHub Actions
- **Qualidade de Código**: ruff + black

## 📦 Instalação e Execução

### Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- Git

### Executando com Docker (Recomendado)

```bash
# Clone o repositório
git clone <repository-url>
cd bncc_api

# Execute com Docker Compose
docker-compose up --build
```

A API estará disponível em:

- **API**: http://localhost:8000
- **Documentação Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Executando em Ambiente Local

```bash
# Clone o repositório
git clone <repository-url>
cd bncc_api

# Crie um ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📋 Uso da API

### Endpoints Principais

#### Habilidades

```bash
# Buscar habilidade específica
curl "http://localhost:8000/api/v1/habilidades/EF67EF01"

# Buscar habilidades com filtros
curl "http://localhost:8000/api/v1/habilidades?etapa=ensino_fundamental&ano=6&componente=educacao_fisica"
```

#### Competências

```bash
# Listar competências gerais
curl "http://localhost:8000/api/v1/competencias/gerais"

# Buscar competências específicas por área
curl "http://localhost:8000/api/v1/competencias/especificas?area=matematica"
```

#### Busca Semântica (IA)

```bash
# Busca inteligente em linguagem natural
curl -X POST "http://localhost:8000/api/v1/busca-semantica" \
     -H "Content-Type: application/json" \
     -d '{"query": "Qual habilidade de matemática do 5º ano aborda frações?"}'
```

### Exemplos de Resposta

#### Habilidade Individual

```json
{
  "codigo": "EF67EF01",
  "descricao": "Experimentar, desfrutar, apreciar e criar diferentes brincadeiras...",
  "etapa": "ensino_fundamental",
  "anos": ["6", "7"],
  "area_conhecimento": "linguagens",
  "componente": "educacao_fisica",
  "competencias_gerais": [1, 4, 8],
  "competencias_especificas": ["EF1", "EF2"]
}
```

#### Busca Semântica

```json
{
  "resposta": "Para o 5º ano do Ensino Fundamental, a habilidade EF05MA03 aborda especificamente o trabalho com frações...",
  "fontes": [
    {
      "codigo": "EF05MA03",
      "relevancia": 0.95
    }
  ],
  "documentos_consultados": 3
}
```

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Executar com cobertura
pytest --cov=app --cov-report=html

# Executar testes específicos
pytest tests/test_api.py -v
```

## 🔧 Desenvolvimento

### Estrutura do Projeto

```
bncc_api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Aplicação FastAPI principal
│   ├── core/
│   │   ├── config.py          # Configurações
│   │   ├── deps.py            # Dependências
│   │   └── security.py        # Autenticação/Autorização
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/     # Endpoints da API
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── models/                # Modelos Pydantic
│   ├── services/              # Lógica de negócio
│   ├── utils/                 # Utilitários
│   └── mcp/                   # Servidor MCP
├── data/                      # Dados da BNCC
├── scripts/                   # Scripts de extração e processamento
├── tests/                     # Testes
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

### Scripts Úteis

```bash
# Processar dados da BNCC
python scripts/extract_bncc_data.py

# Gerar embeddings
python scripts/generate_embeddings.py

# Executar linting
ruff check app/
black app/

# Executar type checking
mypy app/
```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🎯 Roadmap

- [ ] Implementação de cache Redis
- [ ] Autenticação via OAuth2
- [ ] Rate limiting
- [ ] Métricas e monitoramento
- [ ] Deploy em cloud (AWS/GCP)
- [ ] API versioning avançado
- [ ] Webhooks para atualizações

## 📧 Contato

Para dúvidas ou sugestões, abra uma issue no GitHub.
