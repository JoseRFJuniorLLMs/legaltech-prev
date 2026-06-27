from datetime import date
from typing import Dict, Any, List, Tuple
from app.schemas.cnis_schema import ExtratoCNISClean

# -----------------------------------------------------------------------------
# Convenção de conversão de tempo de contribuição.
# 365 dias/ano e 30 dias/mês é a simplificação mais usada por calculadoras
# previdenciárias. O total bruto em DIAS (`total_dias_absolutos`) é o número
# soberano; anos/meses/dias são derivados.  ⚠️ CONFERIR a convenção desejada
# com a Dra. Carolina (há escritórios que contam dia-a-dia em calendário real).
# -----------------------------------------------------------------------------
DIAS_POR_ANO = 365
DIAS_POR_MES = 30


class TimeCalculatorService:
    def compute_legal_time(self, cnis: ExtratoCNISClean) -> Dict[str, Any]:
        anomalies: List[Dict[str, Any]] = []
        vinculos_processados: List[Dict[str, Any]] = []
        intervalos: List[Tuple[date, date]] = []

        soma_bruta_dias = 0  # soma ingênua (com concomitância) — só para transparência

        for v in cnis.vinculos:
            d_inicio = v.data_inicio
            d_fim = v.data_fim

            # Anomalia: vínculo sem baixa formal no CNIS.
            if d_fim is None:
                anomalies.append({
                    "tipo": "DATA_FIM_AUSENTE",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": "Vínculo ativo ou sem encerramento formalizado no CNIS. "
                                 "Teto de cálculo fixado em hoje; idealmente usar a DER. Exige tese fática.",
                })
                d_fim = date.today()  # teto preventivo (rever para DER no peticionamento)

            # Anomalia: datas invertidas (erro de cadastro do INSS).
            if d_fim < d_inicio:
                anomalies.append({
                    "tipo": "DATA_INVERTIDA",
                    "identificador_vinculo": v.identificador_vinculo,
                    "empregador": v.empregador,
                    "descricao": f"Data fim ({d_fim}) anterior à data início ({d_inicio}). "
                                 "Vínculo descartado do cálculo até correção.",
                })
                continue

            dias_vinculo = (d_fim - d_inicio).days + 1  # +1 = contagem inclusiva
            soma_bruta_dias += dias_vinculo
            intervalos.append((d_inicio, d_fim))

            vinculos_processados.append({
                "id": v.identificador_vinculo,
                "empregador": v.empregador,
                "data_inicio": d_inicio.isoformat(),
                "data_fim": d_fim.isoformat(),
                "dias_contados": dias_vinculo,
                "indicadores": v.indicadores_gerais,
            })

        # ---------------------------------------------------------------------
        # CONCOMITÂNCIA: une intervalos sobrepostos/contíguos para que períodos
        # simultâneos (mais de um vínculo no mesmo mês) sejam contados UMA vez.
        # ---------------------------------------------------------------------
        periodos_unificados, total_dias_liquido = self._merge_intervalos(intervalos)
        dias_concomitancia = soma_bruta_dias - total_dias_liquido

        if dias_concomitancia > 0:
            anomalies.append({
                "tipo": "CONCOMITANCIA",
                "identificador_vinculo": "-",
                "empregador": "(múltiplos vínculos)",
                "descricao": f"Detectados {dias_concomitancia} dias de períodos concomitantes "
                             "(vínculos simultâneos). Contados uma única vez no tempo líquido, "
                             "conforme vedação à contagem em dobro.",
            })

        anos = total_dias_liquido // DIAS_POR_ANO
        restante = total_dias_liquido % DIAS_POR_ANO
        meses = restante // DIAS_POR_MES
        dias = restante % DIAS_POR_MES

        return {
            "cliente_nome": cnis.nome,
            "cpf": cnis.cpf,
            "tempo_calculado": {
                "anos": anos,
                "meses": meses,
                "dias": dias,
                "total_dias_absolutos": total_dias_liquido,
            },
            # Rastro de transparência do tratamento de concomitância.
            "tempo_bruto": {
                "soma_dias_sem_deduplicacao": soma_bruta_dias,
                "dias_concomitancia_removidos": dias_concomitancia,
                "total_dias_liquido": total_dias_liquido,
            },
            "periodos_unificados": [
                {"inicio": i.isoformat(), "fim": f.isoformat(), "dias": (f - i).days + 1}
                for i, f in periodos_unificados
            ],
            "vinculos": vinculos_processados,
            "anomalies_detected": anomalies,
        }

    def dias_contribuicao_ate(self, cnis: ExtratoCNISClean, data_corte: date) -> int:
        """Tempo de contribuição líquido (sem concomitância) acumulado ATÉ `data_corte`.
        Usado pelas regras de pedágio, que medem o tempo existente em 13/11/2019."""
        intervalos: List[Tuple[date, date]] = []
        for v in cnis.vinculos:
            ini = v.data_inicio
            fim = v.data_fim or date.today()
            if fim < ini or ini > data_corte:
                continue
            intervalos.append((ini, min(fim, data_corte)))
        _, total = self._merge_intervalos(intervalos)
        return total

    @staticmethod
    def _merge_intervalos(intervalos: List[Tuple[date, date]]) -> Tuple[List[Tuple[date, date]], int]:
        """Une intervalos [inicio, fim] que se sobrepõem ou são contíguos.
        Retorna (lista_unificada, total_de_dias_liquidos com contagem inclusiva)."""
        if not intervalos:
            return [], 0

        ordenados = sorted(intervalos, key=lambda x: x[0])
        merged: List[List[date]] = [list(ordenados[0])]

        for inicio, fim in ordenados[1:]:
            ultimo_fim = merged[-1][1]
            # Sobreposição (inicio <= ultimo_fim) ou contiguidade (inicio == ultimo_fim + 1 dia).
            if (inicio - ultimo_fim).days <= 1:
                if fim > ultimo_fim:
                    merged[-1][1] = fim
            else:
                merged.append([inicio, fim])

        total = sum((f - i).days + 1 for i, f in merged)
        return [(i, f) for i, f in merged], total
