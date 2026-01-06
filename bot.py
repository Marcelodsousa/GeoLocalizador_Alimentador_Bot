import os
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
# 1. CONFIGURAÇÃO GEOGRÁFICA (PRECISÃO TOTAL)
# ==========================================
# Parâmetros que identificamos: Policônica, Datum CEPISA/SAD69, Translação de Helisert
PROJ_CEPI = (
    "+proj=poly +lat_0=-7 +lon_0=-43 +x_0=1000000 +y_0=10000000 "
    "+ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +units=m +no_defs"
)

# Transformador para WGS84 (Google Maps)
transformer = Transformer.from_crs(PROJ_CEPI, "epsg:4326", always_xy=True)

# ==========================================
# 2. SERVIDOR WEB (Manter o Render Ativo)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot de Geolocalização CEPISA: Ativo", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# ==========================================
# 3. LÓGICA DO BOT
# ==========================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⚡ Localizar Poste (PG)", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Sistema de Localização Alto Longá\n\nO que deseja fazer?",
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
    try:
        # Carrega a planilha original (sem necessidade de conversão prévia)
        # Certifique-se que o arquivo está na pasta 'dados/' no seu repositório
        df = pd.read_excel("dados/Postes_Alto_Longa.xlsx")
        
        # Busca pelo ID
        resultado = df[df["ID_POSTE"].astype(str) == codigo]

        if resultado.empty:
            await update.message.reply_text("❌ ID não encontrado na base de dados.")
            return

        row = resultado.iloc[0]
        
        # CÁLCULO DE CONVERSÃO EM TEMPO REAL
        # Converte X e Y da planilha para Lat/Long
        lon, lat = transformer.transform(row['X'], row['Y'])
        
        google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"

        mensagem = (
            f"⚡ *Poste Localizado!*\n"
            f"───────────────────\n"
            f"🔢 *ID:* `{row['ID_POSTE']}`\n"
            f"📍 *X:* `{row['X']}`\n"
            f"📍 *Y:* `{row['Y']}`\n"
            f"───────────────────\n"
            f"🌎 *Latitude:* `{lat:.7f}`\n"
            f"🌎 *Longitude:* `{lon:.7f}`\n\n"
            f"🗺️ [Abrir no Google Maps]({google_maps_url})"
        )
        
        await update.message.reply_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao processar: {e}")

# ==========================================
# 4. EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    # Flask em thread separada para o Render não dar timeout
    threading.Thread(target=run_flask, daemon=True).start()
    
    if not TOKEN:
        print("❌ ERRO: Defina a variável TELEGRAM_TOKEN no painel do Render.")
    else:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(escolher_componente))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_poste))

        print("🤖 Bot rodando com conversão Policônica integrada!")
        app.run_polling(drop_pending_updates=True)