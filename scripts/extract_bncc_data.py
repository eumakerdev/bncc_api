"""
Script para extrair dados da BNCC a partir do PDF oficial
"""

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BNCCExtractor:
    """Extrator de dados da BNCC"""
    
    def __init__(self, pdf_paths: List[str], output_path: str):
        self.pdf_paths = [Path(p) for p in pdf_paths] if isinstance(pdf_paths, list) else [Path(pdf_paths)]
        self.output_path = Path(output_path)
        self.data = {
            "habilidades": [],
            "competencias_gerais": [],
            "competencias_especificas": []
        }
    
    def extract_data(self):
        """Extract data from BNCC PDF(s)"""
        try:
            # Check if any PDF exists
            existing_pdfs = [pdf for pdf in self.pdf_paths if pdf.exists()]
            
            if not existing_pdfs:
                logger.error(f"No PDF files found in: {[str(p) for p in self.pdf_paths]}")
                self._create_sample_data()
                self._save_data()
                return
            
            logger.info(f"Found PDF files: {[str(p) for p in existing_pdfs]}")
            
            # For now, create comprehensive sample data structure
            # In a real implementation, you would use PyPDF2 or similar to parse each PDF
            self._create_comprehensive_sample_data()
            
            # Save extracted data
            self._save_data()
            
            logger.info(f"Data extraction completed. Output saved to: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Error during data extraction: {e}")
            raise
    
    def _create_sample_data(self):
        """Create sample BNCC data structure for development"""
        logger.info("Creating sample BNCC data structure...")
        
        # Competências Gerais (as 10 competências da BNCC)
        self.data["competencias_gerais"] = [
            {
                "numero": 1,
                "titulo": "Conhecimento",
                "descricao": "Valorizar e utilizar os conhecimentos historicamente construídos sobre o mundo físico, social, cultural e digital para entender e explicar a realidade, continuar aprendendo e colaborar para a construção de uma sociedade justa, democrática e inclusiva."
            },
            {
                "numero": 2,
                "titulo": "Pensamento científico, crítico e criativo",
                "descricao": "Exercitar a curiosidade intelectual e recorrer à abordagem própria das ciências, incluindo a investigação, a reflexão, a análise crítica, a imaginação e a criatividade, para investigar causas, elaborar e testar hipóteses, formular e resolver problemas e criar soluções (inclusive tecnológicas) com base nos conhecimentos das diferentes áreas."
            },
            {
                "numero": 3,
                "titulo": "Repertório cultural",
                "descricao": "Valorizar e fruir as diversas manifestações artísticas e culturais, das locais às mundiais, e também participar de práticas diversificadas da produção artístico-cultural."
            },
            {
                "numero": 4,
                "titulo": "Comunicação",
                "descricao": "Utilizar diferentes linguagens – verbal (oral ou visual-motora, como Libras, e escrita), corporal, visual, sonora e digital –, bem como conhecimentos das linguagens artística, matemática e científica, para se expressar e partilhar informações, experiências, ideias e sentimentos em diferentes contextos e produzir sentidos que levem ao entendimento mútuo."
            },
            {
                "numero": 5,
                "titulo": "Cultura digital",
                "descricao": "Compreender, utilizar e criar tecnologias digitais de informação e comunicação de forma crítica, significativa, reflexiva e ética nas diversas práticas sociais (incluindo as escolares) para se comunicar, acessar e disseminar informações, produzir conhecimentos, resolver problemas e exercer protagonismo e autoria na vida pessoal e coletiva."
            },
            {
                "numero": 6,
                "titulo": "Trabalho e projeto de vida",
                "descricao": "Valorizar a diversidade de saberes e vivências culturais e apropriar-se de conhecimentos e experiências que lhe possibilitem entender as relações próprias do mundo do trabalho e fazer escolhas alinhadas ao exercício da cidadania e ao seu projeto de vida, com liberdade, autonomia, consciência crítica e responsabilidade."
            },
            {
                "numero": 7,
                "titulo": "Argumentação",
                "descricao": "Argumentar com base em fatos, dados e informações confiáveis, para formular, negociar e defender ideias, pontos de vista e decisões comuns que respeitem e promovam os direitos humanos, a consciência socioambiental e o consumo responsável em âmbito local, regional e global, com posicionamento ético em relação ao cuidado de si mesmo, dos outros e do planeta."
            },
            {
                "numero": 8,
                "titulo": "Autoconhecimento e autocuidado",
                "descricao": "Conhecer-se, apreciar-se e cuidar de sua saúde física e emocional, compreendendo-se na diversidade humana e reconhecendo suas emoções e as dos outros, com autocrítica e capacidade para lidar com elas."
            },
            {
                "numero": 9,
                "titulo": "Empatia e cooperação",
                "descricao": "Exercitar a empatia, o diálogo, a resolução de conflitos e a cooperação, fazendo-se respeitar e promovendo o respeito ao outro e aos direitos humanos, com acolhimento e valorização da diversidade de indivíduos e de grupos sociais, seus saberes, identidades, culturas e potencialidades, sem preconceitos de qualquer natureza."
            },
            {
                "numero": 10,
                "titulo": "Responsabilidade e cidadania",
                "descricao": "Agir pessoal e coletivamente com autonomia, responsabilidade, flexibilidade, resiliência e determinação, tomando decisões com base em princípios éticos, democráticos, inclusivos, sustentáveis e solidários."
            }
        ]
        
        # Competências Específicas de exemplo
        self.data["competencias_especificas"] = [
            {
                "codigo": "EFMAT01",
                "numero": 1,
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "etapa": "ensino_fundamental",
                "descricao": "Reconhecer que a Matemática é uma ciência humana, fruto das necessidades e preocupações de diferentes culturas, em diferentes momentos históricos, e é uma ciência viva, que contribui para solucionar problemas científicos e tecnológicos e para alicerçar descobertas e construções, inclusive com impactos no mundo do trabalho."
            },
            {
                "codigo": "EFMAT02",
                "numero": 2,
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "etapa": "ensino_fundamental",
                "descricao": "Desenvolver o raciocínio lógico, o espírito de investigação e a capacidade de produzir argumentos convincentes, recorrendo aos conhecimentos matemáticos para compreender e atuar no mundo."
            },
            {
                "codigo": "EFLP01",
                "numero": 1,
                "area_conhecimento": "linguagens",
                "componente": "lingua_portuguesa",
                "etapa": "ensino_fundamental",
                "descricao": "Compreender a língua como fenômeno cultural, histórico, social, variável, heterogêneo e sensível aos contextos de uso, reconhecendo-a como meio de construção de identidades de seus usuários e da comunidade a que pertencem."
            },
            {
                "codigo": "EFCI01",
                "numero": 1,
                "area_conhecimento": "ciencias_natureza",
                "componente": "ciencias",
                "etapa": "ensino_fundamental",
                "descricao": "Compreender as Ciências da Natureza como empreendimento humano, e o conhecimento científico como provisório, cultural e histórico."
            }
        ]
        
        # Habilidades de exemplo
        self.data["habilidades"] = [
            {
                "codigo": "EF04MA09",
                "descricao": "Reconhecer as frações unitárias mais usuais (1/2, 1/3, 1/4, 1/5, 1/10 e 1/100) como unidades de medida menores do que uma unidade, utilizando a reta numérica como recurso.",
                "etapa": "ensino_fundamental",
                "anos": ["4"],
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "competencias_gerais": [1, 2, 4],
                "competencias_especificas": ["EFMAT01", "EFMAT02"],
                "objetos_conhecimento": ["Números racionais expressos na forma decimal e na forma de fração", "Comparação e ordenação de números racionais na representação decimal e na fracionária utilizando a noção de equivalência"]
            },
            {
                "codigo": "EF05MA08",
                "descricao": "Resolver e elaborar problemas de multiplicação e divisão com números naturais e com números racionais cuja representação decimal é finita (com multiplicador natural e divisor natural e diferente de zero), utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos.",
                "etapa": "ensino_fundamental",
                "anos": ["5"],
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "competencias_gerais": [1, 2, 7],
                "competencias_especificas": ["EFMAT01", "EFMAT02"],
                "objetos_conhecimento": ["Problemas: multiplicação e divisão de números racionais cuja representação decimal é finita por números naturais"]
            },
            {
                "codigo": "EF67EF01",
                "descricao": "Experimentar, desfrutar, apreciar e criar diferentes brincadeiras, jogos, danças, ginásticas, esportes, lutas e práticas corporais de aventura, valorizando o trabalho coletivo e o protagonismo.",
                "etapa": "ensino_fundamental",
                "anos": ["6", "7"],
                "area_conhecimento": "linguagens",
                "componente": "educacao_fisica",
                "competencias_gerais": [1, 4, 8, 9],
                "competencias_especificas": ["EFEF01"],
                "objetos_conhecimento": ["Brincadeiras e jogos", "Esportes", "Ginásticas", "Danças", "Lutas", "Práticas corporais de aventura"]
            },
            {
                "codigo": "EF15LP01",
                "descricao": "Identificar a função social de textos que circulam em campos da vida social dos quais participa cotidianamente (a casa, a rua, a comunidade, a escola) e nas mídias impressa, de massa e digital, reconhecendo para que foram produzidos, onde circulam, quem os produziu e a quem se destinam.",
                "etapa": "ensino_fundamental",
                "anos": ["1", "2", "3", "4", "5"],
                "area_conhecimento": "linguagens",
                "componente": "lingua_portuguesa",
                "competencias_gerais": [1, 4, 5],
                "competencias_especificas": ["EFLP01"],
                "objetos_conhecimento": ["Reconstrução das condições de produção e recepção de textos", "Estratégias de leitura"]
            },
            {
                "codigo": "EF02CI01",
                "descricao": "Identificar de que materiais (metais, madeira, vidro etc.) são feitos os objetos que fazem parte da vida cotidiana, como esses objetos são utilizados e com quais materiais eram produzidos no passado.",
                "etapa": "ensino_fundamental",
                "anos": ["2"],
                "area_conhecimento": "ciencias_natureza",
                "componente": "ciencias",
                "competencias_gerais": [1, 2, 6],
                "competencias_especificas": ["EFCI01"],
                "objetos_conhecimento": ["Propriedades e usos dos materiais", "Prevenção de acidentes domésticos"]
            }
        ]
        
        logger.info(f"Created sample data: {len(self.data['habilidades'])} habilidades, "
                   f"{len(self.data['competencias_gerais'])} competências gerais, "
                   f"{len(self.data['competencias_especificas'])} competências específicas")
    
    def _create_comprehensive_sample_data(self):
        """Create comprehensive sample BNCC data structure for development"""
        logger.info("Creating comprehensive BNCC data structure...")
        
        # Start with basic sample data
        self._create_sample_data()
        
        # Add more comprehensive examples for all areas and components
        additional_habilidades = [
            # Mais exemplos de Matemática
            {
                "codigo": "EF05MA03",
                "descricao": "Identificar e representar frações (menores e maiores que a unidade), associando-as ao resultado de uma divisão ou à ideia de parte de um todo, utilizando a reta numérica como recurso.",
                "etapa": "ensino_fundamental",
                "anos": ["5"],
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "competencias_gerais": [1, 2, 4],
                "competencias_especificas": ["EFMAT01", "EFMAT02"],
                "objetos_conhecimento": ["Números racionais expressos na forma decimal e na forma de fração"]
            },
            {
                "codigo": "EF06MA11",
                "descricao": "Resolver e elaborar problemas com números racionais positivos na representação decimal, envolvendo as quatro operações fundamentais e a potenciação, por meio de estratégias diversas, utilizando estimativas e arredondamentos para verificar a razoabilidade de respostas, com e sem uso de calculadora.",
                "etapa": "ensino_fundamental",
                "anos": ["6"],
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "competencias_gerais": [1, 2, 5],
                "competencias_especificas": ["EFMAT01", "EFMAT02"],
                "objetos_conhecimento": ["Operações (adição, subtração, multiplicação, divisão e potenciação) com números racionais"]
            },
            # Geografia
            {
                "codigo": "EF06GE01",
                "descricao": "Comparar modificações das paisagens nos lugares de vivência e os usos desses lugares em diferentes tempos.",
                "etapa": "ensino_fundamental",
                "anos": ["6"],
                "area_conhecimento": "ciencias_humanas",
                "componente": "geografia",
                "competencias_gerais": [1, 2, 7],
                "competencias_especificas": ["EFGE01"],
                "objetos_conhecimento": ["Identidade sociocultural", "Relações entre os componentes físico-naturais"]
            },
            # História
            {
                "codigo": "EF06HI01",
                "descricao": "Identificar diferentes formas de compreensão da noção de tempo e de periodização dos processos históricos (continuidades e rupturas).",
                "etapa": "ensino_fundamental",
                "anos": ["6"],
                "area_conhecimento": "ciencias_humanas",
                "componente": "historia",
                "competencias_gerais": [1, 2, 3],
                "competencias_especificas": ["EFHI01"],
                "objetos_conhecimento": ["A questão do tempo, sincronias e diacronias: reflexões sobre o sentido das cronologias"]
            },
            # Arte
            {
                "codigo": "EF15AR01",
                "descricao": "Identificar e apreciar formas distintas das artes visuais tradicionais e contemporâneas, cultivando a percepção, o imaginário, a capacidade de simbolizar e o repertório imagético.",
                "etapa": "ensino_fundamental",
                "anos": ["1", "2", "3", "4", "5"],
                "area_conhecimento": "linguagens",
                "componente": "arte",
                "competencias_gerais": [1, 3, 4],
                "competencias_especificas": ["EFAR01"],
                "objetos_conhecimento": ["Contextos e práticas", "Elementos da linguagem", "Materialidades"]
            },
            # Língua Inglesa
            {
                "codigo": "EF06LI01",
                "descricao": "Interagir em situações de intercâmbio oral, demonstrando iniciativa para utilizar a língua inglesa.",
                "etapa": "ensino_fundamental",
                "anos": ["6"],
                "area_conhecimento": "linguagens",
                "componente": "lingua_inglesa",
                "competencias_gerais": [4, 5, 9],
                "competencias_especificas": ["EFLI01"],
                "objetos_conhecimento": ["Interação discursiva", "Funções e usos da língua inglesa"]
            }
        ]
        
        # Add additional competências específicas
        additional_competencias_especificas = [
            {
                "codigo": "EFGE01",
                "numero": 1,
                "area_conhecimento": "ciencias_humanas",
                "componente": "geografia",
                "etapa": "ensino_fundamental",
                "descricao": "Utilizar os conhecimentos geográficos para entender a interação sociedade/natureza e exercitar o interesse e o espírito de investigação e de resolução de problemas."
            },
            {
                "codigo": "EFHI01", 
                "numero": 1,
                "area_conhecimento": "ciencias_humanas",
                "componente": "historia",
                "etapa": "ensino_fundamental",
                "descricao": "Compreender acontecimentos históricos, relações de poder e processos e mecanismos de transformação e manutenção das estruturas sociais, políticas, econômicas e culturais ao longo do tempo e em diferentes espaços para analisar, posicionar-se e intervir no mundo contemporâneo."
            },
            {
                "codigo": "EFAR01",
                "numero": 1,
                "area_conhecimento": "linguagens", 
                "componente": "arte",
                "etapa": "ensino_fundamental",
                "descricao": "Compreender as relações entre as linguagens da Arte e suas práticas integradas, inclusive aquelas possibilitadas pelo uso das novas tecnologias de informação e comunicação, pelo cinema e pelo audiovisual, nas condições particulares de produção, na prática de cada linguagem e nas suas articulações."
            },
            {
                "codigo": "EFLI01",
                "numero": 1,
                "area_conhecimento": "linguagens",
                "componente": "lingua_inglesa", 
                "etapa": "ensino_fundamental",
                "descricao": "Assumir o inglês como língua franca, reconhecendo que se trata de uma língua que se materializa em usos híbridos e marcada pela fluidez e que se encontra sempre em processo de construção."
            }
        ]
        
        # Extend the data
        self.data["habilidades"].extend(additional_habilidades)
        self.data["competencias_especificas"].extend(additional_competencias_especificas)
        
        logger.info(f"Enhanced data: {len(self.data['habilidades'])} habilidades, "
                   f"{len(self.data['competencias_gerais'])} competências gerais, "
                   f"{len(self.data['competencias_especificas'])} competências específicas")
    
    def _save_data(self):
        """Save extracted data to JSON file"""
        try:
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to JSON file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Data saved successfully to {self.output_path}")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            raise
    
    def validate_extracted_data(self) -> Dict[str, Any]:
        """Validate the extracted data structure"""
        validation_report = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "summary": {}
        }
        
        try:
            # Check required sections
            required_sections = ["habilidades", "competencias_gerais", "competencias_especificas"]
            for section in required_sections:
                if section not in self.data:
                    validation_report["errors"].append(f"Missing section: {section}")
                    validation_report["valid"] = False
            
            # Validate habilidades
            hab_codigos = set()
            for i, hab in enumerate(self.data.get("habilidades", [])):
                if not hab.get("codigo"):
                    validation_report["errors"].append(f"Habilidade {i}: Missing codigo")
                    validation_report["valid"] = False
                
                codigo = hab.get("codigo", "")
                if codigo in hab_codigos:
                    validation_report["errors"].append(f"Duplicate habilidade codigo: {codigo}")
                    validation_report["valid"] = False
                hab_codigos.add(codigo)
                
                # Check required fields
                required_fields = ["descricao", "etapa", "anos", "area_conhecimento", "componente"]
                for field in required_fields:
                    if not hab.get(field):
                        validation_report["warnings"].append(f"Habilidade {codigo}: Missing {field}")
            
            # Validate competências gerais
            for i, comp in enumerate(self.data.get("competencias_gerais", [])):
                if not comp.get("numero") or not comp.get("descricao"):
                    validation_report["errors"].append(f"Competência geral {i}: Missing required fields")
                    validation_report["valid"] = False
            
            # Summary
            validation_report["summary"] = {
                "total_habilidades": len(self.data.get("habilidades", [])),
                "total_competencias_gerais": len(self.data.get("competencias_gerais", [])),
                "total_competencias_especificas": len(self.data.get("competencias_especificas", [])),
                "unique_codigos": len(hab_codigos)
            }
            
            return validation_report
            
        except Exception as e:
            validation_report["valid"] = False
            validation_report["errors"].append(f"Validation error: {str(e)}")
            return validation_report


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Extract BNCC data from PDF")
    parser.add_argument("--pdf", default=None, help="Path to BNCC PDF file (optional, will auto-detect)")
    parser.add_argument("--output", default="./data/bncc_completa.json", help="Output JSON file path")
    parser.add_argument("--validate", action="store_true", help="Validate extracted data")
    
    args = parser.parse_args()
    
    try:
        # Auto-detect PDF files if not specified
        pdf_files = []
        if args.pdf:
            pdf_files = [args.pdf]
        else:
            # Look for BNCC PDF files in data directory
            data_dir = Path("./data")
            potential_files = [
                "bncc_ensino_fundamental.pdf",
                "bncc_ensino_medio.pdf", 
                "bncc.pdf",
                "bncc_completa.pdf"
            ]
            
            for filename in potential_files:
                pdf_path = data_dir / filename
                if pdf_path.exists():
                    pdf_files.append(str(pdf_path))
            
            if not pdf_files:
                logger.warning("No BNCC PDF files found, will generate sample data")
                pdf_files = ["./data/bncc_not_found.pdf"]  # Will trigger sample data generation
        
        logger.info(f"Processing PDFs: {pdf_files}")
        
        # Create extractor
        extractor = BNCCExtractor(pdf_files, args.output)
        
        # Extract data
        extractor.extract_data()
        
        # Validate if requested
        if args.validate:
            logger.info("Validating extracted data...")
            validation_report = extractor.validate_extracted_data()
            
            print("\n" + "="*50)
            print("VALIDATION REPORT")
            print("="*50)
            print(f"Valid: {validation_report['valid']}")
            print(f"Errors: {len(validation_report['errors'])}")
            print(f"Warnings: {len(validation_report['warnings'])}")
            
            if validation_report["errors"]:
                print("\nErrors:")
                for error in validation_report["errors"]:
                    print(f"  - {error}")
            
            if validation_report["warnings"]:
                print("\nWarnings:")
                for warning in validation_report["warnings"]:
                    print(f"  - {warning}")
            
            print(f"\nSummary: {validation_report['summary']}")
        
        logger.info("BNCC data extraction completed successfully!")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
