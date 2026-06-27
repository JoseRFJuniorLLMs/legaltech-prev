"""Cliente Gemini (google-genai) — substitui o LM Studio local.

Dois modos, escolhidos pelo ambiente:
  - API key (Google AI Studio):  GEMINI_API_KEY
  - Vertex AI (VM GCP, sem key):  GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT

Construção preguiçosa: só exige credencial quando há uma chamada real, para o
PipelineSupervisor poder ser instanciado (health, testes determinísticos) sem
Gemini configurado."""
import logging

from app.config import settings


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        self.model = settings.GEMINI_MODEL

    def _ensure(self):
        if self._client is None:
            from google import genai

            if settings.GEMINI_USE_VERTEX:
                self._client = genai.Client(
                    vertexai=True,
                    project=settings.GCP_PROJECT,
                    location=settings.GCP_LOCATION,
                )
                logging.info("Gemini via Vertex AI (projeto %s, %s)",
                             settings.GCP_PROJECT, self.model)
            else:
                if not settings.GEMINI_API_KEY:
                    raise RuntimeError(
                        "GEMINI_API_KEY ausente. Defina no .env, ou use Vertex AI "
                        "(GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT).")
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logging.info("Gemini via API key (modelo %s)", self.model)
        return self._client

    async def chat(self, system: str, user: str, temperature: float = 0.2,
                   json_output: bool = False, max_retries: int = 4) -> str:
        import asyncio
        from google.genai import types, errors

        client = self._ensure()
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_output else "text/plain",
        )
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = await client.aio.models.generate_content(
                    model=self.model, contents=user, config=config)
                return resp.text or ""
            except errors.ServerError as e:  # 5xx (ex.: 503 "high demand") — transitório
                last_exc = e
            except errors.ClientError as e:  # 429 (rate limit) também é transitório
                last_exc = e
                if getattr(e, "code", None) != 429:
                    raise
            if attempt < max_retries - 1:
                await asyncio.sleep(min(2 ** attempt, 8))  # backoff 1,2,4,8s
        raise last_exc
