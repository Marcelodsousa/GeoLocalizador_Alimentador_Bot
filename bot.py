import os
import asyncio
import threading
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

# Configuração Geográfica
PROJ_CEPI = (
    "+proj=poly +lat_0=-7 +lon_0=-43 +x_0=1000000 +y_0=10000000 "
    "+ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +units=m +no_defs"
)
transformer = Transformer.from_crs(PROJ_CEPI, "epsg:4326", always_xy=True)

# Carregamento da Planilha
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PLANILHA = os.path.join(BASE_DIR, "dados", "postes.xlsx")

try:
    DF_POSTES = pd.read_excel(CAMINHO_PLANILHA)
    print("✅ Planilha carregada com sucesso!")
except Exception as e:
    print(f"❌ Erro na planilha: {e}")
    DF_POSTES = pd.DataFrame()

# Servidor Flask para manter o Render ativo
web_app = Flask(__name__)

@web_app.route("/")
def health():
    return "Bot Operacional", 200

# Lógica do Bot
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⚡ Localizar Poste", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Sistema de Localização de Postes\nUse /status para verificar o servidor.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(DF_POSTES) if not DF_POSTES.empty else 0
    await update.message.reply_text(
        f"✅ **STATUS DO SISTEMA**\n\n📊 **Base:** {total} postes\n🌐 **Servidor:** Online",
        parse_mode="Markdown"
    )

async def escolher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = True
    await query.message.reply_text("Digite o ID do poste:")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in user_state:
        return
    codigo = update.message.text.strip()
    msg = await update.message.reply_text("🔍 Procurando...")
    resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == codigo]
    if resultado.empty:
        await msg.edit_text(f"❌ ID `{codigo}` não encontrado.")
        return
    row = resultado.iloc[0]
    localidade = row.get("LOCALIDADE", "N/A")
    lon, lat = transformer.transform(row["X"], row["Y"])
    url = f"https://www.google.com/maps?q={lat},{lon}"
    await msg.edit_text(
        f"🚩 **Poste localizado!**\n\n📍 **Localidade:** {localidade}\n🔢 **ID:** {codigo}\n"
        f"🌎 **Lat:** `{lat:.7f}`\n🌎 **Lon:** `{lon:.7f}`\n\n🗺️ [Abrir no Google Maps]({url})",
        parse_mode="Markdown",
        disable_web_page_preview=False
    )

# Execução em Thread Separada
def run_bot_thread():
    if not TOKEN:
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(escolher))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))
    
    # drop_pending_updates ajuda a resolver o erro de Conflict ao iniciar
    application.run_polling(drop_pending_updates=True, stop_signals=False, close_loop=False)

if __name__ == "__main__":
    threading.Thread(target=run_bot_thread, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)