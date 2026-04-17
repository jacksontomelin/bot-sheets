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
import extras as ex

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
        "• /buscar nome ou placa\n"
        "• /loja nome — painel completo da loja\n\n"
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

    msg = query.message

    if query.data.startswith("cob_emp:"):
        empresa_key = query.data.split(":")[1]
        ctx.user_data["cob_empresa"] = empresa_key
        emp = cb.EMPRESAS[empresa_key]
        await msg.reply_text(
            "Empresa: " + b(emp["fantasia"]) + "\n\nPasso 2 — Selecione o periodo:",
            parse_mode="HTML", reply_markup=kb_periodo_cob()
        )

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
        ctx.user_data["cob_ini"] = ini
        ctx.user_data["cob_fim"] = fim
        await _step_lojas_cob(msg, ctx)

    elif query.data.startswith("cob_loja:"):
        loja_nome = ":".join(query.data.split(":")[1:])
        await _gerar_pdf_cobranca(msg, ctx, loja_nome)

    elif query.data.startswith("pend_fin:"):
        periodo_key = query.data.split(":")[1]
        await _mostrar_pendentes_fin(msg, periodo_key)

    elif query.data.startswith("loja_painel:"):
        loja_nome = ":".join(query.data.split(":")[1:])
        await _mostrar_painel_loja(msg, loja_nome)

    elif query.data.startswith("op_painel:"):
        op_nome = ":".join(query.data.split(":")[1:])
        await _mostrar_painel_op(msg, op_nome)

    elif query.data.startswith("ok_proc:"):
        row_val = query.data.split(":")[1]
        try:
            if row_val == "TODAS":
                hoje = date.today()
                pend = sh.procuracoes_pendentes(hoje, hoje)
                count = 0
                for r in pend:
                    rn = r.get("__row__", 0)
                    if rn:
                        sh.marcar_procuracao_ok(rn)
                        count += 1
                await msg.reply_text("✅ {} procuracoes marcadas como OK!".format(count))
            else:
                sh.marcar_procuracao_ok(int(row_val))
                await msg.reply_text("✅ Procuracao marcada como OK!")
        except Exception as e:
            await msg.reply_text("Erro: {}".format(e))

    elif query.data.startswith("ok_video:"):
        row_val = query.data.split(":")[1]
        try:
            if row_val == "TODOS":
                hoje = date.today()
                pend = sh.videos_pendentes(hoje, hoje)
                count = 0
                for r in pend:
                    rn = r.get("__row__", 0)
                    if rn:
                        sh.marcar_video_ok(rn)
                        count += 1
                await msg.reply_text("✅ {} videos marcados como OK!".format(count))
            else:
                sh.marcar_video_ok(int(row_val))
                await msg.reply_text("✅ Video marcado como OK!")
        except Exception as e:
            await msg.reply_text("Erro: {}".format(e))

    elif query.data.startswith("rel_pdf:"):
        empresa_key = query.data.split(":")[1]
        await _gerar_relatorio_pdf(msg, empresa_key)

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
    elif txt.startswith("loja ") or txt.startswith("/loja "):
        termo = txt.replace("loja ", "").replace("/loja ", "").strip()
        ctx.args = termo.split()
        await cmd_painel_loja(update, ctx)
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



# ── COBRANCA ──────────────────────────────────────────────────────────────────

def kb_empresa():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Unicar",    callback_data="cob_emp:unicar"),
         InlineKeyboardButton("🏢 Uniaocert", callback_data="cob_emp:uniao")],
    ])

def kb_periodo_cob():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Atual",      callback_data="cob_per:mes"),
         InlineKeyboardButton("📅 Mes Anterior",   callback_data="cob_per:mes_ant")],
        [InlineKeyboardButton("📅 Ultimos 7 dias", callback_data="cob_per:semana"),
         InlineKeyboardButton("📅 Hoje",           callback_data="cob_per:hoje")],
    ])

async def cmd_cobranca(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    ctx.user_data["cob_step"] = "empresa"
    await msg.reply_text(
        "🧾 " + b("SISTEMA DE COBRANCA") + "\n\nPasso 1 — Selecione a empresa emissora:",
        parse_mode="HTML", reply_markup=kb_empresa()
    )

async def cmd_pendentes_fin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _relatorio_pendentes_fin(update)

async def _relatorio_pendentes_fin(update):
    msg = get_msg(update)
    await msg.reply_text(
        "💰 " + b("PENDENTES FINANCEIRO") + "\n\nSelecione o periodo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Mes Atual",      callback_data="pend_fin:mes"),
             InlineKeyboardButton("📅 Mes Anterior",   callback_data="pend_fin:mes_ant")],
            [InlineKeyboardButton("📅 Ultimos 7 dias", callback_data="pend_fin:semana"),
             InlineKeyboardButton("📅 Hoje",           callback_data="pend_fin:hoje")],
        ])
    )

async def _mostrar_pendentes_fin(msg, periodo_key):
    from calendar import monthrange as mr
    hoje = date.today()
    if periodo_key == "mes":
        ini = date(hoje.year, hoje.month, 1)
        fim = date(hoje.year, hoje.month, mr(hoje.year, hoje.month)[1])
        label = "MES ATUAL"
    elif periodo_key == "mes_ant":
        if hoje.month == 1:
            ini = date(hoje.year-1, 12, 1)
            fim = date(hoje.year-1, 12, 31)
        else:
            ini = date(hoje.year, hoje.month-1, 1)
            fim = date(hoje.year, hoje.month-1, mr(hoje.year, hoje.month-1)[1])
        label = "MES ANTERIOR"
    elif periodo_key == "semana":
        ini = hoje - timedelta(days=6)
        fim = hoje
        label = "ULTIMOS 7 DIAS"
    else:
        ini = fim = hoje
        label = "HOJE"
    try:
        dados = cb.relatorio_pendentes(ini, fim)
        if not dados:
            await msg.reply_text("Nenhum pendente financeiro no periodo.")
            return
        total_geral = sum(d["total"] for d in dados.values())
        total_qtd = sum(d["qtd"] for d in dados.values())
        texto = header("💰 PENDENTES FINANCEIRO — " + label)
        texto += "Periodo: {} a {}\n".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
        texto += "Total em aberto: " + b(cb.moeda(total_geral)) + "\n"
        texto += "Servicos pendentes: " + b(str(total_qtd)) + "\n\n"
        for loja, d in sorted(dados.items(), key=lambda x: x[1]["total"], reverse=True):
            texto += "🏪 " + b(loja) + "\n"
            texto += "   {} servicos — ".format(d["qtd"]) + b(cb.moeda(d["total"])) + "\n"
            for item in d["itens"][:3]:
                texto += "   • {} | {} | {}\n".format(
                    item["data"], item["cliente"][:20], item["status"][:15])
            if len(d["itens"]) > 3:
                texto += "   ...e mais {} servicos\n".format(len(d["itens"]) - 3)
            texto += "\n"
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))

async def _step_lojas_cob(msg, ctx):
    empresa_key = ctx.user_data.get("cob_empresa", "unicar")
    ini = ctx.user_data.get("cob_ini")
    fim = ctx.user_data.get("cob_fim")
    try:
        lojas = cb.listar_lojas(ini, fim)
        dados = cb.calcular_cobranca(ini, fim)
        if not lojas:
            await msg.reply_text("Nenhuma loja encontrada no periodo.")
            return
        botoes = []
        for loja in lojas:
            d = dados.get(loja, {})
            total = d.get("total", 0)
            qtd = len(d.get("itens", []))
            if total > 0:
                label = "{} — {} ({} itens)".format(loja[:22], cb.moeda(total), qtd)
                botoes.append([InlineKeyboardButton(label, callback_data="cob_loja:{}".format(loja[:40]))])
        total_geral = sum(d.get("total", 0) for d in dados.values())
        botoes.append([InlineKeyboardButton(
            "📄 TODAS AS LOJAS — {}".format(cb.moeda(total_geral)),
            callback_data="cob_loja:TODAS"
        )])
        texto = "Passo 3 — Selecione a loja:\n\n"
        texto += b("Periodo: {} a {}".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))) + "\n"
        texto += "Total geral: " + b(cb.moeda(total_geral)) + "\n"
        texto += "Empresa: " + b(cb.EMPRESAS[empresa_key]["fantasia"])
        await msg.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes))
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro ao carregar lojas: {}".format(e))

async def _gerar_pdf_cobranca(msg, ctx, loja_nome):
    empresa_key = ctx.user_data.get("cob_empresa", "unicar")
    ini = ctx.user_data.get("cob_ini")
    fim = ctx.user_data.get("cob_fim")
    await msg.reply_text("⏳ Gerando cobranca, aguarde...")
    try:
        if loja_nome == "TODAS":
            dados = cb.calcular_cobranca(ini, fim)
            total_geral = sum(d["total"] for d in dados.values() if d["total"] > 0)
            texto = header("🧾 COBRANCA GERAL")
            texto += "Periodo: {} a {}\n".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
            texto += "Empresa: " + b(cb.EMPRESAS[empresa_key]["fantasia"]) + "\n\n"
            for loja, d in sorted(dados.items()):
                if d["total"] == 0:
                    continue
                texto += "🏪 " + b(loja) + " — " + b(cb.moeda(d["total"])) + "\n"
            texto += "\n" + b("TOTAL GERAL: {}".format(cb.moeda(total_geral)))
            await msg.reply_text(texto, parse_mode="HTML")
            for loja, d in sorted(dados.items()):
                if d["total"] == 0:
                    continue
                pdf_bytes = cb.gerar_pdf(loja, d, empresa_key, ini, fim)
                nome = "cobranca_{}_{}.pdf".format(loja.replace(" ","_")[:20], ini.strftime("%Y%m"))
                await msg.reply_document(document=pdf_bytes, filename=nome,
                    caption="🧾 {} — {}".format(loja, cb.moeda(d["total"])))
        else:
            dados = cb.calcular_cobranca(ini, fim, loja_nome)
            d = dados.get(loja_nome)
            if not d or d["total"] == 0:
                await msg.reply_text("Nenhuma cobranca para {} no periodo.".format(loja_nome))
                return
            texto = header("🧾 COBRANCA: {}".format(loja_nome))
            texto += "Periodo: {} a {}\n\n".format(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
            if d["qtd_servico"] > 0:
                texto += "ATPV/ASS VEND/CV: {} x {} = {}\n".format(
                    d["qtd_servico"], cb.moeda(cb.PRECO_SERVICO), cb.moeda(d["qtd_servico"]*cb.PRECO_SERVICO))
            if d["qtd_proc_comp"] > 0:
                texto += "Proc Comprador: {} x {} = {}\n".format(
                    d["qtd_proc_comp"], cb.moeda(cb.PRECO_PROC_COMP), cb.moeda(d["qtd_proc_comp"]*cb.PRECO_PROC_COMP))
            if d["qtd_proc_vend"] > 0:
                texto += "Proc Vendedor: {} x {} = {}\n".format(
                    d["qtd_proc_vend"], cb.moeda(cb.PRECO_PROC_VEND), cb.moeda(d["qtd_proc_vend"]*cb.PRECO_PROC_VEND))
            if d["qtd_combo"] > 0:
                texto += "Combo (C+V): {} x {} = {}\n".format(
                    d["qtd_combo"], cb.moeda(cb.PRECO_COMBO), cb.moeda(d["qtd_combo"]*cb.PRECO_COMBO))
            texto += "\n" + b("TOTAL: {}".format(cb.moeda(d["total"])))
            await msg.reply_text(texto, parse_mode="HTML")
            pdf_bytes = cb.gerar_pdf(loja_nome, d, empresa_key, ini, fim)
            nome = "cobranca_{}_{}.pdf".format(loja_nome.replace(" ","_")[:20], ini.strftime("%Y%m"))
            await msg.reply_document(document=pdf_bytes, filename=nome,
                caption="📄 Fatura — {}".format(cb.moeda(d["total"])))
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro ao gerar PDF: {}".format(e))



# ── NOVOS COMANDOS ────────────────────────────────────────────────────────────

async def cmd_comparativo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    try:
        c = ex.comparativo()
        hoje  = c["hoje"]
        ontem = c["ontem"]
        mes   = c["mes_atual"]
        mant  = c["mes_ant"]

        def seta(a, b):
            if a > b: return "📈"
            if a < b: return "📉"
            return "➡️"

        def diff(a, b):
            if b == 0: return ""
            p = (a - b) / b * 100
            return " ({:+.1f}%)".format(p)

        texto = header("📈 COMPARATIVO")
        texto += b("HOJE vs ONTEM") + "\n"
        texto += "Registros: {} {} {} {}\n".format(
            hoje["qtd"], seta(hoje["qtd"], ontem["qtd"]), ontem["qtd"], diff(hoje["qtd"], ontem["qtd"]))
        texto += "Faturamento: {} {} {}{}\n".format(
            moeda(hoje["fat"]), seta(hoje["fat"], ontem["fat"]), moeda(ontem["fat"]), diff(hoje["fat"], ontem["fat"]))
        texto += "Liquido: {} {} {}{}\n".format(
            moeda(hoje["liq"]), seta(hoje["liq"], ontem["liq"]), moeda(ontem["liq"]), diff(hoje["liq"], ontem["liq"]))
        texto += "Procuracoes: {} {} {}\n\n".format(
            hoje["proc"], seta(hoje["proc"], ontem["proc"]), ontem["proc"])

        texto += b("{} vs {}".format(c["mes_atual_label"], c["mes_ant_label"])) + "\n"
        texto += "Registros: {} {} {}{}\n".format(
            mes["qtd"], seta(mes["qtd"], mant["qtd"]), mant["qtd"], diff(mes["qtd"], mant["qtd"]))
        texto += "Faturamento: {} {} {}{}\n".format(
            moeda(mes["fat"]), seta(mes["fat"], mant["fat"]), moeda(mant["fat"]), diff(mes["fat"], mant["fat"]))
        texto += "Liquido: {} {} {}{}\n".format(
            moeda(mes["liq"]), seta(mes["liq"], mant["liq"]), moeda(mant["liq"]), diff(mes["liq"], mant["liq"]))

        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_evolucao(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    try:
        dados = ex.evolucao_semana()
        max_qtd = max(d["qtd"] for d in dados) or 1
        texto = header("📅 EVOLUCAO — ULTIMOS 7 DIAS")
        for d in dados:
            barra = "█" * int(d["qtd"] / max_qtd * 10)
            barra = barra or "░"
            texto += "{} {} {} {} — {} — {}\n".format(
                d["dia"], d["data"], barra, d["qtd"],
                moeda(d["fat"]), "{} proc".format(d["proc"])
            )
        total_qtd = sum(d["qtd"] for d in dados)
        total_fat = sum(d["fat"] for d in dados)
        texto += "\nTotal: " + b("{} registros — {}".format(total_qtd, moeda(total_fat)))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_clientes_dia(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    try:
        clientes = ex.clientes_do_dia()
        if not clientes:
            await msg.reply_text("Nenhum cliente registrado hoje.")
            return
        texto = header("👥 CLIENTES DO DIA — {}".format(date.today().strftime("%d/%m/%Y")))
        texto += "Total: " + b(str(len(clientes))) + "\n\n"
        loja_atual = None
        for r in clientes:
            loja = sh._col(r, "loja") or "Sem Loja"
            if loja != loja_atual:
                texto += "\n🏪 " + b(loja) + "\n"
                loja_atual = loja
            proc  = sh._col(r, "procuracao") or "—"
            video = sh._col(r, "video") or "—"
            proc_ico  = "✅" if "ok" in proc.lower() else "⚠️"
            video_ico = "✅" if "ok" in video.lower() else "🎬"
            texto += "  👤 {} | 🚗 {}\n".format(sh._col(r, "cliente")[:22], sh._col(r, "placa"))
            texto += "  📋 {} | 💵 {} | 👤 {}\n".format(
                sh._col(r, "servico")[:18], sh._col(r, "valor"), sh._col(r, "feito_por")[:12])
            texto += "  {} Proc: {} | {} Video: {}\n".format(
                proc_ico, proc[:15], video_ico, video[:15])
            obs = sh._col(r, "observacao") or sh._col(r, "mensagem")
            if obs:
                texto += "  💬 {}\n".format(obs[:40])
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_sem_movimento(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    try:
        lojas = ex.lojas_sem_movimento(dias=7)
        if not lojas:
            await msg.reply_text("✅ Todas as lojas com movimento hoje!")
            return
        texto = header("🔇 LOJAS SEM MOVIMENTO HOJE")
        texto += "Lojas que operaram nos ultimos 7 dias mas nao hoje:\n\n"
        for loja in lojas:
            texto += "  • {}\n".format(loja)
        texto += "\nTotal: " + b(str(len(lojas)))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_painel_loja(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    if hasattr(ctx, 'args') and ctx.args:
        termo = " ".join(ctx.args)
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        lojas_encontradas = ex.buscar_loja(termo, ini, hoje)
        if len(lojas_encontradas) == 1:
            await _mostrar_painel_loja(msg, lojas_encontradas[0])
        elif len(lojas_encontradas) > 1:
            botoes = []
            for i in range(0, len(lojas_encontradas), 2):
                linha = [InlineKeyboardButton(lojas_encontradas[i][:25], callback_data="loja_painel:{}".format(lojas_encontradas[i][:35]))]
                if i+1 < len(lojas_encontradas):
                    linha.append(InlineKeyboardButton(lojas_encontradas[i+1][:25], callback_data="loja_painel:{}".format(lojas_encontradas[i+1][:35])))
                botoes.append(linha)
            await msg.reply_text(
                "Encontrei {} lojas com {}. Selecione:".format(len(lojas_encontradas), termo),
                reply_markup=InlineKeyboardMarkup(botoes)
            )
        else:
            await msg.reply_text("Nenhuma loja encontrada com: {}".format(termo))
        return
    # Sem argumento: mostra todas as lojas do mes
    hoje = date.today()
    ini = date(hoje.year, hoje.month, 1)
    try:
        lojas = ex.listar_lojas_periodo(ini, hoje)
        if not lojas:
            await msg.reply_text("Nenhuma loja encontrada no mes.")
            return
        botoes = []
        for i in range(0, len(lojas), 2):
            linha = [InlineKeyboardButton(lojas[i][:25], callback_data="loja_painel:{}".format(lojas[i][:35]))]
            if i+1 < len(lojas):
                linha.append(InlineKeyboardButton(lojas[i+1][:25], callback_data="loja_painel:{}".format(lojas[i+1][:35])))
            botoes.append(linha)
        await msg.reply_text(
            "🏪 " + b("PAINEL POR LOJA") + "\nSelecione ou use /loja nome:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def _mostrar_painel_loja(msg, loja_nome):
    hoje = date.today()
    ini = date(hoje.year, hoje.month, 1)
    try:
        d = ex.painel_completo_loja(loja_nome, ini, hoje)
        if not d:
            await msg.reply_text("Loja nao encontrada: {}".format(loja_nome))
            return

        texto = header("🏪 PAINEL COMPLETO: {}".format(d["nome_real"]))
        texto += "Periodo: {} a {}\n\n".format(ini.strftime("%d/%m"), hoje.strftime("%d/%m/%Y"))

        # Financeiro
        texto += b("💰 FINANCEIRO") + "\n"
        texto += "Registros: {}\n".format(d["total_registros"])
        texto += "Faturamento bruto: " + b(moeda(d["faturamento"])) + "\n"
        texto += "Custo liquido: " + b(moeda(d["liquido"])) + "\n"
        texto += "Ticket medio: " + b(moeda(d["ticket_medio"])) + "\n\n"

        # Cobranca
        cob = d["cobranca"]
        total_cob = cob.get("total", 0)
        texto += b("🧾 COBRANCA DO PERIODO") + "\n"
        if cob.get("qtd_servico", 0) > 0:
            texto += "  ATPV/ASS VEND/CV: {} x R$30 = {}\n".format(cob["qtd_servico"], moeda(cob["qtd_servico"]*30))
        if cob.get("qtd_proc_comp", 0) > 0:
            texto += "  Proc Comp: {} x R$75 = {}\n".format(cob["qtd_proc_comp"], moeda(cob["qtd_proc_comp"]*75))
        if cob.get("qtd_proc_vend", 0) > 0:
            texto += "  Proc Vend: {} x R$125 = {}\n".format(cob["qtd_proc_vend"], moeda(cob["qtd_proc_vend"]*125))
        if cob.get("qtd_combo", 0) > 0:
            texto += "  Combo: {} x R$125 = {}\n".format(cob["qtd_combo"], moeda(cob["qtd_combo"]*125))
        texto += "  " + b("TOTAL A COBRAR: {}".format(moeda(total_cob))) + "\n\n"

        # Procuracoes e Videos
        texto += b("📝 PROCURACOES") + "\n"
        texto += "  ✅ OK: {} | ⚠️ Pendentes: {} | ❓ Sem status: {}\n\n".format(
            d["proc_ok"], d["proc_pend"], d["proc_sem"])
        texto += b("🎬 VIDEOS") + "\n"
        texto += "  ✅ OK: {} | ⚠️ Pendentes: {}\n\n".format(d["video_ok"], d["video_pend"])

        # Pagamentos
        if d["pagamentos"]:
            texto += b("💳 PAGAMENTOS") + "\n"
            for pg, qtd in list(d["pagamentos"].items())[:4]:
                texto += "  {} — {}x\n".format(pg[:20], qtd)
            texto += "\n"

        # Operadores
        if d["operadores"]:
            texto += b("👤 OPERADORES") + "\n"
            for op, qtd in list(d["operadores"].items())[:5]:
                barra = "█" * min(int(qtd / max(d["operadores"].values()) * 8), 8)
                texto += "  {} {} — {}\n".format(op[:18], barra, qtd)
            texto += "\n"

        # Servicos
        if d["servicos"]:
            texto += b("🗂 SERVICOS") + "\n"
            for svc, qtd in list(d["servicos"].items())[:5]:
                texto += "  {} — {}x\n".format(svc[:22], qtd)
            texto += "\n"

        # Grupos
        if d["grupos"] and len(d["grupos"]) > 1:
            texto += b("🏢 GRUPOS") + "\n"
            for g, qtd in d["grupos"].items():
                texto += "  {} — {}x\n".format(g[:20], qtd)
            texto += "\n"

        # Ultimos clientes
        if d["clientes_recentes"]:
            texto += b("👥 ULTIMOS ATENDIMENTOS") + "\n"
            for c in d["clientes_recentes"]:
                proc_ico  = "✅" if "ok" in (c["proc"] or "").lower() else "⚠️"
                video_ico = "✅" if "ok" in (c["video"] or "").lower() else "🎬"
                texto += "  📅 {} | {} | {}\n".format(c["data"], c["cliente"][:20], c["placa"])
                texto += "  📋 {} | 💵 {} | 👤 {}\n".format(c["servico"][:18], c["valor"], c["operador"][:12])
                texto += "  {} {} {}\n".format(proc_ico, video_ico, c["obs"][:30] if c["obs"] else "")

        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_painel_op(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    if hasattr(ctx, 'args') and ctx.args:
        op_nome = " ".join(ctx.args)
        await _mostrar_painel_op(msg, op_nome)
        return
    hoje = date.today()
    ini = date(hoje.year, hoje.month, 1)
    try:
        ops = ex.listar_operadores(ini, hoje)
        if not ops:
            await msg.reply_text("Nenhum operador encontrado.")
            return
        botoes = []
        for i in range(0, len(ops), 2):
            linha = [InlineKeyboardButton(ops[i][:25], callback_data="op_painel:{}".format(ops[i][:35]))]
            if i+1 < len(ops):
                linha.append(InlineKeyboardButton(ops[i+1][:25], callback_data="op_painel:{}".format(ops[i+1][:35])))
            botoes.append(linha)
        await msg.reply_text(
            "👤 " + b("PAINEL POR OPERADOR") + "\nSelecione:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def _mostrar_painel_op(msg, op_nome):
    hoje = date.today()
    ini = date(hoje.year, hoje.month, 1)
    try:
        d = ex.painel_operador(op_nome, ini, hoje)
        texto = header("👤 OPERADOR: {}".format(op_nome))
        texto += "Periodo: {} a {}\n\n".format(ini.strftime("%d/%m"), hoje.strftime("%d/%m/%Y"))
        texto += "📋 Total servicos: " + b(str(d["total"])) + "\n"
        texto += "💵 Faturamento gerado: " + b(moeda(d["faturamento"])) + "\n"
        texto += "✅ Proc OK: {} | ⚠️ Pendentes: {}\n\n".format(d["proc_ok"], d["proc_pend"])
        if d["por_loja"]:
            texto += b("Por loja:") + "\n"
            for loja, qtd in list(d["por_loja"].items())[:8]:
                barra = "█" * min(qtd, 10)
                texto += "  🏪 {} — {} {}\n".format(loja[:20], barra, qtd)
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


# ── ALERTAS AUTOMATICOS ───────────────────────────────────────────────────────

ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "8687934455"))

# Guarda estado anterior para detectar mudancas
_estado_anterior = {
    "pendentes_proc": set(),
    "pendentes_video": set(),
    "lojas_sem_movimento": set(),
}

async def alerta_30min(ctx):
    """Roda a cada 30 minutos — envia alertas de mudancas e resumo"""
    try:
        hoje = date.today()
        sh.invalidar_cache()

        # ── Dados do dia ──────────────────────────────────────────────────────
        r = sh.resumo_hoje()
        proc_hoje = sh.procuracoes_hoje()
        pend_proc = sh.procuracoes_pendentes(hoje, hoje)
        pend_video = sh.videos_pendentes(hoje, hoje)

        # ── Lojas sem movimento hoje ──────────────────────────────────────────
        rows = sh._fetch()
        lojas_ativas_hoje = set(
            sh._col(r2, "loja") for r2 in rows
            if sh._parse_date(sh._col(r2, "data")) == hoje and sh._col(r2, "loja")
        )
        # Pega lojas que tiveram movimento nos ultimos 7 dias
        from datetime import timedelta
        ini7 = hoje - timedelta(days=7)
        lojas_recentes = set(
            sh._col(r2, "loja") for r2 in rows
            if (d := sh._parse_date(sh._col(r2, "data"))) and ini7 <= d < hoje and sh._col(r2, "loja")
        )
        lojas_sem_mov = lojas_recentes - lojas_ativas_hoje

        # ── Detecta novos pendentes (mudancas desde ultimo ciclo) ─────────────
        chaves_pend_proc = set(
            "{}-{}-{}".format(sh._col(p, "cliente"), sh._col(p, "placa"), sh._col(p, "data"))
            for p in pend_proc
        )
        chaves_pend_video = set(
            "{}-{}-{}".format(sh._col(p, "cliente"), sh._col(p, "placa"), sh._col(p, "data"))
            for p in pend_video
        )
        novos_pend_proc  = chaves_pend_proc  - _estado_anterior["pendentes_proc"]
        novos_pend_video = chaves_pend_video - _estado_anterior["pendentes_video"]
        _estado_anterior["pendentes_proc"]  = chaves_pend_proc
        _estado_anterior["pendentes_video"] = chaves_pend_video
        _estado_anterior["lojas_sem_movimento"] = lojas_sem_mov

        # ── Monta mensagem de alerta ──────────────────────────────────────────
        agora = __import__("datetime").datetime.now().strftime("%H:%M")
        comp = ex.comparativo()
        texto = "🔔 " + b("MONITORAMENTO — {}".format(agora)) + "\n"
        texto += "─" * 26 + "\n\n"

        # Resumo rapido com comparativo
        texto += "📊 " + b("Resumo de hoje ({})".format(r["data"])) + "\n"
        texto += "• Registros: {} {} ontem: {}\n".format(
            r["total"], "📈" if r["total"] >= comp["ontem"]["qtd"] else "📉", comp["ontem"]["qtd"])
        texto += "• Faturamento: {} {} ontem: {}\n".format(
            moeda(r["faturamento"]), "📈" if r["faturamento"] >= comp["ontem"]["fat"] else "📉",
            moeda(comp["ontem"]["fat"]))
        texto += "• Liquido: {}\n".format(moeda(r["liquido"]))
        texto += "• Proc. feitas: {}\n".format(len(proc_hoje))
        texto += "\n"

        # Pendentes de procuracao
        if pend_proc:
            texto += "⚠️ " + b("Proc. pendentes: {}".format(len(pend_proc))) + "\n"
            for p in pend_proc[:5]:
                chave = "{}-{}-{}".format(sh._col(p,"cliente"), sh._col(p,"placa"), sh._col(p,"data"))
                novo = " 🆕" if chave in novos_pend_proc else ""
                texto += "  • {} | {} | {} | 👤 {}{}\n".format(
                    sh._col(p,"cliente")[:18], sh._col(p,"placa"),
                    sh._col(p,"loja")[:12], sh._col(p,"feito_por")[:10], novo)
            if len(pend_proc) > 5:
                texto += "  ...e mais {}\n".format(len(pend_proc) - 5)
            texto += "\n"
        else:
            texto += "✅ Sem procuracoes pendentes\n\n"

        # Pendentes de video
        if pend_video:
            texto += "🎬 " + b("Videos pendentes: {}".format(len(pend_video))) + "\n"
            for p in pend_video[:3]:
                novo = " 🆕" if "{}-{}-{}".format(sh._col(p,"cliente"), sh._col(p,"placa"), sh._col(p,"data")) in novos_pend_video else ""
                texto += "  • {} — {}{}\n".format(sh._col(p,"cliente")[:20], sh._col(p,"loja")[:15], novo)
            if len(pend_video) > 3:
                texto += "  ...e mais {}\n".format(len(pend_video) - 3)
            texto += "\n"
        else:
            texto += "✅ Sem videos pendentes\n\n"

        # Lojas sem movimento
        if lojas_sem_mov:
            texto += "🏪 " + b("Lojas sem mov. hoje:") + "\n"
            for loja in sorted(lojas_sem_mov)[:5]:
                texto += "  • {}\n".format(loja)
            texto += "\n"

        # Alerta especial se tiver novidades
        if novos_pend_proc or novos_pend_video:
            texto += "🚨 " + b("NOVOS PENDENTES DETECTADOS!") + "\n"
            if novos_pend_proc:
                texto += "  {} nova(s) proc. pendente(s)\n".format(len(novos_pend_proc))
            if novos_pend_video:
                texto += "  {} novo(s) video(s) pendente(s)\n".format(len(novos_pend_video))

        await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=texto, parse_mode="HTML")

    except Exception as e:
        log.error("Erro no alerta automatico: {}".format(e))
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="❌ Erro no monitoramento: {}".format(e)
            )
        except Exception:
            pass


async def resumo_diario_manha(ctx):
    """Resumo completo as 8h"""
    try:
        sh.invalidar_cache()
        hoje = date.today()
        from calendar import monthrange
        ini_mes = date(hoje.year, hoje.month, 1)
        fim_mes = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])
        r_mes = sh.resumo_periodo(ini_mes, hoje)
        ranking = sh.ranking_lojas(ini_mes, hoje, top=5)
        ops = sh.ranking_operadores(ini_mes, hoje, top=3)

        texto = "☀️ " + b("BOM DIA! RESUMO DO MES ATÉ HOJE") + "\n"
        texto += "─" * 26 + "\n\n"
        texto += "📅 {} a {}\n\n".format(ini_mes.strftime("%d/%m"), hoje.strftime("%d/%m/%Y"))
        texto += "📋 Total registros: " + b(str(r_mes["total"])) + "\n"
        texto += "💵 Faturamento: " + b(moeda(r_mes["faturamento"])) + "\n"
        texto += "💰 Liquido: " + b(moeda(r_mes["liquido"])) + "\n"
        texto += "📝 Procuracoes: " + b(str(r_mes["procuracoes"])) + "\n\n"

        if ranking:
            texto += "🏆 " + b("Top 5 Lojas do Mes:") + "\n"
            medalhas = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, (loja, qtd, fat) in enumerate(ranking):
                texto += "{} {} — {} reg. — {}\n".format(medalhas[i], loja[:20], qtd, moeda(fat))
            texto += "\n"

        if ops:
            texto += "👤 " + b("Top 3 Operadores:") + "\n"
            for op, qtd in ops:
                texto += "  • {} — {} servicos\n".format(op[:20], qtd)

        await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=texto, parse_mode="HTML")
    except Exception as e:
        log.error("Erro resumo manha: {}".format(e))


async def resumo_diario_noite(ctx):
    """Resumo fechamento as 19h"""
    try:
        sh.invalidar_cache()
        hoje = date.today()
        r = sh.resumo_hoje()
        proc_hoje = sh.procuracoes_hoje()
        pend_proc = sh.procuracoes_pendentes(hoje, hoje)
        pend_video = sh.videos_pendentes(hoje, hoje)

        texto = "🌆 " + b("FECHAMENTO DO DIA — {}".format(r["data"])) + "\n"
        texto += "─" * 26 + "\n\n"
        texto += "📋 Registros hoje: " + b(str(r["total"])) + "\n"
        texto += "💵 Faturamento: " + b(moeda(r["faturamento"])) + "\n"
        texto += "💰 Liquido: " + b(moeda(r["liquido"])) + "\n"
        texto += "📝 Procuracoes: " + b(str(len(proc_hoje))) + " feitas\n\n"

        if pend_proc:
            texto += "⚠️ " + b("{} proc. AINDA pendentes:".format(len(pend_proc))) + "\n"
            for p in pend_proc:
                texto += "  • {} — {}\n".format(sh._col(p,"cliente")[:22], sh._col(p,"loja")[:15])
            texto += "\n"
        else:
            texto += "✅ Todas as procuracoes OK!\n\n"

        if pend_video:
            texto += "🎬 " + b("{} videos pendentes".format(len(pend_video))) + "\n"
        else:
            texto += "✅ Todos os videos OK!\n"

        await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=texto, parse_mode="HTML")
    except Exception as e:
        log.error("Erro resumo noite: {}".format(e))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    hoje = date.today()
    try:
        r = sh.resumo_hoje()
        pend_proc = sh.procuracoes_pendentes(hoje, hoje)
        pend_video = sh.videos_pendentes(hoje, hoje)
        texto = "📡 " + b("STATUS DO SISTEMA") + "\n"
        texto += "─" * 24 + "\n\n"
        texto += "✅ Bot online\n"
        texto += "🔔 Alertas ativos (30 min)\n"
        texto += "📊 Registros hoje: {}\n".format(r["total"])
        texto += "⚠️ Proc. pendentes: {}\n".format(len(pend_proc))
        texto += "🎬 Videos pendentes: {}\n".format(len(pend_video))
        texto += "💵 Faturamento hoje: {}\n".format(moeda(r["faturamento"]))
        await update.message.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text("Erro: {}".format(e))


# ── GESTAO DE PENDENCIAS (ESCRITA) ────────────────────────────────────────────

async def cmd_resolver_pendentes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    hoje = date.today()
    try:
        pend = sh.procuracoes_pendentes(hoje, hoje)
        if not pend:
            await msg.reply_text("✅ Nenhuma procuracao pendente hoje!")
            return
        texto = header("⚠️ RESOLVER PENDENTES — {}".format(hoje.strftime("%d/%m/%Y")))
        texto += "Selecione o que deseja fazer:\n\n"
        botoes = []
        for i, r in enumerate(pend[:10]):
            cliente = sh._col(r, "cliente")[:20]
            loja    = sh._col(r, "loja")[:12]
            row_num = r.get("__row__", 0)
            botoes.append([
                InlineKeyboardButton(
                    "✅ {} — {}".format(cliente, loja),
                    callback_data="ok_proc:{}".format(row_num)
                )
            ])
        botoes.append([InlineKeyboardButton("✅ MARCAR TODAS OK", callback_data="ok_proc:TODAS")])
        await msg.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes))
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_resolver_videos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    hoje = date.today()
    try:
        pend = sh.videos_pendentes(hoje, hoje)
        if not pend:
            await msg.reply_text("✅ Nenhum video pendente hoje!")
            return
        botoes = []
        for r in pend[:10]:
            cliente = sh._col(r, "cliente")[:20]
            row_num = r.get("__row__", 0)
            botoes.append([
                InlineKeyboardButton(
                    "✅ {}".format(cliente),
                    callback_data="ok_video:{}".format(row_num)
                )
            ])
        botoes.append([InlineKeyboardButton("✅ MARCAR TODOS OK", callback_data="ok_video:TODOS")])
        await msg.reply_text(
            "🎬 " + b("VIDEOS PENDENTES") + "\nClique para marcar como OK:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_historico_cliente(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    if not ctx.args:
        await msg.reply_text("Use: /historico nome ou /historico placa")
        return
    termo = " ".join(ctx.args)
    try:
        registros = sh.historico_cliente(termo)
        if not registros:
            await msg.reply_text("Nenhum historico encontrado para: {}".format(termo))
            return
        texto = header("📋 HISTORICO: {}".format(termo.upper()))
        texto += b("{} atendimento(s) encontrado(s)".format(len(registros))) + "\n\n"
        for r in registros[:20]:
            proc  = sh._col(r, "procuracao") or "—"
            video = sh._col(r, "video") or "—"
            proc_ico  = "✅" if "ok" in proc.lower() else "⚠️"
            video_ico = "✅" if "ok" in video.lower() else "🎬"
            texto += "📅 " + b(sh._col(r, "data")) + " | 🏪 {}\n".format(sh._col(r, "loja"))
            texto += "👤 {} | 🚗 {}\n".format(sh._col(r, "cliente")[:22], sh._col(r, "placa"))
            texto += "📋 {} | 💵 {}\n".format(sh._col(r, "servico")[:20], sh._col(r, "valor"))
            texto += "{} Proc: {} | {} Video: {}\n".format(proc_ico, proc[:15], video_ico, video[:15])
            texto += "👤 Operador: {}\n".format(sh._col(r, "feito_por"))
            obs = sh._col(r, "observacao") or sh._col(r, "mensagem")
            if obs:
                texto += "💬 {}\n".format(obs[:40])
            texto += "\n"
        if len(registros) > 20:
            texto += "...e mais {} registros.".format(len(registros) - 20)
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_comparativo_grupos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        grupos = sh.resumo_por_grupo(ini, hoje)
        if not grupos:
            await msg.reply_text("Sem dados de grupos.")
            return
        total_fat = sum(g["faturamento"] for g in grupos.values())
        total_qtd = sum(g["qtd"] for g in grupos.values())
        texto = header("🏢 UNICAR vs UNIAO — {}".format(ini.strftime("%m/%Y")))
        texto += "Total geral: " + b(moeda(total_fat)) + "\n\n"
        for grupo, d in grupos.items():
            barra = "█" * min(int(d["faturamento"] / max(total_fat, 1) * 10), 10)
            texto += b(grupo) + "\n"
            texto += "  {} Registros: {}\n".format(barra, d["qtd"])
            texto += "  💵 Faturamento: {} ({}%)\n".format(
                moeda(d["faturamento"]),
                int(d["faturamento"]/total_fat*100) if total_fat else 0)
            texto += "  💰 Liquido: {}\n\n".format(moeda(d["liquido"]))
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_meta_lojas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    META_DIARIA = int(os.environ.get("META_DIARIA", "5"))
    try:
        hoje = date.today()
        rows = sh._fetch()
        lojas_hoje = defaultdict(int)
        for r in rows:
            if sh._parse_date(sh._col(r, "data")) == hoje:
                loja = sh._col(r, "loja") or "Sem Loja"
                lojas_hoje[loja] += 1
        texto = header("🎯 METAS DO DIA — {}".format(hoje.strftime("%d/%m/%Y")))
        texto += "Meta diaria por loja: " + b(str(META_DIARIA)) + " servicos\n\n"
        bateu = []
        nao_bateu = []
        for loja, qtd in sorted(lojas_hoje.items(), key=lambda x: x[1], reverse=True):
            pct_meta = int(qtd / META_DIARIA * 100)
            barra = "█" * min(int(qtd / META_DIARIA * 10), 10)
            if qtd >= META_DIARIA:
                bateu.append((loja, qtd, barra, pct_meta))
            else:
                nao_bateu.append((loja, qtd, barra, pct_meta))
        if bateu:
            texto += "✅ " + b("BATERAM A META:") + "\n"
            for loja, qtd, barra, pct in bateu:
                texto += "  🏆 {} {} {}/{}  ({}%)\n".format(loja[:18], barra, qtd, META_DIARIA, pct)
            texto += "\n"
        if nao_bateu:
            texto += "⚠️ " + b("ABAIXO DA META:") + "\n"
            for loja, qtd, barra, pct in nao_bateu:
                falta = META_DIARIA - qtd
                texto += "  📍 {} {} {}/{} (faltam {})\n".format(loja[:18], barra, qtd, META_DIARIA, falta)
        await msg.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro: {}".format(e))


async def cmd_relatorio_pdf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = get_msg(update)
    await msg.reply_text(
        "📄 " + b("RELATORIO MENSAL PDF") + "\n\nSelecione a empresa:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏢 Unicar",    callback_data="rel_pdf:unicar"),
             InlineKeyboardButton("🏢 Uniaocert", callback_data="rel_pdf:uniao")],
            [InlineKeyboardButton("📊 Ambas",     callback_data="rel_pdf:ambas")],
        ])
    )


async def _gerar_relatorio_pdf(msg, empresa_key):
    await msg.reply_text("⏳ Gerando relatorio mensal, aguarde...")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        import io
        from calendar import monthrange

        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        fim = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])

        emp_map = {
            "unicar": [cb.EMPRESAS["unicar"]],
            "uniao":  [cb.EMPRESAS["uniao"]],
            "ambas":  [cb.EMPRESAS["unicar"], cb.EMPRESAS["uniao"]],
        }
        empresas = emp_map.get(empresa_key, [cb.EMPRESAS["unicar"]])

        r_mes    = sh.resumo_periodo(ini, fim)
        ranking  = sh.ranking_lojas(ini, fim, top=10)
        ops      = sh.ranking_operadores(ini, fim, top=10)
        svcs     = sh.servicos_por_tipo(ini, fim)
        grupos   = sh.resumo_por_grupo(ini, fim)
        pgs      = sh.formas_pagamento(ini, fim)
        dados_cob = cb.calcular_cobranca(ini, fim)
        total_cob = sum(d["total"] for d in dados_cob.values())

        COR_P  = colors.HexColor("#1a3c6e")
        COR_S  = colors.HexColor("#2e6db4")
        COR_BG = colors.HexColor("#f0f4fa")
        COR_OK = colors.HexColor("#1a7a3c")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        def sp(name, **kw): return ParagraphStyle(name, **kw)
        s_tit  = sp("t", fontSize=18, fontName="Helvetica-Bold", textColor=COR_P, alignment=TA_CENTER)
        s_sub  = sp("s", fontSize=10, fontName="Helvetica",      textColor=colors.grey, alignment=TA_CENTER)
        s_h2   = sp("h", fontSize=12, fontName="Helvetica-Bold", textColor=COR_P, spaceBefore=10)
        s_tot  = sp("tt",fontSize=13, fontName="Helvetica-Bold", textColor=COR_OK, alignment=TA_RIGHT)
        s_rod  = sp("r", fontSize=7,  fontName="Helvetica",      textColor=colors.grey, alignment=TA_CENTER)

        story = []

        # Cabecalho
        for emp in empresas:
            story.append(Paragraph(emp["nome"], s_tit))
            story.append(Paragraph(emp["fantasia"] + " | CNPJ: " + emp["cnpj"], s_sub))
        story.append(Paragraph("RELATORIO MENSAL — {}/{}".format(
            str(hoje.month).zfill(2), hoje.year), s_sub))
        story.append(HRFlowable(width="100%", thickness=2, color=COR_P, spaceAfter=10))

        def moeda_r(v): return "R$ {:,.2f}".format(v).replace(",","X").replace(".",",").replace("X",".")

        # Resumo executivo
        story.append(Paragraph("RESUMO EXECUTIVO", s_h2))
        res_data = [
            ["Indicador", "Valor"],
            ["Total de Registros", str(r_mes["total"])],
            ["Faturamento Bruto", moeda_r(r_mes["faturamento"])],
            ["Custo Liquido", moeda_r(r_mes["liquido"])],
            ["Procuracoes", str(r_mes["procuracoes"])],
            ["Total a Cobrar (Lojas)", moeda_r(total_cob)],
        ]
        rt = Table(res_data, colWidths=[10*cm, 7*cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),COR_P), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),10),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#dddddd")),
            ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(rt)
        story.append(Spacer(1, 10))

        # Ranking lojas
        story.append(Paragraph("RANKING DE LOJAS", s_h2))
        rank_data = [["#", "Loja", "Registros", "Faturamento"]]
        for i, (loja, qtd, fat) in enumerate(ranking, 1):
            rank_data.append([str(i), loja, str(qtd), moeda_r(fat)])
        rkt = Table(rank_data, colWidths=[1*cm, 9*cm, 3*cm, 4*cm])
        rkt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),COR_S), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dddddd")),
            ("ALIGN",(2,0),(-1,-1),"CENTER"),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        story.append(rkt)
        story.append(Spacer(1, 10))

        # Operadores
        story.append(Paragraph("RANKING DE OPERADORES", s_h2))
        op_data = [["#", "Operador", "Servicos"]]
        for i, (op, qtd) in enumerate(ops, 1):
            op_data.append([str(i), op, str(qtd)])
        opt = Table(op_data, colWidths=[1*cm, 12*cm, 4*cm])
        opt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),COR_S), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dddddd")),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        story.append(opt)
        story.append(Spacer(1, 10))

        # Grupos
        if grupos:
            story.append(Paragraph("RESUMO POR GRUPO", s_h2))
            grp_data = [["Grupo", "Registros", "Faturamento", "Liquido"]]
            for grp, d in grupos.items():
                grp_data.append([grp, str(d["qtd"]), moeda_r(d["faturamento"]), moeda_r(d["liquido"])])
            grpt = Table(grp_data, colWidths=[6*cm, 3*cm, 4.5*cm, 4.5*cm])
            grpt.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),COR_S), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, COR_BG]),
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dddddd")),
                ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ]))
            story.append(grpt)
            story.append(Spacer(1, 10))

        # Cobranca por loja
        story.append(Paragraph("COBRANCA POR LOJA", s_h2))
        cob_data = [["Loja", "Servicos", "Proc", "Combo", "Total"]]
        for loja, d in sorted(dados_cob.items()):
            if d["total"] == 0: continue
            cob_data.append([loja[:25], str(d["qtd_servico"]), str(d["qtd_proc_vend"]+d["qtd_proc_comp"]),
                            str(d["qtd_combo"]), moeda_r(d["total"])])
        cob_data.append(["TOTAL GERAL", "", "", "", moeda_r(total_cob)])
        cobt = Table(cob_data, colWidths=[7*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
        cobt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),COR_P), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("BACKGROUND",(0,-1),(-1,-1),COR_OK), ("TEXTCOLOR",(0,-1),(-1,-1),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.white, COR_BG]),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dddddd")),
            ("ALIGN",(1,0),(-1,-1),"CENTER"),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        story.append(cobt)
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Relatorio gerado em {} | Periodo: {}/{} | Sistema de Gestao".format(
                hoje.strftime("%d/%m/%Y"), str(hoje.month).zfill(2), hoje.year), s_rod))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        nome = "relatorio_{}_{}{}.pdf".format(empresa_key, str(hoje.month).zfill(2), hoje.year)
        await msg.reply_document(document=pdf_bytes, filename=nome,
            caption="📊 Relatorio mensal {}/{} gerado!".format(str(hoje.month).zfill(2), hoje.year))

    except Exception as e:
        log.error(e)
        await msg.reply_text("Erro ao gerar relatorio: {}".format(e))


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
    app.add_handler(CommandHandler("pendentes_fin",  cmd_pendentes_fin))
    app.add_handler(CommandHandler("comparativo",    cmd_comparativo))
    app.add_handler(CommandHandler("evolucao",       cmd_evolucao))
    app.add_handler(CommandHandler("loja",           cmd_painel_loja))
    app.add_handler(CommandHandler("operador",       cmd_painel_op))
    app.add_handler(CommandHandler("clientes_dia",   cmd_clientes_dia))
    app.add_handler(CommandHandler("sem_movimento",  cmd_sem_movimento))
    app.add_handler(CommandHandler("resolver",       cmd_resolver_pendentes))
    app.add_handler(CommandHandler("videos_ok",      cmd_resolver_videos))
    app.add_handler(CommandHandler("historico",      cmd_historico_cliente))
    app.add_handler(CommandHandler("grupos_cmp",     cmd_comparativo_grupos))
    app.add_handler(CommandHandler("metas",          cmd_meta_lojas))
    app.add_handler(CommandHandler("relatorio",      cmd_relatorio_pdf))
    app.add_handler(CommandHandler("status",         cmd_status))
    app.add_handler(CommandHandler("cobranca",      cmd_cobranca))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_livre))
    # ── Alertas automaticos ──────────────────────────────────────────────────
    jq = app.job_queue
    # A cada 30 minutos
    jq.run_repeating(alerta_30min, interval=1800, first=10)
    # Resumo matinal 8h (horario de Brasilia = UTC-3)
    import datetime as dt
    jq.run_daily(resumo_diario_manha, time=dt.time(hour=11, minute=0))   # 8h BRT = 11h UTC
    # Resumo noturno 19h BRT = 22h UTC
    jq.run_daily(resumo_diario_noite, time=dt.time(hour=22, minute=0))

    log.info("✅ Bot iniciado com alertas automaticos!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
