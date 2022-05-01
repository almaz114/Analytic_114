import pandas as pd
import numpy as np
import time
# import pytz
import colorama
from colorama import Fore, Back, Style

# import MetaTrader5 as mt5    # Для META TRADER 5
from datetime import datetime
import time
import os
import json
# from class_json import read_from_json  # для работы с json
# import threading

# -- Aiogram -- #
from aiogram import Bot, types    # для Aiogram
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
import asyncio

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton

# from regular_expression import find_name_algorithm      # главная ф-ия для регулярок

colorama.init()

bot = Bot(token="1465371062:AAH25PeGluK6vcb0IrLPFo2J7de_SGzWU0E")
dp = Dispatcher(bot)

# -- login / password / server / path_of_algorithms for MT_account


# --> 1. Клавиатуры KeyboardButton *******************************************

button_hi = KeyboardButton('Привет ты кто ? ! 👋')
button_reg = KeyboardButton('Регистрация -> ! 👋')
button_info = KeyboardButton('Общая информация о системе\nUmbrella ! ')
button_instr = KeyboardButton('Общая инструкция ! ')
greet_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(button_hi).add(button_reg).add(button_info).add(button_instr)
# создаем малеленкую клавиатуру


button1 = KeyboardButton('1️⃣')
button2 = KeyboardButton('2️⃣')
button3 = KeyboardButton('3️⃣')

markup1 = ReplyKeyboardMarkup().add(button1).add(button2).add(button3)
markup2 = ReplyKeyboardMarkup().row(button1, button2, button3)
markup3 = ReplyKeyboardMarkup().row(button1, button2, button3)
markup4 = ReplyKeyboardMarkup().row(button1, button2, button3).add(KeyboardButton('Средний ряд'))

# ******************** для однократного появления клавиатуры ***************** #

greet_kb2 = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(button_hi)

# **********************************************************

# --> 2. Клавиатуры InlineKeyboardMarkup *******************************************

inline_btn_1 = InlineKeyboardButton('Первая кнопка!', callback_data='button1')
inline_kb1 = InlineKeyboardMarkup().add(inline_btn_1)

inline_btn_3 = InlineKeyboardButton('кнопка 3', callback_data='btn3')
inline_btn_4 = InlineKeyboardButton('кнопка 4', callback_data='btn4')
inline_btn_5 = InlineKeyboardButton('кнопка 5', callback_data='btn5')

inline_kb_full = InlineKeyboardMarkup(row_width=2).add(inline_btn_1)
inline_kb_full.add(InlineKeyboardButton('Вторая кнопка', callback_data='btn2'))
inline_kb_full.add(inline_btn_3, inline_btn_4, inline_btn_5)
inline_kb_full.row(inline_btn_3, inline_btn_4, inline_btn_5)
inline_kb_full.insert(InlineKeyboardButton("query=''", switch_inline_query=''))
inline_kb_full.insert(InlineKeyboardButton("query='qwerty'", switch_inline_query='qwerty'))
inline_kb_full.insert(InlineKeyboardButton("Inline в этом же чате", switch_inline_query_current_chat='wasd'))
inline_kb_full.add(InlineKeyboardButton('Уроки aiogram', url='https://surik00.gitbooks.io/aiogram-lessons/content/'))

# urls keyboard
# inline_kb_ursl.add(InlineKeyboardButton('Alfa-Forex', url='https://alfaforex.ru/'))
# inline_kb_ursl.add(InlineKeyboardButton('Alpari', url='https://alpari.finance/ru/'))
# inline_kb_ursl.add(InlineKeyboardButton('Удаленные сервера VPS', url='https://profitserver.ru/'))

# --> Мое Базовое Меню/клавиатура/buttons
# базовое меню
inline_btn_base_1 = InlineKeyboardButton('Umbrella Algorithmic !', callback_data='button_base_1')
inline_btn_base_2 = InlineKeyboardButton('Account info !', callback_data='button_base_2')
inline_btn_base_3 = InlineKeyboardButton('Watch_List !', callback_data='button_base_3')
inline_btn_base_4 = InlineKeyboardButton('Configure algorithm !', callback_data='button_base_4')
# подменю - Umbrella
inline_btn_base_1_1 = InlineKeyboardButton('Описание системы Umbrella !', callback_data='button_base_1_1')
inline_btn_base_1_2 = InlineKeyboardButton('Инструкция !', callback_data='button_base_1_2')
inline_btn_base_1_3 = InlineKeyboardButton('Как приобрести/купить !', callback_data='button_base_1_3')
inline_btn_base_1_4 = InlineKeyboardButton('Ссылки !', callback_data='button_base_1_4')
inline_btn_base_1_5 = InlineKeyboardButton('Статистика !', callback_data='button_base_1_5')
# подменю - Account info
inline_btn_base_2_1 = InlineKeyboardButton('Баланс/просадка/PL !', callback_data='button_base_2_1')
inline_btn_base_2_2 = InlineKeyboardButton('Прибыль/убыток за последние 7 дн !', callback_data='button_base_2_2')
inline_btn_base_2_3 = InlineKeyboardButton('Прибыль/убыток за последний месяц !', callback_data='button_base_2_3')
# подменю - Watch_List
inline_btn_base_3_1 = InlineKeyboardButton('Общий анализ по всем валютам !', callback_data='button_base_3_1')
inline_btn_base_3_2 = InlineKeyboardButton('Анализ по EURUSD !', callback_data='button_base_3_2')
inline_btn_base_3_3 = InlineKeyboardButton('Анализ по GBPUSD !', callback_data='button_base_3_3')
inline_btn_base_3_4 = InlineKeyboardButton('Анализ по AUDUSD !', callback_data='button_base_3_4')
inline_btn_base_3_5 = InlineKeyboardButton('Анализ по USDCAD !', callback_data='button_base_3_5')
inline_btn_base_3_6 = InlineKeyboardButton('Анализ по GBPJPY !', callback_data='button_base_3_6')
# подменю - Config algorithms
inline_btn_base_4_1 = InlineKeyboardButton('алгоритм Hedge !', callback_data='button_base_4_1')

inline_btn_base_4_2 = InlineKeyboardButton('алгоритм TradeExtremum !', callback_data='button_base_4_2')
inline_btn_base_4_3 = InlineKeyboardButton('алгоритм Global_levels !', callback_data='button_base_4_3')
inline_btn_base_4_4 = InlineKeyboardButton('новый алгоритм !', callback_data='button_base_4_4')
# inline_btn_base_4_5 = InlineKeyboardButton('новый алгоритм !', callback_data='button_base_4_5')
# inline_btn_base_4_6 = InlineKeyboardButton('новый алгоритм !', callback_data='button_base_4_6')

# Cоздание самих клавиатур и добавление к ним ранее созданных кнопок
inline_kb_base_menu = InlineKeyboardMarkup().add(inline_btn_base_1, inline_btn_base_2, inline_btn_base_3, inline_btn_base_4)
inline_kb_base_menu_1 = InlineKeyboardMarkup().add(inline_btn_base_1_1, inline_btn_base_1_2, inline_btn_base_1_3, inline_btn_base_1_4, inline_btn_base_1_5)
inline_kb_base_menu_2 = InlineKeyboardMarkup().add(inline_btn_base_2_1, inline_btn_base_2_2, inline_btn_base_2_3)
inline_kb_base_menu_3 = InlineKeyboardMarkup().add(inline_btn_base_3_1, inline_btn_base_3_2, inline_btn_base_3_3, inline_btn_base_3_4, inline_btn_base_3_5, inline_btn_base_3_6)
inline_kb_base_menu_4 = InlineKeyboardMarkup().add(inline_btn_base_4_1, inline_btn_base_4_2, inline_btn_base_4_3, inline_btn_base_4_4)

# Создание подклавиатур
# inline_kb_base_menu 1.4

inline_kb_base_menu_1_4 = InlineKeyboardMarkup().add(inline_btn_base_1, inline_btn_base_2, inline_btn_base_3, inline_btn_base_4)

# -- end
# --
help_message = (
    "Это урок по клавиатурам.",
    "Доступные команды:\n",
    "/start - приветствие",
    "\nШаблоны клавиатур:",
    "/menu - основное меню",
    "/hi2 - скрыть после нажатия",
    "\nИнлайн клавиатуры:",
    "/1 - первая кнопка",
    "/2 - сразу много кнопок"
)


# --- ВЫВОД ИНФОРМАЦИИ ОБ СЧЕТЕ ИЗ ТЕРМИНАЛА #
def telegrambot():
    """ Запуск телеграм бота для взаимодейтсвия с пользователем """
    while True:
        # bot.py
        @dp.message_handler(commands=['1'])
        async def process_command_1(message: types.Message):
            await message.reply("Привет Tony как дела ? ", reply_markup=inline_kb1)

        @dp.callback_query_handler(lambda c: c.data == 'button1')
        async def process_callback_button1(callback_query: types.CallbackQuery):
            now = datetime.now()
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, f'Дела отлично {now}!')

        # new
        @dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn'))
        async def process_callback_kb1btn1(callback_query: types.CallbackQuery):
            code = callback_query.data[-1]
            if code.isdigit():
                code = int(code)
            if code == 2:
                await bot.answer_callback_query(callback_query.id, text='Нажата вторая кнопка')
            elif code == 5:
                await bot.answer_callback_query(
                    callback_query.id,
                    text='Нажата кнопка с номером 5.\nА этот текст может быть длиной до 200 символов 😉', show_alert=True)
            else:
                await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, f'Нажата инлайн кнопка! code={code}')

        @dp.message_handler(commands=['2'])
        async def process_command_2(message: types.Message):
            await message.reply("Отправляю все возможные кнопки", reply_markup=inline_kb_full)
        # end

        # --> help messages
        @dp.message_handler(commands=['help'])
        async def process_help_command(message: types.Message):
            await message.reply(help_message)

        # --> МОЕ ОСНОВНОЕ МЕНЮ ДЛЯ TELEGRAM BOT -------------------------------------------------------
        @dp.message_handler(commands=['menu'])
        async def process_command_2(message: types.Message):
            await message.reply("Основное меню", reply_markup=inline_kb_base_menu)

        # --> вызов меню 1. "Umbrella"
        @dp.callback_query_handler(lambda c: c.data == 'button_base_1')
        async def process_callback_button1(callback_query: types.CallbackQuery):
            now = datetime.now()
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, f'Текущее время: {now}!')
            # inline_kb_base_menu = types.ReplyKeyboardRemove(selective=False)
            await bot.send_message(callback_query.from_user.id, "Список команд для Umberlla", reply_markup=inline_kb_base_menu_1)

        # --> вызов меню 2. "Account info"
        @dp.callback_query_handler(lambda c: c.data == 'button_base_2')
        async def process_callback_button1(callback_query: types.CallbackQuery):
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, "Список команд для Account info", reply_markup=inline_kb_base_menu_2)

        # --> вызов меню 3. "Watch_List"
        @dp.callback_query_handler(lambda c: c.data == 'button_base_3')
        async def process_callback_button1(callback_query: types.CallbackQuery):
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, "Список команд для Watch_List", reply_markup=inline_kb_base_menu_3)

        # --> вызов меню 4. "Configure algorithm"
        @dp.callback_query_handler(lambda c: c.data == 'button_base_4')
        async def process_callback_button4(callback_query: types.CallbackQuery):
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(callback_query.from_user.id, "Список команд для Configure algorithm", reply_markup=inline_kb_base_menu_4)

        # --> вызов подменю 1.1 "Umbrella system --> ОПИСАНИЕ СИСТЕМЫ"
        @dp.callback_query_handler(lambda c: c.data == 'button_base_1_1')
        async def process_callback_button1_1(callback_query: types.CallbackQuery):
            await bot.answer_callback_query(callback_query.id)
            info_text = "Алгоритмическая система Umbrella - это набор автоматизированных торговых систем предназначенных для торговли\
                на валютном рынке Forex используя различные аналитические модули. В данной системе можно гибко настроить управление\
                капиталом , а именно риск на одну сделку, общий риск на депозит в процентном соотношении и абсолютной величине\
                депозита. Дополнительно можно настроить уведомления через telegram_bot для каждого пользователя.\
                В ближайшей перспективе будет работать и для опционного\
                срочного рынка (!!! не путать с бинарными опционами). До конца 2021 г. будет запущена торговля на криптобирже Binance.com "
            await bot.send_message(callback_query.from_user.id, info_text)

        # --> вызов подменю 1.2 "Umbrella system --> КРАТКАЯ ИНСТРУКЦИЯ"

        @dp.callback_query_handler(lambda c: c.data == 'button_base_1_2')
        async def process_callback_button1_2(callback_query: types.CallbackQuery):
            await bot.answer_callback_query(callback_query.id)
            info_text = "1) Необходимо зарегистрироваться у брокера/дилера предостовляющего услуги доступа к валютному рынку Forex\
                и у которого разрешена алгоритмическая торговля на терминале MetaTrader5 !\
                \nРекомендуем следущих дилеров Fx: Alpari (https://alpari.finance/ru/), A-Market (https://amarkets.pro/), а также Альфа-форекс(дочерняя фирма Альфа\
                 Банка - (https://alfaforex.ru/)) либо ВТБ-Форекс\
                \n2) Далее необходимо иметь ноутбук/компьютер (Строго рекомендуется арендовать удаленный сервер VPS (300-500 руб/месяц)\
                на котором будет запущен алгоритмическая система\
                3)Минимальный счет/депозит для торговли рекомендуется в размере от 25000 руб/ 345 долларов и депозит нужно \
                  держать именно в долларах США) \n4) Дополнительно для настройки telegram_bot необходимо узнать свой telegram chat/id\
                  для этого нужно ввести название @userinfobot и отправить ему смс со словом «начать» или «start». После этого система \
                  высылает вам ваши имя, фамилию и отчество плюс id. "
            await bot.send_message(callback_query.from_user.id, info_text)

        # -- О С Н О В Н О Й  П Р О Ц Е С С  Д Л Я  Р А Б О Т Ы  T E L E G R A M  B O T
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if __name__ == '__main__':
            # dp.loop.create_task(scheduled(30))
            executor.start_polling(dp, skip_updates=True)


telegrambot()
