# setup_local_llm.py
from pathlib import Path

def patch_para_llm_local():
    base_dir = Path(".")
    print(f"🔄 Redirecionando os agentes para o LM Studio (Porta 1234)...")

    files_blueprint = {
        # 1. PARSER RECONFIGURADO PARA LM STUDIO
        "app/agents/agent_parser.py": '''import json
import httpx
from pathlib import Path
from app.schemas.cnis_schema import ExtratoCNISClean

class AgentParser:
    def __init__(self, api_key: str = None, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url

    async def parse_cnis(self, file_path: Path, cpf: str) -> ExtratoCNISClean:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()[:20000]

        system_prompt = (
            "Você é um extrator de dados JSON de precisão militar especializado no CNIS do INSS brasileiro.\\n"
            "Retorne ESTRITAMENTE um objeto JSON válido que obedeça ao esquema definido. Não insira markdown além de "
            "tags de bloco json, explicações ou texto introdutório.\\n"
            "Formato Mandatório:\\n"
            "{\\n"
            "  \\"cpf\\": \\"11 digitos numéricos\\",\\n"
            "  \\"nome\\": \\"Nome Completo\\",\\n"
            "  \\"data_nascimento\\": \\"YYYY-MM-DD\\",\\n"
            "  \\"nit\\": \\"Número NIT\\",\\n"
            "  \\"vinculos\\": [\\n"
            "    {\\n"
            "      \\"identificador_vinculo\\": \\"id\\",\\n"
            "      \\"empregador\\": \\"Razão Social\\",\\n"
            "      \\"data_inicio\\": \\"YYYY-MM-DD\\",\\n"
            "      \\"data_fim\\": \\"YYYY-MM-DD\\" ou null,\\n"
            "      \\"competencias\\": [],\\n"
            "      \\"indicadores_gerais\\": []\\n"
            "    }\\n"
            "  ]\\n"
            "}"
        )

        payload = {
            "model": "local-model", # O LM Studio ignora o nome e usa o que estiver carregado
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Texto bruto para extração:\\n{raw_text}\\n\\nFiltrar para CPF: {cpf}"}
            ],
            "temperature": 0.0
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
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
''',

        # 2. ANALISTA RECONFIGURADO PARA LM STUDIO
        "app/agents/agent_analyst.py": '''from typing import Dict, Any
import httpx

class AgentAnalyst:
    def __init__(self, api_key: str = None, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url

    async def analyze_case(self, math_report: Dict[str, Any]) -> str:
        system_prompt = (
            "Você é um conselheiro jurídico e cientista de dados analíticos previdenciários.\\n"
            "Sua função exclusiva é avaliar o relatório computacional enviado, gerando teses e correções "
            "fundamentadas com base nos erros encontrados pela engine determinística. Não altere a contagem de "
            "tempo realizada por código Python. Seja conciso e focado na estratégia de ganho da petição."
        )
        
        user_content = f"Relatório de Cálculos e Anomalias do Motor Python:\\n{math_report}"

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
''',

        # 3. WRITER RECONFIGURADO PARA LM STUDIO
        "app/agents/agent_writer.py": '''from pathlib import Path
from typing import Dict, Any
import httpx

class AgentWriter:
    def __init__(self, api_key: str = None, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url

    async def generate_document(self, client_dir: Path, state: Dict[str, Any]) -> Path:
        output_path = client_dir / "outputs" / "peticao_inicial.md"
        
        system_prompt = (
            "Você é um Procurador Previdenciário Digital Sênior.\\n"
            "Sua missão é materializar o documento final de Petição Inicial em formato Markdown.\\n"
            "Integre a narrativa de Fatos, Fundamentos Jurídicos e Pedidos baseando-se estritamente nos números "
            "calculados pela camada determinística do Python e as sugestões formuladas pelo Agente Analista.\\n"
            "Seja impositivo, formal e cite a legislação pertinente (Lei 8.213/91 e EC 103/19)."
        )

        user_content = (
            f"AUTOR: {state['math_report']['cliente_nome']}\\n"
            f"CPF: {state['cpf']}\\n"
            f"TEMPO DE CONTRIBUIÇÃO DETERMINADO POR PYTHON: {state['math_report']['tempo_calculado']}\\n"
            f"TESES E ANOMALIAS SINALIZADAS: {state['legal_insights']}\\n\\n"
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
''',

        # 4. TEST_RUN ATUALIZADO SEM PASSAGEM DE CHAVE OBRIGATÓRIA
        "app/test/test_run.py": '''import asyncio
import os
import sys
from pathlib import Path

raiz_projeto = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(raiz_projeto))

from app.agents.supervisor import PipelineSupervisor
from app.storage.local_storage import LocalStorageService

async def rodar_teste_pipeline():
    print("📢 MODO LOCAL ATIVO: Direcionando requisições para o LM Studio (Porta 1234)...")

    cpf_teste = "64525430249"
    nome_ficheiro_cnis = "cnis_bruto_teste.txt"

    print("🚀 [INIT] Inicializando o teste do Pipeline Multiagentes...")

    storage = LocalStorageService()
    diretorio_cliente = storage.get_client_dir(cpf_teste)
    pasta_docs = diretorio_cliente / "docs"
    caminho_cnis_mock = pasta_docs / nome_ficheiro_cnis

    conteudo_cnis_mock = """
    REPUBLICA FEDERATIVA DO BRASIL
    SISTEMA DE INFORMAÇÕES DO SISTEMA PREVIDENCIÁRIO (CNIS)
    EXTRATO DE CONTRIBUIÇÕES PREVIDENCIÁRIAS
    
    DADOS DO SEGURADO:
    NOME: JOSÉ RIBAMAR FERREIRA JUNIOR
    CPF: 645.254.302-49
    DATA NASCIMENTO: 15/05/1985
    NIT: 1.634.972
    
    --------------------------------------------------
    RELAÇÕES PREVIDENCIÁRIAS:
    
    VÍNCULO N.º 1
    EMPREGADOR: INSTITUTO NACIONAL DO SEGURO SOCIAL
    CARGO: TECNICO DO SEGURO SOCIAL
    DATA INÍCIO: 01/02/2010
    DATA FIM: 
    INDICADORES: PEXT
    
    COMPETÊNCIAS:
    01/2026 - R$ 6.452,54
    02/2026 - R$ 6.452,54
    03/2026 - R$ 6.452,54
    """

    with open(caminho_cnis_mock, "w", encoding="utf-8") as f:
        f.write(conteudo_cnis_mock.strip())

    print(f"✅ [STORAGE] Ficheiro CNIS de teste gerado em: {caminho_cnis_mock}")

    print("🤖 [SUPERVISOR] Ativando equipe de agentes via HTTP Local...")
    supervisor = PipelineSupervisor(anthropic_api_key="local-bypass")
    
    resultado = await supervisor.execute_pipeline(cpf_teste, nome_ficheiro_cnis)

    print("\n🏁 [FIM] Execução do pipeline concluída!")
    if resultado["success"]:
        print(f"🎉 Sucesso absoluto! Estado final do processo: {resultado['status']}")
        pasta_outputs = diretorio_cliente / "outputs"
        print(f"   - Relatório de Auditoria: {pasta_outputs / 'pipeline_audit.json'}")
        print(f"   - Peça Jurídica Final (Markdown): {pasta_outputs / 'peticao_inicial.md'}")
    else:
        print(f"❌ O pipeline falhou: {resultado.get('error')}")

if __name__ == "__main__":
    asyncio.run(rodar_teste_pipeline())
'''
    }

    for filepath, content in files_blueprint.items():
        full_path = base_dir / filepath
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"  ⚡ Atualizado para Local: {filepath}")

    print("\n✅ Agentes reconfigurados com sucesso!")

if __name__ == "__main__":
    patch_para_llm_local()