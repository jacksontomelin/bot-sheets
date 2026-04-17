"""
cobranca.py — Calcula cobrancas e gera PDF por loja
Regras:
  ATPV / ATPVES                    -> R$ 30,00 por linha
  PROC COMPRADOR apenas            -> R$ 75,00
  PROC VENDEDOR apenas             -> R$ 125,00
  PROC V + CONTRATO (linha unica)  -> R$ 125,00
  COMBO mesmo cliente (C + V)      -> R$ 125,00 (nao soma os dois)
"""
from __future__ import annotations
import io
from datetime import date
from collections import defaultdict

import sheets as sh

# ── Empresas emissoras ────────────────────────────────────────────────────────

EMPRESAS = {
    "unicar": {
        "nome":     "Unicar Processamento de Dados Ltda",
        "fantasia": "Unicar Consultas Veiculares",
        "cnpj":     "57.926.633/0001-42",
        "endereco": "Rua Rodolfo Freygang, 15, Centro",
        "cidade":   "Blumenau - SC",
    },
    "uniao": {
        "nome":     "Pomerode Certificado Digital Ltda",
        "fantasia": "Uniaocert Certificacao e Procuracoes Digitais",
        "cnpj":     "48.338.317/0001-69",
        "endereco": "Rua Presidente Costa e Silva, 400 - Testo Rega",
        "cidade":   "Pomerode - SC, 89.107-000",
    },
}

# ── Precos ────────────────────────────────────────────────────────────────────

PRECO_ATPV       = 30.00
PRECO_PROC_COMP  = 75.00
PRECO_PROC_VEND  = 125.00
PRECO_COMBO      = 125.00

# ── Classificacao de servico ──────────────────────────────────────────────────

def tipo_servico(svc: str) -> str:
    s = svc.upper().strip()
    # Combo numa unica linha
    if ("PROC V" in s or "PROC VEND" in s) and ("CONTRATO" in s or "COMP" in s or "COMPRADOR" in s):
        return "COMBO"
    if "PROC" in s and ("COMP" in s or "COMPRADOR" in s):
        return "PROC_COMP"
    if "PROC" in s and ("VEND" in s or "VENDEDOR" in s):
        return "PROC_VEND"
    if "PROC" in s:
        return "PROC_VEND"   # proc generico -> vendedor
    if "ATPVE" in s or "ATPVES" in s:
        return "ATPV"
    if "ATPV" in s:
        return "ATPV"
    return "OUTRO"


# ── Calculo por loja ──────────────────────────────────────────────────────────

def calcular_cobranca(data_ini: date, data_fim: date, loja_filtro: str | None = None) -> dict:
    """
    Retorna dict:
    {
      loja: {
        "itens": [ {cliente, placa, servico, tipo, valor, data}, ... ],
        "total": float,
        "qtd_atpv": int,
        "qtd_proc_comp": int,
        "qtd_proc_vend": int,
        "qtd_combo": int,
      }
    }
    """
    rows = sh._fetch()
    resultado: dict = {}

    # Filtra periodo e loja
    filtrados = []
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if not d or not (data_ini <= d <= data_fim):
            continue
        loja = sh._col(r, "loja") or "Sem Loja"
        if loja_filtro and loja_filtro.lower() not in loja.lower():
            continue
        filtrados.append(r)

    # Agrupa por loja e detecta combos
    por_loja: dict = defaultdict(list)
    for r in filtrados:
        loja = sh._col(r, "loja") or "Sem Loja"
        por_loja[loja].append(r)

    for loja, itens in por_loja.items():
        linhas = []
        total = 0.0
        qtd = defaultdict(int)

        # Detectar combos: mesmo cliente, mesma loja, mesmo dia com comp+vend em linhas separadas
        # Chave: (cliente, placa, data)
        grupos: dict = defaultdict(list)
        for r in itens:
            chave = (
                sh._col(r, "cliente").upper().strip(),
                sh._col(r, "placa").upper().strip(),
                sh._col(r, "data"),
            )
            grupos[chave].append(r)

        processados = set()

        for chave, grupo in grupos.items():
            tipos_grupo = [tipo_servico(sh._col(r, "servico")) for r in grupo]

            tem_comp = "PROC_COMP" in tipos_grupo
            tem_vend = "PROC_VEND" in tipos_grupo
            tem_combo_linha = "COMBO" in tipos_grupo

            if tem_combo_linha:
                for r in grupo:
                    t = tipo_servico(sh._col(r, "servico"))
                    if t == "COMBO":
                        linhas.append({
                            "cliente": sh._col(r, "cliente"),
                            "placa":   sh._col(r, "placa"),
                            "servico": sh._col(r, "servico"),
                            "tipo":    "COMBO",
                            "valor":   PRECO_COMBO,
                            "data":    sh._col(r, "data"),
                        })
                        total += PRECO_COMBO
                        qtd["COMBO"] += 1
                        processados.add(id(r))
                    elif t == "ATPV":
                        linhas.append({
                            "cliente": sh._col(r, "cliente"),
                            "placa":   sh._col(r, "placa"),
                            "servico": sh._col(r, "servico"),
                            "tipo":    "ATPV",
                            "valor":   PRECO_ATPV,
                            "data":    sh._col(r, "data"),
                        })
                        total += PRECO_ATPV
                        qtd["ATPV"] += 1
                        processados.add(id(r))

            elif tem_comp and tem_vend:
                # Combo de duas linhas -> cobra 125 uma vez
                r_ref = grupo[0]
                linhas.append({
                    "cliente": sh._col(r_ref, "cliente"),
                    "placa":   sh._col(r_ref, "placa"),
                    "servico": "COMBO (Comp + Vend)",
                    "tipo":    "COMBO",
                    "valor":   PRECO_COMBO,
                    "data":    sh._col(r_ref, "data"),
                })
                total += PRECO_COMBO
                qtd["COMBO"] += 1
                for r in grupo:
                    processados.add(id(r))
            else:
                for r in grupo:
                    if id(r) in processados:
                        continue
                    t = tipo_servico(sh._col(r, "servico"))
                    if t == "ATPV":
                        v = PRECO_ATPV
                    elif t == "PROC_COMP":
                        v = PRECO_PROC_COMP
                    elif t == "PROC_VEND":
                        v = PRECO_PROC_VEND
                    elif t == "COMBO":
                        v = PRECO_COMBO
                    else:
                        continue  # OUTRO nao cobra

                    linhas.append({
                        "cliente": sh._col(r, "cliente"),
                        "placa":   sh._col(r, "placa"),
                        "servico": sh._col(r, "servico"),
                        "tipo":    t,
                        "valor":   v,
                        "data":    sh._col(r, "data"),
                    })
                    total += v
                    qtd[t] += 1
                    processados.add(id(r))

        resultado[loja] = {
            "itens":         sorted(linhas, key=lambda x: x["data"]),
            "total":         total,
            "qtd_atpv":      qtd["ATPV"],
            "qtd_proc_comp": qtd["PROC_COMP"],
            "qtd_proc_vend": qtd["PROC_VEND"],
            "qtd_combo":     qtd["COMBO"],
        }

    return resultado


# ── Gera PDF ──────────────────────────────────────────────────────────────────

def gerar_pdf(loja: str, dados: dict, empresa_key: str, data_ini: date, data_fim: date) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    emp = EMPRESAS.get(empresa_key, EMPRESAS["unicar"])
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    COR_PRIMARIA = colors.HexColor("#1a3c6e")
    COR_SECUNDARIA = colors.HexColor("#2e6db4")
    COR_DESTAQUE = colors.HexColor("#f0f4fa")
    COR_VERDE = colors.HexColor("#1a7a3c")

    s_empresa  = ParagraphStyle("emp",  fontSize=14, fontName="Helvetica-Bold", textColor=COR_PRIMARIA, alignment=TA_LEFT)
    s_fantasia = ParagraphStyle("fan",  fontSize=10, fontName="Helvetica",      textColor=COR_SECUNDARIA, alignment=TA_LEFT)
    s_info     = ParagraphStyle("inf",  fontSize=8,  fontName="Helvetica",      textColor=colors.grey,   alignment=TA_LEFT)
    s_titulo   = ParagraphStyle("tit",  fontSize=16, fontName="Helvetica-Bold", textColor=COR_PRIMARIA,  alignment=TA_CENTER, spaceAfter=4)
    s_subtit   = ParagraphStyle("sub",  fontSize=10, fontName="Helvetica",      textColor=colors.grey,   alignment=TA_CENTER, spaceAfter=8)
    s_loja     = ParagraphStyle("loj",  fontSize=13, fontName="Helvetica-Bold", textColor=COR_PRIMARIA,  spaceAfter=4)
    s_total    = ParagraphStyle("tot",  fontSize=14, fontName="Helvetica-Bold", textColor=COR_VERDE,     alignment=TA_RIGHT)
    s_rodape   = ParagraphStyle("rod",  fontSize=7,  fontName="Helvetica",      textColor=colors.grey,   alignment=TA_CENTER)

    story = []

    # ── Cabecalho ──────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(emp["nome"], s_empresa),
        Paragraph("FATURA DE SERVICOS", s_titulo),
    ]]
    header_table = Table(header_data, colWidths=[10*cm, 7*cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(header_table)
    story.append(Paragraph(emp["fantasia"], s_fantasia))
    story.append(Paragraph("CNPJ: {}  |  {}  |  {}".format(emp["cnpj"], emp["endereco"], emp["cidade"]), s_info))
    story.append(HRFlowable(width="100%", thickness=2, color=COR_PRIMARIA, spaceAfter=8))

    # ── Info fatura ────────────────────────────────────────────────────────────
    periodo = "{} a {}".format(data_ini.strftime("%d/%m/%Y"), data_fim.strftime("%d/%m/%Y"))
    emissao = date.today().strftime("%d/%m/%Y")
    info_data = [[
        Paragraph("Periodo: <b>{}</b>".format(periodo), styles["Normal"]),
        Paragraph("Emissao: <b>{}</b>".format(emissao), styles["Normal"]),
    ]]
    info_table = Table(info_data, colWidths=[9*cm, 8*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), COR_DESTAQUE),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # ── Loja ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("Loja: {}".format(loja), s_loja))
    story.append(Spacer(1, 6))

    # ── Resumo ────────────────────────────────────────────────────────────────
    def moeda(v):
        return "R$ {:,.2f}".format(v).replace(",", "X").replace(".", ",").replace("X", ".")

    res = dados
    resumo_data = [
        ["Tipo de Servico", "Qtd", "Unit.", "Subtotal"],
    ]
    if res["qtd_atpv"] > 0:
        resumo_data.append(["ATPV / ATPVES", str(res["qtd_atpv"]),
                            moeda(PRECO_ATPV), moeda(res["qtd_atpv"] * PRECO_ATPV)])
    if res["qtd_proc_comp"] > 0:
        resumo_data.append(["Procuracao Comprador", str(res["qtd_proc_comp"]),
                            moeda(PRECO_PROC_COMP), moeda(res["qtd_proc_comp"] * PRECO_PROC_COMP)])
    if res["qtd_proc_vend"] > 0:
        resumo_data.append(["Procuracao Vendedor", str(res["qtd_proc_vend"]),
                            moeda(PRECO_PROC_VEND), moeda(res["qtd_proc_vend"] * PRECO_PROC_VEND)])
    if res["qtd_combo"] > 0:
        resumo_data.append(["Combo (Comp + Vend)", str(res["qtd_combo"]),
                            moeda(PRECO_COMBO), moeda(res["qtd_combo"] * PRECO_COMBO)])

    resumo_table = Table(resumo_data, colWidths=[8*cm, 2*cm, 3*cm, 4*cm])
    resumo_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  COR_PRIMARIA),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ("ALIGN",         (3,1), (3,-1),  "RIGHT"),
        ("BACKGROUND",    (0,1), (-1,-1), colors.white),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, COR_DESTAQUE]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ]))
    story.append(resumo_table)
    story.append(Spacer(1, 10))

    # ── Total ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=COR_SECUNDARIA))
    story.append(Spacer(1, 4))
    story.append(Paragraph("TOTAL: {}".format(moeda(res["total"])), s_total))
    story.append(Spacer(1, 16))

    # ── Detalhamento ──────────────────────────────────────────────────────────
    story.append(Paragraph("Detalhamento dos servicos", ParagraphStyle(
        "dh", fontSize=10, fontName="Helvetica-Bold", textColor=COR_PRIMARIA, spaceAfter=4)))

    det_data = [["Data", "Cliente", "Placa", "Servico", "Tipo", "Valor"]]
    TIPO_LABEL = {
        "ATPV": "ATPV", "PROC_COMP": "Proc Comp",
        "PROC_VEND": "Proc Vend", "COMBO": "Combo",
    }
    for item in res["itens"]:
        det_data.append([
            item["data"],
            item["cliente"][:25],
            item["placa"],
            item["servico"][:22],
            TIPO_LABEL.get(item["tipo"], item["tipo"]),
            moeda(item["valor"]),
        ])

    det_table = Table(det_data, colWidths=[2*cm, 5.5*cm, 2.2*cm, 4*cm, 2.3*cm, 2.5*cm])
    det_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  COR_SECUNDARIA),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("ALIGN",         (1,1), (1,-1),  "LEFT"),
        ("ALIGN",         (3,1), (3,-1),  "LEFT"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, COR_DESTAQUE]),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#dddddd")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 20))

    # ── Rodape ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "{} | CNPJ {} | {} — {}".format(emp["fantasia"], emp["cnpj"], emp["endereco"], emp["cidade"]),
        s_rodape
    ))

    doc.build(story)
    return buffer.getvalue()
