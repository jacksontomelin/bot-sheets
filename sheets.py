"""
sheets.py — Lê a planilha via CSV público (sem autenticação necessária)
"""
from __future__ import annotations
import csv
import io
import time
import urllib.request
from datetime import datetime, date
from collections import defaultdict

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQOULFphi7aNoOrAylEY1OVZEZ6ilxMKIPvIeIGs1e1i2IMTDf0rPTmYQHyLtmO16moI5kMDlTfzMjO/pub?output=csv"
CACHE_TTL = 300  # segundos

# Nomes normalizados das colunas (lowercase sem acento)
COL = {
    "data":        "DATA",
    "loja":        "LOJA",
    "grupo":       "GRUPO",
    "servico":     "SERVIÇO",
    "valor":       "VALOR",
    "pagamento":   "PAGAMENTO",
    "cliente":     "NOME DO CLIENTE",
    "placa":       "PLACA",
    "veiculo":     "VEÍCULOS",
    "video":       "STATUS VIDEO",
    "feito_por":   "FEITO POR QUEM",
    "procuracao":  "PROCURAÇÃO FEITA NA TELA",
    "mensagem":    "MENSAGEM",
    "observacao":  "OBSERVAÇÃO",
    "liquido":     "CUSTO LÍQUIDO",
}

_cache: dict = {"data": None, "ts": 0}


def _fetch() -> list[dict]:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for row in reader:
        # limpa espaços extras nas chaves e valores
        clean = {k.strip(): v.strip() for k, v in row.items() if k}
        rows.append(clean)

    _cache["data"] = rows
    _cache["ts"] = now
    return rows


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_value(s: str) -> float:
    try:
        return float(s.replace("R$", "").replace(".", "").replace(",", ".").strip())
    except ValueError:
        return 0.0


def _col(row: dict, key: str) -> str:
    return row.get(COL[key], "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Funções de análise
# ─────────────────────────────────────────────────────────────────────────────

def resumo_hoje() -> dict:
    rows = _fetch()
    hoje = date.today()
    registros = [r for r in rows if _parse_date(_col(r, "data")) == hoje]

    total_proc = sum(
        1 for r in registros
        if "proc" in _col(r, "servico").lower() or "proc" in _col(r, "servico").lower()
    )
    proc_pendentes = [
        r for r in registros
        if _col(r, "procuracao").upper() not in ("OK", "OK NO ASSINADOR", "FEITA")
        and ("proc" in _col(r, "servico").lower())
    ]
    faturamento = sum(_parse_value(_col(r, "valor")) for r in registros)
    liquido = sum(_parse_value(_col(r, "liquido")) for r in registros)

    return {
        "total": len(registros),
        "faturamento": faturamento,
        "liquido": liquido,
        "procuracoes": total_proc,
        "proc_pendentes": len(proc_pendentes),
        "data": hoje.strftime("%d/%m/%Y"),
    }


def resumo_periodo(data_ini: date, data_fim: date) -> dict:
    rows = _fetch()
    registros = [
        r for r in rows
        if (d := _parse_date(_col(r, "data"))) and data_ini <= d <= data_fim
    ]
    faturamento = sum(_parse_value(_col(r, "valor")) for r in registros)
    liquido = sum(_parse_value(_col(r, "liquido")) for r in registros)
    proc = sum(1 for r in registros if "proc" in _col(r, "servico").lower())

    return {
        "total": len(registros),
        "faturamento": faturamento,
        "liquido": liquido,
        "procuracoes": proc,
        "inicio": data_ini.strftime("%d/%m/%Y"),
        "fim": data_fim.strftime("%d/%m/%Y"),
    }


def procuracoes_hoje() -> list[dict]:
    rows = _fetch()
    hoje = date.today()
    return [
        r for r in rows
        if _parse_date(_col(r, "data")) == hoje
        and "proc" in _col(r, "servico").lower()
    ]


def procuracoes_pendentes(data_ini: date | None = None, data_fim: date | None = None) -> list[dict]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or hoje
    fim = data_fim or hoje

    result = []
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        if "proc" not in _col(r, "servico").lower():
            continue
        status = _col(r, "procuracao").upper()
        if status not in ("OK", "OK NO ASSINADOR", "FEITA", "CONCLUÍDA", "CONCLUIDA"):
            result.append(r)
    return result


def ranking_lojas(data_ini: date | None = None, data_fim: date | None = None,
                  top: int = 10) -> list[tuple[str, int, float]]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    contagem: dict[str, int] = defaultdict(int)
    faturamento: dict[str, float] = defaultdict(float)

    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        loja = _col(r, "loja") or "Sem Loja"
        contagem[loja] += 1
        faturamento[loja] += _parse_value(_col(r, "valor"))

    ranking = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:top]
    return [(loja, qtd, faturamento[loja]) for loja, qtd in ranking]


def ranking_operadores(data_ini: date | None = None, data_fim: date | None = None,
                       top: int = 10) -> list[tuple[str, int]]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    contagem: dict[str, int] = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        op = _col(r, "feito_por") or "Desconhecido"
        contagem[op] += 1

    return sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:top]


def videos_pendentes(data_ini: date | None = None, data_fim: date | None = None) -> list[dict]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or hoje
    fim = data_fim or hoje

    result = []
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        status = _col(r, "video").upper()
        if status not in ("VIDEO OK", "VIDEO OK, NA PASTA", "OK", "OK NA PASTA"):
            result.append(r)
    return result


def buscar_cliente(termo: str) -> list[dict]:
    rows = _fetch()
    t = termo.lower()
    return [
        r for r in rows
        if t in _col(r, "cliente").lower()
        or t in _col(r, "placa").lower()
        or t in _col(r, "veiculo").lower()
    ]


def servicos_por_tipo(data_ini: date | None = None, data_fim: date | None = None) -> dict[str, int]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    contagem: dict[str, int] = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        svc = _col(r, "servico") or "Sem Serviço"
        contagem[svc] += 1
    return dict(sorted(contagem.items(), key=lambda x: x[1], reverse=True))


def faturamento_por_loja(data_ini: date | None = None, data_fim: date | None = None) -> dict[str, float]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    fat: dict[str, float] = defaultdict(float)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        loja = _col(r, "loja") or "Sem Loja"
        fat[loja] += _parse_value(_col(r, "valor"))
    return dict(sorted(fat.items(), key=lambda x: x[1], reverse=True))


def resumo_por_grupo(data_ini: date | None = None, data_fim: date | None = None) -> dict[str, dict]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    grupos: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "faturamento": 0.0, "liquido": 0.0})
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        g = _col(r, "grupo") or "Sem Grupo"
        grupos[g]["qtd"] += 1
        grupos[g]["faturamento"] += _parse_value(_col(r, "valor"))
        grupos[g]["liquido"] += _parse_value(_col(r, "liquido"))
    return dict(sorted(grupos.items(), key=lambda x: x[1]["faturamento"], reverse=True))


def formas_pagamento(data_ini: date | None = None, data_fim: date | None = None) -> dict[str, int]:
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje

    contagem: dict[str, int] = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        pg = _col(r, "pagamento") or "Não informado"
        contagem[pg] += 1
    return dict(sorted(contagem.items(), key=lambda x: x[1], reverse=True))


def invalidar_cache():
    _cache["ts"] = 0
