import json
import httpx
import pdfplumber  # <-- Biblioteca necessária instalada na venv
from pathlib import Path
from app.schemas.cnis_schema import ExtratoCNISClean

class AgentParser:
    def __init__(self, api_key: str = None, base_url: str = "http://127.0.0.1:1234/v1"):
        # Alterado para 127.0.0.1 para evitar falhas de conexão no Windows
        self.base_url = base_url

    async def parse_cnis(self, file_path: Path, cpf: str) -> ExtratoCNISClean:
        # =================================================================
        # CAMADA DE EXTRAÇÃO DE PDF REAL
        # =================================================================
        raw_text = ""
        print(f"📄 [PARSER] Abrindo e extraindo páginas do PDF: {file_path.name}")
        
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text_page = page.extract_text()
                if text_page:
                    raw_text += f"\n--- PÁGINA {i+1} ---\n" + text_page

        # Expandido o limite de leitura para acomodar o volume de dados de um CNIS real
        raw_text = raw_text[:50000] 
        # =================================================================

        system_prompt = (
            "Você é um extrator de dados JSON de precisão militar especializado no CNIS do INSS brasileiro.\n"
            "Retorne ESTRITAMENTE um objeto JSON válido que obedeça ao esquema definido. Não insira markdown além de "
            "tags de bloco json, explicações ou texto introdutório.\n"
            "Formato Mandatório:\n"
            "{\n"
            "  \"cpf\": \"11 digitos numéricos\",\n"
            "  \"nome\": \"Nome Completo\",\n"
            "  \"data_nascimento\": \"YYYY-MM-DD\",\n"
            "  \"nit\": \"Número NIT\",\n"
            "  \"vinculos\": [\n"
            "    {\n"
            "      \"identificador_vinculo\": \"id\",\n"
            "      \"empregador\": \"Razão Social\",\n"
            "      \"data_inicio\": \"YYYY-MM-DD\",\n"
            "      \"data_fim\": \"YYYY-MM-DD\" ou null,\n"
            "      \"competencias\": [],\n"
            "      \"indicadores_gerais\": []\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Texto bruto do PDF para extração:\n{raw_text}\n\nFiltrar para CPF: {cpf}"}
            ],
            "temperature": 0.0
        }

        # Timeout estendido para 180s pois o processamento de PDFs longos exige mais processamento local
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"].strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        data["cpf"] = cpf
        return ExtratoCNISClean(**data)
