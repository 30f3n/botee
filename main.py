import os
import re
import requests
import asyncio
from flask import Flask, request as flask_request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "6009857231:AAGYrhlbRGtWSimDrYf7IwqCXM07e5zHyxc"
ADMIN_ID = 625787641

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# قاعدة بيانات في الذاكرة لتخزين المحاولات وحالة الحظر
users_db = {}

def get_user(user_id: int):
    if user_id not in users_db:
        users_db[user_id] = {'points': 10, 'banned': False}
    return users_db[user_id]

# ==================== وظيفة البحث عن الرقم ====================
def search_osint(phone_number: str):
    cookies = {
        'sin_user_id': '0e3d6d8838c7f7143fdbc5b7876a2792159918450458f3bc',
    }
    headers = {
        'authority': 'sin-osint.wasmer.app',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'ar-IQ,ar;q=0.9,en;q=0.8',
        'content-type': 'application/json',
        'origin': 'https://sin-osint.wasmer.app',
        'referer': 'https://sin-osint.wasmer.app/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    }
    json_data = {'message': phone_number}

    try:
        response = requests.post(
            'https://sin-osint.wasmer.app/api/ai/chat',
            cookies=cookies,
            headers=headers,
            json=json_data,
            timeout=15
        )
        try:
            res_json = response.json()
            text = res_json.get('reply') or res_json.get('message') or res_json.get('content') or str(res_json)
        except:
            text = response.text

        return re.sub(r'[\*_`#]', '', text).strip()
    except Exception as e:
        return f"حدث خطأ أثناء الاتصال بالمحرّك: {e}"

# ==================== الأزرار ولوحات التحكم ====================
def main_keyboard(bot_username: str, user_id: int):
    invite_link = f"https://t.me/{bot_username}?start={user_id}"
    kb = [
        [InlineKeyboardButton(text="🔗 رابط الإحالة الخاص بك (دعوة)", switch_inline_query=f"\nاشترك عبر الرابط واحصل على نقاط بحث: {invite_link}")],
        [InlineKeyboardButton(text="👨‍💻 مراسلة المطور لشراء نقاط", url=f"tg://user?id={ADMIN_ID}")],
        [InlineKeyboardButton(text="📊 حسابي والنقاط", callback_data="my_account")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ لوحة المطور", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_keyboard():
    kb = [
        [InlineKeyboardButton(text="➕ إضافة نقاط لمستخدم", callback_data="admin_add_points")],
        [InlineKeyboardButton(text="🚫 حظر / إلغاء حظر مستخدم", callback_data="admin_toggle_ban")],
        [InlineKeyboardButton(text="📈 إحصائيات البوت", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== المعالجات (Handlers) ====================
@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data['banned']:
        await message.answer("❌ أنت محظور من استخدام البوت.")
        return

    # معالجة نظام الإحالة ودعوة الأصدقاء
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and referrer_id in users_db:
            if 'referred_by' not in user_data:
                user_data['referred_by'] = referrer_id
                users_db[referrer_id]['points'] += 1  # منح نقطة للمُحيل
                try:
                    await bot.send_message(referrer_id, "🎉 قام شخص بالتسجيل عبر رابطك! حصلت على +1 محاولة جديدة.")
                except:
                    pass

    bot_info = await bot.get_me()
    welcome_msg = (
        f"👋 أهلاً بك عزيزي {message.from_user.full_name} في بوت البحث الشامل!\n\n"
        f"🎁 حصلت على **{user_data['points']} محاولات مجانية** عند التسجيل.\n"
        f"🔎 لإجراء بحث، أرسل الرقم الذي تريد الاستعلام عنه مباشرة في الشات.\n\n"
        f"💡 للحصول على نقاط إضافية، شارك رابط الإحالة مع أصدقائك أو تواصل مع المطور."
    )
    await message.answer(welcome_msg, reply_markup=main_keyboard(bot_info.username, user_id))

@dp.callback_query(F.data == "my_account")
async def my_account(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user(user_id)
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    msg = (
        f"👤 **معلومات حسابك:**\n\n"
        f"🆔 الآيدي: `{user_id}`\n"
        f"🎯 النقاط المتبقية: **{user_data['points']}** محاولات\n\n"
        f"🔗 رابط دعوة الأصدقاء:\n`{invite_link}`"
    )
    await callback.message.answer(msg)
    await callback.answer()

@dp.message(F.text & ~F.text.startswith("/"))
async def process_search(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data['banned']:
        await message.answer("❌ حسابك محظور من الاستخدام.")
        return

    if user_data['points'] <= 0:
        await message.answer("⚠️ نفدت محاولاتك المجانية!\nشارك رابط الإحالة مع أصدقائك للحصول على نقاط إضافية.")
        return

    phone = message.text.strip()
    wait_msg = await message.answer("🔍 جاري إجراء البحث، يرجى الانتظار...")

    user_data['points'] -= 1
    result = await asyncio.to_thread(search_osint, phone)

    report = (
        f"=========================\n"
        f"📌 **تقرير البحث الشامل**\n"
        f"=========================\n\n"
        f"{result}\n\n"
        f"=========================\n"
        f"⚠️ المحاولات المتبقية لديك: {user_data['points']}"
    )

    await wait_msg.delete()
    await message.answer(report)

# ==================== لوحة تحكم المطور ====================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("⚙️ أهلاً بك في لوحة تحكم المطور:", reply_markup=admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    total_users = len(users_db)
    banned_users = sum(1 for u in users_db.values() if u['banned'])
    await callback.message.answer(f"📈 **إحصائيات البوت:**\n\n👥 عدد المستخدمين: {total_users}\n🚫 الحسابات المحظورة: {banned_users}")
    await callback.answer()

@dp.message(Command("add"))
async def add_points_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, uid, pts = message.text.split()
        uid, pts = int(uid), int(pts)
        user = get_user(uid)
        user['points'] += pts
        await message.answer(f"✅ تم إضافة {pts} نقطة للمستخدم {uid}.")
        try:
            await bot.send_message(uid, f"🎁 تم إضافة {pts} محاولات مجانية لحسابك بواسطة المطور!")
        except:
            pass
    except:
        await message.answer("⚠️ الصيغة خاطئة! استخدم:\n`/add USER_ID POINTS`")

@dp.message(Command("ban"))
async def ban_user_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
        user = get_user(uid)
        user['banned'] = not user['banned']
        status = "حظر" if user['banned'] else "إلغاء حظر"
        await message.answer(f"✅ تم {status} المستخدم {uid}.")
    except:
        await message.answer("⚠️ الصيغة خاطئة! استخدم:\n`/ban USER_ID`")

# ==================== إعدادات الـ Webhook و Flask ====================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = flask_request.get_data().decode('UTF-8')
    update = types.Update.model_validate_json(json_str)
    asyncio.run(dp.feed_update(bot, update))
    return "OK", 200

@app.route("/")
def index():
    return "Bot Server is Alive!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)