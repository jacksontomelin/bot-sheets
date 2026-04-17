"""
bot.py — Bot Telegram completo para consulta da planilha de serviços
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

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

# ─── Formatação ───────────────────────────────────────────────────────────────

def moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(parte, total) -> str:
    return f"{parte/total*100:.1f}%" if total else "0%"

def header(titulo: str) -> str:
    return f"{'─'*30}\n{titulo}\n{'─'*30}\n"

def _col(row, key):
    return sh._col(row, key)

# ─── Teclados rápidos ─────────────────────────────────────────────────────────

def kb_principal():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Resumo Hoje",      callback_data="cmd:resumo_hoje"),
         InlineKeyboardButton("📅 Resumo Mês",       callback_data="cmd:resumo_mes")],
        [InlineKeyboardButton("📝 Procurações Hoje", callback_data="cmd:proc_hoje"),
         InlineKeyboardButton("⚠️ Proc. Pendentes",  callback_data="cmd:proc_pendentes")],
        [InlineKeyboardButton("🏆 Ranking Lojas",    callback_data="cmd:rank_lojas"),
         InlineKeyboardButton("👤 Ranking Operadores",callback_data="cmd:rank_ops")],
        [InlineKeyboardButton("🎬 Vídeos Pendentes", callback_data="cmd:videos"),
         InlineKeyboardButton("💰 Faturamento/Loja", callback_data="cmd:fat_loja")],
        [InlineKeyboardButton("🗂️ Por Serviço",      callback_data="cmd:servicos"),
         InlineKeyboardButton("🏢 Por Grupo",        callback_data="cmd:grupos")],
        [InlineKeyboardButton("💳 Pagamentos",       callback_data="cmd:pagamentos"),
         InlineKeyboardButton("🔄 Atualizar Cache",  callback_data="cmd:cache")],
    ])

# ─── Handlers de comandos ─────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 *Bot de Gestão — Planilha de Serviços*\n\n"
        "Escolha uma opção abaixo ou use os comandos:\n\n"
        "📊 *Resumos*\n"
        "• /hoje — resumo do dia\n"
        "• /mes — resumo do mês atual\n"
        "• /semana — resumo dos últimos 7 dias\n\n"
        "📝 *Procurações*\n"
        "• /procuracoes — procurações de hoje\n"
        "• /pendentes — procurações pendentes hoje\n"
        "• /pendentes_mes — pendentes do mês\n\n"
        "🏆 *Rankings*\n"
        "• /ranking — top lojas do mês\n"
        "• /operadores — top operadores do mês\n\n"
        "🎬 *Vídeos*\n"
        "• /videos — vídeos pendentes hoje\n\n"
        "💰 *Financeiro*\n"
        "• /faturamento — faturamento por loja\n"
        "• /grupos — resumo por grupo\n"
        "• /pagamentos — formas de pagamento\n\n"
        "🔍 *Busca*\n"
        "• /buscar `[nome ou placa]`\n\n"
        "🔄 /atualizar — força atualização dos dados\n"
    )
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb_principal())


async def cmd_hoje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _resumo_hoje(update)

async def _resumo_hoje(update):
    try:
        r = sh.resumo_hoje()
        proc_hoje = sh.procuracoes_hoje()
        pend = sh.procuracoes_pendentes()

        texto = (
            f"{header(f'📊 RESUMO DO DIA — {r[\"data\"]}')}"
            f"📋 Total de registros: *{r['total']}*\n"
            f"💵 Faturamento bruto: *{moeda(r['faturamento'])}*\n"
            f"💰 Custo líquido: *{moeda(r['liquido'])}*\n\n"
            f"📝 Procurações realizadas: *{len(proc_hoje)}*\n"
            f"⚠️ Procurações pendentes: *{len(pend)}*\n"
        )
        if pend:
            texto += "\n🔴 *Pendentes:*\n"
            for p in pend[:5]:
                texto += f"  • {_col(p,'cliente')} — {_col(p,'loja')} — {_col(p,'procuracao') or 'Sem status'}\n"
            if len(pend) > 5:
                texto += f"  _...e mais {len(pend)-5}_\n"

        msg = update.message or update.callback_query.message
        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _resumo_mes(update)

async def _resumo_mes(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        fim = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])
        r = sh.resumo_periodo(ini, fim)

        texto = (
            f"{header(f'📅 RESUMO DO MÊS — {r[\"inicio\"]} a {r[\"fim\"]}')}"
            f"📋 Total de registros: *{r['total']}*\n"
            f"💵 Faturamento bruto: *{moeda(r['faturamento'])}*\n"
            f"💰 Custo líquido: *{moeda(r['liquido'])}*\n"
            f"📝 Procurações: *{r['procuracoes']}*\n"
        )
        msg = update.message or update.callback_query.message
        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_semana(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        hoje = date.today()
        ini = hoje - timedelta(days=6)
        r = sh.resumo_periodo(ini, hoje)
        texto = (
            f"{header(f'📅 ÚLTIMOS 7 DIAS — {r[\"inicio\"]} a {r[\"fim\"]}')}"
            f"📋 Total de registros: *{r['total']}*\n"
            f"💵 Faturamento bruto: *{moeda(r['faturamento'])}*\n"
            f"💰 Custo líquido: *{moeda(r['liquido'])}*\n"
            f"📝 Procurações: *{r['procuracoes']}*\n"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        await update.message.reply_text(f"❌ Erro: {e}")


async def cmd_procuracoes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _proc_hoje(update)

async def _proc_hoje(update):
    try:
        procs = sh.procuracoes_hoje()
        msg = update.message or update.callback_query.message
        if not procs:
            await msg.reply_text("📝 Nenhuma procuração registrada hoje.")
            return

        texto = header(f"📝 PROCURAÇÕES HOJE — {date.today().strftime('%d/%m/%Y')}")
        texto += f"Total: *{len(procs)}*\n\n"
        for i, r in enumerate(procs, 1):
            status = _col(r, "procuracao") or "—"
            emoji = "✅" if "ok" in status.lower() else "⚠️"
            texto += (
                f"{emoji} *{i}. {_col(r,'cliente')}*\n"
                f"   🏪 {_col(r,'loja')} | 🚗 {_col(r,'placa')}\n"
                f"   📋 {_col(r,'servico')} | Status: `{status}`\n"
                f"   👤 {_col(r,'feito_por')}\n\n"
            )
        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_pendentes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pendentes(update, apenas_hoje=True)

async def cmd_pendentes_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pendentes(update, apenas_hoje=False)

async def _pendentes(update, apenas_hoje: bool):
    try:
        hoje = date.today()
        if apenas_hoje:
            pend = sh.procuracoes_pendentes(hoje, hoje)
            periodo = f"HOJE — {hoje.strftime('%d/%m/%Y')}"
        else:
            ini = date(hoje.year, hoje.month, 1)
            pend = sh.procuracoes_pendentes(ini, hoje)
            periodo = f"MÊS — {ini.strftime('%d/%m')} a {hoje.strftime('%d/%m/%Y')}"

        msg = update.message or update.callback_query.message
        if not pend:
            await msg.reply_text(f"✅ Nenhuma procuração pendente ({periodo}).")
            return

        texto = header(f"⚠️ PROCURAÇÕES PENDENTES — {periodo}")
        texto += f"Total: *{len(pend)}*\n\n"

        # Agrupa por loja
        por_loja: dict = {}
        for r in pend:
            loja = _col(r, "loja") or "Sem Loja"
            por_loja.setdefault(loja, []).append(r)

        for loja, itens in sorted(por_loja.items()):
            texto += f"🏪 *{loja}* ({len(itens)})\n"
            for r in itens:
                status = _col(r, "procuracao") or "Sem status"
                texto += (
                    f"  • {_col(r,'cliente')} | {_col(r,'placa')}\n"
                    f"    Serviço: {_col(r,'servico')} | `{status}`\n"
                )
            texto += "\n"

        # Divide em chunks se necessário
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_ranking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ranking_lojas(update)

async def _ranking_lojas(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        ranking = sh.ranking_lojas(ini, hoje)

        msg = update.message or update.callback_query.message
        if not ranking:
            await msg.reply_text("Sem dados para o ranking.")
            return

        texto = header(f"🏆 RANKING DE LOJAS — {ini.strftime('%m/%Y')}")
        total_qtd = sum(q for _, q, _ in ranking)
        medalhas = ["🥇", "🥈", "🥉"] + ["▪️"] * 20

        for i, (loja, qtd, fat) in enumerate(ranking):
            barra = "█" * min(int(qtd / max(ranking[0][1], 1) * 10), 10)
            texto += (
                f"{medalhas[i]} *{loja}*\n"
                f"   {barra} {qtd} registros ({pct(qtd, total_qtd)})\n"
                f"   💵 {moeda(fat)}\n\n"
            )
        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_operadores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ranking_ops(update)

async def _ranking_ops(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        ranking = sh.ranking_operadores(ini, hoje)

        msg = update.message or update.callback_query.message
        if not ranking:
            await msg.reply_text("Sem dados para o ranking.")
            return

        texto = header(f"👤 RANKING DE OPERADORES — {ini.strftime('%m/%Y')}")
        total = sum(q for _, q in ranking)
        medalhas = ["🥇", "🥈", "🥉"] + ["▪️"] * 20

        for i, (op, qtd) in enumerate(ranking):
            barra = "█" * min(int(qtd / max(ranking[0][1], 1) * 10), 10)
            texto += f"{medalhas[i]} *{op}*\n   {barra} {qtd} ({pct(qtd, total)})\n\n"

        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_videos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _videos(update)

async def _videos(update):
    try:
        hoje = date.today()
        pendentes = sh.videos_pendentes(hoje, hoje)

        msg = update.message or update.callback_query.message
        if not pendentes:
            await msg.reply_text(f"✅ Nenhum vídeo pendente hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        texto = header(f"🎬 VÍDEOS PENDENTES — {hoje.strftime('%d/%m/%Y')}")
        texto += f"Total: *{len(pendentes)}*\n\n"
        for r in pendentes:
            status = _col(r, "video") or "—"
            texto += (
                f"⚠️ *{_col(r,'cliente')}*\n"
                f"   🚗 {_col(r,'placa')} | 🏪 {_col(r,'loja')}\n"
                f"   📋 {_col(r,'servico')} | Status vídeo: `{status}`\n"
                f"   👤 {_col(r,'feito_por')}\n\n"
            )
        for chunk in _split(texto):
            await msg.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_faturamento(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _fat_loja(update)

async def _fat_loja(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        fat = sh.faturamento_por_loja(ini, hoje)

        msg = update.message or update.callback_query.message
        if not fat:
            await msg.reply_text("Sem dados de faturamento.")
            return

        total = sum(fat.values())
        texto = header(f"💰 FATURAMENTO POR LOJA — {ini.strftime('%m/%Y')}")
        texto += f"*Total geral: {moeda(total)}*\n\n"

        for loja, v in fat.items():
            barra = "█" * min(int(v / max(fat.values()) * 8), 8)
            texto += f"🏪 *{loja}*\n   {barra} {moeda(v)} ({pct(v, total)})\n\n"

        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_servicos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _servicos(update)

async def _servicos(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        svcs = sh.servicos_por_tipo(ini, hoje)

        msg = update.message or update.callback_query.message
        if not svcs:
            await msg.reply_text("Sem dados de serviços.")
            return

        total = sum(svcs.values())
        texto = header(f"🗂️ SERVIÇOS DO MÊS — {ini.strftime('%m/%Y')}")
        texto += f"*Total: {total} registros*\n\n"

        for svc, qtd in svcs.items():
            barra = "█" * min(int(qtd / max(svcs.values()) * 8), 8)
            texto += f"📋 *{svc}*\n   {barra} {qtd} ({pct(qtd, total)})\n\n"

        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_grupos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _grupos(update)

async def _grupos(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        grupos = sh.resumo_por_grupo(ini, hoje)

        msg = update.message or update.callback_query.message
        if not grupos:
            await msg.reply_text("Sem dados por grupo.")
            return

        total_fat = sum(g["faturamento"] for g in grupos.values())
        texto = header(f"🏢 RESUMO POR GRUPO — {ini.strftime('%m/%Y')}")

        for grupo, d in grupos.items():
            texto += (
                f"🏢 *{grupo}*\n"
                f"   📋 {d['qtd']} registros\n"
                f"   💵 Faturamento: {moeda(d['faturamento'])} ({pct(d['faturamento'], total_fat)})\n"
                f"   💰 Líquido: {moeda(d['liquido'])}\n\n"
            )

        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_pagamentos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _pagamentos(update)

async def _pagamentos(update):
    try:
        hoje = date.today()
        ini = date(hoje.year, hoje.month, 1)
        pgs = sh.formas_pagamento(ini, hoje)

        msg = update.message or update.callback_query.message
        if not pgs:
            await msg.reply_text("Sem dados de pagamento.")
            return

        total = sum(pgs.values())
        texto = header(f"💳 FORMAS DE PAGAMENTO — {ini.strftime('%m/%Y')}")
        texto += f"*Total: {total} transações*\n\n"

        icones = {"ACERTO": "🤝", "PIX": "📱", "DINHEIRO": "💵",
                  "CARTÃO": "💳", "BOLETO": "📄", "DÉBITO": "💳"}
        for pg, qtd in pgs.items():
            ico = next((v for k, v in icones.items() if k in pg.upper()), "💳")
            barra = "█" * min(int(qtd / max(pgs.values()) * 8), 8)
            texto += f"{ico} *{pg}*\n   {barra} {qtd} ({pct(qtd, total)})\n\n"

        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        msg = update.message or update.callback_query.message
        await msg.reply_text(f"❌ Erro: {e}")


async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Use: `/buscar nome` ou `/buscar placa`", parse_mode="Markdown")
        return
    termo = " ".join(ctx.args)
    try:
        resultados = sh.buscar_cliente(termo)
        if not resultados:
            await update.message.reply_text(f"🔍 Nenhum resultado para *\"{termo}\"*.", parse_mode="Markdown")
            return

        texto = header(f"🔍 BUSCA: \"{termo}\"")
        texto += f"*{len(resultados)} resultado(s)*\n\n"
        for r in resultados[:15]:
            data = _col(r, "data")
            texto += (
                f"📅 {data} | 🏪 {_col(r,'loja')}\n"
                f"👤 *{_col(r,'cliente')}*\n"
                f"🚗 {_col(r,'placa')} — {_col(r,'veiculo')}\n"
                f"📋 {_col(r,'servico')} | 💵 {_col(r,'valor')}\n"
                f"📝 Proc: `{_col(r,'procuracao') or '—'}` | 🎬 Vídeo: `{_col(r,'video') or '—'}`\n\n"
            )
        if len(resultados) > 15:
            texto += f"_...e mais {len(resultados)-15} resultado(s). Refine a busca._"

        for chunk in _split(texto):
            await update.message.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        log.error(e)
        await update.message.reply_text(f"❌ Erro: {e}")


async def cmd_atualizar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sh.invalidar_cache()
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    await msg.reply_text("🔄 Cache invalidado! Os próximos dados virão direto da planilha.")


# ─── Callback handler (botões) ────────────────────────────────────────────────

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
    }

    fn = dispatch.get(cmd)
    if fn:
        await fn()
    else:
        await query.message.reply_text("Comando desconhecido.")


# ─── Mensagens de texto livre ─────────────────────────────────────────────────

async def texto_livre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()

    if any(w in txt for w in ["hoje", "resumo do dia", "como foi hoje"]):
        await _resumo_hoje(update)
    elif any(w in txt for w in ["mês", "mes", "mensal", "este mês"]):
        await _resumo_mes(update)
    elif any(w in txt for w in ["pendente", "faltando", "sem assinar"]):
        await _pendentes(update, True)
    elif any(w in txt for w in ["procuração", "procuracao"]):
        await _proc_hoje(update)
    elif any(w in txt for w in ["ranking", "melhor loja", "top loja"]):
        await _ranking_lojas(update)
    elif any(w in txt for w in ["operador", "quem fez", "atendente"]):
        await _ranking_ops(update)
    elif any(w in txt for w in ["vídeo", "video"]):
        await _videos(update)
    elif any(w in txt for w in ["faturamento", "receita", "dinheiro"]):
        await _fat_loja(update)
    elif any(w in txt for w in ["serviço", "servico", "tipo de serviço"]):
        await _servicos(update)
    elif any(w in txt for w in ["grupo"]):
        await _grupos(update)
    elif any(w in txt for w in ["pagamento", "forma de pagar", "pix", "acerto"]):
        await _pagamentos(update)
    else:
        await update.message.reply_text(
            "Não entendi. Use /ajuda para ver os comandos ou escolha uma opção:",
            reply_markup=kb_principal()
        )


# ─── Utilitário: split de mensagens longas ────────────────────────────────────

def _split(texto: str, limite: int = 4000) -> list[str]:
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",          start))
    app.add_handler(CommandHandler("ajuda",          start))
    app.add_handler(CommandHandler("hoje",           cmd_hoje))
    app.add_handler(CommandHandler("mes",            cmd_mes))
    app.add_handler(CommandHandler("semana",         cmd_semana))
    app.add_handler(CommandHandler("procuracoes",    cmd_procuracoes))
    app.add_handler(CommandHandler("pendentes",      cmd_pendentes))
    app.add_handler(CommandHandler("pendentes_mes",  cmd_pendentes_mes))
    app.add_handler(CommandHandler("ranking",        cmd_ranking))
    app.add_handler(CommandHandler("operadores",     cmd_operadores))
    app.add_handler(CommandHandler("videos",         cmd_videos))
    app.add_handler(CommandHandler("faturamento",    cmd_faturamento))
    app.add_handler(CommandHandler("servicos",       cmd_servicos))
    app.add_handler(CommandHandler("grupos",         cmd_grupos))
    app.add_handler(CommandHandler("pagamentos",     cmd_pagamentos))
    app.add_handler(CommandHandler("buscar",         cmd_buscar))
    app.add_handler(CommandHandler("atualizar",      cmd_atualizar))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_livre))

    log.info("✅ Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
