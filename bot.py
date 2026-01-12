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
    """Menu inicial"""
    keyboard = [[InlineKeyboardButton("⚡ Localizar Poste", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Sistema de Localização de Postes\nUse /status para verificar o servidor.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica se o bot está respondendo e base de dados ativa"""
    total_postes = len(DF_POSTES) if not DF_POSTES.empty else 0
    msg = (
        "✅ **STATUS DO SISTEMA**\n\n"
        f"🤖 **Bot:** Online\n"
        f"📊 **Base de Dados:** {total_postes} postes carregados\n"
        f"🌐 **Servidor:** Render Operational\n"
        f"⚡ **Modo:** Híbrido (Flask + Threading)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def escolher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a interação de busca"""
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = True
    await query.message.reply_text("Digite o ID do poste:")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Realiza a busca e retorna os dados formatados"""
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
    localidade = row.get("LOCALIDADE", "N/A")
    lon, lat = transformer.transform(row["X"], row["Y"])
    
    # Formato de link compatível com preview no Telegram
    url = f"https://www.google.com/maps?q={lat},{lon}"

    texto_final = (
        f"🚩 **Poste localizado!**\n\n"
        f"📍 **Localidade:** {localidade}\n"
        f"🔢 **ID Poste:** {codigo}\n\n"
        f"🌎 **Latitude:** `{lat}`\n"
        f"🌎 **Longitude:** `{lon}`\n\n"
        f"🗺️ [Abrir no Google Maps]({url})"
    )

    await msg.edit_text(
        texto_final,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )

# ==========================================
# EXECUÇÃO DO BOT (AJUSTE PARA THREAD)
# ==========================================
def run_bot_thread():
    if not TOKEN:
        print("❌ ERRO: TELEGRAM_TOKEN não definido.")
        return

    # Cria loop isolado para a thread secundária para evitar erros de asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(TOKEN).build()
    
    # Adicionando os Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(escolher))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 Bot Telegram iniciado na thread secundária.")
    
    # Roda o bot sem tentar gerenciar sinais de sistema (que pertencem ao Flask)
    application.run_polling(
        drop_pending_updates=True, 
        stop_signals=False, 
        close_loop=False
    )

# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == "__main__":
    # Inicia o Bot na Thread (Monitorado internamente)
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()

    # Inicia o Flask (Processo Principal monitorado pelo Render e UptimeRobot)
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor Web rodando na porta {port}")
    web_app.run(host="0.0.0.0", port=port)