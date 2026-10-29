import logging
import sqlite3
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "9288065772:AAGhfkd0w9YLNnMzc1M-z21T2O_pu8TDppc"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def init_db():
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS players (
                        tg_id INTEGER PRIMARY KEY,
                        tg_username TEXT,
                        ingame_name TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ingame_name TEXT,
                        flower_name TEXT,
                        score INTEGER)''')
    conn.commit()
    conn.close()

init_db()

class Form(StatesGroup):
    registering = State()
    choosing_target = State()
    waiting_target_nick = State()
    waiting_flower_name = State()
    waiting_flower_score = State()
    searching_flower = State()
    viewing_other_profile = State()

def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Мой профиль / Регистрация", callback_query_data="menu_profile")],
        [InlineKeyboardButton(text="👤 Профиль другого игрока", callback_query_data="menu_other_profile")],
        [InlineKeyboardButton(text="🌸 Добавить цветок", callback_query_data="menu_add")],
        [InlineKeyboardButton(text="🔍 Найти цветок по названием", callback_query_data="menu_find")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_query_data="to_main")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Привет! Я бот гильдии. Управляй цветами с помощью кнопок ниже:", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "to_main")
async def go_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("⚙️ Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "menu_profile")
async def profile_click(callback: CallbackQuery, state: FSMContext):
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ingame_name FROM players WHERE tg_id = ?", (callback.from_user.id,))
    res = cursor.fetchone()
    
    if res:
        ingame_name = res[0]
        cursor.execute("SELECT flower_name, score FROM inventory WHERE ingame_name = ? ORDER BY score DESC", (ingame_name,))
        flowers = cursor.fetchall()
        conn.close()
        
        profile_text = f"👤 <b>Ваш профиль:</b>\n• Telegram: @{callback.from_user.username}\n• В игре: <b>{ingame_name}</b>\n\n🌸 <b>Ваши цветы:</b>\n"
        if flowers:
            for fl, sc in flowers:
                profile_text += f"• {fl} — <b>{sc}</b> баллов\n"
        else:
            profile_text += "<i>У вас пока нет добавленных цветов.</i>"
            
        await callback.message.edit_text(profile_text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        conn.close()
        await callback.message.edit_text("📝 Вы еще не зарегистрированы. Введите ваш <b>игровой никнейм</b> в ответ на это сообщение:", parse_mode="HTML")
        await state.set_state(Form.registering)
    await callback.answer()

@dp.message(Form.registering)
async def process_registration(message: Message, state: FSMContext):
    ingame_nick = message.text.strip()
    username = message.from_user.username or "NoUsername"
    
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO players (tg_id, tg_username, ingame_name) VALUES (?, ?, ?)", 
                   (message.from_user.id, username, ingame_nick))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Успешно! Теперь вы привязаны к нику: <b>{ingame_nick}</b>", parse_mode="HTML", reply_markup=back_keyboard())
    await state.clear()

@dp.callback_query(F.data == "menu_other_profile")
async def other_profile_click(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 Введите точный игровой ник игрока, чей профиль вы хотите посмотреть:")
    await state.set_state(Form.viewing_other_profile)
    await callback.answer()

@dp.message(Form.viewing_other_profile)
async def process_viewing_other_profile(message: Message, state: FSMContext):
    target_nick = message.text.strip()
    
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tg_username FROM players WHERE ingame_name = ?", (target_nick,))
    tg_res = cursor.fetchone()
    tg_username = f"@{tg_res[0]}" if tg_res else "<i>Не привязан к ТГ</i>"
    
    cursor.execute("SELECT flower_name, score FROM inventory WHERE ingame_name = ? ORDER BY score DESC", (target_nick,))
    flowers = cursor.fetchall()
    conn.close()
    
    if not flowers and tg_username == "<i>Не привязан к ТГ</i>":
        await message.answer(f"❌ Игрок с ником <b>{target_nick}</b> не найден в базе данных.", parse_mode="HTML", reply_markup=back_keyboard())
        await state.clear()
        return

    response = f"👤 <b>Профиль игрока {target_nick}:</b>\n• Telegram: {tg_username}\n\n🌸 <b>Инвентарь цветов:</b>\n"
    if flowers:
        for fl, sc in flowers:
            response += f"• {fl} — <b>{sc}</b> баллов\n"
    else:
        response += "<i>У этого игрока пока нет цветов в базе.</i>"
        
    await message.answer(response, parse_mode="HTML", reply_markup=back_keyboard())
    await state.clear()

@dp.callback_query(F.data == "menu_add")
async def add_flower_click(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋‍♂️ Себе", callback_query_data="target_self")],
        [InlineKeyboardButton(text="👥 Другому игроку", callback_query_data="target_other")],
        [InlineKeyboardButton(text="🔙 Назад", callback_query_data="to_main")]
    ])
    await callback.message.edit_text("Кому вы хотите добавить цветок?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("target_"))
async def choose_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split("_")[1]
    
    if target == "self":
        conn = sqlite3.connect("guild.db")
        cursor = conn.cursor()
        cursor.execute("SELECT ingame_name FROM players WHERE tg_id = ?", (callback.from_user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if not res:
            await callback.message.edit_text("❌ Сначала зарегистрируйтесь (кнопка 'Мой профиль')!", reply_markup=back_keyboard())
            await state.clear()
            return
            
        await state.update_data(target_nick=res[0])
        await callback.message.edit_text("🌸 Введите название цветка:")
        await state.set_state(Form.waiting_flower_name)
    else:
        await callback.message.edit_text("👤 Введите точный игровой ник игрока:")
        await state.set_state(Form.waiting_target_nick)
    await callback.answer()

@dp.message(Form.waiting_target_nick)
async def process_target_nick(message: Message, state: FSMContext):
    await state.update_data(target_nick=message.text.strip())
    await message.answer("🌸 Введите название цветка:")
    await state.set_state(Form.waiting_flower_name)

@dp.message(Form.waiting_flower_name)
async def process_flower_name(message: Message, state: FSMContext):
    await state.update_data(flower_name=message.text.strip().capitalize())
    await message.answer("🔢 Введите количество баллов (уровень) цветка цифрами:")
    await state.set_state(Form.waiting_flower_score)

@dp.message(Form.waiting_flower_score)
async def process_flower_score(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите число:")
        return
        
    score = int(message.text)
    user_data = await state.get_data()
    target_nick = user_data['target_nick']
    flower_name = user_data['flower_name']
    
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE ingame_name = ? AND flower_name = ?", (target_nick, flower_name))
    cursor.execute("INSERT INTO inventory (ingame_name, flower_name, score) VALUES (?, ?, ?)", (target_nick, flower_name, score))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Успешно добавлено!\nИгрок: {target_nick}\nЦветок: {flower_name}\nБаллы: {score}", reply_markup=back_keyboard())
    await state.clear()

@dp.callback_query(F.data == "menu_find")
async def find_click(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 Введите название цветка для поиска:")
    await state.set_state(Form.searching_flower)
    await callback.answer()

@dp.message(Form.searching_flower)
async def process_search(message: Message, state: FSMContext):
    flower_query = message.text.strip().capitalize()
    
    conn = sqlite3.connect("guild.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT MAX(score) FROM inventory WHERE flower_name = ?", (flower_query,))
    max_score_res = cursor.fetchone()
    
    if not max_score_res or max_score_res[0] is None:
        await message.answer(f"❌ Ни у кого не найдено цветка «{flower_query}»", reply_markup=back_keyboard())
        await state.clear()
        conn.close()
        return
        
    max_score = max_score_res[0]
    
    cursor.execute('''SELECT p.tg_username, i.ingame_name, i.score 
                      FROM inventory i
                      LEFT JOIN players p ON i.ingame_name = p.ingame_name
                      WHERE i.flower_name = ?
                      ORDER BY i.score DESC''', (flower_query,))
    owners = cursor.fetchall()
    conn.close()
    
    response = f"🔍 <b>Результаты поиска по: {flower_query}</b>\n\n"
    for tg_user, ingame, score in owners:
        tg_link = f"@{tg_user}" if tg_user else "Нет ТГ"
        badge = " 🌟 (Макс. уровень)" if score == max_score else ""
        response += f"• {tg_link} (ИГ: <i>{ingame}</i>) — <b>{score}</b> баллов{badge}\n"
        
    await message.answer(response, parse_mode="HTML", reply_markup=back_keyboard())
    await state.clear()

import threading
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is running!")

def run_web():
    app = web.Application()
    app.router.add_get('/', handle)
    web.run_app(app, host="0.0.0.0", port=10000)

if __name__ == "__main__":
    # Запускаем обманку для Render в отдельном потоке
    threading.Thread(target=run_web, daemon=True).start()
    # Запускаем нашего бота
    import asyncio
    asyncio.run(dp.start_polling(bot))
    
