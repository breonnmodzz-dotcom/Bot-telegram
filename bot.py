"""
╔══════════════════════════════════════════════════════════════════╗
║         🛡️  TELEGRAM SECURITY BOT — GUARDIÃO v3                ║
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

import logging, asyncio, re, json, os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
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
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    global bot_admins, trusted_users, anti_link_groups, action_log
    global anti_sticker_groups, anti_gif_groups, group_rules, welcome_messages
    global ban_registry, slowmode_groups
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
    if is_trusted(chat.id, user.id): return

    # Anti-sticker
    if chat.id in anti_sticker_groups and msg.sticker:
        await safe_delete(msg)
        await context.bot.send_message(chat.id,
            f"🚫 Stickers não são permitidos aqui, *{user.full_name}*.",
            parse_mode=ParseMode.MARKDOWN)
        return

    # Anti-GIF
    if chat.id in anti_gif_groups and msg.animation:
        await safe_delete(msg)
        await context.bot.send_message(chat.id,
            f"🎞️ GIFs não são permitidos aqui, *{user.full_name}*.",
            parse_mode=ParseMode.MARKDOWN)
        return

    if await check_spam(update, context): return
    bad = find_banned_word(text)
    if bad:
        try:
            await safe_delete(msg)
            await context.bot.send_message(chat.id,
                f"🚫 Mensagem de *{user.full_name}* removida (palavra proibida: `{bad}`).",
                parse_mode=ParseMode.MARKDOWN)
            await _apply_warn(context, chat.id, user.id, user.full_name, f"Palavra proibida: {bad}")
        except TelegramError: pass
        return
    if chat.id in anti_link_groups and contains_link(text):
        try:
            await safe_delete(msg)
            await context.bot.send_message(chat.id,
                f"🔗 Link de *{user.full_name}* removido. Links não permitidos aqui.",
                parse_mode=ParseMode.MARKDOWN)
            await _apply_warn(context, chat.id, user.id, user.full_name, "Link proibido")
        except TelegramError: pass

# ══════════════════════════════════════════════
#  ⚠️  AVISOS
# ══════════════════════════════════════════════
async def _apply_warn(context, chat_id, user_id, user_name, reason):
    warnings[chat_id][user_id] += 1
    count = warnings[chat_id][user_id]
    save_data()
    if count >= WARN_LIMIT:
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.send_message(chat_id,
                f"🔨 *{user_name}* BANIDO após {WARN_LIMIT} avisos.\n📝 {reason}",
                parse_mode=ParseMode.MARKDOWN)
            log_action(chat_id, "AUTO_BAN", "BOT", user_name, f"{WARN_LIMIT} avisos")
            ban_registry[chat_id].append({
                "uid": user_id, "name": user_name,
                "reason": f"Auto-ban: {WARN_LIMIT} avisos — {reason}",
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            warnings[chat_id][user_id] = 0
            save_data()
        except TelegramError as e: logger.error(f"ban: {e}")
    else:
        await context.bot.send_message(chat_id,
            f"⚠️ *{user_name}* — Aviso *{count}/{WARN_LIMIT}*\n📝 {reason}",
            parse_mode=ParseMode.MARKDOWN)
        log_action(chat_id, "WARN", "BOT", user_name, reason)

# ══════════════════════════════════════════════
#  👑  MENU DO DONO
# ══════════════════════════════════════════════
def owner_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👮 Admins do Bot",   callback_data="owner:admins"),
         InlineKeyboardButton("✅ Confiáveis",       callback_data="owner:trusted")],
        [InlineKeyboardButton("📊 Estatísticas",    callback_data="owner:stats"),
         InlineKeyboardButton("📋 Logs Globais",    callback_data="owner:logs")],
        [InlineKeyboardButton("⚙️ Configurações",  callback_data="owner:config"),
         InlineKeyboardButton("🧹 Zerar Avisos",    callback_data="owner:clear")],
        [InlineKeyboardButton("🔨 Banlist Global",  callback_data="owner:banlist"),
         InlineKeyboardButton("❌ Fechar",           callback_data="owner:close")],
    ])

async def cmd_owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas donos do bot.")
    await update.message.reply_text(
        f"👑 *Painel do Dono — Guardião v2*\n\nOlá, *{update.effective_user.first_name}*!\nEscolha uma opção:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=owner_kb())

async def owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_owner(q.from_user.id):
        return await q.answer("❌ Apenas donos.", show_alert=True)
    await q.answer()
    d = q.data
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="owner:main")]])

    if d == "owner:main":
        await q.message.edit_text("👑 *Painel do Dono — Guardião v2*\n\nEscolha uma opção:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=owner_kb())

    elif d == "owner:admins":
        lines = ["👮 *Admins do Bot:*\n"]
        lines += [f"• `{aid}` — *{n}*" for aid, n in bot_admins.items()] if bot_admins else ["_Nenhum cadastrado._"]
        lines.append("\n_/addadmin | /removeadmin | /listadmins_")
        await q.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:trusted":
        lines = ["✅ *Usuários Confiáveis (todos grupos):*\n"]
        found = False
        for cid, users in trusted_users.items():
            if users:
                found = True
                lines.append(f"*Grupo* `{cid}`:")
                lines += [f"  • `{uid}` — {n}" for uid, n in users.items()]
        if not found: lines.append("_Nenhum cadastrado._")
        lines.append("\n_/trust | /untrust | /listtrust_")
        await q.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:stats":
        bans   = sum(1 for e in action_log if "BAN"  in e["action"])
        mutes  = sum(1 for e in action_log if "MUTE" in e["action"])
        warns  = sum(1 for e in action_log if e["action"] == "WARN")
        purges = sum(1 for e in action_log if e["action"] == "PURGE")
        total_warns = sum(sum(d.values()) for d in warnings.values())
        trusted_total = sum(len(v) for v in trusted_users.values())
        await q.message.edit_text(
            f"📊 *Estatísticas Globais*\n\n"
            f"🔨 Bans: *{bans}* | 🔇 Mutes: *{mutes}*\n"
            f"⚠️ Warns: *{warns}* | 🗑️ Purges: *{purges}*\n"
            f"📋 Total de ações: *{len(action_log)}*\n\n"
            f"👮 Admins do bot: *{len(bot_admins)}*\n"
            f"✅ Confiáveis: *{trusted_total}*\n"
            f"🔗 Grupos c/ anti-link: *{len(anti_link_groups)}*\n"
            f"⚠️ Avisos pendentes: *{total_warns}*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:logs":
        last = action_log[-15:][::-1]
        if not last:
            text = "📋 Nenhuma ação registrada."
        else:
            lines = ["📋 *Últimas 15 ações (global):*\n"]
            for e in last:
                lines.append(f"• `{e['ts']}` *{e['action']}*\n  👮 {e['mod']} → {e['target']}"
                              + (f"\n  📝 {e['reason']}" if e.get("reason") else ""))
            text = "\n\n".join(lines)
        await q.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:config":
        await q.message.edit_text(
            f"⚙️ *Configurações Atuais*\n\n"
            f"📨 Msgs/janela: `{MAX_MESSAGES}` | ⏱️ Janela: `{SPAM_WINDOW}s`\n"
            f"🔇 Mute auto: `{MUTE_MINUTES} min` | ⚠️ Warns p/ ban: `{WARN_LIMIT}`\n"
            f"🚫 Palavras proibidas: `{len(BANNED_WORDS)}`\n"
            f"🌐 Domínios liberados: `{', '.join(ALLOWED_DOMAINS)}`\n\n"
            f"_Edite as constantes no topo do bot.py para alterar._",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:clear":
        await q.message.edit_text("⚠️ *Tem certeza?* Isso zerará TODOS os avisos de TODOS os grupos.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Confirmar", callback_data="owner:clear_ok"),
                InlineKeyboardButton("❌ Cancelar",  callback_data="owner:main"),
            ]]))

    elif d == "owner:clear_ok":
        warnings.clear()
        save_data()
        log_action(0, "CLEAR_ALL_WARNS", q.from_user.full_name, "Global")
        await q.message.edit_text("✅ Todos os avisos foram zerados.", reply_markup=back)

    elif d == "owner:banlist":
        lines = ["🔨 *Banlist Global (últimos 20):*\n"]
        all_bans = []
        for cid, lst in ban_registry.items():
            for entry in lst:
                all_bans.append((cid, entry))
        all_bans.sort(key=lambda x: x[1].get("ts", ""), reverse=True)
        for cid, entry in all_bans[:20]:
            lines.append(f"• `{entry['uid']}` — *{entry['name']}*\n  Grupo: `{cid}` | {entry['ts']}\n  📝 {entry.get('reason','—')}")
        if len(lines) == 1: lines.append("_Nenhum ban registrado._")
        await q.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif d == "owner:close":
        await q.message.delete()

# ══════════════════════════════════════════════
#  👑  COMANDOS DO DONO
# ══════════════════════════════════════════════
async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona admin do bot. Uso: /addadmin (reply) ou /addadmin <id> [nome]"""
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas donos do bot.")
    tid, tname = get_target(update)
    if not tid:
        return await update.message.reply_text("ℹ️ Responda a uma mensagem ou: `/addadmin <id> [nome]`", parse_mode=ParseMode.MARKDOWN)
    if context.args and len(context.args) >= 2:
        tname = " ".join(context.args[1:])
    bot_admins[tid] = tname or str(tid)
    save_data()
    log_action(0, "ADD_BOT_ADMIN", update.effective_user.full_name, str(tname))
    await update.message.reply_text(
        f"✅ *{tname}* (`{tid}`) agora é *Admin do Bot*.\nPode usar todos os comandos de moderação.",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin do bot. Uso: /removeadmin (reply) ou /removeadmin <id>"""
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas donos do bot.")
    tid, _ = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda ou informe o ID.")
    if tid in bot_admins:
        removed = bot_admins.pop(tid)
        save_data()
        log_action(0, "RM_BOT_ADMIN", update.effective_user.full_name, removed)
        await update.message.reply_text(f"🗑️ *{removed}* removido dos admins.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ℹ️ Este usuário não é admin do bot.")

async def cmd_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista admins do bot."""
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas donos do bot.")
    if not bot_admins: return await update.message.reply_text("👮 Nenhum admin cadastrado.")
    lines = ["👮 *Admins do Bot:*\n"] + [f"• `{k}` — *{v}*" for k, v in bot_admins.items()]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aviso oficial no grupo. Uso: /broadcast <texto>"""
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Apenas donos do bot.")
    if not context.args: return await update.message.reply_text("ℹ️ Uso: /broadcast <mensagem>")
    await context.bot.send_message(update.effective_chat.id,
        "📢 *AVISO OFICIAL:*\n\n" + " ".join(context.args), parse_mode=ParseMode.MARKDOWN)
    log_action(update.effective_chat.id, "BROADCAST", update.effective_user.full_name, "Grupo")

# ══════════════════════════════════════════════
#  ✅  CONFIÁVEIS
# ══════════════════════════════════════════════
async def cmd_trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona confiável (isento de filtros). Uso: /trust (reply)"""
    if not await has_mod_power(update, context):
        return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    trusted_users[cid][tid] = tname
    save_data()
    log_action(cid, "TRUST_ADD", update.effective_user.full_name, str(tname))
    await update.message.reply_text(
        f"✅ *{tname}* adicionado aos *confiáveis*.\nIsento de anti-spam, anti-link e filtro de palavras.",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_untrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove confiável. Uso: /untrust (reply)"""
    if not await has_mod_power(update, context):
        return await update.message.reply_text("❌ Apenas moderadores.")
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
    if not await has_mod_power(update, context):
        return await update.message.reply_text("❌ Apenas moderadores.")
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
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_link_groups.add(cid); save_data()
        await update.message.reply_text("🔗 Anti-link *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_link_groups.discard(cid); save_data()
        await update.message.reply_text("🔗 Anti-link *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trava o grupo — nenhum membro pode enviar mensagens."""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, LOCKED_PERMISSIONS)
        await update.message.reply_text("🔒 Grupo *TRAVADO*. Apenas admins podem enviar mensagens.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "LOCK", update.effective_user.full_name, "Grupo")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Erro ao travar: {e}")

async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Destranca o grupo — restaura todas as permissões normais."""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, OPEN_PERMISSIONS)
        await update.message.reply_text("🔓 Grupo *DESTRAVADO*. Membros podem falar novamente.", parse_mode=ParseMode.MARKDOWN)
        log_action(update.effective_chat.id, "UNLOCK", update.effective_user.full_name, "Grupo")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Erro ao destravar: {e}")

async def cmd_antisticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga/desliga anti-sticker. Uso: /antisticker on|off"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_sticker_groups.add(cid); save_data()
        await update.message.reply_text("🚫 Anti-sticker *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_sticker_groups.discard(cid); save_data()
        await update.message.reply_text("🚫 Anti-sticker *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_antigif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga/desliga anti-GIF. Uso: /antigif on|off"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    arg = context.args[0].lower() if context.args else "on"
    if arg == "on":
        anti_gif_groups.add(cid); save_data()
        await update.message.reply_text("🎞️ Anti-GIF *ATIVADO*.", parse_mode=ParseMode.MARKDOWN)
    else:
        anti_gif_groups.discard(cid); save_data()
        await update.message.reply_text("🎞️ Anti-GIF *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define modo lento. Uso: /slowmode <segundos> | /slowmode off"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    if not context.args:
        current = slowmode_groups.get(cid, 0)
        status = f"{current}s" if current else "desativado"
        return await update.message.reply_text(
            f"⏱️ Modo lento atual: *{status}*\nUso: `/slowmode <segundos>` ou `/slowmode off`",
            parse_mode=ParseMode.MARKDOWN)
    arg = context.args[0].lower()
    seconds = 0 if arg == "off" else max(0, min(int(arg), 3600)) if arg.isdigit() else None
    if seconds is None: return await update.message.reply_text("ℹ️ Informe os segundos ou 'off'.")
    try:
        await context.bot.set_chat_slow_mode_delay(cid, seconds)
        if seconds == 0:
            slowmode_groups.pop(cid, None); save_data()
            await update.message.reply_text("⏱️ Modo lento *DESATIVADO*.", parse_mode=ParseMode.MARKDOWN)
        else:
            slowmode_groups[cid] = seconds; save_data()
            await update.message.reply_text(f"⏱️ Modo lento: *{seconds}s* entre mensagens.", parse_mode=ParseMode.MARKDOWN)
        log_action(cid, "SLOWMODE", update.effective_user.full_name, "Grupo", f"{seconds}s")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fixa mensagem (use em reply). Uso: /pin [silent]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    if not update.message.reply_to_message:
        return await update.message.reply_text("ℹ️ Responda à mensagem que deseja fixar.")
    silent = bool(context.args and context.args[0].lower() == "silent")
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id,
            update.message.reply_to_message.message_id,
            disable_notification=silent)
        await update.message.reply_text("📌 Mensagem fixada" + (" silenciosamente." if silent else "."))
        log_action(update.effective_chat.id, "PIN", update.effective_user.full_name, "mensagem")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desfixa mensagem. Uso: /unpin [all]"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    try:
        if context.args and context.args[0].lower() == "all":
            await context.bot.unpin_all_chat_messages(cid)
            await update.message.reply_text("📌 Todas as mensagens desfixadas.")
        elif update.message.reply_to_message:
            await context.bot.unpin_chat_message(cid, update.message.reply_to_message.message_id)
            await update.message.reply_text("📌 Mensagem desfixada.")
        else:
            await context.bot.unpin_chat_message(cid)
            await update.message.reply_text("📌 Última mensagem fixada removida.")
        log_action(cid, "UNPIN", update.effective_user.full_name, "mensagem")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define as regras do grupo. Uso: /setrules <texto>  (use \\n para quebrar linha)"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    if not context.args: return await update.message.reply_text("ℹ️ Uso: `/setrules Regra 1\\nRegra 2...`", parse_mode=ParseMode.MARKDOWN)
    cid = update.effective_chat.id
    group_rules[cid] = " ".join(context.args).replace("\\n", "\n")
    save_data()
    log_action(cid, "SET_RULES", update.effective_user.full_name, "Grupo")
    await update.message.reply_text("✅ Regras do grupo atualizadas!")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe as regras do grupo."""
    cid = update.effective_chat.id
    rules = group_rules.get(cid)
    if not rules: return await update.message.reply_text("ℹ️ Nenhuma regra definida. Use /setrules para definir.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Li e aceito as regras", callback_data=f"rules_ack:{update.effective_user.id}")]])
    await update.message.reply_text(f"📋 *Regras do Grupo:*\n\n{rules}", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define boas-vindas customizadas. Variáveis: {name} {group}
    Uso: /setwelcome Olá {name}, bem-vindo ao {group}!"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    if not context.args:
        return await update.message.reply_text("ℹ️ Uso: `/setwelcome Sua mensagem`\nVariáveis: `{name}` `{group}`", parse_mode=ParseMode.MARKDOWN)
    cid = update.effective_chat.id
    welcome_messages[cid] = " ".join(context.args).replace("\\n", "\n")
    save_data()
    await update.message.reply_text(f"✅ Boas-vindas atualizada!\n\nPrévia:\n_{welcome_messages[cid]}_", parse_mode=ParseMode.MARKDOWN)

async def cmd_resetwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove boas-vindas customizada (volta ao padrão)."""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    welcome_messages.pop(update.effective_chat.id, None)
    save_data()
    await update.message.reply_text("✅ Boas-vindas resetada para o padrão.")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zera todos os avisos de um usuário. Uso: /clearwarns (reply)"""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    tid, tname = get_target(update)
    if not tid: return await update.message.reply_text("ℹ️ Responda à mensagem do usuário.")
    cid = update.effective_chat.id
    warnings[cid][tid] = 0; save_data()
    log_action(cid, "CLEAR_WARNS", update.effective_user.full_name, str(tname))
    await update.message.reply_text(f"🧹 Todos os avisos de *{tname}* foram zerados.", parse_mode=ParseMode.MARKDOWN)

async def cmd_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista usuários banidos neste grupo."""
    if not await has_mod_power(update, context): return await update.message.reply_text("❌ Apenas moderadores.")
    cid = update.effective_chat.id
    bans = ban_registry.get(cid, [])
    if not bans: return await update.message.reply_text("✅ Nenhum ban registrado neste grupo.")
    lines = [f"🔨 *Banidos neste grupo ({len(bans)}):*\n"]
    for entry in bans[-20:][::-1]:
        lines.append(f"• `{entry['uid']}` — *{entry['name']}*\n  📝 {entry.get('reason','—')} | {entry['ts']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o ID do chat e do usuário."""
    user, chat = update.effective_user, update.effective_chat
    tid, tname = get_target(update)
    lines = [f"💬 *Chat ID:* `{chat.id}`", f"👤 *Seu ID:* `{user.id}`"]
    if tid and tid != user.id:
        lines.append(f"🎯 *ID de {tname}:* `{tid}`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reporta mensagem para admins via PM. Use em reply."""
    if not update.message.reply_to_message:
        return await update.message.reply_text("ℹ️ Responda à mensagem que quer reportar.")
    chat, reporter = update.effective_chat, update.effective_user
    reported = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "Sem motivo especificado"
    notified = 0
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            if admin.user.is_bot: continue
            try:
                link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.reply_to_message.message_id}"
                await context.bot.send_message(admin.user.id,
                    f"🚨 *REPORT — {chat.title}*\n\n"
                    f"📢 Por: *{reporter.full_name}* (`{reporter.id}`)\n"
                    f"🎯 Reportado: *{reported.full_name}* (`{reported.id}`)\n"
                    f"📝 Motivo: {reason}\n🔗 [Ver mensagem]({link})",
                    parse_mode=ParseMode.MARKDOWN)
                notified += 1
            except TelegramError: pass
    except TelegramError: pass
    await update.message.reply_text(f"✅ Report enviado para *{notified}* admin(s).\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
    log_action(chat.id, "REPORT", reporter.full_name, reported.full_name, reason)

async def cmd_groupinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Painel de configurações e estatísticas do grupo."""
    chat, cid = update.effective_chat, update.effective_chat.id
    has_rules   = "✅ Definidas"   if group_rules.get(cid)       else "❌ Não definidas"
    has_welcome = "✅ Customizada" if welcome_messages.get(cid)  else "🔄 Padrão"
    antilink    = "✅ Ativo"       if cid in anti_link_groups    else "❌ Inativo"
    antisticker = "✅ Ativo"       if cid in anti_sticker_groups else "❌ Inativo"
    antigif     = "✅ Ativo"       if cid in anti_gif_groups     else "❌ Inativo"
    slow        = f"{slowmode_groups[cid]}s" if cid in slowmode_groups else "❌ Desativado"
    total_warns = sum(warnings[cid].values())
    total_bans  = len(ban_registry.get(cid, []))
    try: count = await context.bot.get_chat_member_count(cid)
    except TelegramError: count = "—"
    await update.message.reply_text(
        f"ℹ️ *{chat.title}*\n🆔 `{cid}`\n👥 Membros: {count}\n\n"
        f"*🔧 Filtros:*\n🔗 Anti-link: {antilink}\n🚫 Anti-sticker: {antisticker}\n"
        f"🎞️ Anti-GIF: {antigif}\n⏱️ Modo lento: {slow}\n\n"
        f"*📄 Conteúdo:*\n📋 Regras: {has_rules}\n👋 Boas-vindas: {has_welcome}\n\n"
        f"*📊 Histórico:*\n⚠️ Avisos ativos: {total_warns}\n🔨 Bans registrados: {total_bans}",
        parse_mode=ParseMode.MARKDOWN)
    


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Histórico do grupo. Uso: /logs [N]"""
    if not await has_mod_power(update, context):
        return await update.message.reply_text("❌ Apenas moderadores.")

    cid = update.effective_chat.id

    try:
        limit = min(int(context.args[0]), 25) if context.args else 10
    except ValueError:
        limit = 10

    entries = [e for e in reversed(action_log) if e["chat_id"] == cid][:limit]

    if not entries:
        return await update.message.reply_text("📋 Nenhuma ação registrada aqui.")

    lines = [f"📋 *Últimas {len(entries)} ações:*\n"]

    for e in entries:
        lines.append(
            f"• `{e['ts']}` *{e['action']}*\n"
            f"  👮 {e['mod']} → {e['target']}"
            + (f"\n  📝 {e['reason']}" if e.get("reason") else "")
        )

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
        f"🛡️ *Guardião v3 — Online!*\n\nOlá, *{update.effective_user.first_name}*!\nCargo: {role}\n\nUse /help para ver os comandos.{extra}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    owner_section = ""
    if is_owner(uid):
        owner_section = ("\n\n*👑 Exclusivo do Dono:*\n"
            "/owner — Painel interativo\n/addadmin — Adiciona admin do bot\n"
            "/removeadmin — Remove admin do bot\n/listadmins — Lista admins\n"
            "/broadcast — Aviso oficial no grupo\n")
    await update.message.reply_text(
        "🛡️ *GUARDIÃO v3 — Comandos*\n\n"
        "*🛡️ Moderação:*\n/ban /unban /kick\n/mute [min] /unmute\n"
        "/warn [motivo] /unwarn /warns\n"
        "/clearwarns — Zera avisos de um usuário\n"
        "/purge <N> — Apaga N mensagens\n"
        "/report — Reporta mensagem para admins\n"
        "/banlist — Histórico de bans\n\n"
        "*📌 Mensagens:*\n"
        "/pin [silent] — Fixa mensagem\n"
        "/unpin [all] — Desfixa mensagem\n\n"
        "*⚙️ Configuração:*\n"
        "/antilink on|off — Anti-link\n"
        "/antisticker on|off — Anti-sticker\n"
        "/antigif on|off — Anti-GIF\n"
        "/lock /unlock /ro — Travar grupo\n"
        "/slowmode <s>|off — Modo lento\n"
        "/setrules <texto> — Define regras\n"
        "/rules — Exibe regras\n"
        "/setwelcome — Boas-vindas custom\n"
        "/resetwelcome — Remove boas-vindas custom\n"
        "/trust /untrust /listtrust\n\n"
        "*📊 Info:*\n"
        "/id — IDs do chat/usuário\n"
        "/groupinfo — Painel do grupo\n"
        "/userinfo — Info do usuário\n"
        "/logs [N] — Histórico de ações"
        + owner_section,
        parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  🚀  MAIN
# ══════════════════════════════════════════════
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
        # Dono
        ("addadmin", cmd_addadmin), ("removeadmin", cmd_removeadmin),
        ("listadmins", cmd_listadmins), ("broadcast", cmd_broadcast),
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

    logger.info("🛡️ Guardião v3 iniciado!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
