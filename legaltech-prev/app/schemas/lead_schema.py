from pydantic import BaseModel, Field
from typing import Optional


class LeadCreateIn(BaseModel):
    cpf: str = Field(..., description="CPF do segurado (com ou sem máscara)")


class ContatoIn(BaseModel):
    email: str = Field(..., description="E-mail para receber o link do CNIS")
    whatsapp: Optional[str] = Field(None, description="WhatsApp (fase 2 do envio)")
