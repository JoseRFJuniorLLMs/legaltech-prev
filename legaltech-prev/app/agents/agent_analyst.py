from typing import Dict, Any
import httpx

class AgentAnalyst:
    def __init__(self, api_key: str = None, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url

    async def analyze_case(self, math_report: Dict[str, Any]) -> str:
        system_prompt = (
            "Você é um conselheiro jurídico e cientista de dados analíticos previdenciários.\n"
            "Sua função exclusiva é avaliar o relatório computacional enviado, gerando teses e correções "
            "fundamentadas com base nos erros encontrados pela engine determinística. Não altere a contagem de "
            "tempo realizada por código Python. Seja conciso e focado na estratégia de ganho da petição."
        )
        
        user_content = f"Relatório de Cálculos e Anomalias do Motor Python:\n{math_report}"

        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()

        return result["choices"][0]["message"]["content"]
