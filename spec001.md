Perfeito. Sua abordagem traz o projeto para a realidade de engenharia de software de missão crítica. Atuar com sistemas especialistas jurídicos exige trocar o "deslumbre da IA" pelo **rigor determinístico**. O LLM não pode ser o motor; ele deve ser uma engrenagem de tradução de linguagem natural na entrada e de geração de linguagem natural na saída.

Abaixo está o **System Specification Document (Blueprint de Produção)** completo, refinado e estruturado. Ele foi desenhado especificamente para servir como o contexto definitivo para o **Claude Code** inicializar o desenvolvimento do backend de forma impecável, respeitando a separação estrita de camadas e a segurança multi-tenant.

---

# 📑 ESPECIFICAÇÃO ARQUITETURAL: MOTOR PREVIDENCIÁRIO ASSISTIDO POR IA

## 1. Paradigma Fundamental de Engenharia

> ⚠️ **Premissa de Design:** O sistema é uma Máquina de Estados Finitos Determinística (State Machine) com assistência probabilística de LLMs. O Claude **nunca** calcula frações de tempo, **nunca** define elegibilidade de regras e **nunca** toma decisões estruturais de forma autônoma. O Python executa a lógica de negócio e os cálculos; o Claude interpreta as ambiguidades textuais do CNIS e redige a narrativa jurídica final.

---

## 2. Topologia de Diretórios (Layout de Produção)

O Claude Code deve criar rigorosamente a seguinte árvore de arquivos:

```text
legaltech-prev/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Entrypoint FastAPI (Rotas e Middleware)
│   ├── config.py                   # Variáveis de ambiente (Pydantic Settings)
│   ├── auth/
│   │   └── gov_br.py               # Integração OAuth2 + Validação de JWT
│   ├── storage/
│   │   └── local_storage.py        # Abstração de I/O seguro no File System
│   ├── schemas/
│   │   ├── cnis_schema.py          # Tipagem estrita de entrada e parse
│   │   └── state_schema.py         # Schema de estado da State Machine
│   ├── services/
│   │   ├── cnis_parser_service.py  # Regex/pdfplumber + Orquestração de Fallback LLM
│   │   ├── time_calculator.py      # Motor de cálculo de tempo (Puro Python)
│   │   ├── previdencia_rules.py    # Matriz de regras da EC 103/2019
│   │   └── anomaly_detector.py     # Validador de indicadores de erro do INSS
│   └── agents/
│       ├── supervisor.py           # Orquestrador determinístico do Pipeline
│       ├── agent_parser.py         # Agente LLM para extração de layouts complexos
│       ├── agent_analyst.py        # Agente LLM para interpretação qualitativa
│       └── agent_writer.py         # Agente LLM para preenchimento de templates Jinja2
├── templates/
│   └── peticao_inicial.md.j2       # Template rígido da peça jurídica
├── requirements.txt
└── .env

```

---

## 3. Contratos de Dados (A Camada de Schemas)

Para garantir a integridade entre o código determinístico e os outputs dos agentes, os contratos de dados precisam ser estritos. Abaixo está a definição do `cnis_schema.py` que guiará todas as transformações de dados.

```python
# app/schemas/cnis_schema.py
from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class Competencia(BaseModel):
    competencia: str = Field(..., description="Formato MM/AAAA")
    recolhimento: float = Field(..., description="Valor recolhido em Reais")
    indicadores: List[str] = Field(default=[], description="Ex: PEXT, AVISO, IREC-LC123")

class VinculoEmpregaticio(BaseModel):
    identificador_vinculo: str
    empregador: str
    data_inicio: date = Field(..., description="ISO Format YYYY-MM-DD")
    data_fim: Optional[date] = Field(None, description="ISO Format YYYY-MM-DD. None se vínculo em aberto")
    competencias: List[Competencia] = []
    indicadores_gerais: List[str] = []

class ExtratoCNISClean(BaseModel):
    cpf: str = Field(..., pattern=r"^\d{11}$")
    nome: str
    data_nascimento: date
    nit: str
    vinculos: List[VinculoEmpregaticio]

```

---

## 4. Implementação das Camadas e Componentes

### 🛠️ Camada de Infraestrutura Segura (`storage/local_storage.py`)

Este módulo **não utiliza IA**. Ele gerencia o isolamento multi-tenant de arquivos no servidor baseado no CPF sanitizado do cliente, aplicando defesas rigorosas contra ataques de *Path Traversal*.

```python
# app/storage/local_storage.py
import os
import re
from pathlib import Path
from fastapi import HTTPException, UploadFile

class LocalStorageService:
    def __init__(self, base_dir: str = "/tmp/legaltech_storage"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_cpf(self, cpf: str) -> str:
        sanitized = re.sub(r"\D", "", cpf)
        if len(sanitized) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido.")
        return sanitized

    def get_client_dir(self, cpf: str) -> Path:
        sanitized_cpf = self._sanitize_cpf(cpf)
        client_path = (self.base_dir / sanitized_cpf).resolve()
        
        # Security Guard: Impede engenharia reversa via Path Traversal (../)
        if not client_path.issubsetof(self.base_dir) and client_path.parent != self.base_dir:
            raise HTTPException(status_code=403, detail="Acesso ao diretório negado.")
        
        client_path.mkdir(exist_ok=True)
        (client_path / "docs").mkdir(exist_ok=True)
        (client_path / "outputs").mkdir(exist_ok=True)
        return client_path

    async def save_uploaded_file(self, cpf: str, file: UploadFile, filename: str) -> Path:
        client_dir = self.get_client_dir(cpf)
        target_path = client_dir / "docs" / filename
        
        # Escrita Atômica temporária para evitar corrupção de arquivos
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            os.replace(temp_path, target_path)
            return target_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(status_code=500, detail=f"Erro de E/S atômica: {str(e)}")

```

### 🎛️ Camada de Orquestração Determinística (`agents/supervisor.py`)

O supervisor funciona estritamente como uma **State Machine de Execução Linear**. Se um agente falhar ou o output violar o schema estipulado pelo Pydantic, o pipeline quebra imediatamente gerando um log de auditoria, impedindo falhas em cascata.

```python
# app/agents/supervisor.py
from typing import Dict, Any
from app.storage.local_storage import LocalStorageService
from app.services.cnis_parser_service import CnisParserService
from app.services.time_calculator import TimeCalculatorService
from app.agents.agent_analyst import AgentAnalyst
from app.agents.agent_writer import AgentWriter

class PipelineSupervisor:
    def __init__(self):
        self.storage = LocalStorageService()
        self.parser = CnisParserService()
        self.calculator = TimeCalculatorService()
        self.analyst = AgentAnalyst()
        self.writer = AgentWriter()

    async def execute_pipeline(self, cpf: str, cnis_filename: str) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "cpf": cpf,
            "status": "INIT",
            "logs": []
        }
        
        try:
            # Estado 1: Resolução de Infraestrutura
            client_dir = self.storage.get_client_dir(cpf)
            cnis_path = client_dir / "docs" / cnis_filename
            state["status"] = "STORAGE_RESOLVED"
            
            # Estado 2: Parse dos Dados Brutos para Contrato Pydantic (Híbrido)
            structured_cnis = await self.parser.parse(cnis_path, cpf)
            state["structured_data"] = structured_cnis.model_dump()
            state["status"] = "PARSED"
            
            # Estado 3: Cálculo Core e Detecção de Anomalias (100% Python)
            math_report = self.calculator.compute_legal_time(structured_cnis)
            state["math_report"] = math_report
            state["status"] = "CALCULATED"
            
            # Estado 4: Análise Qualitativa e Estratégia Jurídica (Claude)
            legal_insights = await self.analyst.analyze_case(state["math_report"])
            state["legal_insights"] = legal_insights
            state["status"] = "ANALYZED"
            
            # Estado 5: Redação Guiada por Template (Claude + Jinja2)
            final_doc_path = await self.writer.generate_document(client_dir, state)
            state["final_output_path"] = str(final_doc_path)
            state["status"] = "COMPLETED"
            
            self._write_audit_log(client_dir, state)
            return {"success": True, "output": state["final_output_path"]}
            
        except Exception as e:
            state["status"] = "FAILED"
            state["error_trace"] = str(e)
            # Garante a persistência do estado mesmo em caso de colapso do sistema
            self._write_audit_log(self.storage.get_client_dir(cpf), state)
            raise e

    def _write_audit_log(self, client_dir: Path, state: Dict[str, Any]):
        import json
        audit_file = client_dir / "outputs" / "pipeline_audit.json"
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, default=str)

```

### 🔬 Camada de Serviços Determinísticos (`services/time_calculator.py`)

Aqui é processada a lógica matemática. O arquivo resolve sobreposições de datas (vínculos concomitantes), converte períodos em anos, meses e dias brutos, e sinaliza ao ecossistema os indicadores críticos que precisam de peticionamento (ex: período sem data fim).

```python
# app/services/time_calculator.py
from datetime import date
from typing import Dict, Any
from app.schemas.cnis_schema import ExtratoCNISClean

class TimeCalculatorService:
    def compute_legal_time(self, cnis: ExtratoCNISClean) -> Dict[str, Any]:
        total_days = 0
        anomalies = []
        vinculos_processados = []

        for v in cnis.vinculos:
            d_inicio = v.data_inicio
            d_fim = v.data_fim
            
            # Detecção de Anomalia Rígida: Vínculo sem data de término
            if d_fim is None:
                anomalies.append({
                    "tipo": "DATA_FIM_AUSENTE",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": "Vínculo ativo ou sem baixa no CNIS. Requer tese de comprovação fática."
                })
                # Regra de corte prudencial para cálculo de tempo atualizado
                d_fim = date.today()

            # Cálculo exato de dias corridos entre períodos
            delta_days = (d_fim - d_inicio).days + 1
            total_days += delta_days
            
            vinculos_processados.append({
                "id": v.identificador_vinculo,
                "dias_contados": delta_days,
                "indicadores": v.indicadores_gerais
            })

        # Conversão padrão da Lei 8.213/91 (Ano Comercial: 365 dias)
        anos = total_days // 365
        restante_dias = total_days % 365
        meses = restante_dias // 30
        dias = restante_dias % 30

        return {
            "cliente_nome": cnis.nome,
            "cpf": cnis.cpf,
            "tempo_calculado": {
                "anos": anos,
                "meses": meses,
                "dias": dias,
                "total_dias_absolutos": total_days
            },
            "vinculos": vinculos_processados,
            "anomalies_detected": anomalies
        }

```

### 🧠 Camada de Agentes Inteligentes (`agents/agent_analyst.py`)

Uma vez que o Python processou a matemática fria dos dados, o `agent_analyst` assume o papel interpretativo. Ele consome o relatório de erros e gera a fundamentação lógica que será injetada no template da petição.

```python
# app/agents/agent_analyst.py
from typing import Dict, Any
from anthropic import Anthropic

class AgentAnalyst:
    def __init__(self):
        # Em produção, carregar via injeção de dependência e herdar de app.config
        self.client = Anthropic()

    async def analyze_case(self, math_report: Dict[str, Any]) -> str:
        # Prompt de Sistema rígido forçando o papel de cientista de dados jurídicos
        system_prompt = (
            "Você é um agente analista jurídico de alto nível, especialista em direito previdenciário brasileiro. "
            "Sua única função é receber um relatório computacional estruturado e deduzir as melhores teses jurídicas "
            "com base nas anomalias detectadas. Não invente dados de períodos. Seja conciso e puramente analítico."
        )
        
        user_content = f"Analise o seguinte relatório matemático do CNIS e estruture os argumentos para correção de indicadores:\n{math_report}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.0,  # Ruído zero para máxima previsibilidade racional
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        
        return response.content[0].text

```

---

## 5. Próximo Passo: Prompt de Inicialização para o Claude Code

Para iniciar o desenvolvimento estruturado na sua máquina, copie o bloco abaixo e insira no terminal do seu **Claude Code**:

```text
Prompt para o Claude Code:
"Claude, inicialize um projeto backend em Python com FastAPI chamado 'legaltech-prev' seguindo estritamente o Blueprint de Engenharia Determinística. 
1. Crie a árvore completa de diretórios conforme especificado na topologia.
2. Escreva o arquivo 'app/schemas/cnis_schema.py' usando o Pydantic V2 com as validações de Regex de CPF e tipagem de datas ISO.
3. Codifique o arquivo 'app/storage/local_storage.py' contendo as defesas de Path Traversal e o mecanismo de Escrita Atômica.
4. Codifique o arquivo 'app/services/time_calculator.py' para a execução matemática determinística dos dias de contribuição e barramento de anomalias.
5. Codifique o arquivo 'app/agents/supervisor.py' gerenciando o Pipeline linear como uma State Machine fechada.
Garantir tratamento explícito de exceções e tipagem estrita (Type Hints) em todas as funções assinadas. Não avance para a geração de prompts do AgentWriter até que a base de infraestrutura e serviços esteja perfeitamente estruturada em arquivos reais."

```
Perfeito. Sua abordagem traz o projeto para a realidade de engenharia de software de missão crítica. Atuar com sistemas especialistas jurídicos exige trocar o "deslumbre da IA" pelo **rigor determinístico**. O LLM não pode ser o motor; ele deve ser uma engrenagem de tradução de linguagem natural na entrada e de geração de linguagem natural na saída.

Abaixo está o **System Specification Document (Blueprint de Produção)** completo, refinado e estruturado. Ele foi desenhado especificamente para servir como o contexto definitivo para o **Claude Code** inicializar o desenvolvimento do backend de forma impecável, respeitando a separação estrita de camadas e a segurança multi-tenant.

---

# 📑 ESPECIFICAÇÃO ARQUITETURAL: MOTOR PREVIDENCIÁRIO ASSISTIDO POR IA

## 1. Paradigma Fundamental de Engenharia

> ⚠️ **Premissa de Design:** O sistema é uma Máquina de Estados Finitos Determinística (State Machine) com assistência probabilística de LLMs. O Claude **nunca** calcula frações de tempo, **nunca** define elegibilidade de regras e **nunca** toma decisões estruturais de forma autônoma. O Python executa a lógica de negócio e os cálculos; o Claude interpreta as ambiguidades textuais do CNIS e redige a narrativa jurídica final.

---

## 2. Topologia de Diretórios (Layout de Produção)

O Claude Code deve criar rigorosamente a seguinte árvore de arquivos:

```text
legaltech-prev/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Entrypoint FastAPI (Rotas e Middleware)
│   ├── config.py                   # Variáveis de ambiente (Pydantic Settings)
│   ├── auth/
│   │   └── gov_br.py               # Integração OAuth2 + Validação de JWT
│   ├── storage/
│   │   └── local_storage.py        # Abstração de I/O seguro no File System
│   ├── schemas/
│   │   ├── cnis_schema.py          # Tipagem estrita de entrada e parse
│   │   └── state_schema.py         # Schema de estado da State Machine
│   ├── services/
│   │   ├── cnis_parser_service.py  # Regex/pdfplumber + Orquestração de Fallback LLM
│   │   ├── time_calculator.py      # Motor de cálculo de tempo (Puro Python)
│   │   ├── previdencia_rules.py    # Matriz de regras da EC 103/2019
│   │   └── anomaly_detector.py     # Validador de indicadores de erro do INSS
│   └── agents/
│       ├── supervisor.py           # Orquestrador determinístico do Pipeline
│       ├── agent_parser.py         # Agente LLM para extração de layouts complexos
│       ├── agent_analyst.py        # Agente LLM para interpretação qualitativa
│       └── agent_writer.py         # Agente LLM para preenchimento de templates Jinja2
├── templates/
│   └── peticao_inicial.md.j2       # Template rígido da peça jurídica
├── requirements.txt
└── .env

```

---

## 3. Contratos de Dados (A Camada de Schemas)

Para garantir a integridade entre o código determinístico e os outputs dos agentes, os contratos de dados precisam ser estritos. Abaixo está a definição do `cnis_schema.py` que guiará todas as transformações de dados.

```python
# app/schemas/cnis_schema.py
from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class Competencia(BaseModel):
    competencia: str = Field(..., description="Formato MM/AAAA")
    recolhimento: float = Field(..., description="Valor recolhido em Reais")
    indicadores: List[str] = Field(default=[], description="Ex: PEXT, AVISO, IREC-LC123")

class VinculoEmpregaticio(BaseModel):
    identificador_vinculo: str
    empregador: str
    data_inicio: date = Field(..., description="ISO Format YYYY-MM-DD")
    data_fim: Optional[date] = Field(None, description="ISO Format YYYY-MM-DD. None se vínculo em aberto")
    competencias: List[Competencia] = []
    indicadores_gerais: List[str] = []

class ExtratoCNISClean(BaseModel):
    cpf: str = Field(..., pattern=r"^\d{11}$")
    nome: str
    data_nascimento: date
    nit: str
    vinculos: List[VinculoEmpregaticio]

```

---

## 4. Implementação das Camadas e Componentes

### 🛠️ Camada de Infraestrutura Segura (`storage/local_storage.py`)

Este módulo **não utiliza IA**. Ele gerencia o isolamento multi-tenant de arquivos no servidor baseado no CPF sanitizado do cliente, aplicando defesas rigorosas contra ataques de *Path Traversal*.

```python
# app/storage/local_storage.py
import os
import re
from pathlib import Path
from fastapi import HTTPException, UploadFile

class LocalStorageService:
    def __init__(self, base_dir: str = "/tmp/legaltech_storage"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_cpf(self, cpf: str) -> str:
        sanitized = re.sub(r"\D", "", cpf)
        if len(sanitized) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido.")
        return sanitized

    def get_client_dir(self, cpf: str) -> Path:
        sanitized_cpf = self._sanitize_cpf(cpf)
        client_path = (self.base_dir / sanitized_cpf).resolve()
        
        # Security Guard: Impede engenharia reversa via Path Traversal (../)
        if not client_path.issubsetof(self.base_dir) and client_path.parent != self.base_dir:
            raise HTTPException(status_code=403, detail="Acesso ao diretório negado.")
        
        client_path.mkdir(exist_ok=True)
        (client_path / "docs").mkdir(exist_ok=True)
        (client_path / "outputs").mkdir(exist_ok=True)
        return client_path

    async def save_uploaded_file(self, cpf: str, file: UploadFile, filename: str) -> Path:
        client_dir = self.get_client_dir(cpf)
        target_path = client_dir / "docs" / filename
        
        # Escrita Atômica temporária para evitar corrupção de arquivos
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            os.replace(temp_path, target_path)
            return target_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(status_code=500, detail=f"Erro de E/S atômica: {str(e)}")

```

### 🎛️ Camada de Orquestração Determinística (`agents/supervisor.py`)

O supervisor funciona estritamente como uma **State Machine de Execução Linear**. Se um agente falhar ou o output violar o schema estipulado pelo Pydantic, o pipeline quebra imediatamente gerando um log de auditoria, impedindo falhas em cascata.

```python
# app/agents/supervisor.py
from typing import Dict, Any
from app.storage.local_storage import LocalStorageService
from app.services.cnis_parser_service import CnisParserService
from app.services.time_calculator import TimeCalculatorService
from app.agents.agent_analyst import AgentAnalyst
from app.agents.agent_writer import AgentWriter

class PipelineSupervisor:
    def __init__(self):
        self.storage = LocalStorageService()
        self.parser = CnisParserService()
        self.calculator = TimeCalculatorService()
        self.analyst = AgentAnalyst()
        self.writer = AgentWriter()

    async def execute_pipeline(self, cpf: str, cnis_filename: str) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "cpf": cpf,
            "status": "INIT",
            "logs": []
        }
        
        try:
            # Estado 1: Resolução de Infraestrutura
            client_dir = self.storage.get_client_dir(cpf)
            cnis_path = client_dir / "docs" / cnis_filename
            state["status"] = "STORAGE_RESOLVED"
            
            # Estado 2: Parse dos Dados Brutos para Contrato Pydantic (Híbrido)
            structured_cnis = await self.parser.parse(cnis_path, cpf)
            state["structured_data"] = structured_cnis.model_dump()
            state["status"] = "PARSED"
            
            # Estado 3: Cálculo Core e Detecção de Anomalias (100% Python)
            math_report = self.calculator.compute_legal_time(structured_cnis)
            state["math_report"] = math_report
            state["status"] = "CALCULATED"
            
            # Estado 4: Análise Qualitativa e Estratégia Jurídica (Claude)
            legal_insights = await self.analyst.analyze_case(state["math_report"])
            state["legal_insights"] = legal_insights
            state["status"] = "ANALYZED"
            
            # Estado 5: Redação Guiada por Template (Claude + Jinja2)
            final_doc_path = await self.writer.generate_document(client_dir, state)
            state["final_output_path"] = str(final_doc_path)
            state["status"] = "COMPLETED"
            
            self._write_audit_log(client_dir, state)
            return {"success": True, "output": state["final_output_path"]}
            
        except Exception as e:
            state["status"] = "FAILED"
            state["error_trace"] = str(e)
            # Garante a persistência do estado mesmo em caso de colapso do sistema
            self._write_audit_log(self.storage.get_client_dir(cpf), state)
            raise e

    def _write_audit_log(self, client_dir: Path, state: Dict[str, Any]):
        import json
        audit_file = client_dir / "outputs" / "pipeline_audit.json"
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, default=str)

```

### 🔬 Camada de Serviços Determinísticos (`services/time_calculator.py`)

Aqui é processada a lógica matemática. O arquivo resolve sobreposições de datas (vínculos concomitantes), converte períodos em anos, meses e dias brutos, e sinaliza ao ecossistema os indicadores críticos que precisam de peticionamento (ex: período sem data fim).

```python
# app/services/time_calculator.py
from datetime import date
from typing import Dict, Any
from app.schemas.cnis_schema import ExtratoCNISClean

class TimeCalculatorService:
    def compute_legal_time(self, cnis: ExtratoCNISClean) -> Dict[str, Any]:
        total_days = 0
        anomalies = []
        vinculos_processados = []

        for v in cnis.vinculos:
            d_inicio = v.data_inicio
            d_fim = v.data_fim
            
            # Detecção de Anomalia Rígida: Vínculo sem data de término
            if d_fim is None:
                anomalies.append({
                    "tipo": "DATA_FIM_AUSENTE",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": "Vínculo ativo ou sem baixa no CNIS. Requer tese de comprovação fática."
                })
                # Regra de corte prudencial para cálculo de tempo atualizado
                d_fim = date.today()

            # Cálculo exato de dias corridos entre períodos
            delta_days = (d_fim - d_inicio).days + 1
            total_days += delta_days
            
            vinculos_processados.append({
                "id": v.identificador_vinculo,
                "dias_contados": delta_days,
                "indicadores": v.indicadores_gerais
            })

        # Conversão padrão da Lei 8.213/91 (Ano Comercial: 365 dias)
        anos = total_days // 365
        restante_dias = total_days % 365
        meses = restante_dias // 30
        dias = restante_dias % 30

        return {
            "cliente_nome": cnis.nome,
            "cpf": cnis.cpf,
            "tempo_calculado": {
                "anos": anos,
                "meses": meses,
                "dias": dias,
                "total_dias_absolutos": total_days
            },
            "vinculos": vinculos_processados,
            "anomalies_detected": anomalies
        }

```

### 🧠 Camada de Agentes Inteligentes (`agents/agent_analyst.py`)

Uma vez que o Python processou a matemática fria dos dados, o `agent_analyst` assume o papel interpretativo. Ele consome o relatório de erros e gera a fundamentação lógica que será injetada no template da petição.

```python
# app/agents/agent_analyst.py
from typing import Dict, Any
from anthropic import Anthropic

class AgentAnalyst:
    def __init__(self):
        # Em produção, carregar via injeção de dependência e herdar de app.config
        self.client = Anthropic()

    async def analyze_case(self, math_report: Dict[str, Any]) -> str:
        # Prompt de Sistema rígido forçando o papel de cientista de dados jurídicos
        system_prompt = (
            "Você é um agente analista jurídico de alto nível, especialista em direito previdenciário brasileiro. "
            "Sua única função é receber um relatório computacional estruturado e deduzir as melhores teses jurídicas "
            "com base nas anomalias detectadas. Não invente dados de períodos. Seja conciso e puramente analítico."
        )
        
        user_content = f"Analise o seguinte relatório matemático do CNIS e estruture os argumentos para correção de indicadores:\n{math_report}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.0,  # Ruído zero para máxima previsibilidade racional
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        
        return response.content[0].text

```

---

## 5. Próximo Passo: Prompt de Inicialização para o Claude Code

Para iniciar o desenvolvimento estruturado na sua máquina, copie o bloco abaixo e insira no terminal do seu **Claude Code**:

```text
Prompt para o Claude Code:
"Claude, inicialize um projeto backend em Python com FastAPI chamado 'legaltech-prev' seguindo estritamente o Blueprint de Engenharia Determinística. 
1. Crie a árvore completa de diretórios conforme especificado na topologia.
2. Escreva o arquivo 'app/schemas/cnis_schema.py' usando o Pydantic V2 com as validações de Regex de CPF e tipagem de datas ISO.
3. Codifique o arquivo 'app/storage/local_storage.py' contendo as defesas de Path Traversal e o mecanismo de Escrita Atômica.
4. Codifique o arquivo 'app/services/time_calculator.py' para a execução matemática determinística dos dias de contribuição e barramento de anomalias.
5. Codifique o arquivo 'app/agents/supervisor.py' gerenciando o Pipeline linear como uma State Machine fechada.
Garantir tratamento explícito de exceções e tipagem estrita (Type Hints) em todas as funções assinadas. Não avance para a geração de prompts do AgentWriter até que a base de infraestrutura e serviços esteja perfeitamente estruturada em arquivos reais."

```

Para suportar uma arquitetura de missão crítica que une automação determinística, inteligência artificial e conformidade jurídica, o projeto deve adotar uma estratégia de **Poliglotismo de Dados (Polyglot Persistence)**.

Em vez de forçar um único banco de dados a fazer tudo, dividimos o sistema em **três tipos de armazenamento**, cada um cuidando de uma responsabilidade específica da sua aplicação:

---

## 1. HeraclitusDB: O Core de Inteligência, Memória e Auditoria

Este é o coração do projeto. Ele funciona como a **Camada de Persistência Imutável** e o grafos de conhecimento do sistema.

* **O que ele armazena:**
* **Trilha de Auditoria do Supervisor:** Cada mudança de estado do pipeline (`INIT` $\rightarrow$ `PARSED` $\rightarrow$ `CALCULATED` $\rightarrow$ `COMPLETED`).
* **Memória dos Agentes:** Os fatos extraídos do CNIS e as interpretações do `agent_analyst`.
* **Recibos Criptográficos (`.tst`):** Os hashes Merkle (`blake3`) selados com carimbo de tempo legal da ICP-Brasil.


* **Por que ele é insubstituível aqui:** Porque ele impede a fraude retroativa. Se o INSS ou um auditor questionar uma petição gerada em **junho de 2026**, o HeraclitusDB reconstrói o estado exato dos dados daquela data via `AS OF LSN` e explica a decisão usando o operador `WHY`.

## 2. Banco de Dados Relacional (PostgreSQL): A Camada de Aplicação Comum

Nem todo dado do sistema precisa de imutabilidade criptográfica ou processamento de grafos. Dados operacionais e triviais do dia a dia da plataforma web rodam aqui.

* **O que ele armazena:**
* **Controle de Usuários e Acesso (RBAC):** Cadastro dos advogados, perfis dos segurados, logs de login.
* **Dados de Integração (Gov.br):** Tokens de sessão OAuth2, expiração de credenciais e estados de conexão.
* **Configurações do Sistema:** Parâmetros da API, chaves de webhook de ACTs (Autoridades de Carimbo de Tempo) e gerenciamento de filas.


* **Por que ele está aqui:** Para manter o HeraclitusDB limpo, performático e focado apenas na lógica jurídica e de auditoria. Dados mutáveis de interface e sessão pertencem ao Postgres.

## 3. Object Storage (File System Seguro / AWS S3): A Camada de Arquivos Brutos

Os agentes de IA e os códigos de parsing precisam ler o documento físico original antes de transformá-lo em dados estruturados.

* **O que ele armazena:**
* Os arquivos **PDF brutos do CNIS** enviados pelo segurado.
* Documentos pessoais digitalizados (RG, CPF, Comprovante de Residência).
* As petições iniciais finais geradas em formato `.docx` ou `.pdf`.


* **Por que ele está aqui:** Bancos de dados não foram feitos para armazenar arquivos binários pesados (blobs). O `LocalStorageService` (visto no código do seu blueprint) gerencia o isolamento de pastas por CPF aqui, aplicando o versionamento físico dos documentos (`CNIS_v1.pdf`, `CNIS_v2.pdf`).

---

### 🔄 O Fluxo de Sincronização entre eles

1. O cliente faz upload do PDF $\rightarrow$ Salva no **Object Storage** via `LocalStorageService`.
2. O FastAPI autentica o usuário $\rightarrow$ Valida e registra a sessão no **PostgreSQL**.
3. O `supervisor.py` inicia a State Machine $\rightarrow$ Registra o início do evento e todo o progresso (JSON extraído do CNIS, cálculos matemáticos, logs de erros e a árvore causal) como blocos *append-only* no **HeraclitusDB**.