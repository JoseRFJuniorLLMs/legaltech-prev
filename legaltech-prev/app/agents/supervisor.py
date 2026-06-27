import json
import logging
import traceback  # <-- Biblioteca nativa para capturar a linha exata e o motivo da falha
from typing import Dict, Any
from pathlib import Path
from app.storage.local_storage import LocalStorageService
from app.agents.agent_parser import AgentParser
from app.services.cnis_parser_service import CnisParserService
from app.services.time_calculator import TimeCalculatorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.agents.agent_analyst import AgentAnalyst
from app.agents.agent_writer import AgentWriter
from app.services.llm_client import LLMClient
from app.services.previdencia_rules import PrevidenciaRulesService
from app.schemas.state_schema import PipelineState
from datetime import date

# Tentativa de inicialização do driver nativo do HeraclitusDB do ecossistema do autor
try:
    import heraclitusdb
    HAS_HERACLITUS = True
except ImportError:
    HAS_HERACLITUS = False

class PipelineSupervisor:
    def __init__(self, hdb_endpoint: str = "127.0.0.1:7474"):
        """Inicializa todos os serviços e tenta acoplar o HeraclitusDB. Todas as
        credenciais são lidas do .env via LLMClient / Settings."""
        self.storage = LocalStorageService()
        self.llm = LLMClient()
        self.parser_agent = AgentParser(llm=self.llm)
        self.cnis_parser_service = CnisParserService(self.parser_agent)
        self.calculator = TimeCalculatorService()
        self.anomaly_detector = AnomalyDetectorService()
        self.analyst_agent = AgentAnalyst(llm=self.llm)
        self.writer_agent = AgentWriter(llm=self.llm)
        self.rules = PrevidenciaRulesService()

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
        state = PipelineState(cpf=cpf, status="INIT")
        
        print(f"\n🚀 [SUPERVISOR] Inicializando State Machine do Pipeline para o CPF: {cpf}")
        self._persist_ledger("PipelineEvent", f"Inicialização da State Machine para o CPF {cpf}", {"status": "INIT"})
        
        try:
            # -----------------------------------------------------------------
            # Fase 1: Isolamento de Disco
            # -----------------------------------------------------------------
            print("📦 [SUPERVISOR] Executando Fase 1: Isolamento de Storage Multi-Tenant...")
            client_dir = self.storage.get_client_dir(cpf)
            cnis_path = client_dir / "docs" / cnis_filename
            state.status = "STORAGE_RESOLVED"
            self._persist_ledger("PipelineEvent", "Isolamento multi-tenant de storage estruturado.", {"status": "STORAGE_RESOLVED"})
            print(f"   -> Sandbox isolada criada com sucesso em: {client_dir}")

            # -----------------------------------------------------------------
            # Fase 2: Parsing Baseado em Esquema Estrito
            # -----------------------------------------------------------------
            print("🤖 [SUPERVISOR] Executando Fase 2: Acionando Agente Parser (Extração Estruturada)...")
            print(f"   -> Enviando arquivo de entrada: {cnis_path.name}")
            structured_cnis = await self.cnis_parser_service.parse(cnis_path, cpf)
            state.structured_data = structured_cnis.model_dump()
            state.status = "PARSED"
            self._persist_ledger("PipelineEvent", "Documento bruto convertido em dados tipados sob contrato Pydantic.", {"status": "PARSED"})
            print("   -> Fase de Parsing concluída! Dados convertidos para Pydantic Clean com sucesso.")

            # -----------------------------------------------------------------
            # Fase 3: Processamento Matemático Frio em Python
            # -----------------------------------------------------------------
            print("🧮 [SUPERVISOR] Executando Fase 3: Calculando Tempo de Contribuição Determinístico...")
            math_report = self.calculator.compute_legal_time(structured_cnis)
            
            indicator_anomalies = self.anomaly_detector.detect_anomalies(structured_cnis)
            math_report["anomalies_detected"].extend(indicator_anomalies)

            state.math_report = math_report
            state.status = "CALCULATED"
            self._persist_ledger("PipelineEvent", "Cálculo do tempo de contribuição efetuado sem delegação probabilística.", {"status": "CALCULATED"})
            print(f"   -> Tempo Computado: {math_report.get('tempo_calculado')}")
            print(f"   -> Inconsistências mapeadas: {len(math_report.get('anomalies_detected', []))} anomalias encontradas.")

            # -----------------------------------------------------------------
            # Fase 3.5: Enquadramento Legal Determinístico (EC 103/2019)
            # -----------------------------------------------------------------
            print("⚖️ [SUPERVISOR] Executando Fase 3.5: Enquadrando nas regras de transição (EC 103/2019)...")
            dias_reforma = self.calculator.dias_contribuicao_ate(structured_cnis, date(2019, 11, 13))
            enquadramento = self.rules.enquadrar(structured_cnis, math_report, dias_ate_reforma=dias_reforma)
            state.enquadramento = enquadramento
            state.status = "ENQUADRADO"
            self._persist_ledger("PipelineEvent", "Enquadramento determinístico nas regras da EC 103/2019.", {"status": "ENQUADRADO"})
            print(f"   -> Regras elegíveis: {enquadramento.get('regras_elegiveis') or 'NENHUMA (verificar avisos)'}")
            for aviso in enquadramento.get("cabecalho", {}).get("avisos", []):
                print(f"   ⚠️  {aviso}")

            # -----------------------------------------------------------------
            # Fase 4: Análise Cognitiva Assistida por IA
            # -----------------------------------------------------------------
            print("🧠 [SUPERVISOR] Executando Fase 4: Acionando Agente Analista (Interpretação Qualitativa)...")
            legal_insights = await self.analyst_agent.analyze_case(math_report, enquadramento)
            state.legal_insights = legal_insights
            state.status = "ANALYZED"
            self._persist_ledger("PipelineEvent", "Geração de teses jurídicas interpretativas via Claude Analyst finalizada.", {"status": "ANALYZED"})
            print("   -> Teses e fundamentações geradas com base jurídica estável.")

            # -----------------------------------------------------------------
            # Fase 5: Redação da Peça através de Injeção de Estruturas
            # -----------------------------------------------------------------
            print("📝 [SUPERVISOR] Executando Fase 5: Acionando Agente Writer (Materialização da Petição)...")
            final_doc_path = await self.writer_agent.generate_document(client_dir, state.model_dump())
            state.final_output_path = str(final_doc_path)
            state.status = "COMPLETED"
            self._persist_ledger("PipelineEvent", f"Petição Inicial gravada com sucesso em {final_doc_path}.", {"status": "COMPLETED"})
            print(f"   -> Sucesso! Petição Inicial gravada em formato físico Markdown: {final_doc_path.name}")

            # Persistência local do Log de Auditoria Clássico
            print("💾 [SUPERVISOR] Salvando Log de Auditoria na Sandbox local...")
            with open(client_dir / "outputs" / "pipeline_audit.json", "w", encoding="utf-8") as f:
                json.dump(state.model_dump(), f, indent=4, default=str)
                
            if self.db:
                print("🔗 [SUPERVISOR] Executando validação de hash blake3 na cadeia Merkle...")
                self.db.verify() # Executa verificação de hash blake3 na cadeia Merkle do HeraclitusDB
                
            print("🏁 [SUPERVISOR] Execução da esteira finalizada com sucesso absoluto!")
            return {"success": True, "output_path": str(final_doc_path), "status": "COMPLETED"}
            
        except Exception as e:
            # -----------------------------------------------------------------
            # CAPTURA AVANÇADA DE ERROS E CRASH LOGS
            # -----------------------------------------------------------------
            rastro_completo = traceback.format_exc()
            
            print("\n❌ [SUPERVISOR CRITICAL ERROR] O Pipeline colapsou internamente!")
            print(f"⚠️ Motivo: {str(e)}")
            print("-----------------------------------------------------------------")
            print(rastro_completo)
            print("-----------------------------------------------------------------")

            state.status = "FAILED"
            state.error_message = str(e)
            state.error_trace = rastro_completo
            
            self._persist_ledger("PipelineError", f"Falha catastrófica disparada no Pipeline: {str(e)}", {"status": "FAILED", "trace": rastro_completo})
            
            # Força gravação de desastre local contendo o rastro de depuração
            try:
                print("💾 [SUPERVISOR] Registrando rastro do colapso no pipeline_audit.json de desastre...")
                with open(self.storage.get_client_dir(cpf) / "outputs" / "pipeline_audit.json", "w", encoding="utf-8") as f:
                    json.dump(state.model_dump(), f, indent=4, default=str)
            except Exception:
                pass
                
            return {
                "success": False, 
                "error": str(e), 
                "trace": rastro_completo, 
                "status": "FAILED"
            }