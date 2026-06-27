import json
from app.schemas.cnis_schema import ExtratoCNISClean
from app.services.llm_client import LLMClient


class AgentParser:
    def __init__(self, llm: LLMClient = None, **_ignored):
        self.llm = llm or LLMClient()

    async def extract_json_from_text(self, raw_text: str, cpf: str) -> ExtratoCNISClean:
        system_prompt = (
            "Você é um extrator de dados JSON de precisão militar especializado no CNIS do INSS brasileiro.\n"
            "Retorne ESTRITAMENTE um objeto JSON válido que obedeça ao esquema definido. Sem markdown, "
            "sem explicações, sem texto introdutório.\n"
            "Formato Mandatório:\n"
            "{\n"
            "  \"cpf\": \"11 digitos numéricos\",\n"
            "  \"nome\": \"Nome Completo\",\n"
            "  \"data_nascimento\": \"YYYY-MM-DD\",\n"
            "  \"sexo\": \"M ou F se constar no extrato; caso contrário null\",\n"
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
        user_content = (
            f"Texto bruto do PDF do CNIS para extração:\n{raw_text}\n\n"
            f"Filtrar para o CPF: {cpf}"
        )

        content = await self.llm.chat(
            system_prompt, user_content, temperature=0.0, json_output=True)

        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        data["cpf"] = cpf
        return ExtratoCNISClean(**data)
