"""
Matriz de enquadramento — regras de transição da EC 103/2019.

⚠️  IMPORTANTE (leia antes de usar em peça real):
    Os limiares de 2019 e 2026 foram conferidos na fonte oficial (Ministério da
    Previdência / INSS). As demais células das tabelas progressivas seguem a
    progressão legal (+6 meses/ano na idade; +1 ponto/ano), mas DEVEM ser
    validadas pela Dra. Carolina ano a ano antes do protocolo.
    Fonte 2026: gov.br/previdencia — "Guia de aposentadoria 2026".

    Este módulo NÃO calcula RMI/valor do benefício, fator previdenciário, nem
    tempo especial/insalubre — só faz o enquadramento de elegibilidade por tempo.
"""
from datetime import date
from typing import Dict, Any, List, Optional, Tuple
from app.schemas.cnis_schema import ExtratoCNISClean

DATA_REFORMA = date(2019, 11, 13)
DIAS_POR_ANO = 365  # mesma convenção do TimeCalculatorService

# Idade mínima progressiva (art. 16) — idade em ANOS (fração = meses/12).
# Base 2019: 56 (F) / 61 (M); +0,5 ano/ano; teto 62 (F, em 2031) / 65 (M, em 2027).
IDADE_PROGRESSIVA = {
    2019: (56.0, 61.0), 2020: (56.5, 61.5), 2021: (57.0, 62.0), 2022: (57.5, 62.5),
    2023: (58.0, 63.0), 2024: (58.5, 63.5), 2025: (59.0, 64.0), 2026: (59.5, 64.5),
    2027: (60.0, 65.0), 2028: (60.5, 65.0), 2029: (61.0, 65.0), 2030: (61.5, 65.0),
    2031: (62.0, 65.0),
}
# Regra de pontos (art. 15) — base 2019: 86 (F) / 96 (M); +1/ano;
# teto 100 (F, em 2033) / 105 (M, em 2028).
PONTOS = {
    2019: (86, 96), 2020: (87, 97), 2021: (88, 98), 2022: (89, 99), 2023: (90, 100),
    2024: (91, 101), 2025: (92, 102), 2026: (93, 103), 2027: (94, 104), 2028: (95, 105),
    2029: (96, 105), 2030: (97, 105), 2031: (98, 105), 2032: (99, 105), 2033: (100, 105),
}
# Tempo mínimo de contribuição exigido (anos) por sexo.
TEMPO_MINIMO_ANOS = {"F": 30, "M": 35}
# Aposentadoria por idade (art. 18) — idade fixa em 2026 e contribuição mínima.
IDADE_APOSENT_IDADE = {"F": 62, "M": 65}
CONTRIB_MINIMA_IDADE_ANOS = 15  # filiados antes da reforma


def _anos(dias: int) -> float:
    return dias / DIAS_POR_ANO


def _fmt(dias: int) -> str:
    a = dias // DIAS_POR_ANO
    r = dias % DIAS_POR_ANO
    m = r // 30
    return f"{a}a {m}m"


def _idade(nascimento: date, ref: date) -> Tuple[int, int, float]:
    anos = ref.year - nascimento.year
    meses = ref.month - nascimento.month
    if ref.day < nascimento.day:
        meses -= 1
    if meses < 0:
        anos -= 1
        meses += 12
    return anos, meses, anos + meses / 12.0


def _req(criterio: str, exigido: str, atual: str, ok: bool) -> Dict[str, Any]:
    return {"criterio": criterio, "exigido": exigido, "atual": atual, "cumprido": ok}


class PrevidenciaRulesService:
    def enquadrar(
        self,
        cnis: ExtratoCNISClean,
        math_report: Dict[str, Any],
        data_der: Optional[date] = None,
        dias_ate_reforma: Optional[int] = None,
    ) -> Dict[str, Any]:
        der = data_der or date.today()
        dias_total = math_report["tempo_calculado"]["total_dias_absolutos"]
        sexo = (cnis.sexo or "").upper().strip()

        idade_a, idade_m, idade_dec = _idade(cnis.data_nascimento, der)
        tempo_anos = _anos(dias_total)

        cabecalho = {
            "data_der": der.isoformat(),
            "idade_na_der": f"{idade_a}a {idade_m}m",
            "tempo_contribuicao": _fmt(dias_total),
            "tempo_contribuicao_anos": round(tempo_anos, 3),
            "sexo": sexo or None,
            "avisos": [],
        }

        if sexo not in ("M", "F"):
            cabecalho["avisos"].append(
                "Sexo não identificado no CNIS — impossível enquadrar regras que dependem de "
                "idade/tempo por sexo. Preencher 'sexo' (M/F) e reprocessar."
            )
            return {"cabecalho": cabecalho, "regras": [], "melhor_enquadramento": None}

        if dias_ate_reforma is None:
            cabecalho["avisos"].append(
                "Tempo até 13/11/2019 não informado — regras de pedágio calculadas como 0; "
                "fornecer `dias_ate_reforma` para análise de pedágio."
            )
            dias_ate_reforma = 0

        min_anos = TEMPO_MINIMO_ANOS[sexo]
        ano_der = der.year
        regras: List[Dict[str, Any]] = [
            self._idade_progressiva(sexo, ano_der, idade_dec, tempo_anos, idade_a, idade_m, dias_total),
            self._pontos(sexo, ano_der, idade_dec, tempo_anos, dias_total),
            self._pedagio(50, sexo, min_anos, dias_ate_reforma, dias_total, idade_dec, idade_a, idade_m),
            self._pedagio(100, sexo, min_anos, dias_ate_reforma, dias_total, idade_dec, idade_a, idade_m),
            self._por_idade(sexo, idade_dec, tempo_anos, idade_a, idade_m, dias_total),
        ]

        elegiveis = [r["regra"] for r in regras if r["elegivel"]]
        return {
            "cabecalho": cabecalho,
            "regras": regras,
            "melhor_enquadramento": elegiveis[0] if elegiveis else None,
            "regras_elegiveis": elegiveis,
        }

    # ------------------------------------------------------------------ regras
    def _idade_progressiva(self, sexo, ano, idade_dec, tempo_anos, ia, im, dias_total):
        idade_exig = IDADE_PROGRESSIVA.get(ano, IDADE_PROGRESSIVA[2031])[0 if sexo == "F" else 1]
        min_anos = TEMPO_MINIMO_ANOS[sexo]
        ok_idade = idade_dec >= idade_exig
        ok_tempo = tempo_anos >= min_anos
        return {
            "regra": "Idade Progressiva",
            "artigo": "Art. 16, EC 103/2019",
            "elegivel": ok_idade and ok_tempo,
            "requisitos": [
                _req("Idade mínima", f"{idade_exig:.1f}a (ano {ano})", f"{ia}a {im}m", ok_idade),
                _req("Tempo de contribuição", f"{min_anos}a", _fmt(dias_total), ok_tempo),
            ],
            "falta": self._falta(ok_idade, ok_tempo, idade_exig - idade_dec, min_anos - tempo_anos),
            "fundamentacao": "Regra de transição por idade mínima progressiva (sobe 6 meses/ano "
                             "até 62a mulher / 65a homem).",
        }

    def _pontos(self, sexo, ano, idade_dec, tempo_anos, dias_total):
        pts_exig = PONTOS.get(ano, PONTOS[2033])[0 if sexo == "F" else 1]
        min_anos = TEMPO_MINIMO_ANOS[sexo]
        pts_atual = idade_dec + tempo_anos
        ok_pts = pts_atual >= pts_exig
        ok_tempo = tempo_anos >= min_anos
        return {
            "regra": "Pontos (idade + tempo)",
            "artigo": "Art. 15, EC 103/2019",
            "elegivel": ok_pts and ok_tempo,
            "requisitos": [
                _req("Pontuação", f"{pts_exig} pts (ano {ano})", f"{pts_atual:.1f} pts", ok_pts),
                _req("Tempo de contribuição", f"{min_anos}a", _fmt(dias_total), ok_tempo),
            ],
            "falta": (f"Faltam {pts_exig - pts_atual:.1f} pontos. " if not ok_pts else "")
                     + (f"Faltam {min_anos - tempo_anos:.2f} anos de contribuição." if not ok_tempo else "")
                     or "Todos os requisitos cumpridos.",
            "fundamentacao": "Soma de idade + tempo de contribuição (frações incluídas); "
                             "exigência sobe 1 ponto/ano.",
        }

    def _pedagio(self, percentual, sexo, min_anos, dias_ate_reforma, dias_total, idade_dec, ia, im):
        min_dias = min_anos * DIAS_POR_ANO
        faltava_dias = max(0, min_dias - dias_ate_reforma)
        pedagio_dias = int(faltava_dias * percentual / 100)
        exigido_total_dias = min_dias + pedagio_dias  # tempo total mínimo exigido com pedágio
        ok_tempo = dias_total >= exigido_total_dias

        requisitos = [
            _req("Tempo mínimo + pedágio", _fmt(exigido_total_dias), _fmt(dias_total), ok_tempo),
            _req("Tempo em 13/11/2019", "(referência do pedágio)", _fmt(dias_ate_reforma), True),
        ]
        elegivel = ok_tempo
        nota = ""

        if percentual == 50:
            # Porta de entrada: faltava MENOS de 2 anos em 13/11/2019.
            gate = dias_ate_reforma >= (min_dias - 2 * DIAS_POR_ANO)
            requisitos.insert(0, _req(
                "Faltava < 2 anos em 13/11/2019", "sim",
                "sim" if gate else f"não (faltavam {_fmt(faltava_dias)})", gate))
            elegivel = gate and ok_tempo
            nota = "Sem idade mínima. Sujeita ao fator previdenciário (conferir RMI)."
        else:  # 100%
            idade_min = 57 if sexo == "F" else 60
            ok_idade = idade_dec >= idade_min
            requisitos.insert(0, _req("Idade mínima fixa", f"{idade_min}a", f"{ia}a {im}m", ok_idade))
            elegivel = ok_idade and ok_tempo
            nota = "Idade fixa (não progride). Não incide fator previdenciário."

        return {
            "regra": f"Pedágio {percentual}%",
            "artigo": f"Art. {'17' if percentual == 50 else '20'}, EC 103/2019",
            "elegivel": elegivel,
            "requisitos": requisitos,
            "falta": "Requisitos cumpridos." if elegivel
                     else f"Tempo total exigido com pedágio: {_fmt(exigido_total_dias)}.",
            "fundamentacao": f"Pedágio de {percentual}% sobre o tempo que faltava em 13/11/2019 "
                             f"({_fmt(faltava_dias)}). {nota}",
        }

    def _por_idade(self, sexo, idade_dec, tempo_anos, ia, im, dias_total):
        idade_min = IDADE_APOSENT_IDADE[sexo]
        ok_idade = idade_dec >= idade_min
        ok_tempo = tempo_anos >= CONTRIB_MINIMA_IDADE_ANOS
        return {
            "regra": "Aposentadoria por Idade",
            "artigo": "Art. 18, EC 103/2019 / Lei 8.213/91",
            "elegivel": ok_idade and ok_tempo,
            "requisitos": [
                _req("Idade mínima", f"{idade_min}a", f"{ia}a {im}m", ok_idade),
                _req("Carência/tempo mínimo", f"{CONTRIB_MINIMA_IDADE_ANOS}a", _fmt(dias_total), ok_tempo),
            ],
            "falta": self._falta(ok_idade, ok_tempo, idade_min - idade_dec,
                                  CONTRIB_MINIMA_IDADE_ANOS - tempo_anos),
            "fundamentacao": "Regra etária (filiados antes da reforma mantêm 15 anos de carência).",
        }

    @staticmethod
    def _falta(ok_idade, ok_tempo, delta_idade, delta_tempo) -> str:
        partes = []
        if not ok_idade:
            partes.append(f"faltam {delta_idade:.2f} anos de idade")
        if not ok_tempo:
            partes.append(f"faltam {delta_tempo:.2f} anos de contribuição")
        return "Requisitos cumpridos." if not partes else "Faltam: " + "; ".join(partes) + "."
