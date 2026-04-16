#---------- © sᴛᴀʟᴋᴇʀ@hehe_stalker
#---------- ᴘʀᴏJᴇᴄᴛ - ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛ sᴇʟʟɪɴɢ ʙᴏᴛ
#-------------------------------------------------------
import os
import asyncio
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject
import html
from html import escape
from bson import ObjectId
from aiogram.types import CopyTextButton
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pymongo import MongoClient
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiogram.utils.deep_linking import create_start_link
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
import re
from aiogram import types
import random
from aiogram.types import InputMediaVideo
from recharge_flow import register_recharge_handlers
from mustjoin import check_join
from config import BOT_TOKEN, ADMIN_IDS

# ================= MongoDB Setup =================
MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv:=Vth0"
client = MongoClient(MONGO_URI)
db = client["SparshStore"]
users_col = db["users"]
orders_col = db["orders"]
countries_col = db["countries"]
numbers_col = db["numbers"]
crypto_col = db["crypto_invoices"]
withdrawals_col = db["withdrawals"]

#--------- Config : don't use @
BOTUSER = "TgIdStoreProbot"
SUPPORT = "The_destiny_world"
USAGE = "SellingLogs"
OWNER = "oye_sparsh"
UPDATES= "SparshSelling"
CHANNEL="CHANNEL"
SALESLOG = "SellingLogs"
ADMINLOG = "-1003790606640"
# ================= Ban Middleware =================
class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            user_doc = users_col.find_one({"_id": user.id})
            if user_doc and user_doc.get("banned", False):
                # If event is a message, reply. If callback, answer alert.
                if isinstance(event, Message):
                    await event.answer("🚫 <b>You are banned from using this bot.</b>", parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 You are banned from using this bot.", show_alert=True)
                return # Stop processing
        return await handler(event, data)
        
# ================= Bot Setup =================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
dp.update.middleware(BanCheckMiddleware()) # <--- ADD THIS LINE


# ================= FSM =================
class AddSession(StatesGroup):
    waiting_country = State()
    waiting_number = State()
    waiting_otp = State()
    waiting_password = State()
    waiting_next_action = State()   # ✅ REQUIRED

class SellSession(StatesGroup):
    # ... existing states ...
    waiting_sell_number = State()

class WithdrawState(StatesGroup):
    waiting_upi = State()
    waiting_amount = State()

class AdminTxnState(StatesGroup):
    waiting_txn = State()
    

# ================ Helpers =================
def get_or_create_user(user_id: int, username: str | None):
    user = users_col.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "username": username or None, "balance": 0.0}
        users_col.insert_one(user)
    return user

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_user_balance(user_id):
    user = users_col.find_one({"_id": user_id})
    return user.get("balance", 0) if user else 0
# ================ Automatic OTP Listener =================
# ================ Automatic OTP Listener =================
async def otp_listener(number_doc, user_id, message_id):
    string_session = number_doc.get("string_session")
    if not string_session:
        return

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.connect()

    try:
        if not await client.is_user_authorized():
            return

        pattern = re.compile(r"\b\d{5}\b")  # OTP pattern

        async for msg in client.iter_messages(777000, limit=10):
            if not msg.message:
                continue

            match = pattern.search(msg.message)
            if not match:
                continue

            # ===== OTP FOUND =====
            code = match.group(0)
            password_text = number_doc.get("password") or "None"

            

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Copy OTP",
                            copy_text=CopyTextButton(text=code)
                        ),
                        InlineKeyboardButton(
                            text="Copy Pass",
                            copy_text=CopyTextButton(text=password_text)
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="• Get Code Again •",
                            callback_data=f"get_otp:{number_doc['number']}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="Remove Bot Session",
                            callback_data=f"logout_bot:{number_doc['number']}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📱 Manage Devices",
                            callback_data=f"manage_devices:{number_doc['number']}"
                        )
                    ],
                    
                    
                    
                ]
            )

            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=(
                    "<pre>Order Completed ✅</pre>\n"
                    f"✅ 𝐍𝗨𝐌𝐁𝐄𝐑 - <code>+{number_doc['number']}</code>\n"
                    f"💬 𝐂𝐎𝐃𝐄 - <code>{code}</code>\n"
                    f"💬 𝐏𝐀𝐒𝐒 - <code>{password_text}</code>\n"
                ),
                parse_mode="HTML",
                reply_markup=kb
            )

            # ===== USER & LOGGING =====
            user = users_col.find_one({"_id": user_id}) or {}
            buyer_name = user.get("username") or f"User {user_id}"
            balance = user.get("balance", "N/A")

            country = number_doc.get("country", "Unknown")
            price = number_doc.get("price", "N/A")
            number = str(number_doc.get("number", "Unknown"))

            if number != "Unknown":
                if not number.startswith("+"):
                    number = f"+{number}"
                masked_number = number[:6] + "•••••"
            else:
                masked_number = "Hidden"

            channel_message = (
                f"<pre><u>✅ <b>New Number Purchase Successful</b></u></pre>\n\n"
                f"➖ <b><u>Country:</u></b> {country}\n"
                f"➖ <b><u>Application:</u> Теlegгам 🍷</b>\n\n"
                f"➕ <b>Number: {masked_number} 📞</b>\n"
                f"➕ <b>OTP:</b> <span class='tg-spoiler'>{code}</span> 💬\n"
                f"➕ <b>Server:</b> (1) 🥂\n"
                f"➕ <b>Password:</b> <span class='tg-spoiler'>{password_text}</span> 🔐\n\n"
                f"<b>• @{BOTUSER}|| @{CHANNEL}</b>"
            )

            buy_button = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="• Buy Now •",
                            url=f"https://t.me/{BOTUSER}?start=starting"
                        )
                    ]
                ]
            )

            await bot.send_message(
                SALESLOG,
                channel_message,
                parse_mode="HTML",
                reply_markup=buy_button
            )

            admin_message = (
                f"<pre>📢 New Purchase Alert</pre>\n\n"
                f"<b>• Application:</b> Telegram\n"
                f"<b>• Country:</b> {country}\n"
                f"<b>• Number:</b> {number}\n"
                f"<b>• OTP:</b> <code>{code}</code>\n"
                f"➖ <b>Password:</b> <span class='tg-spoiler'>{password_text}</span> 🔐\n\n"
                f"<b>👤 User:</b> @{buyer_name} (<code>{user_id}</code>)\n"
                f"<b>💰 Balance:</b> ₹{balance}"
            )
            userbutton = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="USER ID",
                            url=f"tg://openmessage?user_id={user_id}"
                        )
                    ]
                ]
            )

            await bot.send_message(
                ADMINLOGS,
                admin_message,
                parse_mode="HTML",
                reply_markup=userbutton
            )

            # ===== SAVE OTP =====
            numbers_col.update_one(
                {"_id": number_doc["_id"]},
                {
                    "$set": {
                        "last_otp": code,
                        "otp_fetched_at": datetime.now(timezone.utc)
                    }
                }
            )

            break  # stop after OTP

        await asyncio.sleep(1)
    except Exception as e:
        await callback.answer(
            user_id, "💬 No new code Received, Try sending new code first ")

    finally:
        await client.disconnect()
        

  

@dp.callback_query(F.data.startswith("manage_devices:"))
async def manage_devices(call: CallbackQuery):
    number = call.data.split(":", 1)[1]
    doc = numbers_col.find_one({"number": number})

    if not doc or not doc.get("string_session"):
        return await call.answer("❌ No active session", show_alert=True)

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(
        StringSession(doc["string_session"]),
        api_id,
        api_hash
    )
    await client.connect()

    try:
        sessions = await client(GetAuthorizationsRequest())
    except Exception:
        await client.disconnect()
        return await call.answer("❌ Failed to fetch sessions", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for s in sessions.authorizations:
        if s.current:
            continue  # cannot remove current via hash

        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{s.device_model} | {s.platform}",
                callback_data=f"kill_session:{number}:{s.hash}"
            )
        ])

    await client.disconnect()

    if not kb.inline_keyboard:
        return await call.message.answer("✅ No removable sessions")

    await call.message.answer(
        "📱 Click any session to remove:",
        reply_markup=kb
    )


#-----Temrinate sessuon
@dp.callback_query(F.data.startswith("kill_session:"))
async def kill_session(call: CallbackQuery):
    _, number, session_hash = call.data.split(":")
    doc = numbers_col.find_one({"number": number})

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(
        StringSession(doc["string_session"]),
        api_id,
        api_hash
    )
    await client.connect()

    try:
        await client(ResetAuthorizationRequest(hash=int(session_hash)))
        await call.answer("✅ Session removed", show_alert=True)
    except Exception:
        await call.answer("❌ Cannot remove session", show_alert=True)
    finally:
        await client.disconnect()

    #&------Logout bot

@dp.callback_query(F.data.startswith("logout_bot:"))
async def logout_bot(call: CallbackQuery):
    number = call.data.split(":", 1)[1]
    doc = numbers_col.find_one({"number": number})

    if not doc or not doc.get("string_session"):
        return await call.answer("❌ No active session", show_alert=True)

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(doc["string_session"]), api_id, api_hash)
    await client.connect()

    try:
        await client.log_out()
    finally:
        await client.disconnect()

    # 🔥 VERY IMPORTANT
    numbers_col.update_one(
        {"number": number},
        {
            "$set": {
                "active": False,   # session dead
                "used": True
            },
            "$unset": {
                "string_session": ""
            }
        }
    )

    await call.message.answer(
        "✅ Bot session has been logged out\nOTP polling closed for this number"
    )

# ================ START =================
@dp.message(Command("start"))
async def cmd_start(m: Message):
    
    
    args = m.text.split()
    referred_by = None
    is_ref_link = False

    # Check if user started via referral link
    if len(args) > 1 and args[1].startswith("ref"):
        is_ref_link = True
        try:
            referred_by = int(args[1][3:])
        except:
            referred_by = None

    # Check if user already exists
    user = users_col.find_one({"_id": m.from_user.id})

    if user:
        # Existing user
        if is_ref_link:
            # Notify referrer if this user was referred just now
            if "referred_by" not in user and referred_by and referred_by != m.from_user.id:
                users_col.update_one({"_id": m.from_user.id}, {"$set": {"referred_by": referred_by}})
                
                # Notify the referrer
                try:
                    ref_user = users_col.find_one({"_id": referred_by})
                    if ref_user:
                        await bot.send_message(
                            chat_id=referred_by,
                            text=(
                                f"👋 <b>New Referral!</b>\n"
                                f"@{m.from_user.username or m.from_user.full_name} just started the bot using your referral link.\n\n"
                                f"💰 You’ll now earn <b>2%</b> whenever they add balance!"
                            ),
                            parse_mode="HTML"
                        )
                except Exception as e:
                    print("Referral notify error:", e)

            await m.answer("🌟")
        else:
            
            user_data = {
                "_id": m.from_user.id,
                "username": m.from_user.username or None,
                "balance": 0.0,
                "joined_at": datetime.now(timezone.utc),
            }
            
            if referred_by and referred_by != m.from_user.id:
                user_data["referred_by"] = referred_by
                users_col.insert_one(user_data)
                
                await m.answer("you have been counted in New Users list! .")

        # Notify referrer if user was referred
        if referred_by and referred_by != m.from_user.id:
            try:
                ref_user = users_col.find_one({"_id": referred_by})
                if ref_user:
                    await bot.send_message(
                        chat_id=referred_by,
                        text=(
                            f"👋 <b>New Referral!</b>\n"
                            f"@{m.from_user.username or m.from_user.full_name} just started the bot using your referral link.\n\n"
                            f"💰 You’ll earn <b>2%</b> whenever they add balance!"
                        ),
                        parse_mode="HTML"
                    )
            except Exception as e:
                print("Referral notify error:", e)

    if not await check_join(bot, m):
        return

    # Ensure user exists in DB
    get_or_create_user(m.from_user.id, m.from_user.username)
    user_id = m.from_user.id
    full_name = m.from_user.full_name  # always use the name
    safe_name = escape(full_name)
    user_mention = f"<a href='tg://user?id={user_id}'>{safe_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"₹{user['balance']:.2f} " if user else "₹0 "
    
# ================= Main Start Menu =================
    caption = (
        f"<blockquote> Hey, {user_mention}!</blockquote>\n"
        f"<b>𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖳𝗈 Account Robot- 𝖥𝖺𝗌𝗍𝖾𝗌𝗍 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖲𝖾𝗅𝗅𝖾𝗋 𝖡𝗈𝗍🥂</b>\n\n"
        f"<b>🚀 𝖤𝗇𝗃𝗈𝗒 𝖥𝖺𝗌𝗍 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖻𝗎𝗒𝗂𝗇𝗀 𝖤𝗑𝗉𝖾𝗋𝗂𝖾𝗇𝖼𝖾 !\n------------------------------------------------\n• Support - @{SUPPORT}\n• Sales - @{LOGS}</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Balance", callback_data="balance"),
            InlineKeyboardButton(text="🛒 Buy Account", callback_data="buy_server1")
        ],
        
        [
            InlineKeyboardButton(text="🥂 Sell Account", callback_data="sell")
            
        ],
        [
            InlineKeyboardButton(text="💳 Recharge", callback_data="recharge"),
            InlineKeyboardButton(text="👤 Account", callback_data="stats")
        ],
         [
            InlineKeyboardButton(text="Redeem 🎉", callback_data="redeem"),
            InlineKeyboardButton(text="📑 History", callback_data="history")

            ],
        [
            InlineKeyboardButton(text="➕ More..", callback_data="more_menu"),
            InlineKeyboardButton(text="⚡ Refer", callback_data="refer")
    
        ]
       
    ])
    await m.answer(caption, parse_mode="HTML", reply_markup=kb)

    



# ================= More.. Menu =================
@dp.callback_query(lambda cq: cq.data == "more_menu")
async def more_menu(cq: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sales Log", url=f"https://t.me/SparshSalesLogs")],
        [InlineKeyboardButton(text="📑 History", callback_data="history")],
        [InlineKeyboardButton(text="Support", url=f"https://t.me/oye_Sparsh")],
        [InlineKeyboardButton(text="About Account", callback_data="stats")],
        [InlineKeyboardButton(text="Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton(text="Contact Support", url=f"https://t.me/oye_Sparsh")],
        [InlineKeyboardButton(text="How to Buy Account", url=f"https://t.me/oye_Sparsh")],
        [InlineKeyboardButton(text="How to Sell Account", url=f"https://t.me/oye_sparsh")],
        [InlineKeyboardButton(text="How to Recharge", url=f"https://t.me/oye_sparsh")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ])

    await cq.message.edit_text(
        "<b>View more services and help :</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await cq.answer()  # optional: remove "loading..." notification


#=============== Back Button =================
@dp.callback_query(lambda cq: cq.data == "back_main")
async def back_main(cq: CallbackQuery):
    if not await check_join(bot, cq):
        await cq.answer("❗ Join the channel first", show_alert=True)
        return
    user_id = cq.from_user.id
    full_name = cq.from_user.full_name  # always use the name
    safe_name = escape(full_name)
    user_mention = f"<a href='tg://user?id={user_id}'>{safe_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"{user['balance']:.2f} ₹" if user else "0 ₹"
    
    # Rebuild main menu dynamically (reuse your send_main_menu logic)
    photo_url = "https://files.catbox.moe/scgaoh.jpg"
    caption = (
        f"<blockquote> Hey, {user_mention}!</blockquote>\n"
        f"<b>𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖳𝗈 Account Robot- 𝖥𝖺𝗌𝗍𝖾𝗌𝗍 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖲𝖾𝗅𝗅𝖾𝗋 𝖡𝗈𝗍🥂</b>\n\n"
        f"<b>🚀 𝖤𝗇𝗃𝗈𝗒 𝖥𝖺𝗌𝗍 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖻𝗎𝗒𝗂𝗇𝗀 𝖤𝗑𝗉𝖾𝗋𝗂𝖾𝗇𝖼𝖾 !\n------------------------------------------------\n• Support - @{SUPPORT}\n• Sales - @{LOGS}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Balance", callback_data="balance"),
            InlineKeyboardButton(text="🛒 Buy Account", callback_data="buy_server1")
        ],
        [
            InlineKeyboardButton(text="🥂 Sell Account", callback_data="sell")
        ],
        [
            InlineKeyboardButton(text="💳 Recharge", callback_data="recharge"),
            InlineKeyboardButton(text="👤 Account", callback_data="stats")
        ],
         [
            InlineKeyboardButton(text="Redeem 🎉", callback_data="redeem"),
            InlineKeyboardButton(text="📑 History", callback_data="history")
            
         ],
        [
            InlineKeyboardButton(text="➕ More..", callback_data="more_menu"),
            InlineKeyboardButton(text="⚡ Refer", callback_data="refer")
    
        ]
    ])
    await cq.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    await cq.answer()


#================ Balance =================
@dp.callback_query(F.data == "balance")
async def show_balance(cq: CallbackQuery):
    user = users_col.find_one({"_id": cq.from_user.id})
    await cq.answer(f"💰 Balance: {user['balance']:.2f} ₹" if user else "💰 Balance: 0 ₹", show_alert=True)

@dp.message(Command("balance"))
async def cmd_balance(msg: Message):
    user = users_col.find_one({"_id": msg.from_user.id})
    await msg.answer(f"💰 Balance: {user['balance']:.2f} ₹" if user else "💰 Balance: 0 ₹")


#= ================ Buy Flow =================

# Initial "Buy" message with server selection
@dp.callback_query(lambda c: c.data == "buy")
async def callback_buy(cq: CallbackQuery):
    await cq.answer()
    user = get_or_create_user(cq.from_user.id, cq.from_user.username)  # Fetch user info

    text = (
        f"🍷 <b>Buy Ready Telegram Accounts</b>:\n"
        f"––––––—————––––——–––•\n"
        f"<u>• One-click Telegram account purchase\n"
        f"• 100% activation & code delivery\n"
        f"• All accounts are clean [100% No Spam]\n"
        f"• Request multiple codes for free</u>\n"
        f"<b>• Total balance -</b> ₹{user['balance']}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="◍ Server- 1", callback_data="buy_server1")
    )
    kb.row(
        InlineKeyboardButton(text="◍ Server- 2", callback_data="buy_server2")
    )
    kb.row(InlineKeyboardButton(text="▪️ Previous", callback_data="back_main"))

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


#Server 1 continues to normal country menu
@dp.callback_query(lambda c: c.data == "buy_server1")
async def callback_buy_server1(cq: CallbackQuery):
    await cq.answer()
    await send_country_menu(cq)  # Use the same country menu function


# Server 2 shows alert: out of stock
@dp.callback_query(lambda c: c.data == "buy_server2")
async def callback_buy_server2(cq: CallbackQuery):
    await cq.answer("⚠️ Currently this stock is out of stock!", show_alert=True)


# ================= Country Menu with Pagination =================
COUNTRIES_PER_PAGE = 10

async def send_country_menu(cq: CallbackQuery, page: int = 0):
    countries = await asyncio.to_thread(lambda: list(countries_col.find({})))
    total = len(countries)

    if total == 0:
        return await cq.message.edit_text("❌ No countries available. Admin must add stock first.")
    user_id = cq.from_user.id
    full_name = cq.from_user.full_name  # always use the name
    user_mention = f"<a href='tg://user?id={user_id}'>{full_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"₹{user['balance']:.2f} " if user else "₹0 "

    # Pagination logic
    start = page * COUNTRIES_PER_PAGE
    end = start + COUNTRIES_PER_PAGE
    paginated = countries[start:end]

    kb = InlineKeyboardBuilder()
    for c in paginated:
        kb.button(text=html.escape(c["name"]), callback_data=f"country:{c['name']}")
    kb.adjust(2)

    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="▪️Previous", callback_data=f"countries_page:{page-1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="Next▪️", callback_data=f"countries_page:{page+1}"))
    if nav_buttons:
        kb.row(*nav_buttons)

    # Return to main menu
    kb.row(InlineKeyboardButton(text="▪️Home", callback_data="back_main"))

    text = f"<b><u>Buy SpamFree Telegram accounts:</u></b>\n––––––––––––––————––•\n◍ <u><b>Total balance:</b></u> {balance}  \n<u>◍ Server:</u> Server (1)\n◍ <b>Page </b>{page+1} of {(total - 1)//COUNTRIES_PER_PAGE + 1}\n✅ <a href=\"https://t.me/{LOGS}\">Sucessful Purchases</a>\n➖➖➖➖➖➖➖➖➖➖➖"
    await cq.message.edit_text(text, reply_markup=kb.as_markup(),parse_mode="HTML", disable_web_page_preview=True)


# ================= Country Pagination Callback =================
@dp.callback_query(lambda c: c.data.startswith("countries_page:"))
async def paginate_countries(cq: CallbackQuery):
    _, page_str = cq.data.split(":")
    try:
        page = int(page_str)
    except ValueError:
        page = 0
    await send_country_menu(cq, page)
    await cq.answer()

# =============== Country Selection =================
@dp.callback_query(lambda c: c.data.startswith("country:"))
async def callback_country(cq: CallbackQuery):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)

    country = await asyncio.to_thread(lambda: countries_col.find_one({"name": country_name}))
    if not country:
        return await cq.answer("❌ Country not found", show_alert=True)

    text = (
        f"<b>Click Buy to Purchase an account:</b>\n––––––––––––—————–•\n"
        f"<blockquote> <b>Country: {html.escape(country['name'])}</b> </blockquote>\n"
        f"◍ <b><u>Price</u></b>: ₹{country['price']}\n"
        f"◍ <b><u>Stock</u></b>: {country['stock']}\n"
        f"◍ <b><u>Server</u></b> - (1)\n––––––––––––—————–•"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="▪️ Buy", callback_data=f"buy_now:{country_name}")
    )
    kb.row(
        InlineKeyboardButton(text="▪️ Back", callback_data="buy_server1")
    )

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
# ================= Buy Now Flow =================



# ================= Buy Now: Validation & Terms =================
@dp.callback_query(F.data.startswith("buy_now:"))
async def callback_buy_start(cq: CallbackQuery, state: FSMContext):
    # Clear any previous states to avoid conflicts
    await state.clear()
    
    _, country_name = cq.data.split(":", 1)
    
    # Fetch Data Asynchronously
    country, user = await asyncio.to_thread(lambda: (
        countries_col.find_one({"name": country_name}),
        get_or_create_user(cq.from_user.id, cq.from_user.username)
    ))

    # 1. Validate Country Existence
    if not country:
        return await cq.answer("❌ Country data not found.", show_alert=True)

    country_price = country["price"]
    country_stock = country["stock"]
    user_balance = user.get("balance", 0.0)

    # 2. Validate Stock
    if country_stock < 1:
        return await cq.answer(f"⚠️ Out of Stock! No accounts left for {country_name}.", show_alert=True)

    # 3. Validate Balance (If low, show Recharge prompt immediately)
    if user_balance < country_price:
        text = (
            f"🚫 <b>Insufficient Balance</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Required:</b> ₹{country_price:.2f}\n"
            f"💰 <b>Your Balance:</b> ₹{user_balance:.2f}\n"
            f"📉 <b>Shortage:</b> ₹{country_price - user_balance:.2f}\n\n"
            f"<i>Please recharge your wallet to continue.</i>"
        )
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="💳 Recharge Now", callback_data="recharge"))
        kb.row(InlineKeyboardButton(text="🔙 Back", callback_data=f"country:{country_name}"))
        
        return await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())

    # 4. Show Terms & Confirmation (Balance & Stock are OK)
    terms_text = (
        f"⚠️ <b>Account Buying Terms</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Please review the rules before purchasing <b>1 {country_name}</b> account:\n\n"
        f"🚫 <b>No Refunds:</b> All sales are final.\n"
        f"📨 <b>OTP Policy:</b> Once OTP is received, no return allowed.\n"
        f"❄️ <b>Freeze/Limit:</b> Accounts are fresh; we are not responsible for limits after use.\n"
        f"⏳ <b>Warranty:</b> 10 Minutes to check the account.\n\n"
        f"🏷️ <b>Price:</b> ₹{country_price:.2f}\n"
        f"❓ <b>Do you accept these terms?</b>"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Accept", callback_data=f"confirm_buy:{country_name}"),
        InlineKeyboardButton(text="❌ Decline", callback_data=f"country:{country_name}")
    )
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data=f"country:{country_name}"))

    await cq.message.edit_text(terms_text, parse_mode="HTML", reply_markup=kb.as_markup())


# ================= Purchase Execution (Quantity = 1) =================
@dp.callback_query(F.data.startswith("confirm_buy:"))
async def callback_process_purchase(cq: CallbackQuery, state: FSMContext):
    _, country_name = cq.data.split(":", 1)
    user_id = cq.from_user.id
    quantity = 1  # Hardcoded as per requirement

    # Re-fetch data to ensure stock/balance didn't change while reading terms
    country = countries_col.find_one({"name": country_name})
    user = users_col.find_one({"_id": user_id})

    # --- Safety Checks ---
    if not country:
        return await cq.answer("❌ Error: Country missing.", show_alert=True)
    
    if country["stock"] < 1:
        await cq.answer("⚠️ Just sold out! Stock is now 0.", show_alert=True)
        return await send_country_menu(cq) # Redirect to menu

    if user["balance"] < country["price"]:
        await cq.answer("❌ Insufficient balance.", show_alert=True)
        return # Optionally redirect to recharge

    # --- Fetch Unused Number ---
    # We use find_one_and_update (Atomic operation) or find then update
    # Here we fetch one unused number
    number_doc = numbers_col.find_one({"country": country_name, "used": False})
    
    if not number_doc:
        # Stock count mismatch safety
        countries_col.update_one({"name": country_name}, {"$set": {"stock": 0}})
        return await cq.answer("⚠️ System Error: Stock mismatch. Contact Admin.", show_alert=True)

    # --- Calculate New Balance ---
    price = country["price"]
    new_balance = user["balance"] - price

    # --- EXECUTE DB TRANSACTION ---
    try:
        # 1. Deduct Balance
        users_col.update_one({"_id": user_id}, {"$set": {"balance": new_balance}})
        
        # 2. Mark Number as Used
        numbers_col.update_one({"_id": number_doc["_id"]}, {"$set": {"used": True}})
        
        # 3. Create Order Log
        orders_col.insert_one({
            "user_id": user_id,
            "country": country_name,
            "number": number_doc["number"],
            "price": price,
            "status": "purchased",
            "created_at": datetime.now(timezone.utc)
        })
        
        # 4. Decrease Stock
        countries_col.update_one({"name": country_name}, {"$inc": {"stock": -1}})
        
    except Exception as e:
        print(f"Transaction Error: {e}")
        return await cq.answer("❌ Transaction failed. Please try again.", show_alert=True)

    # --- Send Success Message ---
    text_to_copy = str(number_doc["number"])
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="• Get OTP",
                    callback_data=f"get_otp:{number_doc['number']}"
                ),
                InlineKeyboardButton(
                    text="Copy Num",
                    copy_text=CopyTextButton(text=text_to_copy)
                )
            ],
            [
                InlineKeyboardButton(
                    text="• Support •",                    
                    url=f"https://t.me/{SUPPORT}"
                )
            ]
        ]
    )

    success_msg = (
        f"<pre>✅ Purchased Successfully!</pre>\n"
        f"➖ <b><u>Server</u></b>:  Server (1)\n"
        f"➖<b> <u>Country:</u></b> {country_name}\n"
        f"📞 <b>Number:</b> <code>+{number_doc['number']}</code>\n"
        f"🏷️ <b>Price:</b> ₹{price}\n"
        f"💸<b> Balance:</b> ₹{new_balance:.2f}"
    )

    await cq.message.edit_text(
        success_msg,
        parse_mode="HTML",
        reply_markup=kb
    )    


# ================= Admin Add Number Flow =================
@dp.message(Command("add"))
async def cmd_add_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("❌ No countries found. Add some countries first in DB.")
    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"add_country:{c['name']}")
    kb.adjust(2)
    await msg.answer("🌍 Select the country you want to add a number for:", reply_markup=kb.as_markup())
    await state.set_state(AddSession.waiting_country)

@dp.callback_query(F.data.startswith("add_country:"))
async def callback_add_country(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)
    await state.update_data(country=country_name)
    await cq.message.answer(f"📞 Enter the phone number for {country_name} (e.g., +14151234567):")
    await state.set_state(AddSession.waiting_number)

@dp.message(AddSession.waiting_number)
async def add_number_get_code(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = msg.text.strip()
    await state.update_data(number=phone)

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await msg.answer("📩 Code sent! Please enter the OTP you received on Telegram or SMS:")
        await state.update_data(session=session.save(), phone_code_hash=sent.phone_code_hash)
        await client.disconnect()
        await state.set_state(AddSession.waiting_otp)
    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Failed to send code: {e}")


@dp.message(AddSession.waiting_otp)
async def add_number_verify_code(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = data["number"]
    session_str = data["session"]
    phone_code_hash = data.get("phone_code_hash")

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(
            phone=phone,
            code=msg.text.strip(),
            phone_code_hash=phone_code_hash
        )

        string_session = client.session.save()
        await client.disconnect()

        # 🔹 SAVE / UPDATE NUMBER
        numbers_col.update_one(
            {"number": phone},
            {
                "$set": {
                    "country": country,
                    "string_session": string_session,
                    "password": None,
                    "used": False
                }
            },
            upsert=True
        )

        # 🔥 ADD TO STOCK (YOU MISSED THIS)
        countries_col.update_one(
            {"name": country},
            {"$inc": {"stock": 1}},
            upsert=True
        )

        await msg.answer(
            f"✅ Session Added Successfully\n\n"
            f"🌍 Country: {country}\n"
            f"📱 Number: <code>{phone}</code>\n"
            f"🔐 Password: <code>None</code>\n\n"
            f"🔑 String Session:\n"
            f"<blockquote expandable><code>{string_session}</code></blockquote>",
            parse_mode="HTML"
        )

        await msg.answer(
            "➕ Send another phone number for this country\n"
            "❌ Or type <b>cancel</b> to stop.",
            parse_mode="HTML"
        )
        await state.set_state(AddSession.waiting_next_action)
    except Exception as e:
        if "PASSWORD" in str(e).upper():
            await msg.answer("🔐 Two-step verification enabled. Send password:")
            await state.set_state(AddSession.waiting_password)
        else:
            await client.disconnect()
            await msg.answer(f"❌ Error verifying OTP: {e}")
            


@dp.message(AddSession.waiting_password)
async def add_number_with_password(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = data["number"]
    session_str = data["session"]
    password = msg.text.strip()

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(password=password)
        string_session = client.session.save()
        await client.disconnect()

        # 🔹 SAVE / UPDATE NUMBER
        numbers_col.update_one(
            {"number": phone},
            {
                "$set": {
                    "country": country,
                    "string_session": string_session,
                    "password": password,
                    "used": False
                }
            },
            upsert=True
        )

        # 🔥 ADD TO STOCK (CRITICAL)
        countries_col.update_one(
            {"name": country},
            {"$inc": {"stock": 1}},
            upsert=True
        )

        await msg.answer(
            f"✅ Session Added Successfully (2FA)\n\n"
            f"🌍 Country: {country}\n"
            f"📱 Number: <code>{phone}</code>\n"
            f"🔐 Password: <code>{password}</code>\n\n"
            f"🔑 String Session:\n"
            f"<blockquote expandable><code>{string_session}</code></blockquote>",
            parse_mode="HTML"
        )

        await msg.answer(
            "➕ Send another phone number for this country\n"
            "❌ Or type <b>cancel</b> to stop.",
            parse_mode="HTML"
        )
        await state.set_state(AddSession.waiting_next_action)
    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Error signing in with password: {e}")

@dp.message(AddSession.waiting_next_action)
async def add_next_number_or_cancel(msg: Message, state: FSMContext):
    text = msg.text.strip()

    if text.lower() == "cancel":
        await state.clear()
        return await msg.answer("✅ Add number process cancelled.")

    # otherwise assume phone number
    phone = text
    await state.update_data(number=phone)

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
        await state.update_data(
            session=session.save(),
            phone_code_hash=sent.phone_code_hash
        )
        await msg.answer("📩 Code sent! Enter OTP:")
        await state.set_state(AddSession.waiting_otp)
        await client.disconnect()

    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Failed to send code: {e}")
        
        
class RemoveSession(StatesGroup):
    waiting_country = State()
    waiting_number = State()
#Remove
@dp.message(Command("remove"))
async def cmd_remove_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("❌ No countries found.")

    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"remove_country:{c['name']}")
    kb.adjust(2)

    await msg.answer("🌍 Select country to remove number from:", reply_markup=kb.as_markup())
    await state.set_state(RemoveSession.waiting_country)

@dp.callback_query(F.data.startswith("remove_country:"))
async def callback_remove_country(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country = cq.data.split(":", 1)
    await state.update_data(country=country)
    await cq.message.answer(f"📱 Send the phone number to remove from {country}:")
    await state.set_state(RemoveSession.waiting_number)

@dp.message(RemoveSession.waiting_number)
async def remove_number(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = msg.text.strip()

    doc = numbers_col.find_one({"number": phone, "country": country})
    if not doc:
        await msg.answer("❌ Number not found. Use /remove again.")
        await state.clear()
        return

    numbers_col.delete_one({"_id": doc["_id"]})
    countries_col.update_one(
        {"name": country},
        {"$inc": {"stock": -1}}
    )

    await msg.answer(
        f"✅ Number removed successfully\n\n"
        f"🌍 Country: {country}\n"
        f"📱 Number: <code>{phone}</code>",
        parse_mode="HTML"
    )

    await state.clear()

# ===== Admin Country Commands =====
@dp.message(Command("addcountry"))
async def cmd_add_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    await msg.answer("🌍 Send the country name and price separated by a comma (e.g., India,50):")
    await state.set_state("adding_country")

@dp.message(StateFilter("adding_country"))
async def handle_add_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: India,50")
    name, price = msg.text.split(",", 1)
    try:
        price = float(price.strip())
    except ValueError:
        return await msg.answer("❌ Invalid price format.")
    countries_col.update_one({"name": name.strip()}, {"$set": {"price": price, "stock": 0}}, upsert=True)
    await msg.answer(f"✅ Country {name.strip()} added/updated with price {price}.")
    await state.clear()

# ================= Admin: Remove Country =================
@dp.message(Command("removecountry"))
async def cmd_remove_country(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("📭 No countries to remove.")

    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"removecountry:{c['name']}")
    kb.adjust(2)
    await msg.answer("🌍 Select a country to remove:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("removecountry:"))
async def callback_remove_country(cq: CallbackQuery):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)

    result = countries_col.delete_one({"name": country_name})
    if result.deleted_count == 0:
        await cq.message.edit_text(f"❌ Country <b>{country_name}</b> not found.", parse_mode="HTML")
    else:
        await cq.message.edit_text(f"✅ Country <b>{country_name}</b> removed successfully.", parse_mode="HTML")

@dp.message(Command("db"))
async def cmd_db(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("❌ No countries found in DB.")

    text = "📚 <b>Numbers in Database by Country:</b>\n\n"

    for c in countries:
        country_name = c["name"]
        numbers = list(numbers_col.find({"country": country_name}))
        text += f"🌍 <b>{country_name}:</b>\n"
        if numbers:
            for num in numbers:
                text += f"• {num['number']} {'✅' if num.get('used') else ''}\n"
        else:
            text += "No number\n"
        text += "\n"

    await msg.answer(text, parse_mode="HTML")



# --- Admin Command: Set Sell Prices ---

# ====================== SELL ACCOUNT FEATURE (FIXED & FULL) ======================

sell_prices_col = db["sell_prices"]

# --- FSM States ---
class SetPrices(StatesGroup):
    waiting_list = State()

class SellSession(StatesGroup):
    waiting_sell_number = State()
    waiting_sell_otp = State()
    waiting_sell_password = State()


# --- Admin Command: Set Sell Prices ---
@dp.message(Command("setprices"))
async def cmd_set_prices(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    
    await msg.answer(
        "📋 <b>Send the price list in this format:</b>\n\n"
        "<code>+1 USA 🇺🇸 - ₹10</code>\n"
        "<code>+91 India 🇮🇳 - ₹29</code>\n"
        "<code>+232 Sierra Leone 🇸🇱 - ₹13</code>\n\n"
        "⚠️ <i>Sending a new list will overwrite the old one.</i>",
        parse_mode="HTML"
    )
    await state.set_state(SetPrices.waiting_list)


@dp.message(StateFilter(SetPrices.waiting_list))
async def handle_set_prices(msg: Message, state: FSMContext):
    text = msg.text.strip()
    
    # IMPROVED REGEX EXPLANATION:
    # (\+\d{1,4})  -> Captures country code (e.g., +1, +232)
    # \s+          -> Matches spaces
    # (.*?)        -> Captures ANY text/emoji (Country Name + Flag) non-greedily until the hyphen
    # \s*-\s* -> Matches the hyphen separator
    # ₹?           -> Matches optional Rupee symbol
    # \s* -> Optional space
    # (\d+)        -> Captures the price number
    pattern = re.compile(r"(\+\d{1,4})\s+(.*?)\s*-\s*₹?\s*(\d+)", re.MULTILINE)

    entries = pattern.findall(text)

    # 1. Validation: Don't delete old data if the new list is empty/invalid
    if not entries:
        return await msg.answer(
            "❌ <b>Invalid format detected.</b>\n\n"
            "Make sure you use the format:\n"
            "<code>+Code CountryName Flag - ₹Price</code>\n"
            "Example:\n<code>+232 Sierra Leone 🇸🇱 - 13</code>", 
            parse_mode="HTML"
        )

    # 2. Database Update: clear old data ONLY after validation passes
    sell_prices_col.delete_many({})
    
    new_data = []
    response_lines = []

    for code, name, price in entries:
        clean_name = name.strip()
        clean_price = int(price)
        
        new_data.append({
            "code": code.strip(),
            "name": clean_name,
            "price": clean_price
        })
        
        response_lines.append(f"{code} {clean_name} - ₹{clean_price}")

    # Bulk insert is faster and safer
    if new_data:
        sell_prices_col.insert_many(new_data)

    # 3. Confirmation
    formatted_list = "\n".join(response_lines)
    await msg.answer(
        f"✅ <b>Price list updated successfully!</b>\n"
        f"<i>Added {len(new_data)} countries.</i>\n\n"
        f"<pre>{formatted_list}</pre>", 
        parse_mode="HTML"
    )
    await state.clear()

# --- Callback for Sell Button ---
# ==========================================
# 💸 SELL ACCOUNT LOGIC (REWRITTEN & FIXED)
# ==========================================

# --- 1. Sell Menu ---
@dp.callback_query(F.data == "sell")
async def callback_sell(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    prices = list(sell_prices_col.find({}))
    
    if not prices:
        return await cq.message.answer("❌ <b>Sales are currently closed.</b>\nNo price list available.")

    # High UI Price List
    price_list_text = ""
    for p in prices:
        price_list_text += f"🏳️ <code>{p['code']}</code> <b>{p['name']}</b> ➜ ₹{p['price']}\n"

    text = (
        "<b>💸 SELL YOUR TELEGRAM ACCOUNT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📊 Current Buying Rates:</b>\n"
        f"<blockquote expandable>{price_list_text}</blockquote>\n"
        "<b>📝 Instructions:</b>\n"
        "1. Enter your number with country code.\n"
        "2. Send the OTP received.\n"
        "3. If you have a 2FA password, enter it.\n\n"
        "👇 <b>Send your number now:</b>\n"
        "<i>(Example: +14151234567)</i>"
    )

    await cq.message.answer(text, parse_mode="HTML")
    await state.set_state(SellSession.waiting_sell_number)
    
    # --- 2. User Sends Number ---
@dp.message(StateFilter(SellSession.waiting_sell_number))
async def user_sells_number(msg: Message, state: FSMContext):
    phone = msg.text.strip().replace(" ", "")
    
    if not phone.startswith("+") or not phone[1:].isdigit():
        return await msg.answer("❌ <b>Invalid Format!</b>\nPlease start with '+' followed by digits.\n<i>Ex: +14155550199</i>")

    # Match Country and Price
    all_prices = list(sell_prices_col.find({}))
    matched = None
    for p in all_prices:
        if phone.startswith(p["code"]):
            matched = p
            break

    if not matched:
        return await msg.answer("⚠️ <b>Sorry!</b>\nWe are not buying numbers from this country at the moment.")

    country_name = matched["name"]
    price = matched["price"]

    status_msg = await msg.answer(
        f"🌍 <b>Country:</b> {country_name}\n"
        f"💰 <b>Offer Price:</b> ₹{price}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 <i>Connecting to Telegram Servers...</i>"
    )

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        
        # Save session immediately to maintain context
        await state.update_data(
            session=session.save(), # Critical for session continuity
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
            price=price,
            country_name=country_name,
            password_needed=False # Default false
        )
        
        await client.disconnect()
        
        await status_msg.edit_text(
            f"🌍 <b>Country:</b> {country_name}\n"
            f"💰 <b>Offer Price:</b> ₹{price}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📩 <b>OTP Sent!</b>\n\n"
            "Please check your Telegram Service notifications or SMS and enter the code below:\n"
            "<i>(Format: 12345)</i>"
        )
        await state.set_state(SellSession.waiting_sell_otp)

    except Exception as e:
        await client.disconnect()
        await status_msg.edit_text(f"❌ <b>Connection Failed:</b>\n<code>{str(e)}</code>")


# --- 3. User Sends OTP ---
@dp.message(StateFilter(SellSession.waiting_sell_otp))
async def user_sells_otp(msg: Message, state: FSMContext):
    otp_code = msg.text.strip()
    
    # Basic validation
    if not otp_code.isdigit():
        return await msg.answer("❌ <b>Invalid OTP.</b> Send numbers only.")

    data = await state.get_data()
    phone = data["phone"]
    session_str = data["session"]
    phone_code_hash = data["phone_code_hash"]

    status_msg = await msg.answer("🔄 <i>Verifying Code...</i>")

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    client = TelegramClient(StringSession(session_str), api_id, api_hash)

    try:
        await client.connect()
        
        try:
            # Try logging in
            await client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
            
            # --- SCENARIO A: Login Successful (No 2FA) ---
            final_string = client.session.save() # CAPTURE FINAL STRING
            await client.disconnect()
            
            await state.update_data(string_session=final_string, password=None)
            
            # Skip password step, go directly to finalize logic
            await finalize_sell(msg, state, phone, final_string, None)
            
        except SessionPasswordNeededError:
            # --- SCENARIO B: 2FA Required ---
            await client.disconnect()
            await state.update_data(password_needed=True)
            await status_msg.delete()
            await msg.answer(
                "🔐 <b>Two-Step Verification Detected</b>\n\n"
                "Please enter your <b>Password</b> to complete the login.\n"
                "<i>We need this to verify the account.</i>"
            )
            await state.set_state(SellSession.waiting_sell_password)

    except PhoneCodeInvalidError:
        await client.disconnect()
        await status_msg.edit_text("❌ <b>Wrong OTP!</b>\nPlease check and send again.")
    except Exception as e:
        await client.disconnect()
        await status_msg.edit_text(f"❌ <b>Error:</b> {e}")
        
        
# --- 4. User Sends Password (If 2FA) ---
@dp.message(StateFilter(SellSession.waiting_sell_password))
async def user_sell_password(msg: Message, state: FSMContext):
    password = msg.text.strip()
    data = await state.get_data()
    
    phone = data["phone"]
    session_str = data["session"] # Use the initial session to resume
    
    status_msg = await msg.answer("🔄 <i>Verifying Password...</i>")

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    client = TelegramClient(StringSession(session_str), api_id, api_hash)

    try:
        await client.connect()
        await client.sign_in(password=password)
        
        # --- Login Successful (With 2FA) ---
        final_string = client.session.save() # CAPTURE FINAL STRING
        await client.disconnect()
        
        # Proceed to finalize
        await status_msg.delete()
        await finalize_sell(msg, state, phone, final_string, password)

    except PasswordHashInvalidError:
        await client.disconnect()
        await status_msg.edit_text("❌ <b>Wrong Password!</b>\nPlease try again.")
    except Exception as e:
        await client.disconnect()
        await status_msg.edit_text(f"❌ <b>Error:</b> {e}")


# --- 5. Finalize Sell (Save to DB & Notify Admin) ---
async def finalize_sell(msg: Message, state: FSMContext, phone, string_session, password):
    data = await state.get_data()
    country_name = data["country_name"]
    price = data["price"]
    user_id = msg.from_user.id
    username = msg.from_user.username

    # 1. Update Database
    numbers_col.update_one(
        {"number": phone},
        {
            "$set": {
                "country": country_name,
                "number": phone,
                "string_session": string_session, # The valid authenticated session
                "password": password if password else "None",
                "used": False,
                "added_by": user_id,
                "added_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    # 2. Notify Admin
    # Using the specific Admin ID provided in your prompt
    ADMIN_CHAT_ID = -1003790606640

    kb = InlineKeyboardBuilder()
    # Unique callback for selling OTPs
    kb.button(text="📩 Get OTP (Sell)", callback_data=f"get_sell_otp:{phone}")
    kb.button(text=f"✅ Approve ₹{price}", callback_data=f"approve_sell:{user_id}:{phone}:{price}")
    kb.button(text=f"Reject", callback_data=f"reject_sell:{user_id}:{phone}")
    
    kb.adjust(1)

    admin_text = (
        f"<b>📤 NEW ACCOUNT FOR SALE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Seller:</b> @{username or 'N/A'} (<code>{user_id}</code>)\n"
        f"🌍 <b>Country:</b> {country_name}\n"
        f"📞 <b>Number:</b> <code>{phone}</code>\n"
        f"💰 <b>Payout:</b> ₹{price}\n"
        f"🔐 <b>2FA Pass:</b> <code>{password if password else 'None'}</code>\n\n"
        f"🔑 <b>Session String:</b>\n"
        f"<blockquote expandable><code>{string_session}</code></blockquote>"
    )

    try:
        await bot.send_message(
            ADMIN_CHAT_ID,
            admin_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Failed to send to admin: {e}")

    # 3. Notify User
    await msg.answer(
        f"✅ <b>Submission Successful!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 <b>Number:</b> {phone}\n"
        f"💰 <b>Pending:</b> ₹{price}\n\n"
        f"<i>Your account is under review. Balance will be credited after admin verification (usually 1-10 mins).</i>"
    )
    
    await state.clear()
    
    # ==========================================
# 📩 DEDICATED SELL OTP LISTENER (FIXED)
# ==========================================

@dp.callback_query(F.data.startswith("get_sell_otp:"))
async def callback_get_sell_otp(cq: CallbackQuery):
    phone = cq.data.split(":")[1]
    
    # 1. Fetch Session from DB
    number_doc = numbers_col.find_one({"number": phone})
    if not number_doc or not number_doc.get("string_session"):
        return await cq.answer("❌ Session not found in Database.", show_alert=True)

    await cq.answer("🔄 Accessing Account...", show_alert=False)
    
    # High UI status message
    status_msg = await cq.message.answer(f"🔍 <b>Searching for OTP on {phone}...</b>")

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    string_session = number_doc.get("string_session")
    password_text = number_doc.get("password") or "None"

    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            await status_msg.edit_text(f"❌ <b>Session Expired</b>\nAccount {phone} has been logged out.")
            return

        # Use the logic from your working otp_listener
        # Matches any 5-digit number in the message
        pattern = re.compile(r"\b\d{5}\b")
        found_code = None

        # Iterate messages from Telegram Service (777000)
        # Increased limit slightly to ensure we don't miss it
        async for msg in client.iter_messages(777000, limit=15):
            if not msg.message:
                continue

            match = pattern.search(msg.message)
            if match:
                found_code = match.group(0)
                # We stop at the very first (newest) 5-digit code found
                break 
        
        await client.disconnect()

        if found_code:
            # High UI Result Format
            response_text = (
                f"<b>✅ OTP RECEIVED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Code -</b> <code>{found_code}</code>\n"
                f"<b>Number -</b> <code>{phone}</code>\n"
                f"<b>Pass -</b> <code>{password_text}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await status_msg.delete()
            await bot.send_message(
                chat_id=cq.message.chat.id,
                text=response_text,
                parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(
                f"⚠️ <b>OTP Not Found</b>\n"
                f"No 5-digit code found in the last 15 messages from Telegram on {phone}.\n\n"
                f"<i>Try clicking the button again in a few seconds.</i>"
            )

    except Exception as e:
        if client.is_connected():
            await client.disconnect()
        await status_msg.edit_text(f"❌ <b>Error:</b>\n<code>{str(e)}</code>")


# --- Admin: Get OTP Button ---
@dp.callback_query(F.data.startswith("get_otp:"))
async def callback_get_otp(cq: CallbackQuery):
    phone = cq.data.split(":")[1]

    number_doc = numbers_col.find_one({"number": phone})
    if not number_doc:
        return await cq.answer("❌ Number session not found.", show_alert=True)

    await cq.answer("Waiting for OTP.....")

    # 👇 pass message_id of SAME message
    asyncio.create_task(
        otp_listener(
            number_doc=number_doc,
            user_id=cq.from_user.id,
            message_id=cq.message.message_id
        )
    )
        # --- 2. Admin: Approve Sell ---
@dp.callback_query(F.data.startswith("approve_sell:"))
async def callback_approve_sell(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("❌ Not authorized.", show_alert=True)

    _, user_id, phone, price = cq.data.split(":")
    user_id, price = int(user_id), int(price)

    # Add Balance
    users_col.update_one({"_id": user_id}, {"$inc": {"balance": price}})

    # Edit Admin Message
    await cq.message.edit_text(
        cq.message.text + f"\n\n✅ <b>Approved by {cq.from_user.first_name}</b>",
        parse_mode="HTML"
    )

    # Notify User with Withdraw Button
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Withdraw Now", callback_data="init_withdraw")
    
    await bot.send_message(
        user_id,
        f"🎉 <b>Account Approved!</b>\n\n"
        f"✅ Account: <code>{phone}</code>\n"
        f"💰 Added: ₹{price}\n\n"
        f"You can withdraw this amount to your UPI immediately.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await cq.answer("✅ Approved & Balance Added.")

# --- 3. Admin: Reject Sell ---
@dp.callback_query(F.data.startswith("reject_sell:"))
async def callback_reject_sell(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("❌ Not authorized.")

    _, user_id, phone = cq.data.split(":")
    user_id = int(user_id)

    await cq.message.edit_text(
        cq.message.text + f"\n\n❌ <b>Rejected by {cq.from_user.first_name}</b>",
        parse_mode="HTML"
    )
    
    await bot.send_message(
        user_id,
        f"⚠️ <b>Account Rejected</b>\n\nYour submission for <code>{phone}</code> was declined by the admin.",
        parse_mode="HTML"
    )
    await cq.answer("❌ Request Rejected.")
    
    
    # --- User clicks Withdraw ---
@dp.callback_query(F.data == "init_withdraw")
async def start_withdraw(cq: CallbackQuery, state: FSMContext):
    user_bal = get_user_balance(cq.from_user.id)
    if user_bal < 1:
        return await cq.answer("❌ Balance too low.", show_alert=True)

    await cq.message.answer(
        "🏦 <b>Withdrawal Setup</b>\n\nPlease enter your <b>UPI ID</b> (e.g., user@oksbi):",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawState.waiting_upi)
    await cq.answer()

# --- User enters UPI ---
@dp.message(StateFilter(WithdrawState.waiting_upi))
async def process_withdraw_upi(msg: Message, state: FSMContext):
    upi_id = msg.text.strip()
    await state.update_data(upi_id=upi_id)
    
    user_bal = get_user_balance(msg.from_user.id)
    
    await msg.answer(
        f"✅ UPI set to: <code>{upi_id}</code>\n\n"
        f"💰 Your Balance: ₹{user_bal}\n"
        f"Enter the amount you want to withdraw:",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawState.waiting_amount)

# --- User enters Amount ---
@dp.message(StateFilter(WithdrawState.waiting_amount))
async def process_withdraw_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Please enter a valid number.")

    data = await state.get_data()
    upi_id = data.get('upi_id')
    user_id = msg.from_user.id
    current_bal = get_user_balance(user_id)

    # Validation
    if amount > current_bal:
        return await msg.answer(f"❌ Insufficient funds. Your balance is ₹{current_bal}.")
    if amount < 1:
        return await msg.answer("❌ Minimum withdrawal is ₹1.")

    # Deduct Balance
    users_col.update_one({"_id": user_id}, {"$inc": {"balance": -amount}})
    
    # Save Request to DB
    withdraw_doc = {
        "user_id": user_id,
        "username": msg.from_user.username,
        "amount": amount,
        "upi": upi_id,
        "status": "pending"
    }
    result = withdrawals_col.insert_one(withdraw_doc)
    request_id = str(result.inserted_id)

    # Notify User
    await msg.answer(
        f"✅ <b>Withdrawal Request Submitted!</b>\n"
        f"💸 Amount: ₹{amount}\n"
        f"🏦 UPI: <code>{upi_id}</code>\n\n"
        f"You will receive the funds shortly.",
        parse_mode="HTML"
    )
    await state.clear()

    # Notify Admin Group
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve Payment", callback_data=f"pay_wd:{request_id}")
    kb.adjust(1)

    admin_text = (
        f"<b>💸 New Withdrawal Request</b>\n\n"
        f"👤 User: {msg.from_user.full_name} (<code>{user_id}</code>)\n"
        f"💰 Amount: <b>₹{amount}</b>\n"
        f"🏦 UPI: <code>{upi_id}</code>\n"
        f"🆔 Req ID: <code>{request_id}</code>"
    )

    await bot.send_message(
        "-1003723243833", 
        admin_text, 
        reply_markup=kb.as_markup(), 
        parse_mode="HTML"
    )
    
# --- Admin clicks Approve Payment ---
@dp.callback_query(F.data.startswith("pay_wd:"))
async def admin_approve_withdraw(cq: CallbackQuery, state: FSMContext):
    req_id = cq.data.split(":")[1]
    
    # Store request details in FSM to use after getting TXN ID
    await state.update_data(req_id=req_id, message_id=cq.message.message_id, chat_id=cq.message.chat.id)
    
    await cq.message.answer(
        "✍️ <b>Send the Transaction ID (UTR) for this payment:</b>\n"
        "Or type /skip if you don't want to provide one.",
        parse_mode="HTML"
    )
    await state.set_state(AdminTxnState.waiting_txn)
    await cq.answer()

# --- Admin sends TXN ID ---
@dp.message(StateFilter(AdminTxnState.waiting_txn))
async def admin_finalize_withdraw(msg: Message, state: FSMContext):
    txn_id = msg.text.strip()
    data = await state.get_data()
    req_id = data.get('req_id')
    admin_msg_id = data.get('message_id')
    admin_chat_id = data.get('chat_id')

    # Get Request Details
    req_doc = withdrawals_col.find_one({"_id": ObjectId(req_id)})
    if not req_doc:
        await msg.answer("❌ Error: Request not found in DB.")
        return await state.clear()

    # Update DB Status
    withdrawals_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "paid", "txn": txn_id}})

    # 1. Notify User
    user_msg = (
        f"🎉 <b>Withdrawal Approved!</b>\n\n"
        f"💰 Amount: ₹{req_doc['amount']}\n"
        f"🏦 UPI: <code>{req_doc['upi']}</code>\n"
    )
    if txn_id != "/skip":
        user_msg += f"🆔 TXN ID: <code>{txn_id}</code>"
    
    try:
        await bot.send_message(req_doc['user_id'], user_msg, parse_mode="HTML")
    except:
        pass # User might have blocked bot

    # 2. Update Admin Group Message (Strikethrough)
    original_text = (
        f"<b>💸 New Withdrawal Request</b>\n\n"
        f"👤 User: {req_doc['username']} (<code>{req_doc['user_id']}</code>)\n"
        f"💰 Amount: <b>₹{req_doc['amount']}</b>\n"
        f"🏦 UPI: <code>{req_doc['upi']}</code>\n"
        f"🆔 Req ID: <code>{req_id}</code>"
    )

    strikethrough_text = f"<s>{original_text}</s>\n\n✅ <b>PAID by {msg.from_user.first_name}</b>"
    if txn_id != "/skip":
        strikethrough_text += f"\n🆔 Ref: {txn_id}"

    try:
        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=admin_msg_id,
            text=strikethrough_text,
            parse_mode="HTML"
        )
    except Exception as e:
        await msg.answer(f"⚠️ Could not edit original message: {e}")

    await msg.answer("✅ Withdrawal marked as paid.")
    await state.clear()


    

#============== Admin: Edit Country =================
class EditCountry(StatesGroup):
    waiting_new_name = State()
    waiting_new_price = State()

@dp.message(Command("editcountry"))
async def cmd_edit_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("📭 No countries to edit.")
    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"editcountry:{c['name']}")
    kb.adjust(2)
    await msg.answer("🌍 Select a country to edit:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("editcountry:"))
async def callback_edit_country(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)
    country = countries_col.find_one({"name": country_name})
    if not country:
        return await cq.message.edit_text(f"❌ Country {country_name} not found.")

    await state.update_data(country_name=country_name)

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✏️ Change Name", callback_data="editcountry_change_name"),
        InlineKeyboardButton(text="💰 Change Price", callback_data="editcountry_change_price")
    )
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="editcountry_cancel"))
    await cq.message.edit_text(
        f"🛠️ Editing Country: <b>{country_name}</b>\n"
        f"💸 Current Price: ₹{country['price']}",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "editcountry_change_name")
async def callback_edit_change_name(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    data = await state.get_data()
    country_name = data.get("country_name")
    await cq.message.answer(f"✏️ Send new name for <b>{country_name}</b>:", parse_mode="HTML")
    await state.set_state(EditCountry.waiting_new_name)

@dp.message(StateFilter(EditCountry.waiting_new_name))
async def handle_new_country_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get("country_name")
    new_name = msg.text.strip()

    countries_col.update_one({"name": old_name}, {"$set": {"name": new_name}})
    numbers_col.update_many({"country": old_name}, {"$set": {"country": new_name}})
    await msg.answer(f"✅ Country name changed from <b>{old_name}</b> → <b>{new_name}</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "editcountry_change_price")
async def callback_edit_change_price(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    data = await state.get_data()
    country_name = data.get("country_name")
    await cq.message.answer(f"💰 Send new price for <b>{country_name}</b>:", parse_mode="HTML")
    await state.set_state(EditCountry.waiting_new_price)

@dp.message(StateFilter(EditCountry.waiting_new_price))
async def handle_new_country_price(msg: Message, state: FSMContext):
    data = await state.get_data()
    country_name = data.get("country_name")
    try:
        price = float(msg.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Invalid price format. Please send a valid number.")

    countries_col.update_one({"name": country_name}, {"$set": {"price": price}})
    await msg.answer(f"✅ Updated price for <b>{country_name}</b> to ₹{price:.2f}", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "editcountry_cancel")
async def callback_edit_cancel(cq: CallbackQuery, state: FSMContext):
    await cq.answer("❌ Cancelled")
    await state.clear()
    await cq.message.edit_text("❌ Edit cancelled.")


@dp.callback_query(F.data == "stats")
async def callback_howto(cq: CallbackQuery):
    user = users_col.find_one({"_id": cq.from_user.id})
    if not user:
        user = get_or_create_user(cq.from_user.id, cq.from_user.username)
    steps_text = (
        f"<b>◍ Account Seller Bot</b>\n––––––——–––————––––——–––•\n"
        f"<blockquote><b>👤 Name: </b>{cq.from_user.full_name}\n"
        f"<b>💻 Username: </b>@{cq.from_user.username if cq.from_user.username else 'N/A'}\n"
        f"<b>🆔 User ID:</b> {cq.from_user.id}\n"
        f"<b>💰 Balance:</b> ₹{user.get('balance', 0.0):.2f}</blockquote>\n"
        f"––––––——–––————––––——–––•\n •<b> Bot</b>: @{BOTUSER}\n• <b>Sales Log</b>: @{SALESLOG}"
        
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="▪️ Support", url=f"https://t.me/{OWNER}"),
        InlineKeyboardButton(text="▪️ 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚", url=f"https://t.me/vthnet")
    )
    kb.row(
        InlineKeyboardButton(text="▪️ Previous", callback_data="back_main")
    )
    
    await cq.message.edit_text(steps_text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cq.answer()

@dp.callback_query(F.data == "howto")
async def callback_howto(cq: CallbackQuery):
    await cq.answer() # Answer first
    steps_text = ("📚 FᴀQ & Sᴜᴘᴘᴏʀᴛ 😊\n\n🔗 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚:👉 {USAGE}\n💬 Oғғɪᴄɪᴀʟ Sᴜᴘᴘᴏʀᴛ:   👉 {SUPPORT}\n🤖 Oғғɪᴄɪᴀʟ Bᴏᴛ:     👉 {BOT_USER}\n\n🛟 Fᴇᴇʟ Fʀᴇᴇ Tᴏ Rᴇᴀᴄʜ Oᴜ𝙩 Iғ Yᴏᴜ Nᴇᴇᴅ Aɴʏ Hᴇʟᴘ!")
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📲 Support", url=f"https://t.me/{SUPPORT}"),
        InlineKeyboardButton(text="🔗 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚", url=f"https://t.me/vthnet")
    )
    # Added back button
    kb.row(InlineKeyboardButton(text="🔙 Main Menu", callback_data="main_menu")) 
    
    await cq.message.edit_text(steps_text, parse_mode="HTML", reply_markup=kb.as_markup())


@dp.callback_query(lambda c: c.data == "refer")
async def callback_refer(cq: CallbackQuery):
    # Ensure the user exists
    user = get_or_create_user(cq.from_user.id, cq.from_user.username)

    # Create a referral link
    bot_username = (await bot.get_me()).username
    refer_link = f"https://t.me/{bot_username}?start=ref{cq.from_user.id}"

    # Message text
    text = (
        f"Invite your friends to use the bot and earn 2% of every recharge they make!\n ––––––—————–––––———–––•\n"
        f"🔗 <b>Your Referral Link:</b>\n<code>{refer_link}</code>"
    )

    # Build inline keyboard
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="📤 Share Link",
            url=f"https://t.me/share/url?url={refer_link}&text=Join%20and%20earn%20with%20this%20bot!"
        )
    )
    kb.row(
        InlineKeyboardButton(
            text="▪️ Back",
            callback_data="back_main"
        )
    )

    # Safely edit the current message
    await cq.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cq.answer()

# ================= /sales Command =================
@dp.message(Command("sales"))
async def cmd_sales(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ You are not authorized to view sales report.")

    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_day = datetime(now.year, now.month, now.day)
    # Collections assumed
    users_col = db["users"]
    orders_col = db["orders"]
    recharges_col = db["recharges"]  # If you track top-ups

    # Bot Status
    bot_status = "🟢 Active"

    # Total users
    total_users = users_col.count_documents({})

    # All sales
    all_orders = list(orders_col.find({"status": "purchased"}))
    total_numbers_sold = len(all_orders)
    total_earnings = sum(order.get("price", 0) for order in all_orders)
    avg_price = total_earnings / total_numbers_sold if total_numbers_sold else 0

    # Top Country overall
    from collections import Counter
    country_counts = Counter(order.get("country", "Unknown") for order in all_orders)
    top_country = country_counts.most_common(1)[0][0] if country_counts else "N/A"

    # Total Recharge
    total_recharge = sum(txn.get("amount", 0) for txn in recharges_col.find({}))

    # ================= WEEKLY =================
    week_orders = list(orders_col.find({
        "status": "purchased",
        "date": {"$gte": start_of_week}
    }))
    week_sales = sum(o.get("price", 0) for o in week_orders)
    week_count = len(week_orders)
    week_avg = week_sales / week_count if week_count else 0
    week_country_counts = Counter(o.get("country", "Unknown") for o in week_orders)
    week_top_country = week_country_counts.most_common(1)[0][0] if week_country_counts else "N/A"
    week_recharge = sum(txn.get("amount", 0) for txn in recharges_col.find({"date": {"$gte": start_of_week}}))

    # ================= DAILY =================
    day_orders = list(orders_col.find({
        "status": "purchased",
        "date": {"$gte": start_of_day}
    }))
    day_sales = sum(o.get("price", 0) for o in day_orders)
    day_count = len(day_orders)
    day_avg = day_sales / day_count if day_count else 0
    day_country_counts = Counter(o.get("country", "Unknown") for o in day_orders)
    day_top_country = day_country_counts.most_common(1)[0][0] if day_country_counts else "N/A"
    day_recharge = sum(txn.get("amount", 0) for txn in recharges_col.find({"date": {"$gte": start_of_day}}))

    # ================= REPORT =================
    report = (
        "📊 <b>Bot Profit Report</b>\n"
        f"<b>⚙️ Bot Status: </b>{bot_status}\n\n"
        f"<b>👥 Total Users: </b>{total_users}\n"
        f"<b>🔢 Total Numbers Sold: </b>{total_numbers_sold}\n"
        f"💰 Total Sales: ₹{total_earnings:.2f}\n"
        f"⚖️ Avg Price/Number: ₹{avg_price:.2f}\n"
        f"🌍 Top Country: {top_country}\n"
        f"💳 Total Recharge: ₹{total_recharge:.2f}\n\n"
        f"@quickcodes_bot •|• @valriks"
    )

    await msg.answer(report, parse_mode="HTML")

@dp.message(Command("sellcountry"))
async def add_sell_countries(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return await msg.answer("Unauthorized ❌")

    # Remove the command itself and split lines
    lines = msg.text.split("\n")[1:]  # Skip the first line (the command)
    if not lines:
        return await msg.answer(
            "📋 Send like this:\n\n"
            "<code>/sellcountry\n+91 India ₹30\n+1 USA ₹32\n+62 Indonesia ₹28</code>",
            parse_mode="HTML"
        )

    updated = []
    errors = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            parts = line.split(" ")
            prefix = parts[0]
            if not prefix.startswith("+"):
                raise ValueError("Missing +country code")

            # Extract price (₹XX)
            match_price = [p for p in parts if "₹" in p]
            if not match_price:
                raise ValueError("Missing price (₹)")
            price = match_price[-1]  # Take last ₹ value
            country = " ".join(parts[1:parts.index(price)]).strip()

            db["sell_countries"].update_one(
                {"prefix": prefix},
                {"$set": {"country": country, "price": price}},
                upsert=True
            )

            updated.append(f"{prefix} {country} → {price}")
        except Exception as e:
            errors.append(f"❌ {line} ({e})")

    text = ""
    if updated:
        text += "✅ <b>Updated Successfully:</b>\n" + "\n".join(updated) + "\n\n"
    if errors:
        text += "⚠️ <b>Errors:</b>\n" + "\n".join(errors)

    await msg.answer(text or "⚙️ Nothing processed.", parse_mode="HTML")


# ================= Admin Credit/Debit Commands =================
@dp.message(Command("credit"))
async def cmd_credit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    
    await msg.answer("💰 Send user ID and amount to credit separated by a comma (e.g., 123456789,50):")
    await state.set_state("credit_waiting")

@dp.message(StateFilter("credit_waiting"))
async def handle_credit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: 123456789,50")

    user_id_str, amount_str = msg.text.split(",", 1)
    try:
        user_id = int(user_id_str.strip())
        amount = float(amount_str.strip())
    except ValueError:
        return await msg.answer("❌ Invalid user ID or amount format.")

    user = users_col.find_one({"_id": user_id})
    if not user:
        return await msg.answer(f"❌ User with ID {user_id} not found.")

    new_balance = user.get("balance", 0.0) + amount
    users_col.update_one({"_id": user_id}, {"$set": {"balance": new_balance}})
    await msg.answer(f"✅ Credited ₹{amount:.2f} to {user.get('username') or user_id}\n💰 New Balance: ₹{new_balance:.2f}")
    await state.clear()


@dp.message(Command("debit"))
async def cmd_debit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    
    await msg.answer("💸 Send user ID and amount to debit separated by a comma (e.g., 123456789,50):")
    await state.set_state("debit_waiting")

@dp.message(StateFilter("debit_waiting"))
async def handle_debit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: 123456789,50")

    user_id_str, amount_str = msg.text.split(",", 1)
    try:
        user_id = int(user_id_str.strip())
        amount = float(amount_str.strip())
    except ValueError:
        return await msg.answer("❌ Invalid user ID or amount format.")

    user = users_col.find_one({"_id": user_id})
    if not user:
        return await msg.answer(f"❌ User with ID {user_id} not found.")

    new_balance = max(user.get("balance", 0.0) - amount, 0.0)
    users_col.update_one({"_id": user_id}, {"$set": {"balance": new_balance}})
    await msg.answer(f"✅ Debited ₹{amount:.2f} from {user.get('username') or user_id}\n💰 New Balance: ₹{new_balance:.2f}")
    await state.clear()





    # ================= MongoDB Redeem Collection =================
redeem_col = db["redeem_codes"]  # Add this at top with other collections

# ================= Redeem FSM =================
class RedeemState(StatesGroup):
    # For auto-generated redeem codes
    waiting_amount = State()          # Admin enters amount
    waiting_limit = State()           # Admin selects max users via inline numeric keypad

    # For custom redeem codes
    waiting_code = State()            # Admin enters custom code (e.g. DIWALI100)
    waiting_amount_custom = State()   # Admin enters amount for custom code
    waiting_limit_custom = State()    # Admin selects max users for custom code

class UserRedeemState(StatesGroup):
    waiting_code = State()            # User enters redeem code
    
# ================= Helper =================
import random, string
def generate_code(length=8):
    """Generate code like HEIKE938"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))



    
        # ================= Admin: Create Custom Redeem =================
@dp.message(Command("cusredeem"))
async def cmd_custom_redeem(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    await msg.answer("🎟️ Enter the custom redeem code (e.g. DIWALI100):")
    await state.set_state(RedeemState.waiting_code)

# ================= Admin: Handle Custom Code =================
@dp.message(StateFilter(RedeemState.waiting_code))
async def handle_custom_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    if redeem_col.find_one({"code": code}):
        return await msg.answer("⚠️ This code already exists. Try another one.")

    await state.update_data(custom_code=code)
    await msg.answer("💰 Enter the amount for this redeem code:")
    await state.set_state(RedeemState.waiting_amount_custom)

# ================= Admin: Handle Custom Amount =================
@dp.message(StateFilter(RedeemState.waiting_amount_custom))
async def handle_custom_amount(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Invalid amount. Send a number like 50 or 100.")

    await state.update_data(amount=amount, limit_str="")

    # Inline numeric keypad
    kb = InlineKeyboardBuilder()
    for row in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("0", "❌", "✅")):
        kb.row(*[InlineKeyboardButton(text=btn, callback_data=f"cusredeemnum:{btn}") for btn in row])

    await msg.answer(
        "👥 Select max number of users who can claim this custom code:\n<b>0</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await state.set_state(RedeemState.waiting_limit_custom)

# ================= Admin: Handle Custom Inline Number Pad =================
@dp.callback_query(F.data.startswith("cusredeemnum:"))
async def handle_custom_redeem_number(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current = data.get("limit_str", "")
    value = cq.data.split(":")[1]

    if value == "❌":
        current = current[:-1]
    elif value == "✅":
        if not current:
            await cq.answer("❌ Please select at least one user.", show_alert=True)
            return
        try:
            limit = int(current)
        except ValueError:
            await cq.answer("❌ Invalid number.", show_alert=True)
            return

        code = data.get("custom_code")
        amount = data.get("amount")
        created_at = datetime.utcnow()

        # Insert redeem into MongoDB
        redeem_col.insert_one({
            "code": code,
            "amount": amount,
            "max_claims": limit,
            "claimed_count": 0,
            "claimed_users": [],
            "created_at": created_at
        })

        await cq.message.edit_text(
            f"✅ Custom redeem code created!\n\n"
            f"🎟️ Code: <code>{code}</code>\n"
            f"💰 Amount: ₹{amount:.2f}\n"
            f"👥 Max Claims: {limit}",
            parse_mode="HTML"
        )
        await state.clear()
        return
    else:
        current += value
        if len(current) > 6:
            current = current[:6]

    await state.update_data(limit_str=current)

    # Rebuild keypad dynamically
    kb = InlineKeyboardBuilder()
    for row in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("0", "❌", "✅")):
        kb.row(*[InlineKeyboardButton(text=btn, callback_data=f"cusredeemnum:{btn}") for btn in row])

    await cq.message.edit_text(
        f"👥 Select max number of users who can claim this custom code:\n<b>{current or '0'}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cq.answer()
        


# ================= Admin: View Redeems =================
@dp.message(Command("redeemlist"))
async def cmd_redeem_list(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    redeems = list(redeem_col.find())
    if not redeems:
        return await msg.answer("📭 No redeem codes found.")

    text = "🎟️ <b>Active Redeem Codes:</b>\n\n"
    for r in redeems:
        text += (
            f"Code: <code>{r['code']}</code>\n"
            f"💰 Amount: ₹{r['amount']}\n"
            f"👥 {r['claimed_count']} / {r['max_claims']} claimed\n\n"
        )
    await msg.answer(text, parse_mode="HTML")

# ================= User: Redeem Code =================
@dp.callback_query(F.data == "redeem")
async def callback_user_redeem(cq: CallbackQuery, state: FSMContext):
    await cq.answer("✅ Send your redeem code now!", show_alert=False)
    await cq.message.answer("🎟️ Send your redeem code below:")
    await state.set_state(UserRedeemState.waiting_code)

# Command /redeem
@dp.message(F.text == "/redeem")
async def command_user_redeem(message: Message, state: FSMContext):
    await message.answer("✅ Send your redeem code now!")
    await message.answer("🎟️ Send your redeem code below:")
    await state.set_state(UserRedeemState.waiting_code)

@dp.message(StateFilter(UserRedeemState.waiting_code))
async def handle_user_redeem(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    redeem = redeem_col.find_one({"code": code})

    if not redeem:
        await msg.answer("❌ Invalid or expired redeem code.")
        return await state.clear()

    if redeem["claimed_count"] >= redeem["max_claims"]:
        await msg.answer("🚫 This code has reached its claim limit.")
        return await state.clear()

    user = users_col.find_one({"_id": msg.from_user.id})
    if not user:
        await msg.answer("⚠️ Please use /start first.")
        return await state.clear()

    if msg.from_user.id in redeem.get("claimed_users", []):
        await msg.answer("⚠️ You have already claimed this code.")
        return await state.clear()

    # Credit user balance
    users_col.update_one({"_id": msg.from_user.id}, {"$inc": {"balance": redeem["amount"]}})
    redeem_col.update_one(
        {"code": code},
        {"$inc": {"claimed_count": 1}, "$push": {"claimed_users": msg.from_user.id}}
    )

    await msg.answer(
        f"✅ Code <b>{code}</b> redeemed successfully!\n💰 You received ₹{redeem['amount']:.2f}",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(Command("editsell"))
async def cmd_editsell(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    await msg.answer("📋 Send the list in format:\n\n<code>USA ₹50\nIndia ₹10\nUK ₹20</code>")

    @dp.message()  # Next message from admin
    async def handle_sell_edit(m: Message):
        sell_prices_col.delete_many({})
        for line in m.text.splitlines():
            try:
                parts = line.split("₹")
                country = parts[0].strip()
                price = float(parts[1].strip())
                code = "+1" if "USA" in country else "+91" if "India" in country else ""  # add more or editable
                sell_rates_col.insert_one({"country": country, "price": price, "code": code})
            except:
                continue
        await m.answer("✅ Sell rates updated.")

# ================= Admin Live Credits =================
@dp.message(Command("livecredits"))
async def cmd_livecredits(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    await show_live_credits(msg, page=0)

async def show_live_credits(msg_or_call, page: int):
    limit = 10
    skip = page * limit
    
    # Find users with balance > 0, sort DESC by balance
    cursor = users_col.find({"balance": {"$gt": 0}}).sort("balance", -1)
    total_users = users_col.count_documents({"balance": {"$gt": 0}})
    
    users_list = list(cursor.skip(skip).limit(limit))
    
    if not users_list:
        text = "📉 No users currently have a positive balance."
        kb = None
    else:
        text = f"💰 <b>Live Credits (Page {page+1})</b>\n\n"
        for u in users_list:
            u_link = f"<a href='tg://user?id={u['_id']}'>{u.get('username') or u['_id']}</a>"
            text += f"👤 {u_link} : <code>₹{u['balance']:.2f}</code>\n"
            
        kb = InlineKeyboardBuilder()
        if page > 0:
            kb.button(text="⬅️ Prev", callback_data=f"livecredits:{page-1}")
        if (skip + limit) < total_users:
            kb.button(text="Next ➡️", callback_data=f"livecredits:{page+1}")
        kb.adjust(2)
        kb.row(InlineKeyboardButton(text="❌ Close", callback_data="delete_msg"))

    if isinstance(msg_or_call, Message):
        await msg_or_call.answer(text, parse_mode="HTML", reply_markup=kb.as_markup() if kb else None)
    else:
        await msg_or_call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup() if kb else None)

@dp.callback_query(F.data.startswith("livecredits:"))
async def pagination_livecredits(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("❌", show_alert=True)
    page = int(cq.data.split(":")[1])
    await show_live_credits(cq, page)
    await cq.answer()

@dp.callback_query(F.data == "delete_msg")
async def delete_this_msg(cq: CallbackQuery):
    await cq.message.delete()

# ================= User History & Logs =================

@dp.callback_query(F.data == "history")
async def show_user_history(cq: CallbackQuery):
    user_id = cq.from_user.id
    
    # 1. Calculate Total Recharged
    # Note: Assuming 'transactions' collection is used for recharges based on your file
    txns = list(db["transactions"].find({"user_id": user_id, "status": "paid"})) # Or "success" check your recharge_flow
    total_added = sum(t.get("amount", 0) for t in txns)
    
    # 2. Calculate Purchases
    orders = list(orders_col.find({"user_id": user_id, "status": "purchased"}))
    total_purchased = len(orders)
    total_spent = sum(o.get("price", 0) for o in orders)
    
    text = (
        f"📜 <b>User History</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ <b>Accounts Bought:</b> {total_purchased}\n"
        f"💸 <b>Total Spent:</b> ₹{total_spent:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📂 View Purchase Logs", callback_data="purchase_logs:0"))
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="back_main")) # Back to profile/stats
    
    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("purchase_logs:"))
async def show_purchase_logs(cq: CallbackQuery):
    user_id = cq.from_user.id
    page = int(cq.data.split(":")[1])
    limit = 10
    skip = page * limit
    
    # Fetch orders sorted by newest first
    cursor = orders_col.find({"user_id": user_id, "status": "purchased"}).sort("_id", -1)
    total_orders = orders_col.count_documents({"user_id": user_id, "status": "purchased"})
    
    my_orders = list(cursor.skip(skip).limit(limit))
    
    if not my_orders:
        return await cq.answer("❌ No purchase history found.", show_alert=True)
    
    text = f"📂 <b>Purchase Logs (Page {page+1})</b>\n\n"
    
    for order in my_orders:
        ph_number = order.get('number')
        
        # Try to find password in numbers_col
        # Note: If you delete numbers from DB after sell, this might return None.
        # But usually, 'used=True' numbers stay in DB.
        num_doc = numbers_col.find_one({"number": ph_number})
        password = num_doc.get("password") if num_doc else "N/A"
        if not password: password = "None"
        
        text += (
            f"📱 <b>{ph_number}</b>\n"
            f"🔐 Pass: <code>{password}</code>\n"
            f"-------------------\n"
        )
        
    kb = InlineKeyboardBuilder()
    
    # Navigation
    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(text="⬅️", callback_data=f"purchase_logs:{page-1}"))
    if (skip + limit) < total_orders:
        nav_btns.append(InlineKeyboardButton(text="➡️", callback_data=f"purchase_logs:{page+1}"))
        
    if nav_btns:
        kb.row(*nav_btns)
        
    kb.row(InlineKeyboardButton(text="🔙 Back to History", callback_data="history"))
    
    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    

# ================= Admin Ban Commands (Upgraded) =================
async def get_target_id(msg: Message, args: list) -> int | None:
    """Helper to get user ID from reply, username, or manual ID"""
    # 1. Check if it's a reply
    if msg.reply_to_message:
        return msg.reply_to_message.from_user.id
    
    # 2. Check if an ID or @username was provided
    if len(args) < 2:
        return None
    
    target = args[1]
    
    # If it's a numeric ID
    if target.isdigit():
        return int(target)
    
    # If it's a username (this only works if the user is already in your DB)
    if target.startswith("@"):
        username = target.replace("@", "")
        user_doc = users_col.find_one({"username": username})
        if user_doc:
            return user_doc["_id"]
    
    return None

# ================= Admin: Top Users Command =================

@dp.message(Command("topusers"))
async def cmd_top_users(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    # Parse page number from command (e.g., /topusers 2)
    args = msg.text.split()
    page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    limit = 10
    skip = (page - 1) * limit

    # Aggregation to find top spenders
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "total_spend": {"$sum": "$price"}
            }
        },
        {"$sort": {"total_spend": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        }
    ]

    top_spenders = list(orders_col.aggregate(pipeline))

    if not top_spenders:
        return await msg.answer("❌ No spending data found or page out of range.")

    response_text = f"🏆 <b>Top Spending Users (Page {page})</b>\n"
    response_text += "--------------------------------\n"

    for entry in top_spenders:
        user_id = entry["_id"]
        total_spend = entry["total_spend"]
        
        # Get username if available, else use ID
        user_data = entry["user_info"][0] if entry["user_info"] else {}
        username = user_data.get("username")
        name = f"@{username}" if username else f"ID: <code>{user_id}</code>"
        
        response_text += f"👤 {name}\n💰 Total spend: ₹{total_spend:.2f}\n"
        response_text += "---------\n"

    # Add navigation tip
    response_text += f"\n<i>Use <code>/topusers {page + 1}</code> for next page.</i>"
    
    await msg.answer(response_text, parse_mode="HTML")
    

@dp.message(Command("gban"))
async def cmd_gban(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    args = msg.text.split()
    target_id = await get_target_id(msg, args)
    
    if not target_id:
        return await msg.answer("⚠️ <b>Usage:</b>\n• Reply to a user with <code>/gban</code>\n• <code>/gban 12345678</code>\n• <code>/gban @username</code> (User must be in DB)", parse_mode="HTML")

    # Update or Create the user with banned status
    users_col.update_one(
        {"_id": target_id},
        {"$set": {"banned": True}},
        upsert=True # This ensures they are added to DB even if they never started the bot
    )
    
    await msg.answer(f"⛔ User <code>{target_id}</code> has been <b>BANNED</b> from the bot.", parse_mode="HTML")
    
    # Try to notify the user
    try:
        await bot.send_message(target_id, "🚫 <b>You have been banned from using this bot by the admin.</b>", parse_mode="HTML")
    except:
        pass

@dp.message(Command("ungban"))
async def cmd_ungban(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    args = msg.text.split()
    target_id = await get_target_id(msg, args)
    
    if not target_id:
        return await msg.answer("⚠️ <b>Usage:</b> Reply with <code>/ungban</code> or use ID/Username.")

    result = users_col.update_one({"_id": target_id}, {"$set": {"banned": False}})
    
    if result.matched_count > 0:
        await msg.answer(f"✅ User <code>{target_id}</code> has been <b>UNBANNED</b>.", parse_mode="HTML")
    else:
        await msg.answer("❌ User not found in database.")
        

# ================= Admin Broadcast (Forward Version - Aiogram Fix) =================
@dp.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    if not msg.reply_to_message:
        return await msg.answer("⚠️ Reply to the message you want to broadcast with /broadcast.")

    broadcast_msg = msg.reply_to_message
    users = list(users_col.find({}))

    if not users:
        return await msg.answer("⚠️ No users found to broadcast.")

    sent_count = 0
    failed_count = 0

    for user in users:
        user_id = user["_id"]
        try:
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=broadcast_msg.chat.id,
                message_id=broadcast_msg.message_id
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to send to {user_id}: {e}")

    await msg.answer(f"✅ Broadcast completed!\n\nSent: {sent_count}\nFailed: {failed_count}")
    

# ===== Register External Handlers =====
register_recharge_handlers(dp=dp, bot=bot, users_col=users_col, txns_col=db["transactions"], crypto_col=crypto_col, ADMIN_IDS=ADMIN_IDS)

# ===== Bot Runner =====
async def main():
    print("Bot started.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
    
