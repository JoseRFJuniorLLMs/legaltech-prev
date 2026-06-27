import pdfplumber
from pathlib import Path
from app.schemas.cnis_schema import ExtratoCNISClean
from app.agents.agent_parser import AgentParser

class CnisParserService:
    def __init__(self, parser_agent: AgentParser):
        self.parser_agent = parser_agent

    async def parse(self, file_path: Path, cpf: str) -> ExtratoCNISClean:
        raw_text = ""
        print(f"📄 [PARSER SERVICE] Abrindo e extraindo páginas do PDF: {file_path.name}")
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text_page = page.extract_text()
                if text_page:
                    raw_text += f"\n--- PÁGINA {i+1} ---\n" + text_page
        
        # Removemos o limite prudencial para não truncar extratos longos
        
        # Orquestra o fallback para o LLM
        return await self.parser_agent.extract_json_from_text(raw_text, cpf)
