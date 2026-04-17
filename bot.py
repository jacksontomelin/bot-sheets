"""
bot.py — Bot Telegram completo para consulta da planilha de servicos
"""
import os
import logging
from datetime import date, timedelta
from calendar import monthrange

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
import sheets as sh
import cobranca as cb

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

def moeda(v):
    return "R$ {:,.2f}".format(v).replace(",", "X").replace(".", ",").replace("X", ".")

def pct(parte, total):
    return "{:.1f}%".format(parte / total * 100) if total else "0%"

def header(titulo):
    return "=" * 28 + "\n" + titulo + "\n" + "=" * 28 + "\n"

def b(texto):
    return "<b>{}</b>".format(texto)

def code(texto):
    return "<code>{}</code>".format(texto)

def _col(row, key):
    return sh._col(row, key)

def get_msg(update):
    if update.message:
        return update.message
    if update.callback_query:
        return update.callback_query.message
    return None

def _split(texto, limite=4000):
    if len(texto) <= limite:
        return [texto]
    partes, atual = [], ""
    for linha in texto.split("\n"):
        if len(atual) + len(linha) + 1 > limite:
            partes.append(atual)
            atual = ""
        atual += linha + "\n"
    if atual:
        partes.append(atual)
    return partes

def kb_principal():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Resumo Hoje",       callback_data="cmd:resumo_hoje"),
         InlineKeyboardButton("📅 Resumo Mes",        callback_data="cmd:resumo_mes")],
        [InlineKeyboardButton("📝 Procuracoes Hoje",  callback_data="cmd:proc_hoje"),
         InlineKeyboardButton("⚠️ Proc. Pendentes",   callback_data="cmd:proc_pendentes")],
        [InlineKeyboardButton("🏆 Ranking Lojas",     callback_data="cmd:rank_lojas"),
         InlineKeyboardButton("👤 Ranking Operadores",callback_data="cmd:rank_ops")],
        [InlineKeyboardButton("🎬 Videos Pendentes",  callback_data="cmd:videos"),
         InlineKeyboardButton("💰 Faturamento/Loja",  callback_data="cmd:fat_loja")],
        [InlineKeyboardButton("🗂 Por Servico",       callback_data="cmd:servicos"),
         InlineKeyboardButton("🏢 Por Grupo",         callback_data="cmd:grupos")],
        [InlineKeyboardButton("💳 Pagamentos",        callback_data="cmd:pagamentos"),
         InlineKeyboardButton("🔄 Atualizar Cache",   callback_data="cmd:cache")],
        [InlineKeyboardButton("🧾 Gerar Cobranca",    callback_data="cmd:cobranca")],
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 " + b("Bot de Gestao - Planilha de Servicos") + "\n\n"
        "Escolha uma opcao abaixo ou use os comandos:\n\n"
        + b("📊 Resumos") + "\n"
        "• /hoje — resumo do dia\n"
        "• /mes — resumo do mes atual\n"
        "• /semana — ultimos 7 dias\n\n"
        + b("📝 Procuracoes") + "\n"
        "• /procuracoes — procuracoes de hoje\n"
        "• /pendentes — pendentes hoje\n"
        "• /pendentes_mes — pendentes do mes\n\n"
        + b("🏆 Rankings") + "\n"
        "• /ranking — top lojas do mes\n"
        "• /operadores — top operadores\n\n"
        + b("🎬 Videos") + "\n"
        "• /videos — videos pendentes hoje\n\n"
        + b("💰 Financeiro") + "\n"
        "• /faturamento — por loja\n"
        "• /grupos — por grupo\n"
        "• /pagamentos — formas de pagamento\n\n"
        + b("🔍 Busca") + "\n"
        "• /buscar nome ou placa\n\n"
        "🔄 /atualizar — forca atualizacao\n"
    )
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=kb_principal())

async def ajuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)

async def cmd_hoje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _resumo_hoje(update)

async def _resumo_hoje(update):
    msg = get_msg(update)
    try:
        r = sh.resumo_hoje()
        proc_hoje = sh.procuracoes_hoje()
        pend = sh.procuracoes_pendentes()
        texto = header("📊 RESUMO DO DIA — " + r["data"])
        texto += "📋 Total de registros: " + b(str(r["total"])) + "\n"
        texto += "💵 Faturamento bruto: " + b(moeda(r["faturamento"])) + "\n"
        texto += "💰 Custo liquido: " + b(moeda(r["liquido"])) + "\n\n"
        texto += "📝 Procuracoes realizadas: " + b(str(len(proc_hoje))) + "\n"
        texto += "⚠️ Procuracoes pendentes: " + b(str(len(pend))) + "\n"
        if pend:
            texto += "\n🔴 " + b("Pendentes:") + "\n"
            for p in pend[:5]:
                texto += "  • {} — {} — {}\n".format(_col(p, "cliente"), _col(p, "loja"), _col(p, "procuracao") or "Sem status")
            if len(pend) > 5:
                texto += "  ...e mais {}\n".format(len(pend) - 5)
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _resumo_mes(update)

async def _resumo_mes(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        fim = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])
        r = sh.resumo_periodo(ini, fim)
        texto = header("📅 RESUMO DO MES — {} a {}".format(r["inicio"], r["fim"]))
        texto += "📋 Total: " + b(str(r["total"])) + "\n"
        texto += "💵 Faturamento: " + b(moeda(r["faturamento"])) + "\n"
        texto += "💰 Liquido: " + b(moeda(r["liquido"])) + "\n"
        texto += "📝 Procuracoes: " + b(str(r["procuracoes"])) + "\n"
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_semana(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        hoje = date.today()
        ini = hoje - timedelta(days=6)
        r = sh.resumo_periodo(ini, hoje)
        texto = header("📅 ULTIMOS 7 DIAS — {} a {}".format(r["inicio"], r["fim"]))
        texto += "📋 Total: " + b(str(r["total"])) + "\n"
        texto += "💵 Faturamento: " + b(moeda(r["faturamento"])) + "\n"
        texto += "💰 Liquido: " + b(moeda(r["liquido"])) + "\n"
        texto += "📝 Procuracoes: " + b(str(r["procuracoes"])) + "\n"
        await update.message.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await update.message.reply_text("❌ Erro: {}".format(e))

async def cmd_procuracoes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _proc_hoje(update)

async def _proc_hoje(update):
    msg = get_msg(update)
    try:
        procs = sh.procuracoes_hoje()
        if not procs:
            await msg.reply_text("📝 Nenhuma procuracao registrada hoje.")
            return
        texto = header("📝 PROCURACOES HOJE — {}".format(date.today().strftime("%d/%m/%Y")))
        texto += "Total: " + b(str(len(procs))) + "\n\n"
        for i, r in enumerate(procs, 1):
            status = _col(r, "procuracao") or "—"
            emoji = "✅" if "ok" in status.lower() else "⚠️"
            texto += "{} {}. ".format(emoji, i) + b(_col(r, "cliente")) + "\n"
            texto += "   🏪 {} | 🚗 {}\n".format(_col(r, "loja"), _col(r, "placa"))
            texto += "   📋 {} | Status: {}\n".format(_col(r, "servico"), code(status))
            texto += "   👤 {}\n\n".format(_col(r, "feito_por"))
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_pendentes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pendentes(update, True)

async def cmd_pendentes_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pendentes(update, False)

async def _pendentes(update, apenas_hoje):
    msg = get_msg(update)
    try:
        hoje = date.today()
        if apenas_hoje:
            pend = sh.procuracoes_pendentes(hoje, hoje)
            periodo = "HOJE — {}".format(hoje.strftime("%d/%m/%Y"))
        else:
            ini = date(hoje.year, hoje.month, 1)
            pend = sh.procuracoes_pendentes(ini, hoje)
            periodo = "MES — {} a {}".format(ini.strftime("%d/%m"), hoje.strftime("%d/%m/%Y"))
        if not pend:
            await msg.reply_text("✅ Nenhuma procuracao pendente ({}).".format(periodo))
            return
        texto = header("⚠️ PROCURACOES PENDENTES — {}".format(periodo))
        texto += "Total: " + b(str(len(pend))) + "\n\n"
        por_loja = {}
        for r in pend:
            loja = _col(r, "loja") or "Sem Loja"
            por_loja.setdefault(loja, []).append(r)
        for loja, itens in sorted(por_loja.items()):
            texto += "🏪 " + b("{} ({})".format(loja, len(itens))) + "\n"
            for r in itens:
                status = _col(r, "procuracao") or "Sem status"
                texto += "  • {} | {}\n".format(_col(r, "cliente"), _col(r, "placa"))
                texto += "    {} | {}\n".format(_col(r, "servico"), code(status))
            texto += "\n"
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_ranking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ranking_lojas(update)

async def _ranking_lojas(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        ranking = sh.ranking_lojas(ini, hoje)
        if not ranking:
            await msg.reply_text("Sem dados para o ranking.")
            return
        total_qtd = sum(q for _, q, _ in ranking)
        medalhas = ["🥇", "🥈", "🥉"] + ["▪️"] * 20
        texto = header("🏆 RANKING DE LOJAS — {}".format(ini.strftime("%m/%Y")))
        for i, (loja, qtd, fat) in enumerate(ranking):
            barra = "█" * min(int(qtd / max(ranking[0][1], 1) * 10), 10)
            texto += "{} ".format(medalhas[i]) + b(loja) + "\n"
            texto += "   {} {} ({})\n".format(barra, qtd, pct(qtd, total_qtd))
            texto += "   💵 {}\n\n".format(moeda(fat))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_operadores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ranking_ops(update)

async def _ranking_ops(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        ranking = sh.ranking_operadores(ini, hoje)
        if not ranking:
            await msg.reply_text("Sem dados.")
            return
        total = sum(q for _, q in ranking)
        medalhas = ["🥇", "🥈", "🥉"] + ["▪️"] * 20
        texto = header("👤 RANKING DE OPERADORES — {}".format(ini.strftime("%m/%Y")))
        for i, (op, qtd) in enumerate(ranking):
            barra = "█" * min(int(qtd / max(ranking[0][1], 1) * 10), 10)
            texto += "{} ".format(medalhas[i]) + b(op) + "\n"
            texto += "   {} {} ({})\n\n".format(barra, qtd, pct(qtd, total))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_videos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _videos(update)

async def _videos(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        pendentes = sh.videos_pendentes(hoje, hoje)
        if not pendentes:
            await msg.reply_text("✅ Nenhum video pendente hoje.")
            return
        texto = header("🎬 VIDEOS PENDENTES — {}".format(hoje.strftime("%d/%m/%Y")))
        texto += "Total: " + b(str(len(pendentes))) + "\n\n"
        for r in pendentes:
            status = _col(r, "video") or "—"
            texto += "⚠️ " + b(_col(r, "cliente")) + "\n"
            texto += "   🚗 {} | 🏪 {}\n".format(_col(r, "placa"), _col(r, "loja"))
            texto += "   📋 {} | Video: {}\n".format(_col(r, "servico"), code(status))
            texto += "   👤 {}\n\n".format(_col(r, "feito_por"))
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_faturamento(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _fat_loja(update)

async def _fat_loja(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        fat = sh.faturamento_por_loja(ini, hoje)
        if not fat:
            await msg.reply_text("Sem dados.")
            return
        total = sum(fat.values())
        texto = header("💰 FATURAMENTO POR LOJA — {}".format(ini.strftime("%m/%Y")))
        texto += "Total geral: " + b(moeda(total)) + "\n\n"
        for loja, v in fat.items():
            barra = "█" * min(int(v / max(fat.values()) * 8), 8)
            texto += "🏪 " + b(loja) + "\n   {} {} ({})\n\n".format(barra, moeda(v), pct(v, total))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_servicos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _servicos(update)

async def _servicos(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        svcs = sh.servicos_por_tipo(ini, hoje)
        if not svcs:
            await msg.reply_text("Sem dados.")
            return
        total = sum(svcs.values())
        texto = header("🗂 SERVICOS DO MES — {}".format(ini.strftime("%m/%Y")))
        texto += "Total: " + b(str(total)) + " registros\n\n"
        for svc, qtd in svcs.items():
            barra = "█" * min(int(qtd / max(svcs.values()) * 8), 8)
            texto += "📋 " + b(svc) + "\n   {} {} ({})\n\n".format(barra, qtd, pct(qtd, total))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_grupos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _grupos(update)

async def _grupos(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        grupos = sh.resumo_por_grupo(ini, hoje)
        if not grupos:
            await msg.reply_text("Sem dados.")
            return
        total_fat = sum(g["faturamento"] for g in grupos.values())
        texto = header("🏢 RESUMO POR GRUPO — {}".format(ini.strftime("%m/%Y")))
        for grupo, d in grupos.items():
            texto += "🏢 " + b(grupo) + "\n"
            texto += "   📋 {} registros\n".format(d["qtd"])
            texto += "   💵 {} ({})\n".format(moeda(d["faturamento"]), pct(d["faturamento"], total_fat))
            texto += "   💰 Liquido: {}\n\n".format(moeda(d["liquido"]))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_pagamentos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pagamentos(update)

async def _pagamentos(update):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        pgs = sh.formas_pagamento(ini, hoje)
        if not pgs:
            await msg.reply_text("Sem dados.")
            return
        total = sum(pgs.values())
        texto = header("💳 FORMAS DE PAGAMENTO — {}".format(ini.strftime("%m/%Y")))
        texto += "Total: " + b(str(total)) + " transacoes\n\n"
        icones = {"ACERTO": "🤝", "PIX": "📱", "DINHEIRO": "💵", "CARTAO": "💳", "BOLETO": "📄"}
        for pg, qtd in pgs.items():
            ico = next((v for k, v in icones.items() if k in pg.upper()), "💳")
            barra = "█" * min(int(qtd / max(pgs.values()) * 8), 8)
            texto += "{} ".format(ico) + b(pg) + "\n   {} {} ({})\n\n".format(barra, qtd, pct(qtd, total))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("❌ Erro: {}".format(e))

async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Use: /buscar nome ou /buscar placa")
        return
    termo = " ".join(ctx.args)
    try:
        resultados = sh.buscar_cliente(termo)
        if not resultados:
            await update.message.reply_text("🔍 Nenhum resultado para: {}".format(termo))
            return
        texto = header("🔍 BUSCA: {}".format(termo))
        texto += b("{} resultado(s)".format(len(resultados))) + "\n\n"
        for r in resultados[:15]:
            texto += "📅 {} | 🏪 {}\n".format(_col(r, "data"), _col(r, "loja"))
            texto += "👤 " + b(_col(r, "cliente")) + "\n"
            texto += "🚗 {} — {}\n".format(_col(r, "placa"), _col(r, "veiculo"))
            texto += "📋 {} | 💵 {}\n".format(_col(r, "servico"), _col(r, "valor"))
            texto += "📝 Proc: {} | 🎬 Video: {}\n\n".format(
                code(_col(r, "procuracao") or "—"), code(_col(r, "video") or "—"))
        if len(resultados) > 15:
            texto += "...e mais {} resultado(s).".format(len(resultados) - 15)
        for chunk in _split(texto):
            await update.message.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await update.message.reply_text("❌ Erro: {}".format(e))

async def cmd_atualizar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sh.invalidar_cache()
    msg = get_msg(update)
    await msg.reply_text("🔄 Cache invalidado! Proximos dados virao direto da planilha.")

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cmd = query.data.replace("cmd:", "")
    dispatch = {
        "resumo_hoje":    lambda: _resumo_hoje(update),
        "resumo_mes":     lambda: _resumo_mes(update),
        "proc_hoje":      lambda: _proc_hoje(update),
        "proc_pendentes": lambda: _pendentes(update, True),
        "rank_lojas":     lambda: _ranking_lojas(update),
        "rank_ops":       lambda: _ranking_ops(update),
        "videos":         lambda: _videos(update),
        "fat_loja":       lambda: _fat_loja(update),
        "servicos":       lambda: _servicos(update),
        "grupos":         lambda: _grupos(update),
        "pagamentos":     lambda: _pagamentos(update),
        "cache":          lambda: cmd_atualizar(update, ctx),
        "cobranca":       lambda: _cobranca_menu(update),
    }
    fn = dispatch.get(cmd)
    if fn:
        await fn()
        return

    # Cobranca flow
    msg = query.message
    if query.data.startswith("cob_emp:"):
        empresa_key = query.data.split(":")[1]
        query._bot  # just to reference
        await msg.reply_text(
            "Empresa selecionada. Escolha o periodo:",
            reply_markup=kb_periodo()
        )
        # Store empresa in message caption hack via new message with state
        await msg.reply_text("cob_estado:{}".format(empresa_key))

    elif query.data.startswith("cob_per:"):
        from calendar import monthrange as mr
        periodo_key = query.data.split(":")[1]
        hoje = date.today()
        if periodo_key == "mes":
            ini = date(hoje.year, hoje.month, 1)
            fim = date(hoje.year, hoje.month, mr(hoje.year, hoje.month)[1])
        elif periodo_key == "mes_ant":
            if hoje.month == 1:
                ini = date(hoje.year-1, 12, 1); fim = date(hoje.year-1, 12, 31)
            else:
                ini = date(hoje.year, hoje.month-1, 1)
                fim = date(hoje.year, hoje.month-1, mr(hoje.year, hoje.month-1)[1])
        elif periodo_key == "semana":
            ini = hoje - timedelta(days=6); fim = hoje
        else:
            ini = fim = hoje
        # Find empresa from recent messages - default unicar, user can choose
        empresa_key = ctx.user_data.get("cob_empresa", "unicar")
        await _cobranca_lojas(msg, empresa_key, ini, fim)

    elif query.data.startswith("cob_loja:"):
        parts = query.data.split(":")
        empresa_key = parts[1]
        ini_str     = parts[2]
        fim_str     = parts[3]
        loja_nome   = ":".join(parts[4:])
        await _gerar_pdf_loja(msg, empresa_key, ini_str, fim_str, loja_nome)

async def texto_livre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    if any(w in txt for w in ["hoje", "resumo do dia"]):
        await _resumo_hoje(update)
    elif any(w in txt for w in ["mes", "mensal"]):
        await _resumo_mes(update)
    elif any(w in txt for w in ["pendente", "faltando"]):
        await _pendentes(update, True)
    elif any(w in txt for w in ["procuracao"]):
        await _proc_hoje(update)
    elif any(w in txt for w in ["ranking", "melhor loja"]):
        await _ranking_lojas(update)
    elif any(w in txt for w in ["operador"]):
        await _ranking_ops(update)
    elif any(w in txt for w in ["video"]):
        await _videos(update)
    elif any(w in txt for w in ["faturamento"]):
        await _fat_loja(update)
    elif any(w in txt for w in ["servico"]):
        await _servicos(update)
    elif any(w in txt for w in ["grupo"]):
        await _grupos(update)
    elif any(w in txt for w in ["pagamento", "pix"]):
        await _pagamentos(update)
    elif any(w in txt for w in ["cobranca", "cobrar", "fatura"]):
        await _cobranca_menu(update)
    else:
        await update.message.reply_text("Nao entendi. Use /ajuda:", reply_markup=kb_principal())

# ── COBRANCA ──────────────────────────────────────────────────────────────────

def kb_empresa():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Unicar",    callback_data="cob_emp:unicar"),
         InlineKeyboardButton("🏢 Uniaocert", callback_data="cob_emp:uniao")],
    ])

def kb_periodo():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Atual",      callback_data="cob_per:mes"),
         InlineKeyboardButton("📅 Mes Anterior",   callback_data="cob_per:mes_ant")],
        [InlineKeyboardButton("📅 Ultimos 7 dias", callback_data="cob_per:semana"),
         InlineKeyboardButton("📅 Hoje",           callback_data="cob_per:hoje")],
    ])

async def cmd_cobranca(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _cobranca_menu(update)

async def _cobranca_menu(update):
    msg = get_msg(update)
    await msg.reply_text(
        "🧾 " + b("GERACAO DE COBRANCA") + "\n\nSelecione a empresa emissora:",
        parse_mode="HTML",
        reply_markup=kb_empresa()
    )

async def _cobranca_lojas(msg, empresa_key, ini, fim):
    from calendar import monthrange as mr
    try:
        dados = cb.calcular_cobranca(ini, fim)
        if not dados:
            await msg.reply_text("Nenhum dado encontrado para o periodo.")
            return
        botoes = []
        for loja in sorted(dados.keys()):
            total = dados[loja]["total"]
            if total > 0:
                label = "{} — {}".format(loja[:20], moeda(total))
                botoes.append([InlineKeyboardButton(
                    label,
                    callback_data="cob_loja:{}:{}:{}:{}".format(
                        empresa_key, ini.strftime("%Y%m%d"), fim.strftime("%Y%m%d"), loja[:30])
                )])
        botoes.append([InlineKeyboardButton(
            "📄 TODAS AS LOJAS",
            callback_data="cob_loja:{}:{}:{}:TODAS".format(
                empresa_key, ini.strftime("%Y%m%d"), fim.strftime("%Y%m%d"))
        )])
        total_geral = sum(d["total"] for d in dados.values())
        texto = header("🧾 COBRANCA — {} a {}".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")))
        texto += "Total geral: " + b(moeda(total_geral)) + "\n"
        texto += "Lojas com cobranca: " + b(str(len([d for d in dados.values() if d["total"] > 0]))) + "\n\n"
        texto += "Selecione a loja para gerar o PDF:"
        await msg.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes))
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))

async def _gerar_pdf_loja(msg, empresa_key, ini_str, fim_str, loja_nome):
    await msg.reply_text("Gerando PDF, aguarde...")
    try:
        ini = date(int(ini_str[:4]), int(ini_str[4:6]), int(ini_str[6:]))
        fim = date(int(fim_str[:4]), int(fim_str[4:6]), int(fim_str[6:]))
        if loja_nome == "TODAS":
            dados = cb.calcular_cobranca(ini, fim)
            for loja, d in sorted(dados.items()):
                if d["total"] == 0:
                    continue
                pdf_bytes = cb.gerar_pdf(loja, d, empresa_key, ini, fim)
                nome = "cobranca_{}_{}.pdf".format(loja.replace(" ","_")[:20], ini.strftime("%Y%m"))
                await msg.reply_document(document=pdf_bytes, filename=nome,
                    caption="🧾 {} — {}".format(loja, moeda(d["total"])))
        else:
            dados = cb.calcular_cobranca(ini, fim, loja_nome)
            if loja_nome not in dados or dados[loja_nome]["total"] == 0:
                await msg.reply_text("Nenhuma cobranca para {} no periodo.".format(loja_nome))
                return
            d = dados[loja_nome]
            texto = header("🧾 COBRANCA: {}".format(loja_nome))
            texto += "Periodo: {} a {}\n\n".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
            if d["qtd_atpv"] > 0:
                texto += "ATPV/ATPVES: {} x {} = {}\n".format(d["qtd_atpv"], moeda(cb.PRECO_ATPV), moeda(d["qtd_atpv"]*cb.PRECO_ATPV))
            if d["qtd_proc_comp"] > 0:
                texto += "Proc Comprador: {} x {} = {}\n".format(d["qtd_proc_comp"], moeda(cb.PRECO_PROC_COMP), moeda(d["qtd_proc_comp"]*cb.PRECO_PROC_COMP))
            if d["qtd_proc_vend"] > 0:
                texto += "Proc Vendedor: {} x {} = {}\n".format(d["qtd_proc_vend"], moeda(cb.PRECO_PROC_VEND), moeda(d["qtd_proc_vend"]*cb.PRECO_PROC_VEND))
            if d["qtd_combo"] > 0:
                texto += "Combo (Comp+Vend): {} x {} = {}\n".format(d["qtd_combo"], moeda(cb.PRECO_COMBO), moeda(d["qtd_combo"]*cb.PRECO_COMBO))
            texto += "\n" + b("TOTAL: {}".format(moeda(d["total"])))
            await msg.reply_text(texto, parse_mode="HTML")
            pdf_bytes = cb.gerar_pdf(loja_nome, d, empresa_key, ini, fim)
            nome = "cobranca_{}_{}.pdf".format(loja_nome.replace(" ","_")[:20], ini.strftime("%Y%m"))
            await msg.reply_document(document=pdf_bytes, filename=nome, caption="📄 Fatura gerada!")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro ao gerar PDF: {}".format(e))

def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("ajuda",         ajuda))
    app.add_handler(CommandHandler("hoje",          cmd_hoje))
    app.add_handler(CommandHandler("mes",           cmd_mes))
    app.add_handler(CommandHandler("semana",        cmd_semana))
    app.add_handler(CommandHandler("procuracoes",   cmd_procuracoes))
    app.add_handler(CommandHandler("pendentes",     cmd_pendentes))
    app.add_handler(CommandHandler("pendentes_mes", cmd_pendentes_mes))
    app.add_handler(CommandHandler("ranking",       cmd_ranking))
    app.add_handler(CommandHandler("operadores",    cmd_operadores))
    app.add_handler(CommandHandler("videos",        cmd_videos))
    app.add_handler(CommandHandler("faturamento",   cmd_faturamento))
    app.add_handler(CommandHandler("servicos",      cmd_servicos))
    app.add_handler(CommandHandler("grupos",        cmd_grupos))
    app.add_handler(CommandHandler("pagamentos",    cmd_pagamentos))
    app.add_handler(CommandHandler("buscar",        cmd_buscar))
    app.add_handler(CommandHandler("atualizar",     cmd_atualizar))
    app.add_handler(CommandHandler("cobranca",      cmd_cobranca))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_livre))
    log.info("✅ Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
