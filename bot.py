from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import pandas as pd

# =========================
# TOKEN DO BOT
# =========================
TOKEN = "8593219004:AAEDeLnjl7DrJU6VXg8RrcN-FdDCw6_O3Dg"

# =========================
# CONTROLE DE ESTADO
# =========================
user_state = {}

# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🪵 PG (Poste)", callback_data="poste")]
    ]

    await update.message.reply_text(
        "👋 Olá!\n\nO que você deseja localizar?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ESCOLHA DO COMPONENTE
# =========================
async def escolher_componente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_state[query.from_user.id] = query.data

    await query.message.reply_text(
        "Informe o ID do poste:"
    )

# =========================
# BUSCA DO ID
# =========================
async def buscar_poste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state:
        await update.message.reply_text("Use /start para iniciar.")
        return

    codigo = update.message.text.strip()

    try:
        df = pd.read_excel("dados/postes.xlsx")

        # 🔎 DEBUG (pode remover depois)
        # print(df.columns)

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

        await update.message.reply_text(
            mensagem,
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")


# =========================
# INICIALIZAÇÃO
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(escolher_componente))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_poste))

print("🤖 Bot rodando...")
app.run_polling()

