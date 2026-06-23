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
            
            # Captura de anomalia imposta por vínculo sem baixa no sistema do INSS
            if d_fim is None:
                anomalies.append({
                    "tipo": "DATA_FIM_AUSENTE",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": "Vínculo ativo ou sem encerramento formalizado no CNIS. Exige tese fática."
                })
                d_fim = date.today() # Teto de cálculo preventivo

            delta_days = (d_fim - d_inicio).days + 1
            total_days += delta_days
            
            vinculos_processados.append({
                "id": v.identificador_vinculo,
                "empregador": v.empregador,
                "dias_contados": delta_days,
                "indicadores": v.indicadores_gerais
            })

        # Conversão padronizada pela Lei Ordinária 8.213/91 (Ano Comercial de 365 dias)
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
