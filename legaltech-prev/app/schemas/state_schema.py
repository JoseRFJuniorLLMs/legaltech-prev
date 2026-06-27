from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class PipelineState(BaseModel):
    cpf: str = Field(..., description="CPF do cliente em processamento")
    status: str = Field(..., description="Estado atual do pipeline (INIT, PARSED, CALCULATED, etc)")
    logs: list = Field(default_factory=list, description="Lista de logs de execução")
    
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Dados estruturados do CNIS (JSON Pydantic)")
    math_report: Optional[Dict[str, Any]] = Field(None, description="Relatório matemático de cálculos de tempo")
    enquadramento: Optional[Dict[str, Any]] = Field(None, description="Enquadramento nas regras da EC 103/2019")
    legal_insights: Optional[str] = Field(None, description="Teses jurídicas geradas pelo agente analista")
    final_output_path: Optional[str] = Field(None, description="Caminho para o documento final gerado")
    
    error_message: Optional[str] = Field(None, description="Mensagem de erro caso o pipeline colapse")
    error_trace: Optional[str] = Field(None, description="Traceback do erro para auditoria de desastre")
