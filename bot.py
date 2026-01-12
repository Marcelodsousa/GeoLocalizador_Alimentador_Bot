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
    # Ajuste para garantir que nomes de colunas sejam lidos corretamente
    DF_POSTES.columns = [str(c).strip() for c in DF_POSTES.columns]
    print(f"✅ Planilha carregada! Colunas encontradas: {list(DF_POSTES.columns)}")
except Exception as e:
    print(f"❌ Erro na planilha: {e}")
    DF_POSTES = pd.DataFrame()

# ==========================================
# SERVIDOR FLASK (KEEP ALIVE RENDER)
# ==========================================
web_app = Flask(__name__)

@web_app.route("/")
def health():
    return "Bot Operacional", 200

# ==========================================
# LÓGICA DO BOT TELEGRAM
# ==========================================
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
    
    codigo_procurado = update.message.text.strip()
    msg = await update.message.reply_text("🔍 Procurando...")
    
    # Busca o ID na coluna ID_POSTE conforme imagem do Excel
    resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == codigo_procurado]
    
    if resultado.empty:
        await msg.edit_text(f"❌ ID `{codigo_procurado}` não encontrado.")
        return
    
    row = resultado.iloc[0]
    
    # AJUSTE DAS COLUNAS CONFORME SUA IMAGEM EXCEL:
    # Combina INT_NOME_SE com INT_CODIGO_SE
    nome_se = str(row.get("INT_NOME_SE", "N/A"))
    cod_se = str(row.get("INT_CODIGO_SE", "N/A"))
    localidade_completa = f"{nome_se} ({cod_se})"
    
    # Coordenadas X e Y originais para a conversão
    x_coord = row.get("X")
    y_coord = row.get("Y")
    
    lon, lat = transformer.transform(x_coord, y_coord)
    
    # Link para o Google Maps
    url = f"https://www.google.com/maps?q={lat},{lon}"
    
    # LAYOUT FINAL COM BANDEIRA (🚩), LOCALIDADE COMPLETA E NOMES POR EXTENSO
    texto_formatado = (
        f"🚩 **Poste localizado!**\n\n"
        f"📍 **Localidade:** {localidade_completa}\n"
        f"🔢 **ID Poste:** {codigo_procurado}\n\n"
        f"🌎 **Latitude:** `{lat:.15f}`\n"
        f"🌎 **Longitude:** `{lon:.15f}`\n\n"
        f"🗺️ [Abrir no Google Maps]({url})"
    )
    
    await msg.edit_text(
        texto_formatado,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )

# ==========================================
# EXECUÇÃO EM THREAD
# ==========================================
def run_bot_thread():
    if not TOKEN:
        print("❌ ERRO: TOKEN não configurado!")
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(escolher))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))
    
    application.run_polling(drop_pending_updates=True, stop_signals=False, close_loop=False)

if __name__ == "__main__":
    threading.Thread(target=run_bot_thread, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)