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

async def obter_menu_principal():
    """Cria o teclado de atalho no chat"""
    keyboard = [
        [InlineKeyboardButton("🚩 Localizar Poste", callback_data="btn_buscar")],
        [InlineKeyboardButton("📊 Status do Sistema", callback_data="btn_status")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu inicial com teclado de atalhos"""
    reply_markup = await obter_menu_principal()
    await update.message.reply_text(
        "👋 **Sistema de GeoLocalização de Postes**\n\n"
        "Selecione uma opção abaixo ou digite o ID do poste diretamente:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def status_logic(update_or_query):
    """Exibe o status do banco de dados"""
    total = len(DF_POSTES) if not DF_POSTES.empty else 0
    texto = f"✅ **STATUS DO SISTEMA**\n\n📊 **Base:** {total} postes\n🌐 **Servidor:** Online"
    
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(texto, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(texto, parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia cliques no teclado de atalho"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "btn_buscar":
        await query.message.reply_text("🔢 **Por favor, digite o ID do poste:**", parse_mode="Markdown")
    elif query.data == "btn_status":
        await status_logic(query)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa IDs ou orienta interações de texto"""
    texto_usuario = update.message.text.strip()
    
    # Se for um número, tenta localizar o poste
    if texto_usuario.isdigit():
        msg = await update.message.reply_text("🔍 Procurando...")
        resultado = DF_POSTES[DF_POSTES["ID_POSTE"].astype(str) == texto_usuario]
        
        if resultado.empty:
            await msg.edit_text(f"❌ ID `{texto_usuario}` não encontrado.")
            return
        
        row = resultado.iloc[0]
        localidade = f"{row.get('INT_NOME_SE', 'N/A')} ({row.get('INT_CODIGO_SE', 'N/A')})"
        lon, lat = transformer.transform(row.get("X"), row.get("Y"))
        url = f"https://www.google.com/maps?q={lat},{lon}"
        
        res_formatada = (
            f"🚩 **Poste localizado!**\n\n"
            f"📍 **Localidade:** {localidade}\n"
            f"🔢 **ID Poste:** {texto_usuario}\n\n"
            f"🌎 **Latitude:** `{lat:.15f}`\n"
            f"🌎 **Longitude:** `{lon:.15f}`\n\n"
            f"🗺️ [Abrir no Google Maps]({url})"
        )
        await msg.edit_text(res_formatada, parse_mode="Markdown", disable_web_page_preview=False)
    
    # Se for texto comum (Oi, Olá), não fica em silêncio e mostra o menu
    else:
        reply_markup = await obter_menu_principal()
        await update.message.reply_text(
            f"Olá! Você disse: '{texto_usuario}'.\n\n"
            "Para localizar um poste, use o botão abaixo ou digite o ID numérico:",
            reply_markup=reply_markup
        )

# ==========================================
# EXECUÇÃO EM THREAD
# ==========================================
def run_bot_thread():
    if not TOKEN: return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", lambda u, c: status_logic(u)))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))
    
    print("🤖 Bot iniciado com sucesso.")
    application.run_polling(drop_pending_updates=True, stop_signals=False, close_loop=False)

if __name__ == "__main__":
    threading.Thread(target=run_bot_thread, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)