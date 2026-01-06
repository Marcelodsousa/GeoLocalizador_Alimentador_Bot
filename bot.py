import os
import threading
import pandas as pd
from flask import Flask
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
# 1. SERVIDOR WEB (Para o Render não dormir)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    # O Render enviará requisições aqui para checar se o bot está vivo
    return "Bot de Geolocalização: ON", 200

def run_flask():
    # O Render fornece a porta automaticamente na variável PORT
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. LÓGICA DO BOT (Seu código original)
# ==========================================
# Buscando o Token das variáveis de ambiente do Render
TOKEN = os.environ.get("TELEGRAM_TOKEN")
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⚡ PG (Poste)", callback_data="poste")]]
    await update.message.reply_text(
        "👋 Olá!\n\nO que você deseja localizar?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
        # Tenta carregar o Excel da pasta 'dados'
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
        await update.message.reply_text(f"⚠️ Erro ao acessar a base de dados: {e}")

# ==========================================
# 3. EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    # Inicia o servidor Flask em uma thread separada
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 Iniciando o bot...")
    
    try:
        if not TOKEN:
            print("❌ ERRO: A variável TELEGRAM_TOKEN não foi configurada no Render!")
        else:
            # Configuração do Application
            app = ApplicationBuilder().token(TOKEN).build()

            # Handlers
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CallbackQueryHandler(escolher_componente))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_poste))

            print("🤖 Bot rodando e aguardando mensagens...")
            # drop_pending_updates limpa mensagens enviadas enquanto o bot estava desligado
            app.run_polling(drop_pending_updates=True)

    except Exception as e:
        print(f"❌ Erro fatal: {e}")