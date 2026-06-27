import asyncio
import os
import sys
import shutil
from pathlib import Path

# Configuração dinâmica de escopo de diretório (sobe para a raiz 'legaltech-prev')
raiz_projeto = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(raiz_projeto))

from app.agents.supervisor import PipelineSupervisor
from app.storage.local_storage import LocalStorageService

async def rodar_teste_pipeline_real():
    print("📢 MODO LOCAL ATIVO: Conectando ao LM Studio (127.0.0.1:1234)...")
    print("🚨 LEMBRETE: Aumente o 'Context Length' no painel direito do LM Studio para 16384 ou 32768!")

    # Dados reais do seu extrato.pdf
    cpf_teste = "64525430249"  # Seu CPF cadastrado no documento
    nome_final_pdf = "extrato_real.pdf"
    
    # O caminho exato indicado por você no ambiente Windows
    caminho_cnis_real = Path(r"D:\DEV\legaltech-prev\legaltech-prev\app\cnis\extrato.pdf")

    print("\n🚀 [INIT] Inicializando o teste com o seu CNIS Real de 7 páginas...")

    if not caminho_cnis_real.exists():
        print(f"❌ ERRO: O arquivo não foi encontrado no caminho especificado:\n   {caminho_cnis_real}")
        print("Por favor, confirme se criou a pasta 'cnis' e colocou o arquivo 'extrato.pdf' lá dentro.")
        return

    # 1. Instanciar a infraestrutura Multi-Tenant do Storage
    storage = LocalStorageService()
    diretorio_cliente = storage.get_client_dir(cpf_teste)
    pasta_docs = diretorio_cliente / "docs"
    caminho_destino = pasta_docs / nome_final_pdf

    # SIMULAÇÃO DE UPLOAD: Copia o PDF real para a área isolada do tenant (sandbox de segurança)
    print(f"📦 [STORAGE] Simulando Upload: Copiando CNIS real para a Sandbox do Cliente...")
    shutil.copy(caminho_cnis_real, caminho_destino)
    print(f"   -> Destino Seguro: {caminho_destino}")

    # 2. Instanciar o Supervisor e disparar a máquina de estados
    print("🤖 [SUPERVISOR] Ativando a esteira de agentes locais via HTTP...")
    supervisor = PipelineSupervisor()
    
    resultado = await supervisor.execute_pipeline(cpf_teste, nome_final_pdf)

    print("\n🏁 [FIM] Execução do pipeline concluída!")
    if resultado["success"]:
        print(f"🎉 Sucesso absoluto! O CNIS real foi processado sem erros de sintaxe.")
        pasta_outputs = diretorio_cliente / "outputs"
        print(f"\n📂 Verifique as entregas geradas no seu disco rígido:")
        print(f"   - Log de Auditoria Imutável: {pasta_outputs / 'pipeline_audit.json'}")
        print(f"   - Petição Inicial Pronta (Markdown): {pasta_outputs / 'peticao_inicial.md'}")
    else:
        print(f"❌ O pipeline falhou: {resultado.get('error')}")

if __name__ == "__main__":
    asyncio.run(rodar_teste_pipeline_real())