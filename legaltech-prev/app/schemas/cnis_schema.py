from pydantic import BaseModel, Field
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
    cpf: str = Field(..., pattern=r"^\\d{11}$")
    nome: str
    data_nascimento: date
    nit: str
    vinculos: List[VinculoEmpregaticio]
