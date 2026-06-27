# app_interface.py
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# CORREÇÃO CRÍTICA DE PATH (RESOLVE O MODULENOTFOUNDERROR)
# -----------------------------------------------------------------------------
caminho_atual = Path(__file__).resolve().parent

# Verifica se a pasta 'app' está na raiz atual ou dentro da subpasta do repositório
if (caminho_atual / "app").exists():
    raiz_projeto = caminho_atual
elif (caminho_atual / "legaltech-prev" / "app").exists():
    raiz_projeto = caminho_atual / "legaltech-prev"
else:
    raiz_projeto = caminho_atual

# Injeta com prioridade máxima (posição 0) no barramento de busca do Python
if str(raiz_projeto) not in sys.path:
    sys.path.insert(0, str(raiz_projeto))
# -----------------------------------------------------------------------------

import streamlit as st
import asyncio
import json
import os

from app.agents.supervisor import PipelineSupervisor
from app.storage.local_storage import LocalStorageService

# Configuração da página do Streamlit
st.set_page_config(
    page_title="LegalTech Prev - Motor Previdenciário IA",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização customizada básica
st.markdown("""
    <style>
    .main-title { font-size: 2.5rem; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .subtitle { font-size: 1.1rem; color: #4B5563; margin-bottom: 30px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #F3F4F6; border-radius: 4px; padding: 10px 20px; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #E5E7EB; }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# FUNÇÃO ASSÍNCRONA PARA EXECUÇÃO DO PIPELINE
# -----------------------------------------------------------------------------
async def rodar_pipeline_agentes(cpf: str, nome_arquivo: str, bytes_arquivo: bytes):
    """Orquestra o upload físico seguro e dispara o PipelineSupervisor assincronamente."""
    # 1. Instanciar infraestrutura de armazenamento e garantir sandbox por CPF
    storage = LocalStorageService()
    diretorio_cliente = storage.get_client_dir(cpf)
    caminho_destino = diretorio_cliente / "docs" / nome_arquivo
    
    # Grava os bytes do arquivo carregado pelo Streamlit na pasta segura de entrada
    with open(caminho_destino, "wb") as f:
        f.write(bytes_arquivo)
        
    # 2. Instanciar o supervisor da State Machine (Configurado para bypass local / LM Studio)
    supervisor = PipelineSupervisor(anthropic_api_key="local-bypass")
    
    # Executa a esteira determinística completa de ponta a ponta
    resultado = await supervisor.execute_pipeline(cpf, nome_arquivo)
    return resultado, diretorio_cliente

# -----------------------------------------------------------------------------
# INTERFACE E SIDEBAR
# -----------------------------------------------------------------------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3125/3125856.png", width=80)
st.sidebar.markdown("### 🛠️ Painel de Operações")
st.sidebar.info("Certifique-se de que o **LM Studio** esteja rodando na porta `1234` antes de iniciar o processamento.")

st.markdown("<div class='main-title'>⚖️ LegalTech Prev</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Sistema Especialista Previdenciário com Automação Determinística e Assistência de IA</div>", unsafe_allow_html=True)

# Formulário de entrada de dados
with st.container(border=True):
    st.markdown("#### 📥 Upload de Dados do Segurado")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        cpf_input = st.text_input(
            "CPF do Cliente (Apenas Números):", 
            max_chars=11, 
            placeholder="Ex: 64525430249",
            help="O sistema criará um ambiente isolado (sandbox multi-tenant) para este CPF."
        )
    
    with col2:
        file_input = st.file_uploader(
            "Selecione o Extrato CNIS (PDF ou TXT):", 
            type=["pdf", "txt"],
            help="O arquivo passará pela esteira de extração de dados e análise causal."
        )

    submit_button = st.button("🚀 Processar Documento e Gerar Petição", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# FLUXO DE EXECUÇÃO AO CLICAR NO BOTÃO
# -----------------------------------------------------------------------------
if submit_button:
    if not cpf_input or len(cpf_input) != 11 or not cpf_input.isdigit():
        st.error("❌ Por favor, informe um CPF válido contendo exatamente 11 dígitos numéricos.")
    elif file_input is None:
        st.error("❌ Por favor, faça o upload do arquivo de extrato do CNIS.")
    else:
        with st.status("🤖 Executando Pipeline Multiagente... Por favor, aguarde.", expanded=True) as status:
            try:
                st.write("📦 [STORAGE] Resolvendo isolamento criptográfico e criando diretórios de Tenant...")
                
                # Captura os bytes do arquivo enviado na UI
                file_bytes = file_input.getvalue()
                
                # Executa o loop assíncrono nativo para rodar a State Machine do Supervisor
                resultado, dir_cliente = asyncio.run(
                    rodar_pipeline_agentes(cpf_input, file_input.name, file_bytes)
                )
                
                if resultado["success"]:
                    status.update(label="🎉 Processamento Concluído com Sucesso Perfeito!", state="complete", expanded=False)
                    st.success(f"Análise finalizada para o documento: {file_input.name}")
                    
                    # Carregar artefatos gerados pelo disco físico para exibição
                    pasta_outputs = dir_cliente / "outputs"
                    caminho_audit = pasta_outputs / "pipeline_audit.json"
                    caminho_peticao = pasta_outputs / "peticao_inicial.md"
                    
                    # Leitura dos Arquivos Físicos salvos
                    with open(caminho_audit, "r", encoding="utf-8") as f:
                        dados_auditoria = json.load(f)
                        
                    with open(caminho_peticao, "r", encoding="utf-8") as f:
                        conteudo_peticao = f.read()

                    # ---------------------------------------------------------
                    # RENDERIZAÇÃO DOS RESULTADOS NA TELA (TABS VISUAIS)
                    # ---------------------------------------------------------
                    tab_peca, tab_calculos, tab_auditoria = st.tabs([
                        "📄 Peça Jurídica (Petição Inicial)", 
                        "📊 Relatório de Cálculos e Anomalias", 
                        "🛡️ Trilha de Auditoria (HeraclitusDB Compliant)"
                    ])
                    
                    with tab_peca:
                        st.markdown("### 📋 Petição Inicial Gerada (Formato Markdown)")
                        st.text_area("Código-Fonte Markdown:", conteudo_peticao, height=200)
                        
                        # Botão de download nativo do documento jurídico gerado
                        st.download_button(
                            label="📥 Baixar Petição Inicial (.md)",
                            data=conteudo_peticao,
                            file_name=f"peticao_inicial_{cpf_input}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )
                        st.markdown("---")
                        st.markdown(conteudo_peticao) # Renderização visual bonita do markdown

                    with tab_calculos:
                        st.markdown("### 🧮 Resultados Computacionais Core (Motor Python Frio)")
                        math_rep = dados_auditoria.get("math_report", {})
                        
                        # Mapeamento corrigido para o schema em português ('tempo_calculado')
                        tempo = math_rep.get("tempo_calculado", {})
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Anos de Contribuição", f"{tempo.get('anos', 0)} anos")
                        m2.metric("Meses", f"{tempo.get('meses', 0)} meses")
                        m3.metric("Dias", f"{tempo.get('dias', 0)} dias")
                        m4.metric("Total Dias Absolutos", f"{tempo.get('total_dias_absolutos', 0)} dias")
                        
                        # Bloco de Anomalias Críticas do INSS Detectadas
                        st.markdown("#### 🚨 Inconsistências Detectadas no CNIS")
                        anomalias = math_rep.get("anomalies_detected", [])
                        if anomalias:
                            for ano in anomalias:
                                st.warning(f"**{ano.get('tipo')}** no empregador *{ano.get('empregador')}* (Vínculo ID: {ano.get('identificador_vinculo')}) \n\n *{ano.get('descricao')}*")
                        else:
                            st.success("Nenhuma anomalia crítica estrutural de datas foi detectada.")
                            
                        # Sub-aba com os Vínculos e Insights cognitivos do Analista
                        st.markdown("#### 🧠 Direcionamento Estratégico (Teses Jurídicas Deduplicadas)")
                        st.info(dados_auditoria.get("legal_insights", "Sem insights disponíveis."))

                    with tab_auditoria:
                        st.markdown("### 🛡️ Estado Imutável do Event Log da State Machine")
                        st.caption("O JSON abaixo representa a trilha histórica que serve como prova determinística de auditoria.")
                        st.json(dados_auditoria)
                        
                else:
                    status.update(label="❌ Falha crítica na execução do Pipeline", state="error")
                    st.error(f"Erro reportado pela State Machine: {resultado.get('error')}")
                    
            except Exception as e:
                status.update(label="💥 Colapso inesperado do sistema externo", state="error")
                st.exception(e)