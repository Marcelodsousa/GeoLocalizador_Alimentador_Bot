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
# CONFIGURAÇÃO GEOGRÁFICA
# ==========================================
PROJ_CEPI = (
    "+proj=poly +lat_0=-7 +lon_0=-43 +x_0=1000000 +y_0=10000000 "
    "+ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +units=m +no_defs"
)
transformer = Transformer.from_crs(PROJ_CEPI, "epsg:4326", always_xy=True)

# ==========================================
# CARREGAMENTO DA PLANILHA
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PLANILHA = os.path.join(BASE_DIR, "dados", "postes.xlsx")

try:
    DF_POSTES = pd.read_excel(CAMINHO_PLANILHA)
    print("✅ Planilha carregada com sucesso!")
except Exception as e:
    print(f"❌ Erro ao carregar planilha: {e}")
    DF_POSTES = pd.DataFrame()

# ==========================================
# FLASK (KEEP ALIVE / HEALTH CHECK)
# ==========================================
web_app = Flask(__name__)

@web_app.route("/")
def health():
    return "Bot e Web App ativos", 200

# ==========================================
# TELEGRAM BOT (LÓGICA)
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
    user_id = update.message.from_user.id
    if user_id not in user_state:
        await update.message.reply_text("Use /start primeiro.")
        return

    codigo = update.message.text.strip()
    msg = await update.message.reply_text("🔍 Procurando...")

    resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == codigo]
    
    if resultado.empty:
        await msg.edit_text(f"❌ ID `{codigo}` não encontrado.")
        return

    row = resultado.iloc[0]
    lon, lat = transformer.transform(row["X"], row["Y"])
    url = f"https://www.google.com/maps?q={lat},{lon}"

    await msg.edit_text(
        f"📍 **Poste Encontrado**\n\n"
        f"ID: `{codigo}`\n"
        f"Lat: `{lat:.7f}`\n"
        f"Lon: `{lon:.7f}`\n\n"
        f"🔗 [Abrir no Google Maps]({url})",
        parse_mode="Markdown"
    )

# ==========================================
# EXECUÇÃO DO BOT (CORREÇÃO DE THREAD/LOOP)
# ==========================================
def run_bot_thread():
    """Configura o loop de eventos e roda o bot na thread"""
    if not TOKEN:
        print("❌ ERRO: TELEGRAM_TOKEN não definido.")
        return

    # CRIAR E DEFINIR UM NOVO LOOP PARA ESTA THREAD
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Configurar aplicação
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(escolher))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 Bot Telegram iniciado na thread separada.")
    
    # Rodar o bot usando o loop criado
    application.run_polling(drop_pending_updates=True)

# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == "__main__":
    # 1. Inicia o Bot na Thread (com seu próprio loop de eventos)
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()

    # 2. Inicia o Flask no processo principal
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Iniciando Flask na porta {port}")
    web_app.run(host="0.0.0.0", port=port)