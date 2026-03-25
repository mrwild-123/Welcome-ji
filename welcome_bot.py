#!/usr/bin/env python3
import logging
import json
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ChatMemberHandler,
    ChatJoinRequestHandler, ContextTypes,
)
import gender_guesser.detector as gender_detector

BOT_TOKEN = "8634101836:AAFPr7S3s2hlQo0zjExK7XwpYgiaxIhJgv4"  # ← Yahan apna token daalo

DATA_FILE = "welcome_data.json"
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
detector = gender_detector.Detector(case_sensitive=False)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_group_settings(chat_id):
    data = load_data()
    key = str(chat_id)
    if key not in data:
        data[key] = {
            "male":    {"text": "🎉 Welcome bhai *{name}*! 💪", "media_type": None, "media_id": None},
            "female":  {"text": "🌸 Welcome didi *{name}*! 🌺", "media_type": None, "media_id": None},
            "unknown": {"text": "👋 Welcome *{name}*! 😊",      "media_type": None, "media_id": None},
        }
        save_data(data)
    return data[key]

def update_group_settings(chat_id, settings):
    data = load_data()
    data[str(chat_id)] = settings
    save_data(data)

def detect_gender(first_name):
    result = detector.get_gender(first_name)
    if result in ("male", "mostly_male"):
        return "male"
    elif result in ("female", "mostly_female"):
        return "female"
    return "unknown"

async def send_welcome(context, chat_id, user):
    settings = get_group_settings(chat_id)
    first_name = user.first_name or "Friend"
    full_name = f"{first_name} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else full_name
    gender = detect_gender(first_name)
    cfg = settings.get(gender, settings["unknown"])
    text = cfg["text"].format(name=full_name, username=username, first_name=first_name)
    media_type = cfg.get("media_type")
    media_id = cfg.get("media_id")
    try:
        if media_type == "photo" and media_id:
            await context.bot.send_photo(chat_id=chat_id, photo=media_id, caption=text, parse_mode="Markdown")
        elif media_type == "video" and media_id:
            await context.bot.send_video(chat_id=chat_id, video=media_id, caption=text, parse_mode="Markdown")
        elif media_type == "gif" and media_id:
            await context.bot.send_animation(chat_id=chat_id, animation=media_id, caption=text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Welcome error: {e}")

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    old = result.old_chat_member.status
    new = result.new_chat_member.status
    if old in ("left", "kicked") and new == "member":
        user = result.new_chat_member.user
        if not user.is_bot:
            await send_welcome(context, result.chat.id, user)

async def join_request_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    if not request: return
    await context.bot.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
    if not request.from_user.is_bot:
        await send_welcome(context, request.chat.id, request.from_user)

async def is_admin(update, context):
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome Bot Active!*\n\n*Commands:*\n"
        "`/setwelcome male <msg>`\n`/setwelcome female <msg>`\n`/setwelcome unknown <msg>`\n"
        "`/setmedia male` — photo/video reply karke\n`/setmedia female`\n"
        "`/clearmedia male`\n`/preview male`\n`/settings`\n\n"
        "Variables: `{name}` `{username}` `{first_name}`",
        parse_mode="Markdown")

async def cmd_set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Sirf admins!"); return
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Format: `/setwelcome male Welcome {name}!`", parse_mode="Markdown"); return
    gender_key = args[0].lower()
    if gender_key not in ("male", "female", "unknown"):
        await update.message.reply_text("❌ male / female / unknown"); return
    msg_text = " ".join(args[1:])
    settings = get_group_settings(update.effective_chat.id)
    settings[gender_key]["text"] = msg_text
    update_group_settings(update.effective_chat.id, settings)
    await update.message.reply_text(f"✅ *{gender_key}* welcome set!\n_{msg_text}_", parse_mode="Markdown")

async def cmd_set_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Sirf admins!"); return
    args = context.args
    if not args:
        await update.message.reply_text("Photo/video ko reply karke `/setmedia male` likhо", parse_mode="Markdown"); return
    gender_key = args[0].lower()
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("❌ Pehle media bhejo, phir reply karke command do"); return
    settings = get_group_settings(update.effective_chat.id)
    if reply.photo:
        settings[gender_key].update({"media_type": "photo", "media_id": reply.photo[-1].file_id}); label = "Photo"
    elif reply.video:
        settings[gender_key].update({"media_type": "video", "media_id": reply.video.file_id}); label = "Video"
    elif reply.animation:
        settings[gender_key].update({"media_type": "gif", "media_id": reply.animation.file_id}); label = "GIF"
    else:
        await update.message.reply_text("❌ Sirf Photo, Video, GIF!"); return
    update_group_settings(update.effective_chat.id, settings)
    await update.message.reply_text(f"✅ *{gender_key}* ke liye {label} set!", parse_mode="Markdown")

async def cmd_clear_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/clearmedia male`", parse_mode="Markdown"); return
    gender_key = args[0].lower()
    settings = get_group_settings(update.effective_chat.id)
    settings[gender_key].update({"media_type": None, "media_id": None})
    update_group_settings(update.effective_chat.id, settings)
    await update.message.reply_text(f"✅ {gender_key} media remove!")

async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    gender_key = args[0].lower() if args else "male"
    settings = get_group_settings(update.effective_chat.id)
    cfg = settings.get(gender_key, settings["unknown"])
    user = update.effective_user
    text = cfg["text"].format(
        name=user.full_name,
        username=f"@{user.username}" if user.username else user.full_name,
        first_name=user.first_name)
    media_type = cfg.get("media_type")
    media_id = cfg.get("media_id")
    await update.message.reply_text(f"👁 *Preview ({gender_key}):*", parse_mode="Markdown")
    if media_type == "photo" and media_id:
        await update.message.reply_photo(photo=media_id, caption=text, parse_mode="Markdown")
    elif media_type == "video" and media_id:
        await update.message.reply_video(video=media_id, caption=text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    settings = get_group_settings(update.effective_chat.id)
    msg = "⚙️ *Current Settings:*\n\n"
    for g in ("male", "female", "unknown"):
        cfg = settings[g]
        emoji = "👨" if g == "male" else ("👩" if g == "female" else "🤷")
        media = cfg.get("media_type") or "None"
        msg += f"{emoji} *{g.upper()}*\n📝 `{cfg['text'][:50]}`\n🎬 `{media}`\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("setwelcome", cmd_set_welcome))
    app.add_handler(CommandHandler("setmedia", cmd_set_media))
    app.add_handler(CommandHandler("clearmedia", cmd_clear_media))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(ChatMemberHandler(member_joined, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatJoinRequestHandler(join_request_approved))
    logger.info("Bot chal raha hai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
