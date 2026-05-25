import asyncio
import logging
import random
import aiosqlite
import os
from datetime import datetime, date
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (Message, CallbackQuery,
                            InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  CONFIG — এখানে তোমার সব তথ্য বসাও
# ============================================================
BOT_TOKEN   = os.getenv("BOT_TOKEN", "PUT_YOUR_NEW_TOKEN_HERE")
ADMIN_IDS   = [int(x) for x in os.getenv("ADMIN_IDS", "6814149557").split(",")]

REQUIRED_CHANNELS = [
    {"id": -1002171293993, "name": "📢 Channel 1",  "link": "https://t.me/+O5WWlWDJp8NmNDY9"},
    {"id": -1003967522498, "name": "📢 Channel 2",  "link": "https://t.me/sscsuggesion100percent"},
    {"id": -1003915990814, "name": "📢 Channel 3",  "link": "https://t.me/+56MHks408YFkNzJl"},
    {"id": -1003981803402, "name": "📢 Channel 4",  "link": "https://t.me/givewayhub75"},
    {"id": -1003925815027, "name": "📢 Channel 5",  "link": "https://t.me/God_gifttaken"},
    {"id": -1003792704399, "name": "📢 Channel 6",  "link": "https://t.me/+6NcPWNtUhU9iZTA1"},
    {"id": -1003870696375, "name": "📢 Channel 7",  "link": "https://t.me/onlymethodstar"},
    {"id": -1003923737600, "name": "📢 Channel 8",  "link": "https://t.me/auraytff"},
    {"id": -1003927114110, "name": "📢 Channel 9",  "link": "https://t.me/prohithu"},
    {"id": -1003785063763, "name": "📢 Channel 10", "link": "https://t.me/methodwithcrash"},
]
YOUTUBE_LINK        = "https://www.youtube.com/@starhubyt_pro"
YOUTUBE_NAME        = "starhubyt pro"
REFERRAL_REWARD     = 10
DAILY_BONUS_BASE    = 5
MIN_WITHDRAW_STARS  = 500
MIN_WITHDRAW_REFS   = 25
REFERRAL_MILESTONES = {
    10:  {"bonus": 50,  "badge": "🥈 Silver"},
    50:  {"bonus": 200, "badge": "🥇 Gold"},
    100: {"bonus": 500, "badge": "👑 VIP"},
}
STREAK_REWARDS = {1: 5, 2: 5, 3: 8, 4: 8, 5: 10, 6: 10, 7: 25}
SPIN_REWARDS   = [3,  5,  8,  10, 15, 20, 25, 50]
SPIN_WEIGHTS   = [20, 25, 18, 15, 10,  7,  4,  1]
DB_PATH        = "starbot.db"

# ============================================================
#  DATABASE
# ============================================================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                balance INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL,
                badge TEXT DEFAULT '🥉 Bronze', streak INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT NULL,
                joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, description TEXT, reward INTEGER,
                task_type TEXT, task_link TEXT, is_active INTEGER DEFAULT 1
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, task_id INTEGER,
                UNIQUE(user_id, task_id)
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, amount INTEGER, tg_username TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT DEFAULT NULL
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, reward INTEGER,
                spun_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.commit()
    logger.info("✅ Database ready")

async def db_get(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

async def db_all(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchall()

async def db_run(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()

async def get_user(uid):      return await db_get("SELECT * FROM users WHERE user_id=?", (uid,))
async def get_total_users():
    r = await db_get("SELECT COUNT(*) as c FROM users")
    return r["c"] if r else 0

async def create_user(uid, uname, fname, ref_id=None):
    await db_run(
        "INSERT OR IGNORE INTO users (user_id,username,full_name,referred_by) VALUES(?,?,?,?)",
        (uid, uname, fname, ref_id))

async def add_stars(uid, amount):
    if amount > 0:
        await db_run(
            "UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",
            (amount, amount, uid))
    else:
        await db_run("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))

async def add_referral(ref_id, reward):
    await db_run(
        "UPDATE users SET referrals=referrals+1,balance=balance+?,total_earned=total_earned+? WHERE user_id=?",
        (reward, reward, ref_id))

async def set_badge(uid, badge):
    await db_run("UPDATE users SET badge=? WHERE user_id=?", (badge, uid))

async def claim_daily_db(uid, reward, streak):
    today = date.today().isoformat()
    await db_run(
        "UPDATE users SET balance=balance+?,total_earned=total_earned+?,last_daily=?,streak=? WHERE user_id=?",
        (reward, reward, today, streak, uid))

async def get_leaderboard(col="referrals", limit=10):
    return await db_all(f"SELECT * FROM users WHERE is_banned=0 ORDER BY {col} DESC LIMIT ?", (limit,))

async def get_tasks():        return await db_all("SELECT * FROM tasks WHERE is_active=1")
async def task_done(uid, tid): return bool(await db_get("SELECT id FROM completed_tasks WHERE user_id=? AND task_id=?", (uid,tid)))

async def complete_task_db(uid, tid, reward):
    try:
        await db_run("INSERT INTO completed_tasks (user_id,task_id) VALUES(?,?)", (uid, tid))
        await db_run("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",
                     (reward, reward, uid))
        return True
    except: return False

async def create_withdrawal(uid, amount, uname):
    await db_run("INSERT INTO withdrawals (user_id,amount,tg_username) VALUES(?,?,?)", (uid, amount, uname))
    await db_run("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))

async def get_pending_wd():   return await db_all("SELECT * FROM withdrawals WHERE status='pending'")
async def get_user_wd(uid):   return await db_all("SELECT * FROM withdrawals WHERE user_id=? ORDER BY requested_at DESC LIMIT 5", (uid,))
async def update_wd(wid, st):
    await db_run("UPDATE withdrawals SET status=?,processed_at=? WHERE id=?",
                 (st, datetime.now().isoformat(), wid))

async def get_last_spin(uid):
    r = await db_get("SELECT spun_at FROM spin_logs WHERE user_id=? ORDER BY spun_at DESC LIMIT 1", (uid,))
    return r["spun_at"] if r else None

async def log_spin_db(uid, reward):
    await db_run("INSERT INTO spin_logs (user_id,reward) VALUES(?,?)", (uid, reward))
    await db_run("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",
                 (reward, reward, uid))

async def get_all_user_ids():
    rows = await db_all("SELECT user_id FROM users WHERE is_banned=0")
    return [r["user_id"] for r in rows]

async def add_task_db(title, desc, reward, ttype, link):
    await db_run("INSERT INTO tasks (title,description,reward,task_type,task_link) VALUES(?,?,?,?,?)",
                 (title, desc, reward, ttype, link))

# ============================================================
#  HELPERS
# ============================================================
def prog_bar(cur, total, length=10):
    f = int((cur/total)*length) if total else 0
    return f"[{'█'*f}{'░'*(length-f)}] {cur}/{total}"

def get_badge(refs):
    if refs >= 100: return "👑 VIP"
    if refs >= 50:  return "🥇 Gold"
    if refs >= 10:  return "🥈 Silver"
    return "🥉 Bronze"

def can_claim(last):
    if not last: return True
    return date.fromisoformat(last) < date.today()

def streak_reward(s):
    return STREAK_REWARDS.get(min(s,7), 5)

async def check_channels(bot: Bot, uid: int):
    joined, not_joined = [], []
    for ch in REQUIRED_CHANNELS:
        try:
            m = await bot.get_chat_member(ch["id"], uid)
            if m.status in ("member", "administrator", "creator"):
                joined.append(ch)
            elif m.status in ("left", "kicked", "restricted", "banned"):
                not_joined.append(ch)
            else:
                not_joined.append(ch)
        except Exception as e:
            err = str(e).lower()
            # যদি channel ID ভুল হয় বা bot admin না হয় — skip করো
            if "chat not found" in err or "bot is not a member" in err or "peer_id_invalid" in err:
                # Channel check করা যাচ্ছে না — joined ধরো যাতে block না হয়
                joined.append(ch)
            else:
                not_joined.append(ch)
    return joined, not_joined

# ============================================================
#  KEYBOARDS
# ============================================================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance",      callback_data="balance"),
         InlineKeyboardButton(text="👥 Referral",     callback_data="referral")],
        [InlineKeyboardButton(text="📋 Tasks",        callback_data="tasks"),
         InlineKeyboardButton(text="🎁 Daily Bonus",  callback_data="daily")],
        [InlineKeyboardButton(text="🎰 Spin Wheel",   callback_data="spin"),
         InlineKeyboardButton(text="🏆 Leaderboard",  callback_data="leaderboard")],
        [InlineKeyboardButton(text="💸 Withdraw",     callback_data="withdraw"),
         InlineKeyboardButton(text="⚙️ Profile",      callback_data="profile")],
        [InlineKeyboardButton(text="📢 News",         callback_data="news"),
         InlineKeyboardButton(text="🆘 Support",      callback_data="support")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
    ])

def channel_kb(not_joined):
    rows = [[InlineKeyboardButton(text=f"➡️ Join {c['name']}", url=c["link"])]
            for c in not_joined]
    rows.append([InlineKeyboardButton(text="✅ Check Again", callback_data="check_channels")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def lb_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Top Referrers", callback_data="lb_refs"),
         InlineKeyboardButton(text="⭐ Top Earners",   callback_data="lb_earn")],
        [InlineKeyboardButton(text="🏠 Main Menu",     callback_data="main_menu")],
    ])

def wd_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Request Withdrawal", callback_data="req_wd")],
        [InlineKeyboardButton(text="📜 My History",         callback_data="wd_history")],
        [InlineKeyboardButton(text="🏠 Main Menu",          callback_data="main_menu")],
    ])

def yt_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Subscribe {YOUTUBE_NAME}", url=YOUTUBE_LINK)],
        [InlineKeyboardButton(text="✅ I Subscribed", callback_data="yt_ok")],
    ])

def confirm_wd_kb(amount):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data=f"cwf_{amount}"),
         InlineKeyboardButton(text="❌ Cancel",  callback_data="main_menu")],
    ])

def admin_wd_kb(wid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve & Pay", callback_data=f"approve_{wid}"),
         InlineKeyboardButton(text="❌ Reject",        callback_data=f"reject_{wid}")],
    ])

def task_list_kb(tasks):
    rows = [[InlineKeyboardButton(text=f"📌 {t['title']} — ⭐{t['reward']}", callback_data=f"task_{t['task_id']}")]
            for t in tasks]
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def task_action_kb(tid, link, done):
    if done:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Already Completed", callback_data="noop")],
            [InlineKeyboardButton(text="🔙 Back to Tasks",     callback_data="tasks")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Open Task", url=link)],
        [InlineKeyboardButton(text="✅ Mark Done", callback_data=f"done_{tid}")],
        [InlineKeyboardButton(text="🔙 Back",      callback_data="tasks")],
    ])

# ============================================================
#  FSM STATES
# ============================================================
class WDState(StatesGroup):
    amount   = State()
    username = State()
    confirm  = State()

class AdminState(StatesGroup):
    broadcast     = State()
    task_title    = State()
    task_desc     = State()
    task_reward   = State()
    task_type     = State()
    task_link     = State()

# ============================================================
#  ROUTER
# ============================================================
router = Router()

# ---------- /start ----------
@router.message(CommandStart())
async def cmd_start(msg: Message):
    uid   = msg.from_user.id
    name  = msg.from_user.full_name
    uname = msg.from_user.username or ""

    args   = msg.text.split()
    ref_id = None
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id == uid: ref_id = None
        except: pass

    existing = await get_user(uid)
    is_new   = existing is None
    if is_new:
        await create_user(uid, uname, name, ref_id)

    user = await get_user(uid)
    if user["is_banned"]:
        await msg.answer("🚫 You are banned from this bot.")
        return

    joined, not_joined = await check_channels(msg.bot, uid)
    total = len(REQUIRED_CHANNELS)

    if not_joined:
        text = f"👋 <b>Hello, {name}!</b>\n\n📌 <b>Join all channels to unlock the bot:</b>\n\n"
        for ch in REQUIRED_CHANNELS:
            ok = "✅" if ch in joined else "❌"
            text += f"{ok} {ch['name']}\n"
        text += f"\n📊 Progress: {prog_bar(len(joined), total)}\n\n⚠️ Join all 10 channels first!"
        await msg.answer(text, reply_markup=channel_kb(not_joined), parse_mode="HTML")
        return

    # New user referral reward
    if is_new and ref_id:
        referrer = await get_user(ref_id)
        if referrer and not referrer["is_banned"]:
            await add_referral(ref_id, REFERRAL_REWARD)
            updated = await get_user(ref_id)
            new_refs = updated["referrals"]
            badge = get_badge(new_refs)
            await set_badge(ref_id, badge)

            if new_refs in REFERRAL_MILESTONES:
                m = REFERRAL_MILESTONES[new_refs]
                await add_stars(ref_id, m["bonus"])
                try:
                    await msg.bot.send_message(
                        ref_id,
                        f"🎉 <b>Milestone!</b> {new_refs} referrals reached!\n"
                        f"🎁 Bonus: +{m['bonus']} Stars\n🏅 Badge: {m['badge']}",
                        parse_mode="HTML")
                except: pass
            else:
                try:
                    await msg.bot.send_message(
                        ref_id,
                        f"🎉 <b>{name}</b> joined via your link!\n"
                        f"⭐ +{REFERRAL_REWARD} Stars earned!\n"
                        f"👥 Total referrals: <b>{new_refs}</b>",
                        parse_mode="HTML")
                except: pass

    user  = await get_user(uid)
    total_users = await get_total_users()
    bar   = prog_bar(len(joined), total)
    text  = (f"👋 <b>Welcome, {name}!</b>\n\n"
             f"🏅 Badge: {user['badge']}\n"
             f"⭐ Balance: <b>{user['balance']:,} Stars</b>\n"
             f"👥 Referrals: <b>{user['referrals']}</b>\n\n"
             f"📊 Channels: {bar}\n\n"
             f"👤 Total Members: <b>{total_users:,}</b>")
    await msg.answer(text, reply_markup=main_kb(), parse_mode="HTML")

# ---------- Check channels ----------
@router.callback_query(F.data == "check_channels")
async def check_cb(call: CallbackQuery):
    uid = call.from_user.id
    joined, not_joined = await check_channels(call.bot, uid)
    total = len(REQUIRED_CHANNELS)
    if not_joined:
        text = "📌 <b>Channel Status</b>\n\n"
        for ch in REQUIRED_CHANNELS:
            text += f"{'✅' if ch in joined else '❌'} {ch['name']}\n"
        text += f"\n📊 {prog_bar(len(joined), total)}"
        await call.message.edit_text(text, reply_markup=channel_kb(not_joined), parse_mode="HTML")
        await call.answer("❌ Not done yet!")
    else:
        await call.answer("✅ All channels verified!")
        user = await get_user(uid)
        total_users = await get_total_users()
        text = (f"👋 <b>Welcome, {call.from_user.full_name}!</b>\n\n"
                f"🏅 Badge: {user['badge']}\n"
                f"⭐ Balance: <b>{user['balance']:,} Stars</b>\n"
                f"👥 Referrals: <b>{user['referrals']}</b>\n\n"
                f"👤 Total Members: <b>{total_users:,}</b>")
        await call.message.edit_text(text, reply_markup=main_kb(), parse_mode="HTML")

# ---------- Main menu ----------
@router.callback_query(F.data == "main_menu")
async def main_menu_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Send /start first!", show_alert=True); return
    total_users = await get_total_users()
    text = (f"🏠 <b>Main Menu</b>\n\n"
            f"👤 {call.from_user.full_name}\n"
            f"🏅 {user['badge']}\n"
            f"⭐ Balance: <b>{user['balance']:,} Stars</b>\n"
            f"👥 Referrals: <b>{user['referrals']}</b>\n\n"
            f"👤 Total Members: <b>{total_users:,}</b>")
    await call.message.edit_text(text, reply_markup=main_kb(), parse_mode="HTML")
    await call.answer()

# ---------- Balance ----------
@router.callback_query(F.data == "balance")
async def balance_cb(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    text = (f"💰 <b>Your Balance</b>\n\n"
            f"⭐ Current: <b>{user['balance']:,} Stars</b>\n"
            f"💰 Total Earned: <b>{user['total_earned']:,} Stars</b>\n"
            f"👥 Referrals: <b>{user['referrals']}</b>\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 Withdraw requires:\n"
            f"• Min {MIN_WITHDRAW_STARS} Stars\n"
            f"• Min {MIN_WITHDRAW_REFS} referrals")
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

# ---------- Referral ----------
@router.callback_query(F.data == "referral")
async def referral_cb(call: CallbackQuery):
    uid  = call.from_user.id
    user = await get_user(uid)
    binfo = await call.bot.get_me()
    link  = f"https://t.me/{binfo.username}?start={uid}"
    refs  = user["referrals"]
    nexts = next((m for m in [10,50,100] if m > refs), None)
    ntext = f"🎯 Next milestone: <b>{nexts} refs</b>" if nexts else "🏆 All milestones done!"
    text  = (f"👥 <b>Referral System</b>\n\n"
             f"🔗 Your link:\n<code>{link}</code>\n\n"
             f"👤 Referrals: <b>{refs}</b>\n"
             f"⭐ Earned: <b>{refs*REFERRAL_REWARD:,} Stars</b>\n\n"
             f"{ntext}\n\n"
             f"━━━━━━━━━━━━━━━\n"
             f"🎁 Milestones:\n"
             f"10 refs → +50 Stars + 🥈\n"
             f"50 refs → +200 Stars + 🥇\n"
             f"100 refs → +500 Stars + 👑")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Share Link",
                              url=f"https://t.me/share/url?url={link}&text=🌟 Join and earn Telegram Stars!")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# ---------- Profile ----------
@router.callback_query(F.data == "profile")
async def profile_cb(call: CallbackQuery):
    u = await get_user(call.from_user.id)
    text = (f"⚙️ <b>Your Profile</b>\n\n"
            f"🆔 ID: <code>{u['user_id']}</code>\n"
            f"👤 Name: {u['full_name']}\n"
            f"🏅 Badge: {u['badge']}\n"
            f"⭐ Balance: <b>{u['balance']:,} Stars</b>\n"
            f"💰 Total Earned: {u['total_earned']:,} Stars\n"
            f"👥 Referrals: {u['referrals']}\n"
            f"🔥 Streak: {u['streak']} days\n"
            f"📅 Joined: {u['joined_date'][:10]}")
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

# ---------- Daily Bonus ----------
@router.callback_query(F.data == "daily")
async def daily_cb(call: CallbackQuery):
    uid  = call.from_user.id
    user = await get_user(uid)
    if not can_claim(user["last_daily"]):
        await call.message.edit_text(
            f"🎁 <b>Daily Bonus</b>\n\n"
            f"⏰ Already claimed today!\n"
            f"🔥 Streak: <b>{user['streak']} days</b>\n\n"
            f"Come back tomorrow! 💫",
            reply_markup=back_kb(), parse_mode="HTML")
        await call.answer("Already claimed!"); return

    last = user["last_daily"]
    cur_streak = user["streak"]
    if last:
        diff = (date.today() - date.fromisoformat(last)).days
        cur_streak = (cur_streak + 1) if diff == 1 else 1
    else:
        cur_streak = 1

    reward = streak_reward(cur_streak)
    await claim_daily_db(uid, reward, cur_streak)
    updated = await get_user(uid)
    fire = "🔥" * min(cur_streak, 7)
    text = (f"🎁 <b>Daily Bonus Claimed!</b>\n\n"
            f"⭐ +{reward} Stars\n"
            f"{fire} Day {min(cur_streak,7)}/7\n\n"
            f"💰 New Balance: <b>{updated['balance']:,} Stars</b>")
    if cur_streak >= 7:
        text += "\n\n🏆 <b>7-Day streak! Max reward!</b>"
    else:
        text += f"\n\n💡 Tomorrow: +{streak_reward(cur_streak+1)} Stars"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer(f"✅ +{reward} Stars!")

# ---------- Spin Wheel ----------
@router.callback_query(F.data == "spin")
async def spin_cb(call: CallbackQuery):
    uid = call.from_user.id
    last = await get_last_spin(uid)
    if last:
        diff_h = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 3600
        if diff_h < 6:
            h, m = int(6-diff_h), int(((6-diff_h) % 1)*60)
            await call.message.edit_text(
                f"🎰 <b>Spin Wheel</b>\n\n⏰ Next spin in: <b>{h}h {m}m</b>\n\nSpin every 6 hours!",
                reply_markup=back_kb(), parse_mode="HTML")
            await call.answer("⏰ Not ready yet!"); return

    reward = random.choices(SPIN_REWARDS, weights=SPIN_WEIGHTS, k=1)[0]
    await log_spin_db(uid, reward)
    updated = await get_user(uid)
    slots = random.choices(["⭐","💎","🌟","✨","🎁","💰","🔥","🎯"], k=3)
    text = (f"🎰 <b>Spin Result!</b>\n\n"
            f"┌────────────┐\n"
            f"│ {slots[0]}  {slots[1]}  {slots[2]} │\n"
            f"└────────────┘\n\n"
            f"🎉 Won: <b>+{reward} Stars!</b>\n"
            f"💰 Balance: <b>{updated['balance']:,} Stars</b>\n"
            f"⏰ Next spin: 6 hours")
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer(f"🎉 +{reward} Stars!")

# ---------- Tasks ----------
@router.callback_query(F.data == "tasks")
async def tasks_cb(call: CallbackQuery):
    tasks = await get_tasks()
    if not tasks:
        await call.message.edit_text(
            "📋 <b>Tasks</b>\n\nNo tasks available right now. Check back later!",
            reply_markup=back_kb(), parse_mode="HTML")
        await call.answer(); return
    await call.message.edit_text(
        f"📋 <b>Task Marketplace</b>\n\n{len(tasks)} tasks available. Tap to view:",
        reply_markup=task_list_kb(tasks), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("task_"))
async def task_detail(call: CallbackQuery):
    tid   = int(call.data.split("_")[1])
    tasks = await get_tasks()
    task  = next((t for t in tasks if t["task_id"] == tid), None)
    if not task:
        await call.answer("Task not found!", show_alert=True); return
    done  = await task_done(call.from_user.id, tid)
    text  = (f"📌 <b>{task['title']}</b>\n\n"
             f"📝 {task['description']}\n\n"
             f"⭐ Reward: <b>{task['reward']} Stars</b>\n"
             f"🔖 Type: {task['task_type']}\n"
             f"📊 Status: {'✅ Done' if done else '⏳ Pending'}")
    await call.message.edit_text(text, reply_markup=task_action_kb(tid, task["task_link"], done), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("done_"))
async def mark_done(call: CallbackQuery):
    tid   = int(call.data.split("_")[1])
    tasks = await get_tasks()
    task  = next((t for t in tasks if t["task_id"] == tid), None)
    if not task:
        await call.answer("Task not found!", show_alert=True); return
    ok = await complete_task_db(call.from_user.id, tid, task["reward"])
    if ok:
        user = await get_user(call.from_user.id)
        await call.message.edit_text(
            f"🎉 <b>Task Completed!</b>\n\n"
            f"📌 {task['title']}\n"
            f"⭐ +{task['reward']} Stars\n\n"
            f"💰 Balance: <b>{user['balance']:,} Stars</b>",
            reply_markup=back_kb(), parse_mode="HTML")
        await call.answer(f"✅ +{task['reward']} Stars!")
    else:
        await call.answer("⚠️ Already completed!", show_alert=True)

@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer("Already completed!", show_alert=True)

# ---------- Leaderboard ----------
@router.callback_query(F.data == "leaderboard")
async def lb_cb(call: CallbackQuery):
    await call.message.edit_text(
        "🏆 <b>Leaderboard</b>\n\nChoose category:",
        reply_markup=lb_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.in_({"lb_refs", "lb_earn"}))
async def lb_data(call: CallbackQuery):
    by_refs = call.data == "lb_refs"
    col     = "referrals" if by_refs else "total_earned"
    title   = "👥 Top Referrers" if by_refs else "⭐ Top Earners"
    users   = await get_leaderboard(col)
    medals  = ["🥇","🥈","🥉"]
    text    = f"🏆 <b>{title}</b>\n\n"
    for i, u in enumerate(users, 1):
        m = medals[i-1] if i <= 3 else f"{i}."
        n = f"@{u['username']}" if u["username"] else u["full_name"]
        v = u["referrals"] if by_refs else u["total_earned"]
        text += f"{m} {n} — {'👥' if by_refs else '⭐'} {v:,}\n"
    me = await get_user(call.from_user.id)
    if me:
        all_u = await get_leaderboard(col, 9999)
        rank  = next((i+1 for i,u in enumerate(all_u) if u["user_id"]==call.from_user.id), None)
        if rank:
            v = me["referrals"] if by_refs else me["total_earned"]
            text += f"\n👤 Your rank: <b>#{rank}</b> ({v:,})"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

# ---------- Withdraw ----------
@router.callback_query(F.data == "withdraw")
async def withdraw_cb(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    ok   = user["balance"] >= MIN_WITHDRAW_STARS and user["referrals"] >= MIN_WITHDRAW_REFS
    text = (f"💸 <b>Withdrawal</b>\n\n"
            f"⭐ Balance: <b>{user['balance']:,}</b>\n"
            f"👥 Referrals: <b>{user['referrals']}</b>\n\n"
            f"Requirements:\n"
            f"{'✅' if user['balance'] >= MIN_WITHDRAW_STARS else '❌'} Min {MIN_WITHDRAW_STARS} Stars\n"
            f"{'✅' if user['referrals'] >= MIN_WITHDRAW_REFS else '❌'} Min {MIN_WITHDRAW_REFS} referrals\n"
            f"✅ YouTube subscribed\n\n"
            f"{'✅ <b>You are eligible!</b>' if ok else '❌ <b>Not eligible yet.</b>'}")
    await call.message.edit_text(text, reply_markup=wd_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "req_wd")
async def req_wd(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if user["balance"] < MIN_WITHDRAW_STARS:
        await call.answer(f"❌ Need {MIN_WITHDRAW_STARS} Stars min!", show_alert=True); return
    if user["referrals"] < MIN_WITHDRAW_REFS:
        await call.answer(f"❌ Need {MIN_WITHDRAW_REFS} referrals min!", show_alert=True); return
    await call.message.edit_text(
        f"📺 <b>Subscribe to our YouTube first!</b>\n\n1. Subscribe below\n2. Tap 'I Subscribed'",
        reply_markup=yt_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "yt_ok")
async def yt_ok(call: CallbackQuery, state: FSMContext):
    user = await get_user(call.from_user.id)
    await call.message.edit_text(
        f"💸 <b>Enter withdrawal amount</b>\n\n"
        f"💰 Available: <b>{user['balance']:,} Stars</b>\n"
        f"📌 Min: {MIN_WITHDRAW_STARS} Stars\n\n"
        f"Type the amount:",
        reply_markup=back_kb(), parse_mode="HTML")
    await state.set_state(WDState.amount)
    await call.answer()

@router.message(WDState.amount)
async def wd_amount(msg: Message, state: FSMContext):
    try: amount = int(msg.text.strip())
    except:
        await msg.answer("❌ Enter a valid number!"); return
    user = await get_user(msg.from_user.id)
    if amount < MIN_WITHDRAW_STARS:
        await msg.answer(f"❌ Minimum is {MIN_WITHDRAW_STARS} Stars!"); return
    if amount > user["balance"]:
        await msg.answer(f"❌ You only have {user['balance']} Stars!"); return
    await state.update_data(amount=amount)
    await msg.answer("👤 Now send your <b>Telegram username</b> (e.g. @yourusername):", parse_mode="HTML")
    await state.set_state(WDState.username)

@router.message(WDState.username)
async def wd_username(msg: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(username=msg.text.strip())
    await msg.answer(
        f"💸 <b>Confirm?</b>\n\n⭐ {data['amount']} Stars → {msg.text.strip()}",
        reply_markup=confirm_wd_kb(data["amount"]), parse_mode="HTML")
    await state.set_state(WDState.confirm)

@router.callback_query(F.data.startswith("cwf_"))
async def confirm_wd(call: CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    amount = data.get("amount")
    uname  = data.get("username")
    if not amount or not uname:
        await call.answer("Session expired!", show_alert=True); await state.clear(); return
    user = await get_user(call.from_user.id)
    if user["balance"] < amount:
        await call.answer("❌ Not enough balance!", show_alert=True); await state.clear(); return
    await create_withdrawal(call.from_user.id, amount, uname)
    await state.clear()
    await call.message.edit_text(
        f"✅ <b>Withdrawal Requested!</b>\n\n"
        f"⭐ {amount} Stars → {uname}\n"
        f"⏳ Status: Pending\n\n"
        f"Processing: 24-48 hours",
        reply_markup=back_kb(), parse_mode="HTML")
    # Notify admins
    pends = await get_pending_wd()
    last  = pends[-1] if pends else None
    for aid in ADMIN_IDS:
        try:
            await call.bot.send_message(
                aid,
                f"💸 <b>New Withdrawal!</b>\n\n"
                f"👤 {call.from_user.full_name} ({call.from_user.id})\n"
                f"📱 {uname}\n⭐ {amount} Stars\n🆔 #{last['id'] if last else '?'}",
                reply_markup=admin_wd_kb(last["id"] if last else 0),
                parse_mode="HTML")
        except: pass
    await call.answer("✅ Request sent!")

@router.callback_query(F.data == "wd_history")
async def wd_history(call: CallbackQuery):
    hist = await get_user_wd(call.from_user.id)
    if not hist:
        await call.message.edit_text("📜 No withdrawals yet.", reply_markup=back_kb()); await call.answer(); return
    emoji = {"pending":"⏳","approved":"✅","rejected":"❌","paid":"💰"}
    text  = "📜 <b>Withdrawal History</b>\n\n"
    for w in hist:
        text += f"{emoji.get(w['status'],'❓')} <b>{w['amount']} Stars</b> — {w['status'].upper()}\n   {w['requested_at'][:10]} | {w['tg_username']}\n\n"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

# Admin approve/reject
@router.callback_query(F.data.startswith("approve_"))
async def approve_wd(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Admin only!", show_alert=True); return
    wid = int(call.data.split("_")[1])
    await update_wd(wid, "paid")
    await call.message.edit_text(call.message.text + "\n\n✅ <b>APPROVED & PAID</b>", parse_mode="HTML")
    await call.answer("✅ Approved!")

@router.callback_query(F.data.startswith("reject_"))
async def reject_wd(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Admin only!", show_alert=True); return
    wid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)) as cur:
            w = await cur.fetchone()
        if w:
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (w[2], w[1]))
            await db.commit()
    await update_wd(wid, "rejected")
    await call.message.edit_text(call.message.text + "\n\n❌ <b>REJECTED — Stars refunded</b>", parse_mode="HTML")
    await call.answer("❌ Rejected!")

# ---------- News / Support ----------
@router.callback_query(F.data == "news")
async def news_cb(call: CallbackQuery):
    await call.message.edit_text(
        "📢 <b>News</b>\n\n🆕 Bot is live! Start earning.\n🎁 Daily bonus resets every day.\n🏆 Leaderboard resets weekly.",
        reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "support")
async def support_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🆘 <b>Support</b>\n\n👤 Admin: @your_admin_username\n⏰ Response: 24 hours\n\n🆔 Your ID: <code>{call.from_user.id}</code>",
        reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

# ============================================================
#  ADMIN COMMANDS
# ============================================================
@router.message(Command("admin"))
async def admin_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    total = await get_total_users()
    pends = await get_pending_wd()
    await msg.answer(
        f"🛠 <b>Admin Panel</b>\n\n"
        f"👥 Users: <b>{total:,}</b>\n"
        f"💸 Pending WD: <b>{len(pends)}</b>\n\n"
        f"/broadcast — Message all users\n"
        f"/addtask — Add new task\n"
        f"/pendingwd — Pending withdrawals\n"
        f"/ban [id] — Ban user\n"
        f"/unban [id] — Unban user\n"
        f"/addstars [id] [amount] — Give stars\n"
        f"/userinfo [id] — User details\n"
        f"/stats — Statistics",
        parse_mode="HTML")

@router.message(Command("stats"))
async def stats_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    total = await get_total_users()
    pends = await get_pending_wd()
    await msg.answer(f"📊 Users: {total:,} | Pending WD: {len(pends)}")

@router.message(Command("broadcast"))
async def broadcast_cmd(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await msg.answer("📢 Send your broadcast message:")
    await state.set_state(AdminState.broadcast)

@router.message(AdminState.broadcast)
async def do_broadcast(msg: Message, state: FSMContext):
    await state.clear()
    ids   = await get_all_user_ids()
    sent  = 0
    for uid in ids:
        try:
            await msg.bot.send_message(uid, f"📢 <b>Announcement</b>\n\n{msg.text}", parse_mode="HTML")
            sent += 1
        except: pass
    await msg.answer(f"✅ Broadcast sent to {sent}/{len(ids)} users!")

@router.message(Command("pendingwd"))
async def pending_wd_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    pends = await get_pending_wd()
    if not pends:
        await msg.answer("✅ No pending withdrawals!"); return
    for w in pends:
        await msg.answer(
            f"💸 <b>WD #{w['id']}</b>\n👤 {w['user_id']}\n📱 {w['tg_username']}\n⭐ {w['amount']}\n📅 {w['requested_at'][:16]}",
            reply_markup=admin_wd_kb(w["id"]), parse_mode="HTML")

@router.message(Command("ban"))
async def ban_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /ban [user_id]"); return
    await db_run("UPDATE users SET is_banned=1 WHERE user_id=?", (int(args[1]),))
    await msg.answer(f"🚫 User {args[1]} banned!")

@router.message(Command("unban"))
async def unban_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /unban [user_id]"); return
    await db_run("UPDATE users SET is_banned=0 WHERE user_id=?", (int(args[1]),))
    await msg.answer(f"✅ User {args[1]} unbanned!")

@router.message(Command("addstars"))
async def addstars_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    args = msg.text.split()
    if len(args) < 3:
        await msg.answer("Usage: /addstars [user_id] [amount]"); return
    await add_stars(int(args[1]), int(args[2]))
    await msg.answer(f"✅ Added {args[2]} Stars to {args[1]}!")

@router.message(Command("userinfo"))
async def userinfo_cmd(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /userinfo [user_id]"); return
    u = await get_user(int(args[1]))
    if not u:
        await msg.answer("❌ User not found!"); return
    await msg.answer(
        f"👤 <b>User Info</b>\n\n"
        f"🆔 {u['user_id']}\n👤 {u['full_name']}\n🏅 {u['badge']}\n"
        f"⭐ {u['balance']:,} Stars\n👥 {u['referrals']} refs\n"
        f"🚫 Banned: {'Yes' if u['is_banned'] else 'No'}",
        parse_mode="HTML")

@router.message(Command("addtask"))
async def addtask_cmd(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await msg.answer("📋 Task title:"); await state.set_state(AdminState.task_title)

@router.message(AdminState.task_title)
async def at_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text)
    await msg.answer("📝 Description:"); await state.set_state(AdminState.task_desc)

@router.message(AdminState.task_desc)
async def at_desc(msg: Message, state: FSMContext):
    await state.update_data(desc=msg.text)
    await msg.answer("⭐ Reward (Stars):"); await state.set_state(AdminState.task_reward)

@router.message(AdminState.task_reward)
async def at_reward(msg: Message, state: FSMContext):
    try:
        await state.update_data(reward=int(msg.text))
        await msg.answer("🔖 Type (YouTube/Telegram/Website):"); await state.set_state(AdminState.task_type)
    except: await msg.answer("❌ Number only!")

@router.message(AdminState.task_type)
async def at_type(msg: Message, state: FSMContext):
    await state.update_data(ttype=msg.text)
    await msg.answer("🔗 Link (URL):"); await state.set_state(AdminState.task_link)

@router.message(AdminState.task_link)
async def at_link(msg: Message, state: FSMContext):
    data = await state.get_data(); await state.clear()
    await add_task_db(data["title"], data["desc"], data["reward"], data["ttype"], msg.text)
    await msg.answer(f"✅ Task added: {data['title']} (+{data['reward']} Stars)")

# ============================================================
#  MAIN
# ============================================================
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("🤖 Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
