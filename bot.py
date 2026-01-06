from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import pandas as pd
import os
from flask import Flask
import threading

# --- Servidor Web para o Render ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# --- Lógica do Bot ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🪵 PG (Poste)", callback_data="poste")]]
    await update.message.reply_text("👋 Olá!\n\nO que deseja localizar?", reply_markup=InlineKeyboardMarkup(keyboard))

async def escolher_componente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = query.data
    await query.message.reply_text("Informe o ID do poste:")

async def buscar_poste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_state:
        await update.message.reply_text("Use /start para iniciar.")
        return

    codigo = update.message.text.strip()
    try:
        # Caminho corrigido para a pasta dados
        df = pd.read_excel("dados/postes.xlsx")
        resultado = df[df["ID_POSTE"].astype(str) == codigo]

        if resultado.empty:
            await update.message.reply_text("❌ Poste não encontrado.")
            return

        row = resultado.iloc[0]
        mensagem = (
            f"⚡ *Poste localizado!*\n\n"
            f"📍 *Localidade:* {row['INT_NOME_SE']} ({row['INT_CODIGO_SE']})\n"
            f"🔢 *ID Poste:* {row['ID_POSTE']}\n\n"
            f"🌎 *Latitude:* {row['LATITUDE']}\n"
            f"🌎 *Longitude:* {row['LONGITUDE']}\n\n"
            f"🗺️ [Abrir no Google Maps]({row['GOOGLE_MAPS']})"
        )
        await update.message.reply_text(mensagem, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Erro ao ler banco de dados: {e}")

if __name__ == "__main__":
    # Inicia o servidor web em uma thread separada
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Inicia o Bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(escolher_componente))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_poste))
    
    print("🤖 Bot rodando...")
    app.run_polling()