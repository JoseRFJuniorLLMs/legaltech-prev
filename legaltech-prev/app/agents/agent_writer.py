import sys
import json
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
from app.services.llm_client import LLMClient

# Root do projeto para localizar o template
ROOT = Path(__file__).resolve().parent.parent.parent

class AgentWriter:
    def __init__(self, llm: LLMClient = None, **_ignored):
        self.llm = llm or LLMClient()
        self.env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))

    async def generate_document(self, client_dir: Path, state: Dict[str, Any]) -> Path:
        output_path = client_dir / "outputs" / "peticao_inicial.md"

        # Pede ao LLM os blocos narrativos em JSON estruturado — imune a variações de formatação
        system_prompt = (
            "Você é um Procurador Previdenciário Digital Sênior.\n"
            "Retorne EXCLUSIVAMENTE um JSON válido com duas chaves: 'fatos' e 'teses'.\n"
            "- 'fatos': narrativa factual da vida laboral do segurado (2-3 parágrafos).\n"
            "- 'teses': fundamentação jurídica estratégica baseada nas anomalias e no enquadramento legal.\n"
            "PROIBIDO: inventar datas, tempo de contribuição ou declarar regras não elegíveis como elegíveis.\n"
            "Baseie-se ESTRITAMENTE nos dados do motor Python e no enquadramento legal fornecido."
        )
        user_content = (
            f"AUTOR: {state['math_report']['cliente_nome']}\n"
            f"CPF: {state['cpf']}\n"
            f"TEMPO CALCULADO PELO PYTHON: {state['math_report']['tempo_calculado']}\n"
            f"ENQUADRAMENTO LEGAL EC 103/2019: {state.get('enquadramento')}\n"
            f"INSIGHTS E ANOMALIAS DO ANALISTA: {state['legal_insights']}\n\n"
            "Gere o JSON com as chaves 'fatos' e 'teses' agora."
        )

        raw = await self.llm.chat(system_prompt, user_content, temperature=0.2, json_output=True)

        # Parse seguro: json_output=True garante que o LLM retorna JSON válido
        try:
            blocos = json.loads(raw)
            text_fatos = blocos.get("fatos", "").strip()
            text_teses = blocos.get("teses", "").strip()
        except (json.JSONDecodeError, AttributeError):
            # Fallback defensivo: se por algum motivo o JSON veio corrompido, usa texto bruto nas teses
            text_fatos = ""
            text_teses = raw.strip()

        # Pega a regra enquadrada, se houver
        enquadramento = state.get("enquadramento", {})
        cabecalho = enquadramento.get("cabecalho", {})
        regras_elegiveis = enquadramento.get("regras_elegiveis", [])
        
        regra_nome = regras_elegiveis[0] if regras_elegiveis else "Pedido Subsidiário / Sem Regra Elegível"
        regra_detalhe = next((r for r in enquadramento.get("regras", []) if r["regra"] == regra_nome), {})

        # Contexto para o Jinja2
        context = {
            "autor_nome": state["math_report"]["cliente_nome"],
            "autor_cpf": state["cpf"],
            "text_fatos": text_fatos,
            "text_teses": text_teses,
            "tempo_anos": state["math_report"]["tempo_calculado"]["anos"],
            "tempo_meses": state["math_report"]["tempo_calculado"]["meses"],
            "tempo_dias": state["math_report"]["tempo_calculado"]["dias"],
            "tempo_total_dias": state["math_report"]["tempo_calculado"]["total_dias_absolutos"],
            "idade_na_der": cabecalho.get("idade_na_der", "N/A"),
            "data_der": cabecalho.get("data_der", "N/A"),
            "vinculos": state["math_report"]["vinculos"],
            "regra_nome": regra_nome,
            "regra_artigo": regra_detalhe.get("artigo", ""),
            "regra_requisitos": regra_detalhe.get("requisitos", [])
        }

        template = self.env.get_template("peticao_inicial.md.j2")
        rendered_markdown = template.render(context)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered_markdown)
        return output_path
