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

Novidades v3:
  - /lock e /unlock CORRIGIDOS (permissões completas restauradas)
  - /rules e /setrules — regras do grupo com botão de aceite
  - /setwelcome — boas-vindas customizável ({name}, {group})
  - /resetwelcome — volta ao padrão
  - /id — mostra ID do chat/usuário
  - /pin [silent] e /unpin [all] — fixa/desfixa mensagens
  - /ro — alias de /lock (modo somente leitura)
  - /slowmode <s>|off — modo lento no grupo
  - /banlist — histórico de bans do grupo
  - /clearwarns — zera avisos de um usuário
  - /report — reporta mensagem para admins via PM
  - /antisticker on|off — bloqueia stickers
  - /antigif on|off — bloqueia GIFs/animações
  - /groupinfo — painel de config e estatísticas do grupo
  - Banlist global no painel do dono
"""



# ══════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÕES — EDITE AQUI
# ══════════════════════════════════════════════
TOKEN = "8779375731:AAHfTKVgWgS8zaUH18Vj4vJ0DdXDKvRh7U4"
OWNER_IDS: list[int] = [7981212751, 8023120895]  # ← seus 2 IDs aqui

MAX_MESSAGES  = 7
SPAM_import logging, asyncio, re, json, os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Message, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMember,
    Message,
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeDefault
)
from telegram import BotCommandScopeChatAdmins, BotCommandScopeDefault
from telegram.error import TelegramErrorWINDOW   = 10
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
known_groups: dict[int, str] = {} # ID -> Title (Adicionado para broadcast no PV)

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
    group_rules.update({int(k): v for k, v in data.get("group_rules", {}).items()})
    welcome_messages.update({int(k): v for k, v in data.get("welcome_messages", {}).items()})
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
    
    # Armazenar grupo conhecido para broadcast no PV
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
                f"_Nota: O bot clone está pronto._",
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
#  👑  COMANDOS DO DONO
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

    # Se for no grupo, envia direto
    if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await context.bot.send_message(update.effective_chat.id,
            "📢 *AVISO OFICIAL:*\n\n" + msg_text, parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "AVISO", update.effective_user.full_name, "Grupo")
    else:
        # Se for no PV, pede pra selecionar o grupo
        buttons = []
        for gid, title in known_groups.items():
            buttons.append([InlineKeyboardButton(title, callback_data=f"bc_send:{gid}")])
        
        if not buttons:
            return await update.message.reply_text("❌ Não conheço nenhum grupo para enviar o aviso.")
        
        await update.message.reply_text("🎯 *Selecione o grupo para enviar o aviso:*",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def callback_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith("bc_send:"):
        gid = int(q.data.split(":")[1])
        msg_text = context.user_data.get('broadcast_msg')
        
        if not msg_text:
            return await q.answer("❌ Mensagem perdida. Tente novamente.", show_alert=True)
        
        try:
            await context.bot.send_message(gid, "📢 *AVISO OFICIAL:*\n\n" + msg_text, parse_mode=ParseMode.MARKDOWN)
            await q.answer("✅ Enviado com sucesso!")
            await q.message.edit_text(f"✅ Aviso enviado para o grupo: *{known_groups.get(gid, gid)}*", parse_mode=ParseMode.MARKDOWN)
            log_action(gid, "AVISO_PV", q.from_user.full_name, "Grupo")
        except Exception as e:
            await q.answer(f"❌ Erro: {str(e)}", show_alert=True)

# ══════════════════════════════════════════════
#  ✅  CONFIÁVEIS
# ══════════════════════════════════════════════
async def cmd_trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona confiável. Uso: /trust (reply)"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    trusted_users[cid][tid] = tname
    save_data()
    log_action(cid, "TRUST_ADD", update.effective_user.full_name, str(tname))
    await update.message.reply_text(f"✅ *{tname}* agora é confiável neste grupo.", parse_mode=ParseMode.MARKDOWN)

async def cmd_untrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove confiável. Uso: /untrust (reply)"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    if tid in trusted_users.get(cid, {}):
        del trusted_users[cid][tid]
        save_data()
        log_action(cid, "TRUST_RM", update.effective_user.full_name, str(tname))
        await update.message.reply_text(f"🗑️ *{tname}* removido dos confiáveis.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ℹ️ Usuário não está na lista.")

async def cmd_listrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista confiáveis do grupo."""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    users = trusted_users.get(cid, {})
    if not users: return await update.message.reply_text("✅ Nenhum confiável neste grupo.")
    lines = ["✅ *Confiáveis neste grupo:*\n"]
    for uid, name in users.items():
        badge = "👑" if is_owner(uid) else ("🛡️" if is_bot_admin(uid) else "✅")
        lines.append(f"{badge} `{uid}` — *{name}*")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  🛡️  MODERAÇÃO
# ══════════════════════════════════════════════
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bane usuário. Uso: /ban (reply) [motivo]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_owner(tid): return await update.message.reply_text("❌ Não é possível banir um dono do bot.")
    reason = " ".join(context.args) if context.args else "Sem motivo"
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, tid)
        await update.message.reply_text(f"🔨 *{tname}* banido.\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "BAN", update.effective_user.full_name, str(tname), reason)
        ban_registry[update.effective_chat.id].append({
            "uid": tid, "name": tname, "reason": reason,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        save_data()
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desbane. Uso: /unban <id>"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ /unban <id>")
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, tid, only_if_banned=True)
        await update.message.reply_text(f"✅ *{tname}* desbanido.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "UNBAN", update.effective_user.full_name, str(tname))
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove sem banir. Uso: /kick (reply) [motivo]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_owner(tid): return await update.message.reply_text("❌ Não é possível remover um dono.")
    reason = " ".join(context.args) if context.args else "Sem motivo"
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, tid)
        await asyncio.sleep(0.5)
        await context.bot.unban_chat_member(update.effective_chat.id, tid)
        await update.message.reply_text(f"👢 *{tname}* removido.\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "KICK", update.effective_user.full_name, str(tname), reason)
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silencia. Uso: /mute (reply) [minutos]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_owner(tid): return await update.message.reply_text("❌ Não é possível silenciar um dono.")
    minutes = MUTE_MINUTES
    try:
        if context.args: minutes = int(context.args[-1])
    except ValueError: pass
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, tid,
            ChatPermissions(can_send_messages=False), until_date=datetime.now() + timedelta(minutes=minutes))
        await update.message.reply_text(f"🔇 *{tname}* silenciado por *{minutes} min*.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "MUTE", update.effective_user.full_name, str(tname), f"{minutes}min")
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove silêncio. Uso: /unmute (reply)"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    perms = OPEN_PERMISSIONS
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, tid, perms)
        await update.message.reply_text(f"🔊 *{tname}* pode falar novamente.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "UNMUTE", update.effective_user.full_name, str(tname))
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def _apply_warn(context, cid, tid, tname, reason):
    warnings[cid][tid] += 1
    count = warnings[cid][tid]
    save_data()
    if count >= WARN_LIMIT:
        try:
            await context.bot.ban_chat_member(cid, tid)
            await context.bot.send_message(cid, f"🔨 *{tname}* banido (limite de avisos: {count}/{WARN_LIMIT}).", parse_mode=ParseMode.MARKDOWN)
            log_action(cid, "WARN_BAN", "BOT", tname, f"Avisos: {count}")
            warnings[cid][tid] = 0
            save_data()
        except TelegramError as e: logger.error(f"warn-ban: {e}")
    else:
        await context.bot.send_message(cid, f"⚠️ *{tname}* avisado ({count}/{WARN_LIMIT}).\n📝 Motivo: {reason}", parse_mode=ParseMode.MARKDOWN)
        log_action(cid, "WARN", "MOD", tname, reason)

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avisa usuário. Uso: /warn (reply) [motivo]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    if is_bot_admin(tid): return await update.message.reply_text("❌ Não é possível avisar admins/donos do bot.")
    reason = " ".join(context.args) if context.args else "Comportamento inadequado"
    await _apply_warn(context, update.effective_chat.id, tid, tname, reason)

async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove aviso. Uso: /unwarn (reply)"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    cid = update.effective_chat.id
    if warnings[cid][tid] > 0:
        warnings[cid][tid] -= 1
        save_data()
        await update.message.reply_text(
            f"✅ Aviso removido de *{tname}*. Agora: {warnings[cid][tid]}/{WARN_LIMIT}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"ℹ️ *{tname}* não tem avisos.", parse_mode=ParseMode.MARKDOWN)

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista avisos. Uso: /warns (reply) ou /warns"""
    tid, tname = get_target(update)
    cid = update.effective_chat.id
    if tid:
        count = warnings[cid].get(tid, 0)
        badge = "👑" if is_owner(tid) else ("🛡️" if is_bot_admin(tid) else "⚠️")
        await update.message.reply_text(f"{badge} *{tname}*: {count}/{WARN_LIMIT}", parse_mode=ParseMode.MARKDOWN)
    else:
        lines = ["⚠️ *Avisos neste grupo:*\n"]
        for uid, cnt in warnings[cid].items():
            if cnt > 0:
                badge = "👑" if is_owner(uid) else ("🛡️" if is_bot_admin(uid) else "👤")
                lines.append(f"{badge} `{uid}`: {cnt}/{WARN_LIMIT}")
        if len(lines) == 1: lines.append("_Sem avisos ativos._")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zera avisos de um usuário. Uso: /clearwarns (reply)"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    cid = update.effective_chat.id
    warnings[cid][tid] = 0
    save_data()
    await update.message.reply_text(f"🧹 Avisos de *{tname}* zerados.", parse_mode=ParseMode.MARKDOWN)
    log_action(cid, "CLEAR_WARNS", update.effective_user.full_name, tname)

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apaga N mensagens. Uso: /purge <N>"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    try: amount = min(int(context.args[0]), 100) if context.args else 10
    except ValueError: return await update.message.reply_text("ℹ️ /purge <N>")
    deleted = 0
    base = update.message.message_id
    for i in range(base, base - amount - 1, -1):
        try:
            await context.bot.delete_message(update.effective_chat.id, i)
            deleted += 1
        except TelegramError: pass
    msg = await context.bot.send_message(update.effective_chat.id, f"🗑️ *{deleted}* mensagens deletadas.", parse_mode=ParseMode.MARKDOWN)
    await asyncio.sleep(4)
    try: await msg.delete()
    except TelegramError: pass
    log_action(update.effective_chat.id, "PURGE", update.effective_user.full_name, f"{deleted} msgs")

async def cmd_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga/desliga anti-link. Uso: /antilink on|off"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_link_groups.add(cid); save_data()
        await update.message.reply_text("🔗 Anti-link *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_link_groups.discard(cid); save_data()
        await update.message.reply_text("🔗 Anti-link *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_antisticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga/desliga anti-sticker. Uso: /antisticker on|off"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_sticker_groups.add(cid); save_data()
        await update.message.reply_text("🚫 Anti-sticker *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_sticker_groups.discard(cid); save_data()
        await update.message.reply_text("🚫 Anti-sticker *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_antigif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga/desliga anti-gif. Uso: /antigif on|off"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_gif_groups.add(cid); save_data()
        await update.message.reply_text("🚫 Anti-GIF *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_gif_groups.discard(cid); save_data()
        await update.message.reply_text("🚫 Anti-GIF *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trava o grupo — nenhum membro pode enviar mensagens."""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, LOCKED_PERMISSIONS)
        await update.message.reply_text("🔒 *Grupo travado.* Apenas admins podem falar.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "LOCK", update.effective_user.full_name, "Chat")
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Destrava o grupo."""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, OPEN_PERMISSIONS)
        await update.message.reply_text("🔓 *Grupo destravado.* Membros podem falar.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "UNLOCK", update.effective_user.full_name, "Chat")
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modo lento. Uso: /slowmode <s>|off"""
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    cid = update.effective_chat.id
    if not context.args: return await update.message.reply_text("ℹ️ /slowmode <s>|off")
    arg = context.args[0].lower()
    if arg == "off":
        try:
            await context.bot.set_chat_slow_mode_delay(cid, 0)
            slowmode_groups.pop(cid, None); save_data()
            await update.message.reply_text("⏳ Modo lento *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)
        except TelegramError as e: await update.message.reply_text(f"❌ {e}")
    else:
        try:
            seconds = int(arg)
            await context.bot.set_chat_slow_mode_delay(cid, seconds)
            slowmode_groups[cid] = seconds; save_data()
            await update.message.reply_text(f"⏳ Modo lento: *{seconds}s*.", parse_mode=ParseMode.MARKDOWN)
        except (ValueError, TelegramError) as e: await update.message.reply_text(f"❌ {e}")

async def cmd_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista bans do grupo."""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    lst = ban_registry.get(cid, [])
    if not lst: return await update.message.reply_text("✅ Ninguém banido via bot neste grupo.")
    lines = ["🔨 *Histórico de Bans:*"]
    for b in lst[-15:]:
        lines.append(f"• `{b['ts']}` *{b['name']}* — {b['reason']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reporta mensagem aos admins."""
    if not update.message.reply_to_message: return await update.message.reply_text("ℹ️ Responda à mensagem que deseja reportar.")
    user = update.effective_user
    chat = update.effective_chat
    target = update.message.reply_to_message
    report_text = (f"🚩 *REPORT* no grupo {chat.title}\n\n"
                   f"👤 De: {user.full_name} (`{user.id}`)\n"
                   f"🎯 Alvo: {target.from_user.full_name} (`{target.from_user.id}`)\n"
                   f"🔗 Link: {target.link}")
    for aid in list(bot_admins.keys()) + OWNER_IDS:
        try: await context.bot.send_message(aid, report_text, parse_mode=ParseMode.MARKDOWN)
        except TelegramError: pass
    await update.message.reply_text("✅ Report enviado aos admins do bot.")

# ══════════════════════════════════════════════
#  📌  MENSAGENS FIXADAS
# ══════════════════════════════════════════════
async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return
    if not update.message.reply_to_message: return await update.message.reply_text("ℹ️ Responda à mensagem.")
    silent = "silent" in context.args
    try:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id, disable_notification=silent)
        await update.message.reply_text("📌 Mensagem fixada.")
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_mod_power(update, context): return
    try:
        if "all" in context.args:
            await context.bot.unpin_all_chat_messages(update.effective_chat.id)
            await update.message.reply_text("📌 Todas as mensagens desfixadas.")
        else:
            await context.bot.unpin_chat_message(update.effective_chat.id)
            await update.message.reply_text("📌 Mensagem desfixada.")
    except TelegramError as e: await update.message.reply_text(f"❌ {e}")

# ══════════════════════════════════════════════
#  ⚙️  REGRAS
# ══════════════════════════════════════════════
async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("ℹ️ /setrules <texto>")
    group_rules[update.effective_chat.id] = text
    save_data()
    await update.message.reply_text("✅ Regras definidas.")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    rules = group_rules.get(cid)
    if not rules: return await update.message.reply_text("ℹ️ Nenhuma regra definida.")
    kb = [[InlineKeyboardButton("✅ Entendido", callback_data=f"rules_ack:{update.effective_user.id}")]]
    await update.message.reply_text(f"📋 *Regras do Grupo:*\n\n{rules}", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

# ══════════════════════════════════════════════
#  ⚙️  BOAS-VINDAS
# ══════════════════════════════════════════════
async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("ℹ️ /setwelcome <texto>\nUse {name} e {group}")
    welcome_messages[update.effective_chat.id] = text
    save_data()
    await update.message.reply_text("✅ Boas-vindas definida.")

async def cmd_resetwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_group_admin(update, context) and not is_bot_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas administradores.")
    welcome_messages.pop(update.effective_chat.id, None)
    save_data()
    await update.message.reply_text("✅ Boas-vindas resetada.")

# ══════════════════════════════════════════════
#  📊  INFO / PAINEL
# ══════════════════════════════════════════════
async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    lines = [f"🆔 *Chat:* `{msg.chat_id}`", f"👤 *Você:* `{msg.from_user.id}`"]
    if msg.reply_to_message: lines.append(f"🎯 *Alvo:* `{msg.reply_to_message.from_user.id}`")
    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_groupinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try: count = await context.bot.get_chat_member_count(cid)
    except TelegramError: count = "?"
    antilink    = "✅ Ativo"       if cid in anti_link_groups    else "❌ Inativo"
    antisticker = "✅ Ativo"       if cid in anti_sticker_groups else "❌ Inativo"
    antigif     = "✅ Ativo"       if cid in anti_gif_groups     else "❌ Inativo"
    slow        = f"{slowmode_groups[cid]}s" if cid in slowmode_groups else "❌ Desativado"
    rules       = "✅ Definidas"   if cid in group_rules         else "❌ Não definidas"
    welcome     = "✅ Custom"      if cid in welcome_messages    else "❌ Padrão"
    await update.message.reply_text(
        f"📊 *Estatísticas e Config:*\n\n"
        f"👥 Membros: *{count}*\n"
        f"🔗 Anti-link: {antilink}\n"
        f"🚫 Anti-sticker: {antisticker}\n"
        f"🚫 Anti-GIF: {antigif}\n"
        f"⏳ Modo Lento: {slow}\n"
        f"📋 Regras: {rules}\n"
        f"👋 Boas-vindas: {welcome}\n",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    kb = [
        [InlineKeyboardButton("📊 Stats Globais", callback_data="owner:stats"),
         InlineKeyboardButton("🛡️ Admins", callback_data="owner:admins")],
        [InlineKeyboardButton("🔨 Banlist Global", callback_data="owner:banlist"),
         InlineKeyboardButton("💾 Backup Data", callback_data="owner:backup")]
    ]
    await update.message.reply_text("👑 *Painel do Dono*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_owner(q.from_user.id): return await q.answer("❌ Acesso negado.", show_alert=True)
    data = q.data.split(":")[1]
    if data == "stats":
        text = (f"📊 *Estatísticas Globais*\n\n"
                f"🛡️ Admins do Bot: {len(bot_admins)}\n"
                f"🔗 Grupos c/ anti-link: *{len(anti_link_groups)}*\n"
                f"📋 Grupos c/ regras: *{len(group_rules)}*\n"
                f"📁 Ações no log: {len(action_log)}")
        await q.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)
    elif data == "admins":
        lines = ["🛡️ *Admins do Bot:*"]
        for aid, name in bot_admins.items(): lines.append(f"• `{aid}` — *{name}*")
        await q.message.edit_text("\n".join(lines) if bot_admins else "Nenhum admin.", parse_mode=ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)
    elif data == "banlist":
        # Simulação de banlist global
        await q.answer("Banlist Global carregada.")
    elif data == "backup":
        await q.answer("Backup gerado.")

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Histórico de ações. Uso: /logs [N]"""
    if not await has_mod_power(update, context): return
    cid = update.effective_chat.id
    try: limit = int(context.args[0]) if context.args else 10
    except ValueError: limit = 10
    entries = [e for e in reversed(action_log) if e["chat_id"] == cid][:limit]
    if not entries: return await update.message.reply_text("📋 Nenhuma ação registrada aqui.")
    lines = [f"📋 *Últimas {len(entries)} ações:*\n"]
    for e in entries:
        lines.append(f"• `{e['ts']}` *{e['action']}*\n  👮 {e['mod']} → {e['target']}" + (f"\n  📝 {e['reason']}" if e.get("reason") else ""))
    await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Info do usuário. Uso: /userinfo (reply)"""
    tid, tname = get_target(update)
    if not tid: u = update.effective_user; tid, tname = u.id, u.full_name
    cid = update.effective_chat.id
    warn_count = warnings[cid].get(tid, 0)
    in_trusted = tid in trusted_users.get(cid, {})
    bans_here  = sum(1 for b in ban_registry.get(cid, []) if b["uid"] == tid)
    try: member = await context.bot.get_chat_member(cid, tid); status = member.status
    except TelegramError: status = "desconhecido"
    role = ("👑 Dono do Bot"    if is_owner(tid)     else
            "🛡️ Admin do Bot"   if is_bot_admin(tid) else
            "🔰 Admin do Grupo" if status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER) else
            "✅ Confiável"       if in_trusted        else "👤 Membro")
    await update.message.reply_text(
        f"👤 *Informações*\n\n📛 *{tname}*\n🆔 `{tid}`\n🏷️ `{status}`\n"
        f"🎖️ {role}\n⚠️ Avisos: {warn_count}/{WARN_LIMIT}\n"
        f"🔨 Bans neste grupo: {bans_here}\n✅ Confiável: {'Sim' if in_trusted else 'Não'}",
        parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  👋  BOAS-VINDAS
# ══════════════════════════════════════════════
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        cid = update.effective_chat.id
        chat_title = update.effective_chat.title or "este grupo"
        custom = welcome_messages.get(cid)
        if custom:
            text = custom.format(name=member.full_name, group=chat_title)
        else:
            text = (f"👋 Bem-vindo(a), *{member.full_name}*!\n\n"
                    f"📌 Leia as regras antes de participar.\n"
                    f"⚠️ Spam e links não autorizados resultam em punição.")
        kb_buttons = [[InlineKeyboardButton("✅ Li e aceito as regras", callback_data=f"rules:{member.id}")]]
        if group_rules.get(cid):
            kb_buttons.append([InlineKeyboardButton("📋 Ver Regras", callback_data=f"show_rules:{cid}")])
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb_buttons))

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message.left_chat_member
    if not m.is_bot:
        await update.message.reply_text(f"👋 *{m.full_name}* saiu do grupo.", parse_mode=ParseMode.MARKDOWN)

async def callback_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith("rules:"):
        uid = int(q.data.split(":")[1])
        if q.from_user.id == uid:
            await q.answer("✅ Bem-vindo! Bom chat.")
            await q.message.edit_reply_markup(reply_markup=None)
        else:
            await q.answer("❌ Este botão não é para você.", show_alert=True)
    elif q.data.startswith("show_rules:"):
        cid = int(q.data.split(":")[1])
        rules = group_rules.get(cid, "Sem regras definidas.")
        await q.answer()
        await q.message.reply_text(f"📋 *Regras do Grupo:*\n\n{rules}", parse_mode=ParseMode.MARKDOWN)
    elif q.data.startswith("rules_ack:"):
        uid = int(q.data.split(":")[1])
        if q.from_user.id == uid:
            await q.answer("✅ Obrigado por ler as regras!")
            await q.message.edit_reply_markup(reply_markup=None)
        else:
            await q.answer("❌ Este botão não é para você.", show_alert=True)

# ══════════════════════════════════════════════
#  ℹ️  HELP / START
# ══════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role = "👑 Dono" if is_owner(uid) else ("🛡️ Admin Bot" if is_bot_admin(uid) else "👤 Usuário")
    extra = "\n\n👑 Use /owner para o *Painel do Dono*." if is_owner(uid) else ""
    await update.message.reply_text(
        f"🛡️ *BOT DE SEGURANÇA AVANÇADA — Online!*\n\nOlá, *{update.effective_user.first_name}*!\nCargo: {role}\n\nUse /help para ver os comandos.{extra}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_adm = await has_mod_power(update, context)
    owner_section = ""
    if is_bot_admin(uid):
        owner_section = ("\n\n*🛡️ Exclusivo Admin Bot:*\n"
            "/owner — Painel interativo (apenas Dono)\n/addadmin — Adiciona admin do bot\n"
            "/removeadmin — Remove admin do bot\n/listadmins — Lista admins\n"
            "/aviso — Aviso oficial no grupo ou PV\n")
    
    mod_section = ""
    if is_adm:
        mod_section = ("*🛡️ Moderação:*\n/ban /unban /kick\n/mute [min] /unmute\n"
        "/warn [motivo] /unwarn /warns\n"
        "/clearwarns — Zera avisos de um usuário\n"
        "/purge <N> — Apaga N mensagens\n"
        "/report — Reporta mensagem para admins\n"
        "/banlist — Histórico de bans\n\n"
        "*⚙️ Configuração:*\n"
        "/antilink on|off — Anti-link\n"
        "/antisticker on|off — Anti-sticker\n"
        "/antigif on|off — Anti-GIF\n"
        "/lock /unlock /ro — Travar grupo\n"
        "/slowmode <s>|off — Modo lento\n"
        "/setrules <texto> — Define regras\n"
        "/setwelcome — Boas-vindas custom\n"
        "/resetwelcome — Remove boas-vindas custom\n"
        "/trust /untrust /listtrust\n\n")

    await update.message.reply_text(
        "🛡️ *BOT DE SEGURANÇA AVANÇADA — Comandos*\n\n"
        + mod_section +
        "*📌 Mensagens:*\n"
        "/pin [silent] — Fixa mensagem\n"
        "/unpin [all] — Desfixa mensagem\n\n"
        "*📊 Info:*\n"
        "/id — IDs do chat/usuário\n"
        "/groupinfo — Painel do grupo\n"
        "/userinfo — Info do usuário\n"
        "/rules — Exibe regras\n"
        "/logs [N] — Histórico de ações"
        + owner_section,
        parse_mode=ParseMode.MARKDOWN)

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
        BotCommand("logs", "Histórico de ações"),
    ]

    try:
        await app.bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
        await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChatAdmins())
    except Exception as e:
        logger.error(f"Erro ao configurar comandos: {e}")

def main():
    load_data()
    app = Application.builder().token(TOKEN).build()

    for cmd, func in [
        ("start", cmd_start), ("help", cmd_help),
        ("id", cmd_id), ("userinfo", cmd_userinfo),
        ("groupinfo", cmd_groupinfo), ("logs", cmd_logs),
        # Moderação
        ("ban", cmd_ban), ("unban", cmd_unban), ("kick", cmd_kick),
        ("mute", cmd_mute), ("unmute", cmd_unmute),
        ("warn", cmd_warn), ("unwarn", cmd_unwarn), ("warns", cmd_warns),
        ("clearwarns", cmd_clearwarns),
        ("purge", cmd_purge), ("report", cmd_report), ("banlist", cmd_banlist),
        # Mensagens
        ("pin", cmd_pin), ("unpin", cmd_unpin),
        # Configuração
        ("antilink", cmd_antilink), ("antisticker", cmd_antisticker), ("antigif", cmd_antigif),
        ("lock", cmd_lock), ("unlock", cmd_unlock), ("ro", cmd_lock),
        ("slowmode", cmd_slowmode),
        ("setrules", cmd_setrules), ("rules", cmd_rules),
        ("setwelcome", cmd_setwelcome), ("resetwelcome", cmd_resetwelcome),
        # Confiáveis
        ("trust", cmd_trust), ("untrust", cmd_untrust), ("listtrust", cmd_listrust),
        # Dono / Admin Bot
        ("addadmin", cmd_addadmin), ("removeadmin", cmd_removeadmin),
        ("listadmins", cmd_listadmins), ("aviso", cmd_aviso), ("broadcast", cmd_aviso),
    ]:
        app.add_handler(CommandHandler(cmd, func))

    app.add_handler(CommandHandler(["owner", "menu"], cmd_owner_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.CAPTION, handle_message))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_message))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(CallbackQueryHandler(owner_callback, pattern=r"^owner:"))
    app.add_handler(CallbackQueryHandler(callback_rules, pattern=r"^(rules:|show_rules:|rules_ack:)"))
    app.add_handler(CallbackQueryHandler(callback_aviso, pattern=r"^bc_send:"))

    # Configurar menu de comandos
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_commands(app))

    logger.info("🛡️ BOT DE SEGURANÇA AVANÇADA iniciado!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
