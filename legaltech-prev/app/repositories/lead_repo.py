"""Repositório de leads — event-sourced sobre o HeraclitusDB (mesma filosofia
append-only da memória do Claude). Cada passo do funil é um EVENTO; o estado
atual do lead é a dobra dos eventos por LSN. Fallback local em JSONL se o Hera
estiver indisponível, para o app rodar em dev."""
import json
import time
import secrets
import logging
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.config import settings
from app.services.hera_client import HeraClient

GEN = settings.GENERATED_BY
# campos do estado que dobramos a partir dos eventos
_STATE_KEYS = ("lead_id", "cpf", "email", "whatsapp", "token", "cnis_file", "status", "resumo")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LeadRepository:
    def __init__(self, hera: Optional[HeraClient] = None) -> None:
        self.hera = hera or HeraClient()
        self.fallback_path = Path("/tmp/legaltech_storage/_leads/leads_events.jsonl").resolve()
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------- escrita
    def _append(self, kind: str, content: str, attrs: Dict[str, str]) -> int:
        attrs = {**attrs, "generated_by": GEN, "ts": _now()}
        if self.hera.available:
            try:
                return self.hera.append(kind, content, attrs)
            except Exception as e:  # noqa: BLE001
                logging.warning("Hera append falhou (%s); usando fallback JSON.", e)
        rec = {"kind": kind, "content": content, "attrs": attrs, "lsn": int(time.time() * 1000)}
        with open(self.fallback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec["lsn"]

    # ----------------------------------------------------------------- leitura
    def _events_by(self, key: str, value: str) -> List[Dict[str, Any]]:
        # key/value aqui são sempre gerados pelo servidor (lead_id hex, token urlsafe),
        # sem aspas — interpolação segura no GQL.
        if self.hera.available:
            try:
                gql = f'MATCH (n) WHERE n.generated_by = "{GEN}" AND n.{key} = "{value}" RETURN n'
                return self.hera.query(gql)
            except Exception as e:  # noqa: BLE001
                logging.warning("Hera query falhou (%s); usando fallback JSON.", e)
        rows: List[Dict[str, Any]] = []
        if self.fallback_path.exists():
            for line in self.fallback_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                a = r.get("attrs", {})
                if a.get(key) == value:
                    rows.append({**a, "content": r.get("content"), "lsn": r.get("lsn")})
        return rows

    def _fold(self, events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not events:
            return None
        events = sorted(events, key=lambda r: r.get("lsn", 0))
        state: Dict[str, Any] = {}
        for e in events:
            for k in _STATE_KEYS:
                if e.get(k) not in (None, ""):
                    state[k] = e[k]
        return state or None

    # ------------------------------------------------------------------ API
    def create(self, cpf: str) -> str:
        lead_id = uuid4().hex[:12]
        self._append("LeadCreated", f"lead {lead_id} criado", {
            "lead_id": lead_id, "cpf": cpf, "status": "created"})
        return lead_id

    def set_contato(self, lead_id: str, email: str, whatsapp: Optional[str]) -> str:
        token = secrets.token_urlsafe(16)
        self._append("LeadContato", f"contato do lead {lead_id}", {
            "lead_id": lead_id, "email": email, "whatsapp": whatsapp or "",
            "token": token, "status": "link_sent"})
        return token

    def mark_cnis(self, lead_id: str, filename: str) -> None:
        self._append("LeadCnis", f"cnis recebido do lead {lead_id}", {
            "lead_id": lead_id, "cnis_file": filename, "status": "cnis_received"})

    def mark_processed(self, lead_id: str, ok: bool, resumo: str) -> None:
        self._append("LeadProcessed", f"pipeline do lead {lead_id}", {
            "lead_id": lead_id, "status": "processed" if ok else "failed",
            "resumo": (resumo or "")[:500]})

    def get(self, lead_id: str) -> Optional[Dict[str, Any]]:
        return self._fold(self._events_by("lead_id", lead_id))

    def get_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        events = self._events_by("token", token)
        folded = self._fold(events)
        if not folded:
            return None
        return self.get(folded["lead_id"])
