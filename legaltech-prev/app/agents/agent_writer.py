from pathlib import Path
from typing import Dict, Any
import httpx

class AgentWriter:
    def __init__(self, api_key: str = None, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url

    async def generate_document(self, client_dir: Path, state: Dict[str, Any]) -> Path:
        output_path = client_dir / "outputs" / "peticao_inicial.md"
        
        system_prompt = (
            "Você é um Procurador Previdenciário Digital Sênior.\n"
            "Sua missão é materializar o documento final de Petição Inicial em formato Markdown.\n"
            "Integre a narrativa de Fatos, Fundamentos Jurídicos e Pedidos baseando-se estritamente nos números "
            "calculados pela camada determinística do Python e as sugestões formuladas pelo Agente Analista.\n"
            "Seja impositivo, formal e cite a legislação pertinente (Lei 8.213/91 e EC 103/19)."
        )

        user_content = (
            f"AUTOR: {state['math_report']['cliente_nome']}\n"
            f"CPF: {state['cpf']}\n"
            f"TEMPO DE CONTRIBUIÇÃO DETERMINADO POR PYTHON: {state['math_report']['tempo_calculado']}\n"
            f"TESES E ANOMALIAS SINALIZADAS: {state['legal_insights']}\n\n"
            "Gere a petição inicial completa agora."
        )

        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result["choices"][0]["message"]["content"])

        return output_path
