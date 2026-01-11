import os
import threading
import asyncio
import pandas as pd
from flask import Flask
from pyproj import Transformer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==========================================
# 1. CONFIGURAÇÃO GEOGRÁFICA
# ==========================================
PROJ_CEPI = (
    "+proj=poly +lat_0=-7 +lon_0=-43 +x_0=1000000 +y_0=10000000 "
    "+ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +units=m +no_defs"
)

transformer = Transformer.from_crs(PROJ_CEPI, "epsg:4326", always_xy=True)

# ==========================================
# 2. PLANILHA (CAMINHO ROBUSTO + CACHE)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PLANILHA = os.path.join(BASE_DIR, "dados", "postes.xlsx")

if not os.path.exists(CAMINHO_PLANILHA):
    raise FileNotFoundError(f"❌ Planilha não encontrada: {CAMINHO_PLANILHA}")

DF_POSTES = pd.read_excel(CAMINHO_PLANILHA)

# ==========================================
# 3. SERVIDOR WEB (RENDER)
# ==========================================
web_app = Flask(__name__)

@web_app.route("/")
def health_check():
    return "Bot de Geolocalização CEPISA: Ativo", 200

# ==========================================
# 4. BOT TELEGRAM
# ==========================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⚡ Localizar Poste (PG)", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Sistema de Localização de Postes\n\nO que deseja fazer?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def escolher_componente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = query.data
    await query.message.reply_text("🔢 Digite o ID do Poste (Ex: 5917428):")

async def buscar_poste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_state:
        await update.message.reply_text("Use /start para começar.")
        return

    codigo = update.message.text.strip()

    msg_status = await update.message.reply_text("🔍 Procurando o poste, aguarde...")

    try:
        resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == codigo]

        if resultado.empty:
            await msg_status.edit_text("❌ ID não encontrado na base de dados.")
            return

        row = resultado.iloc[0]

        lon, lat = transformer.transform(row["X"], row["Y"])
        google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"

        municipio = row.get("INT_NOME_SE", "N/D")

        mensagem = (
            f"🚩 *Poste Localizado!*\n"
            f"───────────────────\n"
            f"🔢 *ID:* `{row['ID_POSTE']}`\n"
            f"🏙️ *Município:* {municipio}\n"
            f"📍 *X:* `{row['X']}`\n"
            f"📍 *Y:* `{row['Y']}`\n"
            f"───────────────────\n"
            f"🌎 *Latitude:* `{lat:.7f}`\n"
            f"🌎 *Longitude:* `{lon:.7f}`\n\n"
            f"🗺️ [Abrir no Google Maps]({google_maps_url})"
        )

        await msg_status.edit_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await msg_status.edit_text("⚠️ Erro ao processar a solicitação.")
        print(f"Erro interno: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 *Status do Sistema*\n"
        "───────────────────\n"
        "🤖 Bot: ONLINE\n"
        "☁️ Servidor: Render ativo\n"
        "📡 Monitoramento: UptimeRobot OK",
        parse_mode="Markdown"
    )

# ==========================================
# 5. EXECUÇÃO CORRETA (EVENT LOOP + THREAD)
# ==========================================
def start_bot():
    print(">>> START_BOT FOI EXECUTADO <<<")

    if not TOKEN:
        print("❌ TELEGRAM_TOKEN não definido")
        return

    async def main():
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CallbackQueryHandler(escolher_componente))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_poste))

        print("🤖 Bot Telegram iniciado e aguardando mensagens...")
        await app.run_polling(
            drop_pending_updates=True,
            stop_signals=None   # 🔴 LINHA CRÍTICA
        )

    asyncio.run(main())

# ==========================================
# 6. INICIALIZAÇÃO DO BOT (GUNICORN)
# ==========================================
threading.Thread(target=start_bot, daemon=True).start()
