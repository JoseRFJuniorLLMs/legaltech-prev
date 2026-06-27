from typing import Dict, Any
from app.services.llm_client import LLMClient


class AgentAnalyst:
    def __init__(self, llm: LLMClient = None, **_ignored):
        self.llm = llm or LLMClient()

    async def analyze_case(self, math_report: Dict[str, Any], enquadramento: Dict[str, Any] = None) -> str:
        system_prompt = (
            "Você é um conselheiro jurídico e cientista de dados analíticos previdenciários.\n"
            "Sua função exclusiva é avaliar o relatório computacional e o ENQUADRAMENTO LEGAL já decidido pela "
            "engine determinística (Python), gerando teses e estratégia. REGRAS RÍGIDAS:\n"
            "1. NÃO altere a contagem de tempo nem a elegibilidade — quem decide é o Python.\n"
            "2. NÃO declare elegível uma regra marcada como inelegível, nem vice-versa.\n"
            "3. Priorize a(s) regra(s) em 'regras_elegiveis'; se vazio, explique o que falta e a melhor estratégia.\n"
            "Seja conciso e focado na estratégia de ganho da petição."
        )
        user_content = (
            f"Relatório de Cálculos e Anomalias do Motor Python:\n{math_report}\n\n"
            f"Enquadramento determinístico (EC 103/2019) — NÃO contrarie:\n{enquadramento}"
        )
        return await self.llm.chat(system_prompt, user_content, temperature=0.1)
