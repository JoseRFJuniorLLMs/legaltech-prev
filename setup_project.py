# setup_project.py
import os
from pathlib import Path

def create_project():
    base_dir = Path("legaltech-prev")
    print(f"📦 Inicializando criação do ecossistema legaltech-prev em: {base_dir.resolve()}")
    
    # Definição do conteúdo de cada arquivo do sistema com separação estrita de escopo
    files_blueprint = {
        # 1. CONTRATO DE DADOS PYDANTIC
        "app/schemas/cnis_schema.py": '''from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class Competencia(BaseModel):
    competencia: str = Field(..., description="Formato MM/AAAA")
    recolhimento: float = Field(..., description="Valor recolhido em Reais")
    indicadores: List[str] = Field(default=[], description="Ex: PEXT, AVISO, IREC-LC123")

class VinculoEmpregaticio(BaseModel):
    identificador_vinculo: str
    empregador: str
    data_inicio: date = Field(..., description="ISO Format YYYY-MM-DD")
    data_fim: Optional[date] = Field(None, description="ISO Format YYYY-MM-DD. None se vínculo em aberto")
    competencias: List[Competencia] = Field(default=[])
    indicadores_gerais: List[str] = Field(default=[])

class ExtratoCNISClean(BaseModel):
    cpf: str = Field(..., pattern=r"^\\\\d{11}$")
    nome: str
    data_nascimento: date
    nit: str
    vinculos: List[VinculoEmpregaticio]
''',

        # 2. CAMADA DE INFRAESTRUTURA COMPARTIMENTADA (MULTI-TENANT)
        "app/storage/local_storage.py": '''import os
import re
from pathlib import Path
from fastapi import HTTPException, UploadFile

class LocalStorageService:
    def __init__(self, base_dir: str = "/tmp/legaltech_storage"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_cpf(self, cpf: str) -> str:
        sanitized = re.sub(r"\\\\D", "", cpf)
        if len(sanitized) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido. Deve conter 11 dígitos numéricos.")
        return sanitized

    def get_client_dir(self, cpf: str) -> Path:
        sanitized_cpf = self._sanitize_cpf(cpf)
        client_path = (self.base_dir / sanitized_cpf).resolve()
        
        # Guardião contra ataques de Path Traversal (../)
        if not str(client_path).startswith(str(self.base_dir)):
            raise HTTPException(status_code=403, detail="Violação de segurança detectada no Path.")
        
        client_path.mkdir(exist_ok=True)
        (client_path / "docs").mkdir(exist_ok=True)
        (client_path / "outputs").mkdir(exist_ok=True)
        return client_path

    async def save_uploaded_file(self, cpf: str, file: UploadFile, filename: str) -> Path:
        client_dir = self.get_client_dir(cpf)
        target_path = client_dir / "docs" / filename
        
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            os.replace(temp_path, target_path) # Escrita atômica segura
            return target_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(status_code=500, detail=f"Erro crítico de I/O atômico: {str(e)}")
''',

        # 3. MOTOR DE CÁLCULO E DETECÇÃO DE ANOMALIAS (100% DETERMINÍSTICO EM PYTHON)
        "app/services/time_calculator.py": '''from datetime import date
from typing import Dict, Any
from app.schemas.cnis_schema import ExtratoCNISClean

class TimeCalculatorService:
    def compute_legal_time(self, cnis: ExtratoCNISClean) -> Dict[str, Any]:
        total_days = 0
        anomalies = []
        vinculos_processados = []

        for v in cnis.vinculos:
            d_inicio = v.data_inicio
            d_fim = v.data_fim
            
            # Captura de anomalia imposta por vínculo sem baixa no sistema do INSS
            if d_fim is None:
                anomalies.append({
                    "tipo": "DATA_FIM_AUSENTE",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": "Vínculo ativo ou sem encerramento formalizado no CNIS. Exige tese fática."
                })
                d_fim = date.today() # Teto de cálculo preventivo

            delta_days = (d_fim - d_inicio).days + 1
            total_days += delta_days
            
            vinculos_processados.append({
                "id": v.identificador_vinculo,
                "empregador": v.empregador,
                "dias_contados": delta_days,
                "indicadores": v.indicadores_gerais
            })

        # Conversão padronizada pela Lei Ordinária 8.213/91 (Ano Comercial de 365 dias)
        anos = total_days // 365
        restante_dias = total_days % 365
        meses = restante_dias // 30
        dias = restante_dias % 30

        return {
            "cliente_nome": cnis.nome,
            "cpf": cnis.cpf,
            "tempo_calculado": {
                "anos": anos,
                "meses": meses,
                "dias": dias,
                "total_dias_absolutos": total_days
            },
            "vinculos": vinculos_processados,
            "anomalies_detected": anomalies
        }
''',

        # 4. AGENTE PARSER (EXTRAÇÃO ASSISTIDA DO CNIS BRUTO PARA PYDANTIC VIA CLAUDE)
        "app/agents/agent_parser.py": '''import json
from pathlib import Path
from anthropic import Anthropic
from app.schemas.cnis_schema import ExtratoCNISClean

class AgentParser:
    def __init__(self, api_key: str = None):
        self.client = Anthropic(api_key=api_key)

    async def parse_cnis(self, file_path: Path, cpf: str) -> ExtratoCNISClean:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()[:20000] # Buffer controlado de leitura textual

        system_prompt = (
            "Você é um extrator de dados JSON de precisão militar especializado no CNIS do INSS brasileiro.\\n"
            "Retorne ESTRITAMENTE um objeto JSON válido que obedeça ao esquema definido. Não insira markdown além de "
            "tags de bloco json, explicações ou texto introdutório.\\n"
            "Formato Mandatório:\\n"
            "{\\n"
            "  \\"cpf\\": \\"11 digitos numéricos\\",\\n"
            "  \\"nome\\": \\"Nome Completo\\",\\n"
            "  \\"data_nascimento\\": \\"YYYY-MM-DD\\",\\n"
            "  \\"nit\\": \\"Número NIT\\",\\n"
            "  \\"vinculos\\": [\\n"
            "    {\\n"
            "      \\"identificador_vinculo\\": \\"id\\",\\n"
            "      \\"empregador\\": \\"Razão Social\\",\\n"
            "      \\"data_inicio\\": \\"YYYY-MM-DD\\",\\n"
            "      \\"data_fim\\": \\"YYYY-MM-DD\\" ou null,\\n"
            "      \\"competencias\\": [],\\n"
            "      \\"indicadores_gerais\\": []\\n"
            "    }\\n"
            "  ]\\n"
            "}"
        )

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.0, # Determinismo na extração sintática
            system=system_prompt,
            messages=[{"role": "user", "content": f"Texto bruto para extração:\\n{raw_text}\\n\\nFiltrar para CPF: {cpf}"}]
        )
        
        content = response.content[0].text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        data["cpf"] = cpf # Trava de Segurança Multi-Tenant
        return ExtratoCNISClean(**data)
''',

        # 5. AGENTE ANALISTA JURÍDICO (INTERPRETAÇÃO COGNITIVA SEM ERRO MATEMÁTICO)
        "app/agents/agent_analyst.py": '''from typing import Dict, Any
from anthropic import Anthropic

class AgentAnalyst:
    def __init__(self, api_key: str = None):
        self.client = Anthropic(api_key=api_key)

    async def analyze_case(self, math_report: Dict[str, Any]) -> str:
        system_prompt = (
            "Você é um conselheiro jurídico e cientista de dados analíticos previdenciários.\\n"
            "Sua função exclusiva é avaliar o relatório computacional enviado, gerando teses e correções "
            "fundamentadas com base nos erros encontrados pela engine determinística. Não altere a contagem de "
            "tempo realizada por código Python. Seja conciso e focado na estratégia de ganho da petição."
        )
        
        user_content = f"Relatório de Cálculos e Anomalias do Motor Python:\\n{math_report}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        
        return response.content[0].text
''',

        # 6. AGENTE REDATOR DE PEÇAS (GERADOR EXCLUSIVO DA NARRATIVA JURÍDICA EM TEMPLATE)
        "app/agents/agent_writer.py": '''from pathlib import Path
from typing import Dict, Any
from anthropic import Anthropic

class AgentWriter:
    def __init__(self, api_key: str = None):
        self.client = Anthropic(api_key=api_key)

    async def generate_document(self, client_dir: Path, state: Dict[str, Any]) -> Path:
        output_path = client_dir / "outputs" / "peticao_inicial.md"
        
        system_prompt = (
            "Você é um Procurador Previdenciário Digital Sênior.\\n"
            "Sua missão é materializar o documento final de Petição Inicial em formato Markdown. "
            "Integre a narrativa de Fatos, Fundamentos Jurídicos e Pedidos baseando-se estritamente nos números "
            "calculados pela camada determinística do Python e as sugestões formuladas pelo Agente Analista.\\n"
            "Seja impositivo, formal e cite a legislação pertinente (Lei 8.213/91 e EC 103/19)."
        )

        user_content = (
            f"AUTOR: {state['math_report']['cliente_nome']}\\n"
            f"CPF: {state['cpf']}\\n"
            f"TEMPO DE CONTRIBUIÇÃO DETERMINADO POR PYTHON: {state['math_report']['tempo_calculado']}\\n"
            f"TESES E ANOMALIAS SINALIZADAS: {state['legal_insights']}\\n\\n"
            "Gere a petição inicial completa agora."
        )

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.content[0].text)

        return output_path
''',

        # 7. SUPERVISOR GERAL (MÁQUINA DE ESTADO COM DRIVER NATIVO HERACLITUSDB INTEGRADO)
        "app/agents/supervisor.py": '''import json
import logging
from typing import Dict, Any
from pathlib import Path
from app.storage.local_storage import LocalStorageService
from app.agents.agent_parser import AgentParser
from app.services.time_calculator import TimeCalculatorService
from app.agents.agent_analyst import AgentAnalyst
from app.agents.agent_writer import AgentWriter

# Tentativa de inicialização do driver nativo do HeraclitusDB do ecossistema do autor
try:
    import heraclitusdb
    HAS_HERACLITUS = True
except ImportError:
    HAS_HERACLITUS = False

class PipelineSupervisor:
    def __init__(self, anthropic_api_key: str = None, hdb_endpoint: str = "127.0.0.1:7474"):
        self.storage = LocalStorageService()
        self.parser_agent = AgentParser(api_key=anthropic_api_key)
        self.calculator = TimeCalculatorService()
        self.analyst_agent = AgentAnalyst(api_key=anthropic_api_key)
        self.writer_agent = AgentWriter(api_key=anthropic_api_key)
        
        if HAS_HERACLITUS:
            try:
                self.db = heraclitusdb.connect(hdb_endpoint)
                logging.info("HeraclitusDB acoplado com sucesso. Ativando imunidade contra fraude retroativa.")
            except Exception as e:
                logging.warning(f"HeraclitusDB offline no endpoint {hdb_endpoint}. Operando com fallback determinístico local: {e}")
                self.db = None
        else:
            self.db = None

    def _persist_ledger(self, event_type: str, text: str, meta: Dict[str, Any]):
        """Garante persistência append-only immutável se HeraclitusDB ativo; fallback em logger"""
        if self.db:
            try:
                self.db.append(event_type, text, attrs=meta)
                return
            except Exception:
                pass
        logging.info(f"[{event_type}] {text} -> Metadata: {meta}")

    async def execute_pipeline(self, cpf: str, cnis_filename: str) -> Dict[str, Any]:
        state: Dict[str, Any] = {"cpf": cpf, "status": "INIT", "logs": []}
        self._persist_ledger("PipelineEvent", f"Inicialização da State Machine para o CPF {cpf}", {"status": "INIT"})
        
        try:
            # Fase 1: Isolamento de Disco
            client_dir = self.storage.get_client_dir(cpf)
            cnis_path = client_dir / "docs" / cnis_filename
            state["status"] = "STORAGE_RESOLVED"
            self._persist_ledger("PipelineEvent", "Isolamento multi-tenant de storage estruturado.", {"status": "STORAGE_RESOLVED"})
            
            # Fase 2: Parsing Baseado em Esquema Estrito
            structured_cnis = await self.parser_agent.parse_cnis(cnis_path, cpf)
            state["structured_data"] = structured_cnis.model_dump()
            state["status"] = "PARSED"
            self._persist_ledger("PipelineEvent", "Documento bruto convertido em dados tipados sob contrato Pydantic.", {"status": "PARSED"})
            
            # Fase 3: Processamento Matemático Frio em Python
            math_report = self.calculator.compute_legal_time(structured_cnis)
            state["math_report"] = math_report
            state["status"] = "CALCULATED"
            self._persist_ledger("PipelineEvent", "Cálculo do tempo de contribuição efetuado sem delegação probabilística.", {"status": "CALCULATED"})
            
            # Fase 4: Análise Cognitiva Assistida por IA
            legal_insights = await self.analyst_agent.analyze_case(math_report)
            state["legal_insights"] = legal_insights
            state["status"] = "ANALYZED"
            self._persist_ledger("PipelineEvent", "Geração de teses jurídicas interpretativas via Claude Analyst finalizada.", {"status": "ANALYZED"})
            
            # Fase 5: Redação da Peça através de Injeção de Estruturas
            final_doc_path = await self.writer_agent.generate_document(client_dir, state)
            state["final_output_path"] = str(final_doc_path)
            state["status"] = "COMPLETED"
            self._persist_ledger("PipelineEvent", f"Petição Inicial gravada com sucesso em {final_doc_path}.", {"status": "COMPLETED"})
            
            # Persistência local do Log de Auditoria Clássico
            with open(client_dir / "outputs" / "pipeline_audit.json", "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4, default=str)
                
            if self.db:
                self.db.verify() # Executa verificação de hash blake3 na cadeia Merkle do HeraclitusDB
                
            return {"success": True, "output_path": str(final_doc_path), "status": "COMPLETED"}
            
        except Exception as e:
            state["status"] = "FAILED"
            state["error_trace"] = str(e)
            self._persist_ledger("PipelineError", f"Falha catastrófica disparada no Pipeline: {str(e)}", {"status": "FAILED"})
            
            # Força gravação de desastre local
            try:
                with open(self.storage.get_client_dir(cpf) / "outputs" / "pipeline_audit.json", "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=4, default=str)
            except Exception:
                pass
                
            return {"success": False, "error": str(e), "status": "FAILED"}
''',

        # 8. REQUIREMENTS.TXT
        "requirements.txt": '''fastapi>=0.100.0
uvicorn>=0.22.0
pydantic>=2.0.0
anthropic>=0.5.0
python-multipart>=0.0.6
'''
    }

    # Execução e gravação em árvore
    for filepath, content in files_blueprint.items():
        full_path = base_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"  ✅ Gravado: {filepath}")

    print("\n🚀 Instalação concluída com sucesso! Para rodar seu ambiente execute:")
    print(f"  cd {base_dir}")
    print("  pip install -r requirements.txt")
    print("\nO módulo Supervisor está configurado com os drivers nativos do HeraclitusDB.")

if __name__ == "__main__":
    create_project()