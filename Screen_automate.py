import csv
import telegram
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Временное хранилище данных за день
daily_data = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "sleep": {},
    "mood": {},
    "exam_prep": [],
    "weight": {},
    "food": {},
    "work": [],
    "study": [],
    "summary": {}
}

# Состояние пользователей
user_states = {}

# Функция для расчёта продолжительности
def calculate_duration(start_time, end_time):
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    if end < start:
        end += timedelta(days=1)
    delta = end - start
    return delta.total_seconds() / 3600

# Функция записи в CSV
def save_to_csv(data):
    filename = "diary.csv"
    
    base_headers = [
        "Дата", "Сон_Пробуждения", "Сон_Выспанность_(0-5)", "Сон_Время_ч", "Сон_Усталость_Утром_(0-5)",
        "Настроение_Утро_(0-5)", "Настроение_Вечер_(0-5)", "Настроение_Причина"
    ]
    exam_headers = [f"ЕГЭ_{i}_{field}" for i in range(1, len(data["exam_prep"]) + 1) for field in [
        "Предмет", "Начало", "Конец", "Продолжительность_ч", "Усталость_До_(0-5)", "Усталость_После_(0-5)",
        "Сложность_(0-5)", "Отвлечения", "Что_Делал", "Объём"
    ]]
    middle_headers = ["Вес_кг", "Вес_Время_Дня", "Еда_Приёмы", "Еда_Качество_(0-5)", "Еда_Тип"]
    work_headers = [f"Работа_{i}_{field}" for i in range(1, len(data["work"]) + 1) for field in [
        "Начало", "Конец", "Продолжительность_ч", "Энергия_До_(0-5)", "Энергия_После_(0-5)",
        "Дела_Завершено", "Сложность_(0-5)", "Фокус_ч", "Отвлечения", "Тип"
    ]]
    study_headers = [f"Обучение_{i}_{field}" for i in range(1, len(data["study"]) + 1) for field in [
        "Начало", "Конец", "Продолжительность_ч", "Энергия_До_(0-5)", "Энергия_После_(0-5)",
        "Отвлечения", "Что_Делал", "Прогресс_(0-5)"
    ]]
    summary_headers = ["Итог_Усталость_Вечер_(0-5)", "Итог_Оценка_Дня_(0-5)", "Итог_Заметки"]
    headers = base_headers + exam_headers + middle_headers + work_headers + study_headers + summary_headers

    row = [data["date"]]
    row.extend([data["sleep"].get(k, "") for k in ["wakeups", "quality", "hours", "fatigue_morning"]])
    row.extend([data["mood"].get(k, "") for k in ["morning", "evening", "reason"]])
    for session in data["exam_prep"]:
        row.extend([session.get(k, "") for k in ["subject", "start", "end", "duration", "fatigue_before",
                                                 "fatigue_after", "difficulty", "distractions", "activity", "volume"]])
    row.extend([data["weight"].get(k, "") for k in ["kg", "time_of_day"]])
    row.extend([data["food"].get(k, "") for k in ["meals", "quality", "type"]])
    for session in data["work"]:
        row.extend([session.get(k, "") for k in ["start", "end", "duration", "energy_before", "energy_after",
                                                 "tasks", "difficulty", "focus", "distractions", "type"]])
    for session in data["study"]:
        row.extend([session.get(k, "") for k in ["start", "end", "duration", "energy_before", "energy_after",
                                                 "distractions", "activity", "progress"]])
    row.extend([data["summary"].get(k, "") for k in ["fatigue_evening", "day_rating", "notes"]])

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            old_data = list(reader)
            if not old_data:
                old_data = [headers]
    except FileNotFoundError:
        old_data = [headers]

    new_data = []
    date_exists = False
    for line in old_data:
        if line[0] == data["date"] and line[0] != headers[0]:
            new_data.append(row)
            date_exists = True
        else:
            new_data.append(line)
    if not date_exists:
        if len(old_data) == 1:
            new_data = [headers, row]
        else:
            new_data.append(row)

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(new_data)

# Команда /start
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Заполнить данные о сне", callback_data='input_sleep')],
        [InlineKeyboardButton("Заполнить настроение", callback_data='input_mood')],
        [InlineKeyboardButton("Начать подготовку к ЕГЭ", callback_data='input_exam_prep')],
        [InlineKeyboardButton("Заполнить вес тела", callback_data='input_weight')],
        [InlineKeyboardButton("Заполнить данные о еде", callback_data='input_food')],
        [InlineKeyboardButton("Начать работать", callback_data='input_work')],
        [InlineKeyboardButton("Начать учиться", callback_data='input_study')],
        [InlineKeyboardButton("Заполнить итог дня", callback_data='input_summary')],
        [InlineKeyboardButton("Редактировать текущий день", callback_data='edit_data')],
        [InlineKeyboardButton("Редактировать историю", callback_data='edit_history')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Выбери, что хочешь сделать:\n/edit — редактировать текущий день\n/history — редактировать историю", reply_markup=reply_markup)

# Команда /edit
async def edit_command(update, context):
    await edit_data(update.message.chat_id, update.message)

# Команда /history
async def history_command(update, context):
    await edit_history(update.message.chat_id, update.message)

# Обработка кнопок
async def button(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if query.data == 'input_sleep':
        user_states[chat_id] = {'state': 'sleep_wakeups'}
        await query.edit_message_text("Сколько раз просыпался?")
    elif query.data == 'input_mood':
        user_states[chat_id] = {'state': 'mood_morning'}
        await query.edit_message_text("Оценка настроения утром (0-5)?")
    elif query.data == 'input_exam_prep':
        user_states[chat_id] = {'state': 'exam_subject', 'session': {}}
        await query.edit_message_text("Какой предмет (математика, русский, физика, обществознание)?")
    elif query.data == 'input_weight':
        user_states[chat_id] = {'state': 'weight_kg'}
        await query.edit_message_text("Вес (кг)?")
    elif query.data == 'input_food':
        user_states[chat_id] = {'state': 'food_meals'}
        await query.edit_message_text("Сколько приёмов пищи?")
    elif query.data == 'input_work':
        user_states[chat_id] = {'state': 'work_energy_before', 'session': {}}
        await query.edit_message_text("Энергия до работы (0-5)?")
    elif query.data == 'input_study':
        user_states[chat_id] = {'state': 'study_energy_before', 'session': {}}
        await query.edit_message_text("Энергия до обучения (0-5)?")
    elif query.data == 'input_summary':
        user_states[chat_id] = {'state': 'summary_fatigue'}
        await query.edit_message_text("Усталость вечером (0-5, 5 — максимально устал)?")
    elif query.data == 'edit_data':
        await edit_data(chat_id, query)
    elif query.data == 'edit_history':
        await edit_history(chat_id, query)

# Обработка текстовых сообщений
async def handle_message(update, context):
    chat_id = update.message.chat_id
    text = update.message.text
    
    if chat_id not in user_states:
        await update.message.reply_text("Нажми /start, чтобы начать!")
        return

    state = user_states[chat_id].get('state')
    
    # Сон
    if state == 'sleep_wakeups':
        daily_data["sleep"]["wakeups"] = int(text)
        user_states[chat_id]['state'] = 'sleep_quality'
        await update.message.reply_text("Оценка выспанности (0-5)?")
    elif state == 'sleep_quality':
        daily_data["sleep"]["quality"] = int(text)
        user_states[chat_id]['state'] = 'sleep_hours'
        await update.message.reply_text("Время сна (часы)?")
    elif state == 'sleep_hours':
        daily_data["sleep"]["hours"] = float(text)
        user_states[chat_id]['state'] = 'sleep_fatigue'
        await update.message.reply_text("Усталость утром (0-5, 5 — максимально устал)?")
    elif state == 'sleep_fatigue':
        daily_data["sleep"]["fatigue_morning"] = int(text)
        user_states[chat_id]['state'] = 'sleep_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_sleep'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о сне?", reply_markup=reply_markup)

    # Настроение
    elif state == 'mood_morning':
        daily_data["mood"]["morning"] = int(text)
        user_states[chat_id]['state'] = 'mood_evening'
        await update.message.reply_text("Оценка настроения вечером (0-5)?")
    elif state == 'mood_evening':
        daily_data["mood"]["evening"] = int(text)
        user_states[chat_id]['state'] = 'mood_reason'
        await update.message.reply_text("Причина настроения (опционально)?")
    elif state == 'mood_reason':
        daily_data["mood"]["reason"] = text
        user_states[chat_id]['state'] = 'mood_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_mood'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о настроении?", reply_markup=reply_markup)

    # ЕГЭ
    elif state == 'exam_subject':
        user_states[chat_id]['session']['subject'] = text
        user_states[chat_id]['state'] = 'exam_fatigue_before'
        await update.message.reply_text("Ментальная усталость до (0-5)?")
    elif state == 'exam_fatigue_before':
        user_states[chat_id]['session']['fatigue_before'] = int(text)
        user_states[chat_id]['state'] = 'exam_start'
        await update.message.reply_text("Время начала (чч:мм)?")
    elif state == 'exam_start':
        user_states[chat_id]['session']['start'] = text
        user_states[chat_id]['state'] = 'exam_finish'
        keyboard = [[InlineKeyboardButton("Закончить", callback_data='exam_finish')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Начали! Нажми 'Закончить', когда завершишь.", reply_markup=reply_markup)
    elif state == 'exam_end':
        user_states[chat_id]['session']['end'] = text
        user_states[chat_id]['session']['duration'] = calculate_duration(
            user_states[chat_id]['session']['start'], text)
        user_states[chat_id]['state'] = 'exam_fatigue_after'
        await update.message.reply_text("Ментальная усталость после (0-5)?")
    elif state == 'exam_fatigue_after':
        user_states[chat_id]['session']['fatigue_after'] = int(text)
        user_states[chat_id]['state'] = 'exam_difficulty'
        await update.message.reply_text("Сложность материала (0-5)?")
    elif state == 'exam_difficulty':
        user_states[chat_id]['session']['difficulty'] = int(text)
        user_states[chat_id]['state'] = 'exam_distractions'
        await update.message.reply_text("Сколько раз отвлекался?")
    elif state == 'exam_distractions':
        user_states[chat_id]['session']['distractions'] = int(text)
        user_states[chat_id]['state'] = 'exam_activity'
        await update.message.reply_text("Что делал?")
    elif state == 'exam_activity':
        user_states[chat_id]['session']['activity'] = text
        user_states[chat_id]['state'] = 'exam_volume'
        await update.message.reply_text("Объём работы (например, 5 задач)?")
    elif state == 'exam_volume':
        user_states[chat_id]['session']['volume'] = text
        daily_data["exam_prep"].append(user_states[chat_id]['session'])
        user_states[chat_id]['state'] = 'exam_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_exam'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о подготовке к ЕГЭ?", reply_markup=reply_markup)

    # Вес
    elif state == 'weight_kg':
        daily_data["weight"]["kg"] = float(text)
        user_states[chat_id]['state'] = 'weight_time'
        await update.message.reply_text("Время взвешивания (утро/вечер)?")
    elif state == 'weight_time':
        daily_data["weight"]["time_of_day"] = text
        user_states[chat_id]['state'] = 'weight_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_weight'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о весе?", reply_markup=reply_markup)

    # Еда
    elif state == 'food_meals':
        daily_data["food"]["meals"] = int(text)
        user_states[chat_id]['state'] = 'food_quality'
        await update.message.reply_text("Оценка качества питания (0-5)?")
    elif state == 'food_quality':
        daily_data["food"]["quality"] = int(text)
        user_states[chat_id]['state'] = 'food_type'
        await update.message.reply_text("Тип еды (например, овощи, фастфуд)?")
    elif state == 'food_type':
        daily_data["food"]["type"] = text
        user_states[chat_id]['state'] = 'food_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_food'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о еде?", reply_markup=reply_markup)

    # Работа
    elif state == 'work_energy_before':
        user_states[chat_id]['session']['energy_before'] = int(text)
        user_states[chat_id]['state'] = 'work_start'
        await update.message.reply_text("Время начала (чч:мм)?")
    elif state == 'work_start':
        user_states[chat_id]['session']['start'] = text
        user_states[chat_id]['state'] = 'work_finish'
        keyboard = [[InlineKeyboardButton("Закончить", callback_data='work_finish')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Начали! Нажми 'Закончить', когда завершишь.", reply_markup=reply_markup)
    elif state == 'work_end':
        user_states[chat_id]['session']['end'] = text
        user_states[chat_id]['session']['duration'] = calculate_duration(
            user_states[chat_id]['session']['start'], text)
        user_states[chat_id]['state'] = 'work_energy_after'
        await update.message.reply_text("Энергия после работы (0-5)?")
    elif state == 'work_energy_after':
        user_states[chat_id]['session']['energy_after'] = int(text)
        user_states[chat_id]['state'] = 'work_tasks'
        await update.message.reply_text("Сколько дел завершил?")
    elif state == 'work_tasks':
        user_states[chat_id]['session']['tasks'] = int(text)
        user_states[chat_id]['state'] = 'work_difficulty'
        await update.message.reply_text("Сложность работы (0-5)?")
    elif state == 'work_difficulty':
        user_states[chat_id]['session']['difficulty'] = int(text)
        user_states[chat_id]['state'] = 'work_focus'
        await update.message.reply_text("Время в фокусе (часы)?")
    elif state == 'work_focus':
        user_states[chat_id]['session']['focus'] = float(text)
        user_states[chat_id]['state'] = 'work_distractions'
        await update.message.reply_text("Сколько раз отвлекался?")
    elif state == 'work_distractions':
        user_states[chat_id]['session']['distractions'] = int(text)
        user_states[chat_id]['state'] = 'work_type'
        await update.message.reply_text("Тип задач (например, рутина)?")
    elif state == 'work_type':
        user_states[chat_id]['session']['type'] = text
        daily_data["work"].append(user_states[chat_id]['session'])
        user_states[chat_id]['state'] = 'work_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_work'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные о работе?", reply_markup=reply_markup)

    # Обучение
    elif state == 'study_energy_before':
        user_states[chat_id]['session']['energy_before'] = int(text)
        user_states[chat_id]['state'] = 'study_start'
        await update.message.reply_text("Время начала (чч:мм)?")
    elif state == 'study_start':
        user_states[chat_id]['session']['start'] = text
        user_states[chat_id]['state'] = 'study_finish'
        keyboard = [[InlineKeyboardButton("Закончить", callback_data='study_finish')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Начали! Нажми 'Закончить', когда завершишь.", reply_markup=reply_markup)
    elif state == 'study_end':
        user_states[chat_id]['session']['end'] = text
        user_states[chat_id]['session']['duration'] = calculate_duration(
            user_states[chat_id]['session']['start'], text)
        user_states[chat_id]['state'] = 'study_energy_after'
        await update.message.reply_text("Энергия после обучения (0-5)?")
    elif state == 'study_energy_after':
        user_states[chat_id]['session']['energy_after'] = int(text)
        user_states[chat_id]['state'] = 'study_distractions'
        await update.message.reply_text("Сколько раз отвлекался?")
    elif state == 'study_distractions':
        user_states[chat_id]['session']['distractions'] = int(text)
        user_states[chat_id]['state'] = 'study_activity'
        await update.message.reply_text("Что делал?")
    elif state == 'study_activity':
        user_states[chat_id]['session']['activity'] = text
        user_states[chat_id]['state'] = 'study_progress'
        await update.message.reply_text("Оценка прогресса (0-5)?")
    elif state == 'study_progress':
        user_states[chat_id]['session']['progress'] = int(text)
        daily_data["study"].append(user_states[chat_id]['session'])
        user_states[chat_id]['state'] = 'study_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_study'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить данные об обучении?", reply_markup=reply_markup)

    # Итог дня
    elif state == 'summary_fatigue':
        daily_data["summary"]["fatigue_evening"] = int(text)
        user_states[chat_id]['state'] = 'summary_rating'
        await update.message.reply_text("Общая оценка дня (0-5)?")
    elif state == 'summary_rating':
        daily_data["summary"]["day_rating"] = int(text)
        user_states[chat_id]['state'] = 'summary_notes'
        await update.message.reply_text("Заметки (опционально)?")
    elif state == 'summary_notes':
        daily_data["summary"]["notes"] = text
        user_states[chat_id]['state'] = 'summary_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_summary'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить итог дня?", reply_markup=reply_markup)

    # Редактирование сессий
    elif state.startswith('exam_edit_'):
        session_num = user_states[chat_id]['session_num']
        daily_data["exam_prep"][session_num]["subject"] = text
        user_states[chat_id]['state'] = f'exam_edit_fatigue_before_{session_num}'
        await update.message.reply_text("Ментальная усталость до (0-5)?")
    elif state.startswith('exam_edit_fatigue_before_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["fatigue_before"] = int(text)
        user_states[chat_id]['state'] = f'exam_edit_start_{session_num}'
        await update.message.reply_text("Время начала (чч:мм)?")
    elif state.startswith('exam_edit_start_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["start"] = text
        user_states[chat_id]['state'] = f'exam_edit_end_{session_num}'
        await update.message.reply_text("Время конца (чч:мм)?")
    elif state.startswith('exam_edit_end_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["end"] = text
        daily_data["exam_prep"][session_num]["duration"] = calculate_duration(
            daily_data["exam_prep"][session_num]["start"], text)
        user_states[chat_id]['state'] = f'exam_edit_fatigue_after_{session_num}'
        await update.message.reply_text("Ментальная усталость после (0-5)?")
    elif state.startswith('exam_edit_fatigue_after_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["fatigue_after"] = int(text)
        user_states[chat_id]['state'] = f'exam_edit_difficulty_{session_num}'
        await update.message.reply_text("Сложность материала (0-5)?")
    elif state.startswith('exam_edit_difficulty_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["difficulty"] = int(text)
        user_states[chat_id]['state'] = f'exam_edit_distractions_{session_num}'
        await update.message.reply_text("Сколько раз отвлекался?")
    elif state.startswith('exam_edit_distractions_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["distractions"] = int(text)
        user_states[chat_id]['state'] = f'exam_edit_activity_{session_num}'
        await update.message.reply_text("Что делал?")
    elif state.startswith('exam_edit_activity_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["activity"] = text
        user_states[chat_id]['state'] = f'exam_edit_volume_{session_num}'
        await update.message.reply_text("Объём работы (например, 5 задач)?")
    elif state.startswith('exam_edit_volume_'):
        session_num = int(state.split('_')[-1])
        daily_data["exam_prep"][session_num]["volume"] = text
        user_states[chat_id]['state'] = 'exam_edit_save'
        keyboard = [[InlineKeyboardButton("Сохранить", callback_data='save_exam'),
                     InlineKeyboardButton("Не сохранять", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сохранить изменения в сессии ЕГЭ?", reply_markup=reply_markup)

    # История
    elif state == 'history_date':
        await load_history(chat_id, text, update.message)

# Обработка сохранения
async def handle_save(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if query.data.startswith('save_'):
        save_to_csv(daily_data)
        await query.edit_message_text(f"Данные сохранены! Нажми /start для продолжения.")
    elif query.data == 'exam_finish':
        user_states[chat_id]['state'] = 'exam_end'
        await query.edit_message_text("Время конца (чч:мм)?")
    elif query.data == 'work_finish':
        user_states[chat_id]['state'] = 'work_end'
        await query.edit_message_text("Время конца (чч:мм)?")
    elif query.data == 'study_finish':
        user_states[chat_id]['state'] = 'study_end'
        await query.edit_message_text("Время конца (чч:мм)?")
    elif query.data == 'cancel':
        await query.edit_message_text("Данные не сохранены. Нажми /start для продолжения.")
    
    if chat_id in user_states:
        del user_states[chat_id]

# Редактирование текущего дня
# Редактирование текущего дня
async def edit_data(chat_id, message):
    keyboard = [
        [InlineKeyboardButton("Сон", callback_data='edit_sleep')],
        [InlineKeyboardButton("Настроение", callback_data='edit_mood')],
        [InlineKeyboardButton("ЕГЭ", callback_data='edit_exam')],
        [InlineKeyboardButton("Вес", callback_data='edit_weight')],
        [InlineKeyboardButton("Еда", callback_data='edit_food')],
        [InlineKeyboardButton("Работа", callback_data='edit_work')],
        [InlineKeyboardButton("Обучение", callback_data='edit_study')],
        [InlineKeyboardButton("Итог дня", callback_data='edit_summary')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Исправление: используем полное имя telegram.Message для проверки типа
    if isinstance(message, telegram.Message):
        await message.reply_text("Что хочешь отредактировать?", reply_markup=reply_markup)
    else:
        await message.edit_message_text("Что хочешь отредактировать?", reply_markup=reply_markup)
# Редактирование истории
async def edit_history(chat_id, message):
    try:
        with open("diary.csv", 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
            if len(data) <= 1:
                await message.edit_message_text("История пуста.")
                return
            dates = [row[0] for row in data[1:]]
            await message.edit_message_text(f"Доступные даты: {', '.join(dates)}\nВведи дату (гггг-мм-дд):")
            user_states[chat_id] = {'state': 'history_date'}
    except FileNotFoundError:
        await message.edit_message_text("Файл diary.csv не найден.")

async def load_history(chat_id, date, message):
    global daily_data
    try:
        with open("diary.csv", 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
            headers = data[0]
            for row in data[1:]:
                if row[0] == date:
                    daily_data = {"date": date, "sleep": {}, "mood": {}, "exam_prep": [], "weight": {},
                                  "food": {}, "work": [], "study": [], "summary": {}}
                    daily_data["sleep"] = {"wakeups": row[1], "quality": row[2], "hours": row[3], "fatigue_morning": row[4]}
                    daily_data["mood"] = {"morning": row[5], "evening": row[6], "reason": row[7]}
                    i = 8
                    while i < len(row) and "ЕГЭ" in headers[i]:
                        daily_data["exam_prep"].append({
                            "subject": row[i], "start": row[i+1], "end": row[i+2], "duration": row[i+3],
                            "fatigue_before": row[i+4], "fatigue_after": row[i+5], "difficulty": row[i+6],
                            "distractions": row[i+7], "activity": row[i+8], "volume": row[i+9]
                        })
                        i += 10
                    daily_data["weight"] = {"kg": row[i], "time_of_day": row[i+1]}
                    i += 2
                    daily_data["food"] = {"meals": row[i], "quality": row[i+1], "type": row[i+2]}
                    i += 3
                    while i < len(row) and "Работа" in headers[i]:
                        daily_data["work"].append({
                            "start": row[i], "end": row[i+1], "duration": row[i+2], "energy_before": row[i+3],
                            "energy_after": row[i+4], "tasks": row[i+5], "difficulty": row[i+6], "focus": row[i+7],
                            "distractions": row[i+8], "type": row[i+9]
                        })
                        i += 10
                    while i < len(row) and "Обучение" in headers[i]:
                        daily_data["study"].append({
                            "start": row[i], "end": row[i+1], "duration": row[i+2], "energy_before": row[i+3],
                            "energy_after": row[i+4], "distractions": row[i+5], "activity": row[i+6], "progress": row[i+7]
                        })
                        i += 8
                    daily_data["summary"] = {"fatigue_evening": row[i], "day_rating": row[i+1], "notes": row[i+2]}
                    await message.reply_text(f"Данные за {date} загружены. Используй /edit для редактирования.")
                    break
            else:
                await message.reply_text("Дата не найдена.")
    except FileNotFoundError:
        await message.reply_text("Файл diary.csv не найден.")
    finally:
        if chat_id in user_states:
            del user_states[chat_id]

# Обработка редактирования
async def handle_edit(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    action = query.data.split('_')[1]

    if action == 'sleep':
        user_states[chat_id] = {'state': 'sleep_wakeups'}
        await query.edit_message_text(f"Текущие данные о сне: {daily_data['sleep']}\nСколько раз просыпался?")
    elif action == 'mood':
        user_states[chat_id] = {'state': 'mood_morning'}
        await query.edit_message_text(f"Текущие данные о настроении: {daily_data['mood']}\nОценка настроения утром (0-5)?")
    elif action == 'exam':
        if daily_data["exam_prep"]:
            keyboard = [[InlineKeyboardButton(f"Сессия {i+1}", callback_data=f"exam_session_{i}") 
                         for i in range(len(daily_data["exam_prep"]))]] + \
                       [[InlineKeyboardButton("Добавить новую", callback_data='input_exam_prep')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выбери сессию для редактирования или добавь новую:", reply_markup=reply_markup)
        else:
            user_states[chat_id] = {'state': 'exam_subject', 'session': {}}
            await query.edit_message_text("Сессий ЕГЭ нет. Какой предмет?")
    elif action == 'weight':
        user_states[chat_id] = {'state': 'weight_kg'}
        await query.edit_message_text(f"Текущие данные о весе: {daily_data['weight']}\nВес (кг)?")
    elif action == 'food':
        user_states[chat_id] = {'state': 'food_meals'}
        await query.edit_message_text(f"Текущие данные о еде: {daily_data['food']}\nСколько приёмов пищи?")
    elif action == 'work':
        if daily_data["work"]:
            keyboard = [[InlineKeyboardButton(f"Сессия {i+1}", callback_data=f"work_session_{i}") 
                         for i in range(len(daily_data["work"]))]] + \
                       [[InlineKeyboardButton("Добавить новую", callback_data='input_work')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выбери сессию для редактирования или добавь новую:", reply_markup=reply_markup)
        else:
            user_states[chat_id] = {'state': 'work_energy_before', 'session': {}}
            await query.edit_message_text("Сессий работы нет. Энергия до работы (0-5)?")
    elif action == 'study':
        if daily_data["study"]:
            keyboard = [[InlineKeyboardButton(f"Сессия {i+1}", callback_data=f"study_session_{i}") 
                         for i in range(len(daily_data["study"]))]] + \
                       [[InlineKeyboardButton("Добавить новую", callback_data='input_study')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выбери сессию для редактирования или добавь новую:", reply_markup=reply_markup)
        else:
            user_states[chat_id] = {'state': 'study_energy_before', 'session': {}}
            await query.edit_message_text("Сессий обучения нет. Энергия до обучения (0-5)?")
    elif action == 'summary':
        user_states[chat_id] = {'state': 'summary_fatigue'}
        await query.edit_message_text(f"Текущий итог дня: {daily_data['summary']}\nУсталость вечером (0-5)?")
    elif action.startswith('exam_session_') or action.startswith('work_session_') or action.startswith('study_session_'):
        category, session_num = action.split('_')[0], int(action.split('_')[2])
        if category == 'exam':
            sess = daily_data["exam_prep"][session_num]
            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data=f"edit_{category}_{session_num}")],
                [InlineKeyboardButton("Удалить", callback_data=f"delete_{category}_{session_num}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Сессия {session_num + 1}: {sess}\nЧто сделать?", reply_markup=reply_markup)
        elif category == 'work':
            sess = daily_data["work"][session_num]
            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data=f"edit_{category}_{session_num}")],
                [InlineKeyboardButton("Удалить", callback_data=f"delete_{category}_{session_num}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Сессия {session_num + 1}: {sess}\nЧто сделать?", reply_markup=reply_markup)
        elif category == 'study':
            sess = daily_data["study"][session_num]
            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data=f"edit_{category}_{session_num}")],
                [InlineKeyboardButton("Удалить", callback_data=f"delete_{category}_{session_num}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Сессия {session_num + 1}: {sess}\nЧто сделать?", reply_markup=reply_markup)
    elif action.startswith('edit_exam_') or action.startswith('edit_work_') or action.startswith('edit_study_'):
        category, session_num = action.split('_')[1], int(action.split('_')[2])
        user_states[chat_id] = {'state': f'{category}_edit_{session_num}', 'session_num': session_num}
        if category == 'exam':
            await query.edit_message_text(f"Редактируем сессию ЕГЭ {session_num + 1}: {daily_data['exam_prep'][session_num]}\nНовый предмет?")
        elif category == 'work':
            await query.edit_message_text(f"Редактируем сессию работы {session_num + 1}: {daily_data['work'][session_num]}\nНовая энергия до работы (0-5)?")
        elif category == 'study':
            await query.edit_message_text(f"Редактируем сессию обучения {session_num + 1}: {daily_data['study'][session_num]}\nНовая энергия до обучения (0-5)?")
    elif action.startswith('delete_'):
        category, session_num = action.split('_')[1], int(action.split('_')[2])
        if category == 'exam':
            del daily_data["exam_prep"][session_num]
        elif category == 'work':
            del daily_data["work"][session_num]
        elif category == 'study':
            del daily_data["study"][session_num]
        save_to_csv(daily_data)
        await query.edit_message_text(f"Сессия {session_num + 1} удалена и сохранена в CSV!")

# Главная функция
def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CallbackQueryHandler(button, pattern='^(input_|edit_)'))
    application.add_handler(CallbackQueryHandler(handle_save, pattern='^(save_|exam_finish|work_finish|study_finish|cancel)'))
    application.add_handler(CallbackQueryHandler(handle_edit, pattern='^(edit_|delete_)'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()