import json
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
