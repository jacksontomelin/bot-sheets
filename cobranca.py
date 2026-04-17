"""
cobranca.py — Calcula cobrancas e gera PDF por loja
Regras:
  PROC V / PROC V + CONTRATO               -> R$ 125,00
  PROC C / COMPRADOR sozinho               -> R$ 75,00
  ASS VEND + ASS COMP (combo doc)          -> R$ 125,00
  ASS COMP sozinho                         -> R$ 75,00
  ASS VEND / ATPV / CV / ASS DOC / VIDEO   -> R$ 30,00
  IMPL. SAFEID e outros                    -> R$ 0,00
"""
from __future__ import annotations
import io
from datetime import date
from collections import defaultdict
import sheets as sh

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

PRECO_SERVICO   = 30.00
PRECO_PROC_COMP = 75.00
PRECO_PROC_VEND = 125.00
PRECO_COMBO     = 125.00


def classificar_linha(svc: str) -> list[tuple[str, float]]:
    s = svc.upper().strip()
    tem_proc_v   = "PROC V" in s
    tem_proc_c   = "PROC C" in s or "COMPRADOR" in s
    tem_ass_vend = "ASS VEND" in s
    tem_ass_comp = "ASS COMP" in s
    tem_contrato = "CONTRATO" in s
    tem_servico  = "CV" in s or "ASS DOC" in s or "VIDEO" in s or "ATPV" in s or tem_ass_vend

    combo_proc = (tem_proc_v or tem_contrato) and tem_proc_c
    combo_ass  = tem_ass_vend and tem_ass_comp

    if combo_proc or combo_ass:
        return [("COMBO", PRECO_COMBO)]
    elif tem_proc_v or tem_contrato:
        return [("PROC_VEND", PRECO_PROC_VEND)]
    elif tem_proc_c:
        return [("PROC_COMP", PRECO_PROC_COMP)]
    elif tem_ass_comp and not tem_ass_vend:
        return [("PROC_COMP", PRECO_PROC_COMP)]
    elif tem_servico:
        return [("SERVICO", PRECO_SERVICO)]
    return []


def listar_lojas(data_ini: date, data_fim: date) -> list[str]:
    rows = sh._fetch()
    lojas = set()
    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if d and data_ini <= d <= data_fim:
            loja = sh._col(r, "loja")
            if loja:
                lojas.add(loja.strip())
    return sorted(lojas)


def calcular_cobranca(data_ini: date, data_fim: date, loja_filtro: str | None = None) -> dict:
    rows = sh._fetch()
    por_loja: dict = defaultdict(list)

    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if not d or not (data_ini <= d <= data_fim):
            continue
        loja = (sh._col(r, "loja") or "Sem Loja").strip()
        if loja_filtro and loja_filtro != "TODAS" and loja.lower() != loja_filtro.lower():
            continue
        por_loja[loja].append(r)

    resultado = {}
    for loja, itens_loja in por_loja.items():
        linhas = []
        total = 0.0
        qtd = defaultdict(int)

        for r in itens_loja:
            svc = sh._col(r, "servico")
            cobrados = classificar_linha(svc)
            if not cobrados:
                continue
            for tipo, valor in cobrados:
                linhas.append({
                    "data":    sh._col(r, "data"),
                    "cliente": sh._col(r, "cliente"),
                    "placa":   sh._col(r, "placa"),
                    "servico": svc,
                    "tipo":    tipo,
                    "valor":   valor,
                })
                total += valor
                qtd[tipo] += 1

        resultado[loja] = {
            "itens":         sorted(linhas, key=lambda x: x["data"]),
            "total":         total,
            "qtd_servico":   qtd["SERVICO"],
            "qtd_proc_comp": qtd["PROC_COMP"],
            "qtd_proc_vend": qtd["PROC_VEND"],
            "qtd_combo":     qtd["COMBO"],
        }

    return resultado


def relatorio_pendentes(data_ini: date, data_fim: date) -> dict:
    """Retorna resumo financeiro de pendentes por loja (procuracoes sem status OK)"""
    rows = sh._fetch()
    resultado = defaultdict(lambda: {"total": 0.0, "qtd": 0, "itens": []})

    for r in rows:
        d = sh._parse_date(sh._col(r, "data"))
        if not d or not (data_ini <= d <= data_fim):
            continue
        status_proc = sh._col(r, "procuracao").upper()
        if status_proc in ("OK", "OK NO ASSINADOR", "FEITA", "CONCLUIDA", "CONCLUIDA"):
            continue
        svc = sh._col(r, "servico")
        cobrados = classificar_linha(svc)
        if not cobrados:
            continue
        loja = (sh._col(r, "loja") or "Sem Loja").strip()
        for tipo, valor in cobrados:
            resultado[loja]["total"] += valor
            resultado[loja]["qtd"] += 1
            resultado[loja]["itens"].append({
                "data":    sh._col(r, "data"),
                "cliente": sh._col(r, "cliente"),
                "placa":   sh._col(r, "placa"),
                "servico": svc,
                "status":  sh._col(r, "procuracao") or "Sem status",
                "valor":   valor,
            })

    return dict(sorted(resultado.items()))


def moeda(v: float) -> str:
    return "R$ {:,.2f}".format(v).replace(",","X").replace(".",",").replace("X",".")


def gerar_pdf(loja: str, dados: dict, empresa_key: str, data_ini: date, data_fim: date) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    emp = EMPRESAS.get(empresa_key, EMPRESAS["unicar"])
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    COR_P  = colors.HexColor("#1a3c6e")
    COR_S  = colors.HexColor("#2e6db4")
    COR_BG = colors.HexColor("#f0f4fa")
    COR_OK = colors.HexColor("#1a7a3c")

    def sp(name, **kw):
        return ParagraphStyle(name, **kw)

    s_emp  = sp("emp", fontSize=13, fontName="Helvetica-Bold", textColor=COR_P, leading=16)
    s_fan  = sp("fan", fontSize=9,  fontName="Helvetica",      textColor=COR_S)
    s_inf  = sp("inf", fontSize=7,  fontName="Helvetica",      textColor=colors.grey)
    s_tit  = sp("tit", fontSize=15, fontName="Helvetica-Bold", textColor=COR_P, alignment=TA_CENTER)
    s_loja = sp("loj", fontSize=12, fontName="Helvetica-Bold", textColor=COR_P)
    s_tot  = sp("tot", fontSize=13, fontName="Helvetica-Bold", textColor=COR_OK, alignment=TA_RIGHT)
    s_dh   = sp("dh",  fontSize=9,  fontName="Helvetica-Bold", textColor=COR_P,  spaceBefore=8)
    s_rod  = sp("rod", fontSize=7,  fontName="Helvetica",      textColor=colors.grey, alignment=TA_CENTER)

    story = []

    # Cabecalho
    cab = Table([[Paragraph(emp["nome"], s_emp), Paragraph("FATURA DE SERVICOS", s_tit)]],
                colWidths=[10*cm, 7*cm])
    cab.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(cab)
    story.append(Paragraph(emp["fantasia"], s_fan))
    story.append(Paragraph("CNPJ: {}  |  {}  |  {}".format(emp["cnpj"], emp["endereco"], emp["cidade"]), s_inf))
    story.append(HRFlowable(width="100%", thickness=2, color=COR_P, spaceAfter=8))

    # Info periodo
    info = Table([[
        Paragraph("Periodo: <b>{} a {}</b>".format(data_ini.strftime("%d/%m/%Y"), data_fim.strftime("%d/%m/%Y")), styles["Normal"]),
        Paragraph("Emissao: <b>{}</b>".format(date.today().strftime("%d/%m/%Y")), styles["Normal"]),
        Paragraph("Empresa: <b>{}</b>".format(emp["fantasia"]), styles["Normal"]),
    ]], colWidths=[6*cm, 4.5*cm, 6.5*cm])
    info.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),COR_BG),
        ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8), ("FONTSIZE",(0,0),(-1,-1),8),
    ]))
    story.append(info)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Loja: {}".format(loja), s_loja))
    story.append(Spacer(1, 6))

    # Resumo
    res = dados
    resumo = [["Tipo de Servico", "Qtd", "Unit.", "Subtotal"]]
    if res["qtd_servico"] > 0:
        resumo.append(["ATPV / ASS VEND / CV / ASS DOC", str(res["qtd_servico"]),
            moeda(PRECO_SERVICO), moeda(res["qtd_servico"] * PRECO_SERVICO)])
    if res["qtd_proc_comp"] > 0:
        resumo.append(["Procuracao Comprador", str(res["qtd_proc_comp"]),
            moeda(PRECO_PROC_COMP), moeda(res["qtd_proc_comp"] * PRECO_PROC_COMP)])
    if res["qtd_proc_vend"] > 0:
        resumo.append(["Procuracao Vendedor (PROC V)", str(res["qtd_proc_vend"]),
            moeda(PRECO_PROC_VEND), moeda(res["qtd_proc_vend"] * PRECO_PROC_VEND)])
    if res["qtd_combo"] > 0:
        resumo.append(["Combo (Comp + Vend)", str(res["qtd_combo"]),
            moeda(PRECO_COMBO), moeda(res["qtd_combo"] * PRECO_COMBO)])

    rt = Table(resumo, colWidths=[8*cm, 2*cm, 3*cm, 4*cm])
    rt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),COR_P), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
        ("ALIGN",(1,0),(-1,-1),"CENTER"), ("ALIGN",(3,1),(3,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#dddddd")),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(rt)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=COR_S))
    story.append(Spacer(1, 4))
    story.append(Paragraph("TOTAL: {}".format(moeda(res["total"])), s_tot))
    story.append(Spacer(1, 14))

    # Detalhamento
    story.append(Paragraph("Detalhamento", s_dh))
    TIPO_LABEL = {"SERVICO":"R$ 30","PROC_COMP":"Proc Comp","PROC_VEND":"Proc Vend","COMBO":"Combo"}
    det = [["Data","Cliente","Placa","Servico","Tipo","Valor"]]
    for item in res["itens"]:
        det.append([
            item["data"], item["cliente"][:24], item["placa"],
            item["servico"][:22], TIPO_LABEL.get(item["tipo"], item["tipo"]),
            moeda(item["valor"]),
        ])
    dt = Table(det, colWidths=[2*cm, 5.5*cm, 2.2*cm, 4*cm, 2.3*cm, 2.5*cm])
    dt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),COR_S), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(0,0),(-1,-1),"CENTER"), ("ALIGN",(1,1),(1,-1),"LEFT"),
        ("ALIGN",(3,1),(3,-1),"LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dddddd")),
        ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(dt)
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "{} | CNPJ {} | {} - {}".format(emp["fantasia"], emp["cnpj"], emp["endereco"], emp["cidade"]),
        s_rod))

    doc.build(story)
    return buffer.getvalue()
