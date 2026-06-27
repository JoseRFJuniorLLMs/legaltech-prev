"""Envio de e-mail: link do CNIS para o cliente e petição final para a Carolina.
Sem SMTP configurado, roda em modo dev (loga em vez de enviar) — o app funciona
de ponta a ponta sem credenciais. WhatsApp é fase 2 (Meta Business API)."""
import smtplib
import logging
import asyncio
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings


class Notifier:
    def _build_msg(self, to: str, subject: str, body: str, attachment: Optional[Path] = None) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if attachment and attachment.exists():
            msg.add_attachment(
                attachment.read_bytes(), maintype="application",
                subtype="octet-stream", filename=attachment.name)
        return msg

    def _smtp_send_sync(self, msg: EmailMessage) -> None:
        """Envio bloqueante — executado em thread separada via asyncio.to_thread."""
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
            s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASS)
            s.send_message(msg)

    async def _send(self, to: str, subject: str, body: str, attachment: Optional[Path] = None) -> Dict[str, Any]:
        # B4 Fix: SMTP é síncrono/bloqueante. Rodar em thread separada para não
        # travar o event loop do FastAPI durante o timeout do servidor de e-mail.
        if not settings.SMTP_HOST:
            logging.info("[EMAIL dev] para=%s | assunto=%s\n%s", to, subject, body)
            return {"sent": False, "mode": "dev-log", "to": to}
        msg = self._build_msg(to, subject, body, attachment)
        await asyncio.to_thread(self._smtp_send_sync, msg)
        return {"sent": True, "mode": "smtp", "to": to}

    async def send_link(self, email: str, link: str, whatsapp: Optional[str] = None) -> Dict[str, Any]:
        body = (
            "Olá! Para a análise gratuita do seu CNIS, são 2 passos rápidos:\n\n"
            "1) Baixe seu CNIS no Meu INSS: https://meu.inss.gov.br "
            "(entre com sua conta gov.br > Extratos > Extrato de Contribuição (CNIS)).\n"
            f"2) Volte e envie o PDF aqui: {link}\n\n"
            "Seus dados são apagados após a análise. Qualquer dúvida, é só responder este e-mail."
        )
        res = await self._send(email, "Seu link para enviar o CNIS", body)
        if whatsapp:
            logging.info("[WHATSAPP fase 2] enviaria link para %s: %s", whatsapp, link)
        return res

    async def send_peticao(self, lead: Dict[str, Any], peticao_path: Optional[Path]) -> Dict[str, Any]:
        body = (
            "Nova petição gerada pelo motor previdenciário.\n\n"
            f"CPF do cliente: {lead.get('cpf')}\n"
            f"Status: {lead.get('status')}\n"
            f"Resumo do enquadramento: {lead.get('resumo', '(ver anexo)')}\n\n"
            "Petição inicial em anexo (revisar antes do protocolo)."
        )
        return await self._send(
            settings.CAROLINA_EMAIL, f"Petição gerada — CPF {lead.get('cpf')}", body, peticao_path)
