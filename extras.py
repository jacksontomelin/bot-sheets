"""
extras.py — Funcoes extras de analise para o bot
"""
from __future__ import annotations
from datetime import date, timedelta
from collections import defaultdict
from calendar import monthrange
import sheets as sh


def clientes_do_dia(dia: date | None = None) -> list[dict]:
    """Todos os clientes atendidos no dia com status completo"""
    rows = sh._fetch()
    d_alvo = dia or date.today()
    result = []
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if d == d_alvo:
            result.append(r)
    return sorted(result, key=lambda x: sh._col(x, "loja"))


def painel_loja(loja_nome: str, data_ini: date, data_fim: date) -> dict:
    """Painel completo de uma loja"""
    rows = sh._fetch()
    itens = []
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if not d or not (data_ini <= d <= data_fim):
            continue
        if sh._col(r, "loja").strip().lower() == loja_nome.strip().lower():
            itens.append(r)

    faturamento = sum(sh._parse_value(sh._col(r, "valor")) for r in itens)
    liquido     = sum(sh._parse_value(sh._col(r, "liquido")) for r in itens)
    proc_ok     = sum(1 for r in itens if "ok" in sh._col(r, "procuracao").lower())
    proc_pend   = sum(1 for r in itens if "ok" not in sh._col(r, "procuracao").lower() and sh._col(r, "procuracao"))
    video_ok    = sum(1 for r in itens if "ok" in sh._col(r, "video").lower())
    video_pend  = sum(1 for r in itens if "ok" not in sh._col(r, "video").lower() and sh._col(r, "video"))

    ops = defaultdict(int)
    for r in itens:
        op = sh._col(r, "feito_por") or "?"
        ops[op] += 1

    svcs = defaultdict(int)
    for r in itens:
        svc = sh._col(r, "servico") or "?"
        svcs[svc] += 1

    return {
        "loja":        loja_nome,
        "total":       len(itens),
        "faturamento": faturamento,
        "liquido":     liquido,
        "proc_ok":     proc_ok,
        "proc_pend":   proc_pend,
        "video_ok":    video_ok,
        "video_pend":  video_pend,
        "operadores":  dict(sorted(ops.items(), key=lambda x: x[1], reverse=True)),
        "servicos":    dict(sorted(svcs.items(), key=lambda x: x[1], reverse=True)),
        "itens":       itens,
    }


def comparativo(hoje: date | None = None) -> dict:
    """Comparativo hoje vs ontem e mes atual vs mes anterior"""
    rows = sh._fetch()
    hoje = hoje or date.today()
    ontem = hoje - timedelta(days=1)

    def total_dia(d):
        rs = [r for r in rows if sh._parse_date(sh._col(r, "data")) == d]
        return {
            "qtd": len(rs),
            "fat": sum(sh._parse_value(sh._col(r, "valor")) for r in rs),
            "liq": sum(sh._parse_value(sh._col(r, "liquido")) for r in rs),
            "proc": sum(1 for r in rs if "proc" in sh._col(r, "servico").lower()),
        }

    def total_mes(ano, mes):
        ini = date(ano, mes, 1)
        fim = date(ano, mes, monthrange(ano, mes)[1])
        rs = [r for r in rows if (d := sh._parse_date(sh._col(r, "data"))) and ini <= d <= fim]
        return {
            "qtd": len(rs),
            "fat": sum(sh._parse_value(sh._col(r, "valor")) for r in rs),
            "liq": sum(sh._parse_value(sh._col(r, "liquido")) for r in rs),
        }

    # Mes anterior
    if hoje.month == 1:
        mes_ant_ano, mes_ant = hoje.year - 1, 12
    else:
        mes_ant_ano, mes_ant = hoje.year, hoje.month - 1

    return {
        "hoje":     total_dia(hoje),
        "ontem":    total_dia(ontem),
        "mes_atual": total_mes(hoje.year, hoje.month),
        "mes_ant":  total_mes(mes_ant_ano, mes_ant),
        "data_hoje": hoje.strftime("%d/%m/%Y"),
        "data_ontem": ontem.strftime("%d/%m/%Y"),
        "mes_atual_label": "{:02d}/{}".format(hoje.month, hoje.year),
        "mes_ant_label": "{:02d}/{}".format(mes_ant, mes_ant_ano),
    }


def painel_operador(operador: str, data_ini: date, data_fim: date) -> dict:
    """Tudo que um operador fez no periodo"""
    rows = sh._fetch()
    itens = [
        r for r in rows
        if (d := sh._parse_date(sh._col(r, "data")))
        and data_ini <= d <= data_fim
        and operador.lower() in sh._col(r, "feito_por").lower()
    ]
    faturamento = sum(sh._parse_value(sh._col(r, "valor")) for r in itens)
    proc_ok   = sum(1 for r in itens if "ok" in sh._col(r, "procuracao").lower())
    proc_pend = sum(1 for r in itens if "ok" not in sh._col(r, "procuracao").lower() and sh._col(r, "procuracao"))

    por_loja = defaultdict(int)
    for r in itens:
        por_loja[sh._col(r, "loja") or "?"] += 1

    return {
        "operador":  operador,
        "total":     len(itens),
        "faturamento": faturamento,
        "proc_ok":   proc_ok,
        "proc_pend": proc_pend,
        "por_loja":  dict(sorted(por_loja.items(), key=lambda x: x[1], reverse=True)),
        "itens":     itens,
    }


def lojas_sem_movimento(dias: int = 1) -> list[str]:
    """Lojas que tiveram movimento recente mas nao hoje"""
    rows = sh._fetch()
    hoje = date.today()
    ini = hoje - timedelta(days=dias)

    ativas_hoje = set(
        sh._col(r, "loja").strip() for r in rows
        if sh._parse_date(sh._col(r, "data")) == hoje and sh._col(r, "loja")
    )
    recentes = set(
        sh._col(r, "loja").strip() for r in rows
        if (d := sh._parse_date(sh._col(r, "data")))
        and ini <= d < hoje and sh._col(r, "loja")
    )
    return sorted(recentes - ativas_hoje)


def evolucao_semana() -> list[dict]:
    """Evolucao dos ultimos 7 dias"""
    rows = sh._fetch()
    hoje = date.today()
    result = []
    for i in range(6, -1, -1):
        d = hoje - timedelta(days=i)
        rs = [r for r in rows if sh._parse_date(sh._col(r, "data")) == d]
        result.append({
            "data":  d.strftime("%d/%m"),
            "dia":   ["Seg","Ter","Qua","Qui","Sex","Sab","Dom"][d.weekday()],
            "qtd":   len(rs),
            "fat":   sum(sh._parse_value(sh._col(r, "valor")) for r in rs),
            "proc":  sum(1 for r in rs if "proc" in sh._col(r, "servico").lower() or "ass" in sh._col(r, "servico").lower()),
        })
    return result


def listar_operadores(data_ini: date, data_fim: date) -> list[str]:
    rows = sh._fetch()
    ops = set()
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if d and data_ini <= d <= data_fim:
            op = sh._col(r, "feito_por")
            if op:
                ops.add(op.strip())
    return sorted(ops)


def listar_lojas_periodo(data_ini: date, data_fim: date) -> list[str]:
    rows = sh._fetch()
    lojas = set()
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if d and data_ini <= d <= data_fim:
            loja = sh._col(r, "loja")
            if loja:
                lojas.add(loja.strip())
    return sorted(lojas)


def painel_completo_loja(loja_nome: str, data_ini: date, data_fim: date) -> dict:
    """Painel 360 da loja com todos os dados financeiros e operacionais"""
    rows = sh._fetch()
    itens = []
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if not d or not (data_ini <= d <= data_fim):
            continue
        if loja_nome.lower().strip() in sh._col(r, "loja").lower().strip():
            itens.append(r)

    if not itens:
        return {}

    faturamento  = sum(sh._parse_value(sh._col(r, "valor")) for r in itens)
    liquido      = sum(sh._parse_value(sh._col(r, "liquido")) for r in itens)
    ticket_medio = faturamento / len(itens) if itens else 0

    # Procuracoes
    proc_ok   = [r for r in itens if "ok" in sh._col(r, "procuracao").lower()]
    proc_pend = [r for r in itens if "ok" not in sh._col(r, "procuracao").lower() and sh._col(r, "procuracao").strip()]
    proc_sem  = [r for r in itens if not sh._col(r, "procuracao").strip()]

    # Videos
    video_ok   = [r for r in itens if "ok" in sh._col(r, "video").lower()]
    video_pend = [r for r in itens if "ok" not in sh._col(r, "video").lower() and sh._col(r, "video").strip()]

    # Pagamentos
    pgs = defaultdict(int)
    for r in itens:
        pg = sh._col(r, "pagamento") or "Nao informado"
        pgs[pg] += 1

    # Operadores
    ops = defaultdict(int)
    for r in itens:
        op = sh._col(r, "feito_por") or "?"
        ops[op] += 1

    # Servicos
    svcs = defaultdict(int)
    for r in itens:
        svc = sh._col(r, "servico") or "?"
        svcs[svc] += 1

    # Grupos
    grupos = defaultdict(int)
    for r in itens:
        g = sh._col(r, "grupo") or "?"
        grupos[g] += 1

    # Por dia
    por_dia = defaultdict(int)
    for r in itens:
        por_dia[sh._col(r, "data")] += 1

    # Clientes recentes
    clientes_recentes = []
    for r in sorted(itens, key=lambda x: sh._col(x, "data"), reverse=True)[:5]:
        clientes_recentes.append({
            "data":      sh._col(r, "data"),
            "cliente":   sh._col(r, "cliente"),
            "placa":     sh._col(r, "placa"),
            "servico":   sh._col(r, "servico"),
            "valor":     sh._col(r, "valor"),
            "proc":      sh._col(r, "procuracao"),
            "video":     sh._col(r, "video"),
            "operador":  sh._col(r, "feito_por"),
            "obs":       sh._col(r, "observacao") or sh._col(r, "mensagem"),
        })

    # Calcula cobranca
    import cobranca as cb
    dados_cob = cb.calcular_cobranca(data_ini, data_fim, loja_nome)
    loja_key = next((k for k in dados_cob if loja_nome.lower() in k.lower()), None)
    cobranca = dados_cob.get(loja_key, {"total": 0, "qtd_servico": 0, "qtd_proc_comp": 0, "qtd_proc_vend": 0, "qtd_combo": 0})

    return {
        "loja":             loja_nome,
        "total_registros":  len(itens),
        "faturamento":      faturamento,
        "liquido":          liquido,
        "ticket_medio":     ticket_medio,
        "proc_ok":          len(proc_ok),
        "proc_pend":        len(proc_pend),
        "proc_sem":         len(proc_sem),
        "video_ok":         len(video_ok),
        "video_pend":       len(video_pend),
        "pagamentos":       dict(sorted(pgs.items(), key=lambda x: x[1], reverse=True)),
        "operadores":       dict(sorted(ops.items(), key=lambda x: x[1], reverse=True)),
        "servicos":         dict(sorted(svcs.items(), key=lambda x: x[1], reverse=True)),
        "grupos":           dict(sorted(grupos.items(), key=lambda x: x[1], reverse=True)),
        "por_dia":          dict(sorted(por_dia.items())),
        "clientes_recentes": clientes_recentes,
        "cobranca":         cobranca,
        "nome_real":        loja_key or loja_nome,
    }


def buscar_loja(termo: str, data_ini: date, data_fim: date) -> list[str]:
    """Busca lojas que contem o termo no nome"""
    rows = sh._fetch()
    lojas = set()
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if d and data_ini <= d <= data_fim:
            loja = sh._col(r, "loja").strip()
            if loja and termo.lower() in loja.lower():
                lojas.add(loja)
    return sorted(lojas)
