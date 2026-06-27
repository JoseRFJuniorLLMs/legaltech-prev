from typing import Dict, Any, List
from app.schemas.cnis_schema import ExtratoCNISClean

class AnomalyDetectorService:
    def __init__(self):
        # Mapeamento básico de siglas críticas de erro do CNIS
        self.indicadores_criticos = {
            "PEXT": "Vínculo extemporâneo. Necessita comprovação documental contemporânea (ex: CTPS, contrato).",
            "AVISO": "Aviso de divergência de dados. Necessita verificação no INSS.",
            "IREC-LC123": "Recolhimento com alíquota reduzida (LC 123). Não conta para tempo de contribuição comum sem complementação.",
            "IGF-DEF": "Informação de GFIP com defeito. O INSS pode desconsiderar o período."
        }

    def detect_anomalies(self, cnis: ExtratoCNISClean) -> List[Dict[str, Any]]:
        anomalies = []
        
        for v in cnis.vinculos:
            if v.indicadores_gerais:
                for indicador in v.indicadores_gerais:
                    if indicador in self.indicadores_criticos:
                        anomalies.append({
                            "tipo": "INDICADOR_CRITICO",
                            "identificador_vinculo": v.identificador_vinculo,
                            "empregador": v.empregador,
                            "descricao": f"Indicador '{indicador}' detectado: {self.indicadores_criticos[indicador]}"
                        })
        return anomalies
