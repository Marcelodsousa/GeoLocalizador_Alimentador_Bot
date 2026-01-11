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

# ==========================================
# 1. CONFIGURAÇÃO GEOGRÁFICA
# ==========================================
PROJ_CEPI = (
    "+proj=poly +lat_0=-7 +lon_0=-43 +x_0=1000000 +y_0=10000000 "
    "+ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +units=m +no_defs"
)

transformer = Transformer.from_crs(PROJ_CEPI, "epsg:4326", always_xy=True)

# ==========================================
# 2. PLANILHA
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PLANILHA = os.path.join(BASE_DIR, "dados", "postes.xlsx")

DF_POSTES = pd.read_excel(CAMINHO_PLANILHA)

# ==========================================
# 3. FLASK (KEEP ALIVE)
# ==========================================
web_app = Flask(__name__)

@web_app.route("/")
def health():
    return "Bot ativo", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ==========================================
# 4. TELEGRAM BOT
# ==========================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⚡ Localizar Poste", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Sistema de Localização de Postes",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def escolher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = True
    await query.message.reply_text("Digite o ID do poste:")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in user_state:
        await update.message.reply_text("Use /start primeiro.")
        return

    codigo = update.message.text.strip()
    msg = await update.message.reply_text("🔍 Procurando...")

    resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == codigo]
    if resultado.empty:
        await msg.edit_text("❌ ID não encontrado.")
        return

    row = resultado.iloc[0]
    lon, lat = transformer.transform(row["X"], row["Y"])
    url = f"https://www.google.com/maps?q={lat},{lon}"

    await msg.edit_text(
        f"📍 Poste `{codigo}`\n"
        f"Lat: `{lat:.7f}`\n"
        f"Lon: `{lon:.7f}`\n\n"
        f"[Abrir no Google Maps]({url})",
        parse_mode="Markdown"
    )

# ==========================================
# 5. LOOP PRINCIPAL (SEM run_polling)
# ==========================================
async def telegram_loop():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(escolher))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 Bot Telegram iniciado")

    await app.initialize()
    await app.start()
    await app.bot.initialize()

    # 🔴 mantém o processo vivo SEM fechar loop
    await asyncio.Event().wait()

# ==========================================
# 6. BOOT
# ==========================================
if __name__ == "__main__":
    print("🚀 Iniciando serviço")

    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(telegram_loop())
