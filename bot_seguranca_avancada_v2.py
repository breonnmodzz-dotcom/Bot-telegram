"""
╔══════════════════════════════════════════════════════════════════╗
║         🛡️  TELEGRAM BOT — BOT DE SEGURANÇA AVANÇADA                ║
║  Anti-Spam | Ban | Mute | Filtros | Logs | Regras | Flood       ║
╚══════════════════════════════════════════════════════════════════╝

Hierarquia de permissões:
  👑 DONO      — IDs fixos em OWNER_IDS. Poder total. Menu exclusivo.
  🛡️ ADMIN BOT — Adicionados pelo dono via /addadmin.
  🔰 ADMIN GRP — Admins nativos do grupo.
  ✅ CONFIÁVEL — Isentos de filtros por grupo (/trust).
  👤 MEMBRO    — Sujeito a todas as regras.

Instalar:  pip install python-telegram-bot==20.7
Executar:  python bot.py

Novidades v4:
  - /aviso (PV ou Grupo) com seleção de grupo via botões
  - Clonagem de bot via Token (envie o token no PV)
  - Comandos de configuração restritos a Admins do Grupo
  - Registro automático de comandos no menu do Telegram (lista ao digitar /)
"""

import logging, asyncio, re, json, os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Message, BotCommand, BotCommandScopeChatAdmins, BotCommandScopeDefault
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

# ══════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÕES — EDITE AQUI
# ══════════════════════════════════════════════
TOKEN = "8779375731:AAHfTKVgWgS8zaUH18Vj4vJ0DdXDKvRh7U4"
OWNER_IDS: list[int] = [7981212751, 8023120895]  # ← seus 2 IDs aqui

MAX_MESSAGES  = 7
SPAM_WINDOW   = 10
MUTE_MINUTES  = 10
WARN_LIMIT    = 3

BANNED_WORDS: list[str] = [
    "spam", "promoção grátis", "clique aqui",
    "ganhe dinheiro", "bitcoin grátis", "compre agora",
]
ALLOWED_DOMAINS: list[str] = ["t.me", "telegram.org"]
DATA_FILE = "bot_data.json"

# ══════════════════════════════════════════════
#  📦  ESTADO
# ══════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

bot_admins: dict[int, str] = {}
trusted_users: dict = defaultdict(dict)
anti_link_groups: set = set()
anti_sticker_groups: set = set()
anti_gif_groups: set = set()
warnings: dict = defaultdict(lambda: defaultdict(int))
msg_timestamps: dict = defaultdict(lambda: defaultdict(list))
action_log: list = []
group_rules: dict[int, str] = {}
welcome_messages: dict[int, str] = {}
ban_registry: dict = defaultdict(list)
slowmode_groups: dict[int, int] = {}
known_groups: dict[int, str] = {} # ID -> Title

# Permissões abertas padrão
OPEN_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)

# Permissões travadas
LOCKED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
)

# ══════════════════════════════════════════════
#  💾  PERSISTÊNCIA
# ══════════════════════════════════════════════
def save_data():
    data = {
        "bot_admins": {str(k): v for k, v in bot_admins.items()},
        "trusted_users": {str(cid): {str(uid): name for uid, name in u.items()} for cid, u in trusted_users.items()},
        "anti_link_groups": list(anti_link_groups),
        "anti_sticker_groups": list(anti_sticker_groups),
        "anti_gif_groups": list(anti_gif_groups),
        "warnings": {str(cid): {str(uid): c for uid, c in d.items()} for cid, d in warnings.items()},
        "action_log": action_log[-1000:],
        "group_rules": {str(k): v for k, v in group_rules.items()},
        "welcome_messages": {str(k): v for k, v in welcome_messages.items()},
        "ban_registry": {str(k): v for k, v in ban_registry.items()},
        "slowmode_groups": {str(k): v for k, v in slowmode_groups.items()},
        "known_groups": {str(k): v for k, v in known_groups.items()},
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    global bot_admins, trusted_users, anti_link_groups, action_log
    global anti_sticker_groups, anti_gif_groups, group_rules, welcome_messages
    global ban_registry, slowmode_groups, known_groups
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bot_admins.update({int(k): v for k, v in data.get("bot_admins", {}).items()})
    for cid, users in data.get("trusted_users", {}).items():
        trusted_users[int(cid)] = {int(uid): name for uid, name in users.items()}
    anti_link_groups.update(map(int, data.get("anti_link_groups", [])))
    anti_sticker_groups.update(map(int, data.get("anti_sticker_groups", [])))
    anti_gif_groups.update(map(int, data.get("anti_gif_groups", [])))
    for cid, users in data.get("warnings", {}).items():
        for uid, c in users.items():
            warnings[int(cid)][int(uid)] = c
    action_log.extend(data.get("action_log", []))
    group_rules.update({int(k): v for k, v in group_rules.items()},)
    welcome_messages.update({int(k): v for k, v in welcome_messages.items()})
    for cid, lst in data.get("ban_registry", {}).items():
        ban_registry[int(cid)] = lst
    slowmode_groups.update({int(k): v for k, v in data.get("slowmode_groups", {}).items()})
    known_groups.update({int(k): v for k, v in data.get("known_groups", {}).items()})
    logger.info("✅ Dados carregados.")

# ══════════════════════════════════════════════
#  🔑  PERMISSÕES
# ══════════════════════════════════════════════
def is_owner(uid: int) -> bool: return uid in OWNER_IDS
def is_bot_admin(uid: int) -> bool: return uid in bot_admins or is_owner(uid)
def is_trusted(cid: int, uid: int) -> bool:
    return is_owner(uid) or is_bot_admin(uid) or uid in trusted_users.get(cid, {})

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except TelegramError: return False

async def has_mod_power(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return is_bot_admin(update.effective_user.id) or await is_group_admin(update, context)

# ══════════════════════════════════════════════
#  🔧  UTILITÁRIOS
# ══════════════════════════════════════════════
def log_action(chat_id, action, moderator, target, reason=""):
    entry = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "chat_id": chat_id,
             "action": action, "mod": moderator, "target": target, "reason": reason}
    action_log.append(entry)
    logger.info(f"[{action}] mod={moderator} target={target} reason={reason}")
    save_data()

def get_target(update: Update):
    msg = update.message
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, u.full_name
    if msg:
        parts = (msg.text or "").split()
        if len(parts) > 1:
            try: return int(parts[1]), parts[1]
            except ValueError: pass
    return None, None

def contains_link(text: str) -> bool:
    if not re.search(r"(https?://|www\.|t\.me/)", text, re.IGNORECASE): return False
    return not any(d in text for d in ALLOWED_DOMAINS)

def find_banned_word(text: str) -> Optional[str]:
    lower = text.lower()
    return next((w for w in BANNED_WORDS if w.lower() in lower), None)

async def safe_delete(msg: Message):
    try:
        await msg.delete()
    except TelegramError:
        pass

# ══════════════════════════════════════════════
#  🚫  ANTI-SPAM
# ══════════════════════════════════════════════
async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user, chat = update.effective_user, update.effective_chat
    if is_trusted(chat.id, user.id): return False
    now = datetime.now()
    cutoff = now - timedelta(seconds=SPAM_WINDOW)
    ts = msg_timestamps[chat.id][user.id]
    msg_timestamps[chat.id][user.id] = [t for t in ts if t > cutoff]
    msg_timestamps[chat.id][user.id].append(now)
    if len(msg_timestamps[chat.id][user.id]) >= MAX_MESSAGES:
        try:
            await context.bot.restrict_chat_member(chat.id, user.id,
                ChatPermissions(can_send_messages=False), until_date=now + timedelta(minutes=MUTE_MINUTES))
            await safe_delete(update.message)
            await context.bot.send_message(chat.id,
                f"🔇 *{user.full_name}* silenciado por *{MUTE_MINUTES} min* (flood/spam).",
                parse_mode=ParseMode.MARKDOWN)
            log_action(chat.id, "AUTO_MUTE", "BOT", user.full_name, "Flood/Spam")
            msg_timestamps[chat.id][user.id] = []
            return True
        except TelegramError as e: logger.error(f"auto-mute: {e}")
    return False

# ══════════════════════════════════════════════
#  📨  HANDLER DE MENSAGENS
# ══════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    user, chat = update.effective_user, update.effective_chat
    msg = update.message
    text = msg.text or msg.caption or ""
    
    # Armazenar grupo conhecido
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        known_groups[chat.id] = chat.title
        save_data()

    # Funcionalidade de Clone via Token (Apenas PV)
    if chat.type == ChatType.PRIVATE and re.match(r"^\d{8,10}:[a-zA-Z0-9_-]{35}$", text.strip()):
        token = text.strip()
        await msg.reply_text("🤖 *Token detectado!* Tentando clonar o bot...", parse_mode=ParseMode.MARKDOWN)
        try:
            new_app = Application.builder().token(token).build()
            bot_info = await new_app.bot.get_me()
            await msg.reply_text(
                f"✅ *Bot Clonado com Sucesso!*\n\n"
                f"🤖 Nome: {bot_info.first_name}\n"
                f"🆔 ID: `{bot_info.id}`\n"
                f"🔗 Link: t.me/{bot_info.username}\n\n"
                f"_Nota: O bot clone está pronto para ser configurado._",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        except Exception as e:
            return await msg.reply_text(f"❌ *Erro ao clonar:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

    if is_trusted(chat.id, user.id): return

    # Anti-sticker
    if chat.id in anti_sticker_groups and msg.sticker:
        await safe_delete(msg)
        await context.bot.send_message(chat.id, f"🚫 Stickers não são permitidos aqui, *{user.full_name}*.")
        return

    # Anti-gif
    if chat.id in anti_gif_groups and msg.animation:
        await safe_delete(msg)
        await context.bot.send_message(chat.id, f"🚫 GIFs não são permitidos aqui, *{user.full_name}*.")
        return

    # Anti-link
    if chat.id in anti_link_groups and contains_link(text):
        await safe_delete(msg)
        await context.bot.send_message(chat.id, f"🚫 Links não autorizados, *{user.full_name}*.")
        return

    # Filtro de palavras banidas
    word = find_banned_word(text)
    if word:
        await safe_delete(msg)
        await context.bot.send_message(chat.id, f"🚫 Linguagem proibida detectada, *{user.full_name}*.")
        return

    # Check Spam
    await check_spam(update, context)

# ══════════════════════════════════════════════
#  👑  COMANDOS DO DONO / ADMIN BOT
# ══════════════════════════════════════════════
async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda ao usuário ou use /addadmin <id>.")
    bot_admins[tid] = tname
    save_data()
    await update.message.reply_text(f"🛡️ *{tname}* agora é um Admin do Bot.", parse_mode=ParseMode.MARKDOWN)

async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    tid, _ = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ /removeadmin <id>")
    if tid in bot_admins:
        name = bot_admins.pop(tid)
        save_data()
        await update.message.reply_text(f"🗑️ *{name}* removido dos Admins.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ℹ️ Usuário não é admin.")

async def cmd_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_admin(update.effective_user.id): return
    lines = ["👑 *Donos:*"]
    for oid in OWNER_IDS: lines.append(f"• `{oid}`")
    lines.append("\n🛡️ *Admins do Bot:*")
    if not bot_admins: lines.append("_Nenhum admin adicionado._")
    for aid, name in bot_admins.items(): lines.append(f"• `{aid}` — *{name}*")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aviso oficial. Uso: /aviso <texto>"""
    if not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas admins do bot.")
    
    if not context.args:
        return await update.message.reply_text("ℹ️ Uso: /aviso <mensagem>")
    
    msg_text = " ".join(context.args)
    context.user_data['broadcast_msg'] = msg_text

    if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await context.bot.send_message(update.effective_chat.id, "📢 *AVISO OFICIAL:*\n\n" + msg_text, parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "AVISO", update.effective_user.full_name, "Grupo")
    else:
        buttons = []
        for gid, title in known_groups.items():
            buttons.append([InlineKeyboardButton(title, callback_data=f"bc_send:{gid}")])
        if not buttons: return await update.message.reply_text("❌ Não conheço nenhum grupo para enviar o aviso.")
        await update.message.reply_text("🎯 *Selecione o grupo para enviar o aviso:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def callback_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith("bc_send:"):
        gid = int(q.data.split(":")[1])
        msg_text = context.user_data.get('broadcast_msg')
        if not msg_text: return await q.answer("❌ Mensagem perdida.", show_alert=True)
        try:
            await context.bot.send_message(gid, "📢 *AVISO OFICIAL:*\n\n" + msg_text, parse_mode=ParseMode.MARKDOWN)
            await q.answer("✅ Enviado!")
            await q.message.edit_text(f"✅ Aviso enviado para: *{known_groups.get(gid, gid)}*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e: await q.answer(f"❌ Erro: {str(e)}", show_alert=True)

# ══════════════════════════════════════════════
#  ✅  CONFIÁVEIS (Apenas Admins do Grupo)
# ══════════════════════════════════════════════
async def cmd_trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores do grupo.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    trusted_users[cid][tid] = tname
    save_data()
    await update.message.reply_text(f"✅ *{tname}* agora é confiável neste grupo.", parse_mode=ParseMode.MARKDOWN)

async def cmd_untrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores do grupo.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    if tid in trusted_users.get(cid, {}):
        del trusted_users[cid][tid]
        save_data()
        await update.message.reply_text(f"🗑️ *{tname}* removido dos confiáveis.", parse_mode=ParseMode.MARKDOWN)

async def cmd_listrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores do grupo.")
    cid = update.effective_chat.id
    users = trusted_users.get(cid, {})
    if not users: return await update.message.reply_text("✅ Nenhum confiável neste grupo.")
    lines = ["✅ *Confiáveis neste grupo:*\n"]
    for uid, name in users.items(): lines.append(f"• `{uid}` — *{name}*")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  🛡️  MODERAÇÃO (Apenas Admins do Grupo)
# ══════════════════════════════════════════════
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_owner(tid): return await update.message.reply_text("❌ Não é possível banir um dono.")
    reason = " ".join(context.args) if context.args else "Sem motivo"
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, tid)
        await update.message.reply_text(f"🔨 *{tname}* banido.\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
        ban_registry[update.effective_chat.id].append({"uid": tid, "name": tname, "reason": reason, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        save_data()
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ /unban <id>")
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, tid, only_if_banned=True)
        await update.message.reply_text(f"✅ *{tname}* desbanido.", parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_owner(tid): return await update.message.reply_text("❌ Não é possível remover um dono.")
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, tid)
        await asyncio.sleep(0.5)
        await context.bot.unban_chat_member(update.effective_chat.id, tid)
        await update.message.reply_text(f"👢 *{tname}* removido.", parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    minutes = MUTE_MINUTES
    try:
        if context.args: minutes = int(context.args[-1])
    except ValueError: pass
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, tid, ChatPermissions(can_send_messages=False), until_date=datetime.now() + timedelta(minutes=minutes))
        await update.message.reply_text(f"🔇 *{tname}* silenciado por *{minutes} min*.", parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, tid, OPEN_PERMISSIONS)
        await update.message.reply_text(f"🔊 *{tname}* pode falar novamente.", parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    cid = update.effective_chat.id
    warnings[cid][tid] += 1
    count = warnings[cid][tid]
    save_data()
    if count >= WARN_LIMIT:
        await context.bot.ban_chat_member(cid, tid)
        await update.message.reply_text(f"🔨 *{tname}* banido (limite de avisos: {count}/{WARN_LIMIT}).", parse_mode=ParseMode.MARKDOWN)
        warnings[cid][tid] = 0; save_data()
    else:
        await update.message.reply_text(f"⚠️ *{tname}* avisado ({count}/{WARN_LIMIT}).", parse_mode=ParseMode.MARKDOWN)

async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    cid = update.effective_chat.id
    if warnings[cid][tid] > 0:
        warnings[cid][tid] -= 1; save_data()
        await update.message.reply_text(f"✅ Aviso removido de *{tname}*. Agora: {warnings[cid][tid]}/{WARN_LIMIT}", parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text(f"ℹ️ *{tname}* não tem avisos.", parse_mode=ParseMode.MARKDOWN)

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    warnings[update.effective_chat.id][tid] = 0; save_data()
    await update.message.reply_text(f"🧹 Avisos de *{tname}* zerados.", parse_mode=ParseMode.MARKDOWN)

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    try: amount = min(int(context.args[0]), 100) if context.args else 10
    except ValueError: return await update.message.reply_text("ℹ️ /purge <N>")
    base = update.message.message_id
    deleted = 0
    for i in range(base, base - amount - 1, -1):
        try: await context.bot.delete_message(update.effective_chat.id, i); deleted += 1
        except TelegramError: pass
    msg = await context.bot.send_message(update.effective_chat.id, f"🗑️ *{deleted}* mensagens deletadas.", parse_mode=ParseMode.MARKDOWN)
    await asyncio.sleep(4); await msg.delete()

# ══════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÃO (Apenas Admins do Grupo)
# ══════════════════════════════════════════════
async def cmd_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on": anti_link_groups.add(cid); msg = "🔗 Anti-link *ATIVADO*."
    else: anti_link_groups.discard(cid); msg = "🔗 Anti-link *DESATIVADO*."
    save_data(); await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_antisticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on": anti_sticker_groups.add(cid); msg = "🚫 Anti-sticker *ATIVADO*."
    else: anti_sticker_groups.discard(cid); msg = "🚫 Anti-sticker *DESATIVADO*."
    save_data(); await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_antigif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on": anti_gif_groups.add(cid); msg = "🚫 Anti-GIF *ATIVADO*."
    else: anti_gif_groups.discard(cid); msg = "🚫 Anti-GIF *DESATIVADO*."
    save_data(); await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    await context.bot.set_chat_permissions(update.effective_chat.id, LOCKED_PERMISSIONS)
    await update.message.reply_text("🔒 *Grupo travado.*", parse_mode=ParseMode.MARKDOWN)

async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    await context.bot.set_chat_permissions(update.effective_chat.id, OPEN_PERMISSIONS)
    await update.message.reply_text("🔓 *Grupo destravado.*", parse_mode=ParseMode.MARKDOWN)

async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    if not context.args: return await update.message.reply_text("ℹ️ /slowmode <s>|off")
    arg = context.args[0].lower()
    if arg == "off": await context.bot.set_chat_slow_mode_delay(cid, 0); slowmode_groups.pop(cid, None); msg = "⏳ Modo lento *DESATIVADO*."
    else:
        try: sec = int(arg); await context.bot.set_chat_slow_mode_delay(cid, sec); slowmode_groups[cid] = sec; msg = f"⏳ Modo lento: *{sec}s*."
        except: return await update.message.reply_text("❌ Valor inválido.")
    save_data(); await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("ℹ️ /setrules <texto>")
    group_rules[update.effective_chat.id] = text; save_data()
    await update.message.reply_text("✅ Regras definidas.")

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas administradores.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("ℹ️ /setwelcome <texto>")
    welcome_messages[update.effective_chat.id] = text; save_data()
    await update.message.reply_text("✅ Boas-vindas definida.")

# ══════════════════════════════════════════════
#  📊  INFO / HELP / START
# ══════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🛡️ *BOT DE SEGURANÇA AVANÇADA — Online!*\n\nOlá, *{update.effective_user.first_name}*!\nUse /help para ver os comandos.", parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_adm = await has_mod_power(update, context)
    is_b_adm = is_bot_admin(update.effective_user.id)
    text = "🛡️ *BOT DE SEGURANÇA AVANÇADA — Comandos*\n\n"
    text += "*📊 Info:*\n/id /groupinfo /userinfo /rules\n\n"
    if is_adm:
        text += "*🛡️ Moderação:*\n/ban /unban /kick /mute /unmute /warn /warns /clearwarns /purge /banlist /logs\n\n"
        text += "*⚙️ Configuração:*\n/antilink /antisticker /antigif /lock /unlock /slowmode /setrules /setwelcome /trust /untrust /listtrust\n\n"
    if is_b_adm:
        text += "*👑 Admin Bot:*\n/aviso /listadmins /addadmin /removeadmin /owner"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text(f"🆔 *Chat:* `{msg.chat_id}`\n👤 *Você:* `{msg.from_user.id}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_groupinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try: count = await context.bot.get_chat_member_count(cid)
    except: count = "?"
    await update.message.reply_text(f"📊 *Estatísticas do Grupo:*\n\n👥 Membros: *{count}*\n🆔 ID: `{cid}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid, tname = get_target(update)
    if not tid: tid, tname = update.effective_user.id, update.effective_user.full_name
    await update.message.reply_text(f"👤 *Usuário:* {tname}\n🆔 ID: `{tid}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = group_rules.get(update.effective_chat.id, "Nenhuma regra definida.")
    await update.message.reply_text(f"📋 *Regras:*\n\n{rules}", parse_mode=ParseMode.MARKDOWN)

async def cmd_owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    kb = [[InlineKeyboardButton("📊 Stats Globais", callback_data="owner:stats")]]
    await update.message.reply_text("👑 *Painel do Dono*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  🚀  MAIN & MENU REGISTRATION
# ══════════════════════════════════════════════
async def setup_commands(app: Application):
    # Comandos padrão (para todos)
    default_commands = [
        BotCommand("start", "Inicia o bot"),
        BotCommand("help", "Lista de comandos"),
        BotCommand("id", "Mostra seu ID e do chat"),
        BotCommand("rules", "Mostra as regras do grupo"),
        BotCommand("userinfo", "Informações do usuário"),
        BotCommand("groupinfo", "Informações do grupo"),
    ]
    
    # Comandos para Admins de Grupo
    admin_commands = default_commands + [
        BotCommand("ban", "Bane um usuário"),
        BotCommand("unban", "Desbane um usuário"),
        BotCommand("kick", "Remove um usuário"),
        BotCommand("mute", "Silencia um usuário"),
        BotCommand("unmute", "Remove silêncio"),
        BotCommand("warn", "Dá um aviso"),
        BotCommand("purge", "Apaga mensagens"),
        BotCommand("antilink", "Configura anti-link"),
        BotCommand("lock", "Trava o grupo"),
        BotCommand("unlock", "Destrava o grupo"),
        BotCommand("setrules", "Define as regras"),
        BotCommand("setwelcome", "Define boas-vindas"),
    ]

    await app.bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    # O Telegram aplicará admin_commands para qualquer admin em qualquer chat
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChatAdmins())

def main():
    load_data()
    app = Application.builder().token(TOKEN).build()

    # Registro de Handlers
    handlers = [
        ("start", cmd_start), ("help", cmd_help), ("id", cmd_id),
        ("rules", cmd_rules), ("userinfo", cmd_userinfo), ("groupinfo", cmd_groupinfo),
        ("ban", cmd_ban), ("unban", cmd_unban), ("kick", cmd_kick),
        ("mute", cmd_mute), ("unmute", cmd_unmute), ("warn", cmd_warn),
        ("unwarn", cmd_unwarn), ("warns", cmd_warn), ("clearwarns", cmd_clearwarns),
        ("purge", cmd_purge), ("antilink", cmd_antilink), ("antisticker", cmd_antisticker),
        ("antigif", cmd_antigif), ("lock", cmd_lock), ("unlock", cmd_unlock),
        ("slowmode", cmd_slowmode), ("setrules", cmd_setrules), ("setwelcome", cmd_setwelcome),
        ("trust", cmd_trust), ("untrust", cmd_untrust), ("listtrust", cmd_listrust),
        ("addadmin", cmd_addadmin), ("removeadmin", cmd_removeadmin),
        ("listadmins", cmd_listadmins), ("aviso", cmd_aviso), ("broadcast", cmd_aviso),
        ("owner", cmd_owner_menu)
    ]
    
    for cmd, func in handlers:
        app.add_handler(CommandHandler(cmd, func))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_aviso, pattern=r"^bc_send:"))
    
    # Configurar menu de comandos na inicialização
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_commands(app))

    logger.info("🛡️ BOT INICIADO!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
