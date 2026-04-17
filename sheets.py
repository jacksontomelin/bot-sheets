"""
sheets.py — Google Sheets API client com leitura E escrita
"""
from __future__ import annotations
import re, time, json, os
from datetime import datetime, date
from collections import defaultdict

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1Le6dTaOLZ3UWRtzKxasraRa6Z6jTIccEqlwmg5cZo68")
CACHE_TTL = 120

COL = {
    "data": "DATA", "loja": "LOJA", "grupo": "GRUPO",
    "servico": "SERVIÇO", "valor": "VALOR", "pagamento": "PAGAMENTO",
    "cliente": "NOME DO CLIENTE", "placa": "PLACA", "veiculo": "VEÍCULOS",
    "video": "STATUS VIDEO", "feito_por": "FEITO POR QUEM",
    "procuracao": "PROCURAÇÃO FEITA NA TELA", "mensagem": "MENSAGEM",
    "observacao": "OBSERVAÇÃO", "liquido": "CUSTO LÍQUIDO",
}

_cache: dict = {"data": None, "ts": 0, "headers": None, "service": None}


def _get_service():
    if _cache["service"]:
        return _cache["service"]
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    else:
        creds = Credentials.from_service_account_file(
            os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    _cache["service"] = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _cache["service"]


def _fetch() -> list[dict]:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range="A:Z"
    ).execute()
    values = result.get("values", [])
    if not values:
        return []

    headers = [h.strip() for h in values[0]]
    _cache["headers"] = headers
    rows = []
    for i, row in enumerate(values[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        d = {h: padded[j].strip() for j, h in enumerate(headers)}
        d["__row__"] = i  # numero real da linha na planilha
        rows.append(d)

    _cache["data"] = rows
    _cache["ts"] = now
    return rows


def _col(row: dict, key: str) -> str:
    return row.get(COL.get(key, key), "").strip()


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_value(s: str) -> float:
    try:
        return float(s.replace("R$","").replace(".","").replace(",",".").strip())
    except ValueError:
        return 0.0


def invalidar_cache():
    _cache["ts"] = 0


# ── ESCRITA NA PLANILHA ───────────────────────────────────────────────────────

def _col_index(col_name: str) -> int | None:
    headers = _cache.get("headers")
    if not headers:
        _fetch()
        headers = _cache.get("headers", [])
    for i, h in enumerate(headers):
        if h.strip() == col_name:
            return i
    return None


def _col_letter(index: int) -> str:
    letters = ""
    while index >= 0:
        letters = chr(index % 26 + 65) + letters
        index = index // 26 - 1
    return letters


def atualizar_celula(row_num: int, col_key: str, valor: str) -> bool:
    """Atualiza uma celula especifica na planilha"""
    try:
        col_name = COL.get(col_key, col_key)
        col_idx = _col_index(col_name)
        if col_idx is None:
            return False
        col_letter = _col_letter(col_idx)
        range_str = "{}{}".format(col_letter, row_num)
        svc = _get_service()
        svc.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_str,
            valueInputOption="USER_ENTERED",
            body={"values": [[valor]]}
        ).execute()
        invalidar_cache()
        return True
    except Exception as e:
        raise e


def marcar_procuracao_ok(row_num: int) -> bool:
    return atualizar_celula(row_num, "procuracao", "OK NO ASSINADOR")


def marcar_video_ok(row_num: int) -> bool:
    return atualizar_celula(row_num, "video", "VIDEO OK, NA PASTA")


def adicionar_observacao(row_num: int, obs: str) -> bool:
    return atualizar_celula(row_num, "observacao", obs)


def adicionar_nova_linha(dados: dict) -> bool:
    """Adiciona uma nova linha na planilha"""
    try:
        _fetch()
        headers = _cache.get("headers", [])
        linha = [""] * len(headers)
        for key, valor in dados.items():
            col_name = COL.get(key, key)
            if col_name in headers:
                idx = headers.index(col_name)
                linha[idx] = valor
        svc = _get_service()
        svc.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [linha]}
        ).execute()
        invalidar_cache()
        return True
    except Exception as e:
        raise e


# ── CONSULTAS ─────────────────────────────────────────────────────────────────

def resumo_hoje() -> dict:
    rows = _fetch()
    hoje = date.today()
    registros = [r for r in rows if _parse_date(_col(r, "data")) == hoje]
    proc_hoje = [r for r in registros if "proc" in _col(r, "servico").lower() or "ass" in _col(r, "servico").lower()]
    pend = procuracoes_pendentes(hoje, hoje)
    return {
        "total": len(registros),
        "faturamento": sum(_parse_value(_col(r, "valor")) for r in registros),
        "liquido": sum(_parse_value(_col(r, "liquido")) for r in registros),
        "procuracoes": len(proc_hoje),
        "proc_pendentes": len(pend),
        "data": hoje.strftime("%d/%m/%Y"),
    }


def resumo_periodo(data_ini: date, data_fim: date) -> dict:
    rows = _fetch()
    registros = [r for r in rows if (d := _parse_date(_col(r, "data"))) and data_ini <= d <= data_fim]
    return {
        "total": len(registros),
        "faturamento": sum(_parse_value(_col(r, "valor")) for r in registros),
        "liquido": sum(_parse_value(_col(r, "liquido")) for r in registros),
        "procuracoes": sum(1 for r in registros if "proc" in _col(r, "servico").lower() or "ass" in _col(r, "servico").lower()),
        "inicio": data_ini.strftime("%d/%m/%Y"),
        "fim": data_fim.strftime("%d/%m/%Y"),
    }


def procuracoes_hoje() -> list[dict]:
    rows = _fetch()
    hoje = date.today()
    return [r for r in rows if _parse_date(_col(r, "data")) == hoje
            and ("proc" in _col(r, "servico").lower() or "ass" in _col(r, "servico").lower())]


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
        svc = _col(r, "servico").upper()
        if not ("PROC" in svc or "ASS VEND" in svc or "ASS COMP" in svc or "CONTRATO" in svc):
            continue
        status = _col(r, "procuracao").upper()
        if status not in ("OK", "OK NO ASSINADOR", "FEITA", "CONCLUIDA"):
            result.append(r)
    return result


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
        if "OK" not in status:
            result.append(r)
    return result


def buscar_cliente(termo: str) -> list[dict]:
    rows = _fetch()
    t = termo.lower()
    return [r for r in rows if t in _col(r, "cliente").lower()
            or t in _col(r, "placa").lower() or t in _col(r, "veiculo").lower()]


def historico_cliente(termo: str) -> list[dict]:
    rows = _fetch()
    t = termo.lower()
    result = [r for r in rows if t in _col(r, "cliente").lower() or t in _col(r, "placa").lower()]
    return sorted(result, key=lambda x: _col(x, "data"), reverse=True)


def ranking_lojas(data_ini=None, data_fim=None, top=10):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    contagem: dict = defaultdict(int)
    faturamento: dict = defaultdict(float)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        loja = _col(r, "loja") or "Sem Loja"
        contagem[loja] += 1
        faturamento[loja] += _parse_value(_col(r, "valor"))
    ranking = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:top]
    return [(loja, qtd, faturamento[loja]) for loja, qtd in ranking]


def ranking_operadores(data_ini=None, data_fim=None, top=10):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    contagem: dict = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        op = _col(r, "feito_por") or "Desconhecido"
        contagem[op] += 1
    return sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:top]


def faturamento_por_loja(data_ini=None, data_fim=None):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    fat: dict = defaultdict(float)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        fat[_col(r, "loja") or "Sem Loja"] += _parse_value(_col(r, "valor"))
    return dict(sorted(fat.items(), key=lambda x: x[1], reverse=True))


def servicos_por_tipo(data_ini=None, data_fim=None):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    contagem: dict = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        contagem[_col(r, "servico") or "Sem Servico"] += 1
    return dict(sorted(contagem.items(), key=lambda x: x[1], reverse=True))


def resumo_por_grupo(data_ini=None, data_fim=None):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    grupos: dict = defaultdict(lambda: {"qtd": 0, "faturamento": 0.0, "liquido": 0.0})
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        g = _col(r, "grupo") or "Sem Grupo"
        grupos[g]["qtd"] += 1
        grupos[g]["faturamento"] += _parse_value(_col(r, "valor"))
        grupos[g]["liquido"] += _parse_value(_col(r, "liquido"))
    return dict(sorted(grupos.items(), key=lambda x: x[1]["faturamento"], reverse=True))


def formas_pagamento(data_ini=None, data_fim=None):
    rows = _fetch()
    hoje = date.today()
    ini = data_ini or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    contagem: dict = defaultdict(int)
    for r in rows:
        d = _parse_date(_col(r, "data"))
        if not d or not (ini <= d <= fim):
            continue
        contagem[_col(r, "pagamento") or "Nao informado"] += 1
    return dict(sorted(contagem.items(), key=lambda x: x[1], reverse=True))
