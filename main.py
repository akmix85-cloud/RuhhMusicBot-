import os
from collections import deque

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityVideo, HighQualityAudio

from youtubesearchpython import VideosSearch
import yt_dlp


# ================= CONFIG =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STRING_SESSION = os.getenv("STRING_SESSION")

OWNER_ID = 7726604282


# ================= CLIENT =================
app = Client(
    "dream_music",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    session_string=STRING_SESSION,
)

call = PyTgCalls(app)


# ================= STORAGE =================
queues = {}
current_audio = {}


# ================= HELPERS =================
async def is_admin(chat_id, user_id):
    member = await app.get_chat_member(chat_id, user_id)
    return member.privileges and member.privileges.can_manage_voice_chats


def mention(user):
    return f"{user.first_name}"


# ================= START =================
@app.on_message(filters.command("start"))
async def start(_, m):
    owner = await app.get_users(OWNER_ID)
    await m.reply(
        f"""
🎧 Dream With Music

👑 Owner: {owner.first_name}

▶ Use /play or /vplay song name
""",
        disable_web_page_preview=True
    )


# ================= PLAY (AUDIO) =================
@app.on_message(filters.command("play") & filters.group)
async def play(_, m):
    await m.delete()

    if len(m.command) < 2:
        return

    chat_id = m.chat.id
    query = " ".join(m.command[1:])

    search = VideosSearch(query, limit=1)
    r = search.result()["result"][0]

    title = r["title"]
    duration = r["duration"]
    video_id = r["id"]
    thumb = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    url = r["link"]

    with yt_dlp.YoutubeDL({"format": "bestaudio"}) as ydl:
        info = ydl.extract_info(url, download=False)
        audio = info["url"]

    queues.setdefault(chat_id, deque())

    if chat_id in call.active_calls:
        queues[chat_id].append(audio)
        pos = len(queues[chat_id])
        return await app.send_message(
            chat_id,
            f"""
↪ Added To Queue At #{pos}

✨ Title: {title}
⏱ Duration: {duration}
🌹 Requested By: {mention(m.from_user)}
""",
            disable_web_page_preview=True
        )

    current_audio[chat_id] = audio
    await call.join_group_call(chat_id, AudioPiped(audio))

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("⏸", callback_data="pause"),
            InlineKeyboardButton("▶", callback_data="resume"),
            InlineKeyboardButton("⏭", callback_data="skip"),
            InlineKeyboardButton("⏹", callback_data="end"),
        ]]
    )

    await app.send_photo(
        chat_id,
        photo=thumb,
        caption=f"""
▶ STARTED STREAMING

✨ Title: {title}
⏱ Duration: {duration}
🌹 Requested By: {mention(m.from_user)}

🎧 𐍂υᖾᖾ 𐌼υδιϲ
""",
        reply_markup=buttons
    )


# ================= VPLAY (VIDEO) =================
@app.on_message(filters.command("vplay") & filters.group)
async def vplay(_, m):
    await m.delete()

    if len(m.command) < 2:
        return

    chat_id = m.chat.id
    query = " ".join(m.command[1:])

    search = VideosSearch(query, limit=1)
    r = search.result()["result"][0]

    title = r["title"]
    duration = r["duration"]
    video_id = r["id"]
    thumb = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    url = r["link"]

    ydl_opts = {"format": "bestvideo+bestaudio/best", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        stream_url = info["url"]

    await call.join_group_call(
        chat_id,
        AudioVideoPiped(
            stream_url,
            HighQualityVideo(),
            HighQualityAudio(),
        ),
    )

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("⏸", callback_data="pause"),
            InlineKeyboardButton("▶", callback_data="resume"),
            InlineKeyboardButton("⏭", callback_data="skip"),
            InlineKeyboardButton("⏹", callback_data="end"),
        ]]
    )

    await app.send_photo(
        chat_id,
        photo=thumb,
        caption=f"""
🎥 VIDEO STREAMING STARTED

✨ Title: {title}
⏱ Duration: {duration}
🌹 Requested By: {mention(m.from_user)}

🎧 𐍂υᖾᖾ 𐌼υδιϲ
""",
        reply_markup=buttons
    )


# ================= AUTO NEXT =================
@call.on_stream_end()
async def next_song(_, update):
    chat_id = update.chat_id
    if queues.get(chat_id):
        audio = queues[chat_id].popleft()
        current_audio[chat_id] = audio
        await call.change_stream(chat_id, AudioPiped(audio))
    else:
        await call.leave_group_call(chat_id)
        current_audio.pop(chat_id, None)


# ================= BUTTON CALLBACKS =================
@app.on_callback_query()
async def buttons(_, cb):
    chat_id = cb.message.chat.id
    user = cb.from_user
    data = cb.data

    if not await is_admin(chat_id, user.id):
        return await cb.answer("Admin only ❌", show_alert=True)

    if data == "pause":
        await call.pause_stream(chat_id)
        await app.send_message(chat_id, f"⏸ Paused by {mention(user)}")

    elif data == "resume":
        await call.resume_stream(chat_id)
        await app.send_message(chat_id, f"▶ Resumed by {mention(user)}")

    elif data == "skip":
        if queues.get(chat_id):
            audio = queues[chat_id].popleft()
            await call.change_stream(chat_id, AudioPiped(audio))
            await app.send_message(chat_id, f"⏭ Skipped by {mention(user)}")

    elif data == "end":
        queues.pop(chat_id, None)
        await call.leave_group_call(chat_id)
        await app.send_message(chat_id, f"⏹ Ended by {mention(user)}")


# ================= RUN =================
call.start()
app.run()
