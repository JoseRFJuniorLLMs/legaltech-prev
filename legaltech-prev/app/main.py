"""Backend FastAPI — fluxo de captação (passos 1 e 3) plugando o motor jurídico.

Fluxo:
  POST /api/leads                  cliente digita CPF (tela 1)
  POST /api/leads/{id}/contato     cliente dá e-mail/WhatsApp; gera token e envia link (tela 2)
  GET  /api/l/{token}              resolve o link que o cliente clicou
  POST /api/leads/{id}/cnis        cliente sobe o CNIS -> roda o motor -> envia peça p/ Carolina
  GET  /api/leads/{id}             status atual do lead

Rodar (a partir de D:\\DEV\\legaltech-prev\\legaltech-prev):
  ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000
"""
import re
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas.lead_schema import LeadCreateIn, ContatoIn
from app.repositories.lead_repo import LeadRepository
from app.services.notifier import Notifier
from app.storage.local_storage import LocalStorageService
from fastapi import Depends
from app.auth.gov_br import verify_gov_br_token
from app.agents.supervisor import PipelineSupervisor

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LegalTech Prev API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir ao domínio do front em produção
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = LeadRepository()
notifier = Notifier()
storage = LocalStorageService()


def _clean_cpf(cpf: str) -> str:
    c = re.sub(r"\D", "", cpf or "")
    if len(c) != 11:
        raise HTTPException(status_code=400, detail="CPF inválido. Deve conter 11 dígitos.")
    return c


@app.get("/api/health")
def health():
    return {"ok": True, "hera": repo.hera.available, "carolina": settings.CAROLINA_EMAIL}


@app.post("/api/leads")
def create_lead(body: LeadCreateIn):
    cpf = _clean_cpf(body.cpf)
    lead_id = repo.create(cpf)
    return {"lead_id": lead_id, "cpf": cpf, "status": "created"}


@app.post("/api/leads/{lead_id}/contato")
def set_contato(lead_id: str, body: ContatoIn):
    lead = repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    token = repo.set_contato(lead_id, body.email, body.whatsapp)
    link = f"{settings.BASE_URL}/enviar-cnis?token={token}"
    delivery = notifier.send_link(body.email, link, body.whatsapp)
    return {"lead_id": lead_id, "token": token, "link": link, "status": "link_sent", "envio": delivery}


@app.get("/api/l/{token}")
def resolve_token(token: str):
    lead = repo.get_by_token(token)
    if not lead:
        raise HTTPException(status_code=404, detail="Link inválido ou expirado.")
    return {"lead_id": lead["lead_id"], "cpf": lead["cpf"], "status": lead["status"]}


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: str):
    lead = repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    return lead


@app.post("/api/leads/{lead_id}/cnis")
async def upload_cnis(lead_id: str, file: UploadFile = File(...), token_data: dict = Depends(verify_gov_br_token)):
    lead = repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    cpf = lead["cpf"]

    # Bug 5 Fix: cruzar CPF do token gov.br com o CPF do lead no banco.
    # Em produção, token_data["cpf"] viria decodificado do JWT assinado pelo gov.br.
    token_cpf = re.sub(r"\D", "", token_data.get("cpf", ""))
    if token_cpf and token_cpf != cpf:
        raise HTTPException(
            status_code=403,
            detail="O CPF autenticado pelo Gov.br não corresponde ao CPF deste processo. Acesso negado."
        )

    await storage.save_uploaded_file(cpf, file, file.filename)
    repo.mark_cnis(lead_id, file.filename)

    # Dispara o motor (parser->cálculo->enquadramento->análise->redação).
    supervisor = PipelineSupervisor()
    result = await supervisor.execute_pipeline(cpf, file.filename)
    ok = bool(result.get("success"))

    if ok:
        peticao = storage.get_client_dir(cpf) / "outputs" / "peticao_inicial.md"
        notifier.send_peticao(lead, peticao if peticao.exists() else None)

    repo.mark_processed(lead_id, ok, result.get("error") or "ok")
    return {
        "lead_id": lead_id,
        "success": ok,
        "status": "processed" if ok else "failed",
        "detail": result.get("error"),
    }
