"""
Реализация Аналитический центра - комплекс аналитических модулей,
каждый из которых отвечает за свою часть логику, эти модули запускаются асинхронно
по своему временному алгоритму/периоду

используется:
asyncio
loguru - для отлова ошибок и сохранения ошибок в файлы
notifiers - для работы с telegram (для уведомлений при появлений сигналов)
Class_Meta_Trader - Собственный Класс для работы с валютным рынком для получения данных временных рядов
Postge_Sql - для работы с базой данных
"""

import asyncio
# import pyqtgraph, operator
import datetime
import inspect
import json
import os
import os.path
import re
import sys
from typing import Union
from datetime import datetime
import time
from distutils.util import strtobool
import numpy as np
import pandas as pd

# from schedule import every, repeat, run_pending
import MetaTrader5 as mt5
import pytz
import notifiers  # для получение уведомлений
# from datetime import datetime
from loguru import logger  # для ведения логов
from notifiers import get_notifier
from notifiers.logging import NotificationHandler
from rich.console import Console
from rich.table import Table

# I M P O R T  C L A S S_M E T A_T R A D E R  A S  C L A S S_MT5
# from Class_Meta_Trader import Meta_Trader  # импорт класса работы с Meta Trader 5
from Class_Meta_Trader import get_data_from_url  # для получения данных из Kovach signals
from Class_Meta_Trader import read_json_file  # для чтения json файлов
from Class_Meta_Trader import get_history_price  # получаем данные из рынка

# import class for workinf with database (Postgre)
from Postgres_Class import info_database

# -- notification params --
params = {"xxx": 123}
notifier = notifiers.get_notifier("gmail")  # уведомления через "gmail"
handler = NotificationHandler("gmail", defaults=params)  # используем указанные ранее параметры

# -- login / password / server / path_of_algorithms for MT_account
account_dict = read_json_file(filename="config_files/account_info.json")  # read data login/pass/server from json file
base_dict = read_json_file(filename="config_files/settings.json")  # read global_server from json file
database_dict = read_json_file(filename="config_files//settings_database.json")  # get data server for kovach
telegram_dict = read_json_file(filename="config_files/telegram_bot.json")

base_dir = base_dict['Base_dir']    # ||| Главная папка проекта |||
symbols = base_dict['symbols']      # список валютных пар по ко-м работаем

# -- > логирование ошибок/нужной информации в определенные файлы < -- #
logger.add(base_dir + "logs//errors.log", format="{time} {level} {message}", rotation="10:00", retention="4 days",
           level="ERROR", compression="zip", enqueue=True)
# logger.add("files//logs//info_debug.log", format="{time} {level} {message}", rotation="10:00", retention="2 days",
#            level="INFO", compression="zip", enqueue=True)
logger.add(base_dir + "logs//info_warning.log", format="{time} {level} {message}", rotation="10:00", retention="5 days",
           level="WARNING", compression="zip", enqueue=True)

# -- обьявление переменных -- #
# symbols = ["EURUSD", "USDCAD", "EURGBP", "NZDUSD", "AUDUSD", "GBPUSD"]  # список валютных пар

# dict_a = list_a[0]  # словарь со значениями Login/Password/Server
# login, password, server = account_dict["Login"], account_dict["Password"], account_dict["Server"]  # get data

# -- > обьявим обьект для работы с классом Class_metatrader <--
# Terminal = Meta_Trader(login, password, server)

# -- > переменные для работы с БД Postgre_Sql
database, user_name_db = database_dict["database"], database_dict['user_name_db']
password, host, port = database_dict['password'], database_dict['host'], database_dict['port']

# -- Token / Chat_id for telegram_bot ----
token = telegram_dict["Token"]
chat_id = telegram_dict["Chat_id"]

cur_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
working_days = [1, 2, 3, 4, 5]

# -- Версия программы
version_main = 'Analytic_Center 1.1'


# current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
# current_day_name = datetime.today().strftime('%A')  # проверка текущего дня недели (имя дня недели)
# -- end -- #################


# ||| Check connect to MT5
# установим подключение к терминалу MetaTrader 5
def test_mt5_connection():
    try:
        if not mt5.initialize():
            logger.error(f"\ninitialize() failed, error code = {mt5.last_error()}")
            logger.info("wait some time because error !!!")
            time.sleep(90)
            connection_mt5_status = False
            quit()
        else:
            connection_mt5_status = True
            return connection_mt5_status
    except:
        test_mt5_connection()


connection_mt5_status = test_mt5_connection()

# ||| Check connect to Data_Base (Postgre_SQL)
status_db = info_database(database=database, user=user_name_db, password=password, host=host, port=port)

# --- set rich table
table_1 = Table(title=version_main)
today = datetime.now()

table_1.add_column("name", justify="center", style="cyan", no_wrap=False)
table_1.add_column("value", style="magenta")
table_1.add_column("datetime", justify="center", style="green")
table_1.add_row("Состояние аналитического центра", "Включено", str(today.strftime("%Y-%m-%d-%H.%M.%S")))
table_1.add_row("Рабочая папка проекта", base_dir, "xx")
table_1.add_row("Текущий день недели", str(cur_day), "xx")
table_1.add_row("Connection_mt5_status", str(connection_mt5_status), "xx")
table_1.add_row("Connect_DataBase_status", str(status_db), "xx")
os.system('cls')
console = Console()
console.print(table_1)
time.sleep(5)

# data_frame = get_history_price(symbol="EURUSD", count_bars=90, filename_path=base_dir, timeframe="d1", day=21, month=3,
#                                year=2021)


#  О С Н О В Н О Й  К О Д  П Р О Г Р А М М Ы (запуск асинхронного цикла функций по расписанию )


async def async_func():
    print('Begin 1 ...')
    await asyncio.sleep(1)
    print('... End 1!')


async def async_func_2():
    print('Begin 2 ...')
    await asyncio.sleep(1)
    print('... End 2!')


async def get_save_history_prices(symbol: Union[str, list], count_bars: int, timeframe: str, day: int, month: int, year: int):
    """
    получение и сохранение dataframe/числовых рядов в .csv
    """
    await asyncio.sleep(1)
    if isinstance(symbol, list) and len(symbol):
        for i, sym in enumerate(symbol):
            data_frame = get_history_price(symbol=sym, count_bars=count_bars, filename_path=base_dir,
                                           timeframe=timeframe, day=day, month=month, year=year)
            await asyncio.sleep(6)


async def main():
    while True:
        day_week = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
        date = datetime.today()
        current_year = date.year
        current_month = date.month
        current_day = date.day
        current_hour = date.hour
        current_minute = date.minute
        # logger.info(f"{current_year=}")

        if day_week in working_days:
            # task = asyncio.create_task(async_func())
            os.system('cls')
            logger.info(f"{datetime.now()}")
            await asyncio.sleep(60)
            # await task

            if current_hour == 4 and current_minute == 5:
                os.system('cls')
                logger.info(f"\nNow begin get dataframe (dataframe= Day) from Mt5 and save to .csv")
                task_2 = asyncio.create_task(get_save_history_prices(symbol=symbols, count_bars=90, timeframe='d1', day=current_day, month=current_month, year=current_year))
                await task_2

            if current_hour in (4, 8, 12, 16, 20, 0) and current_minute == 15:
                os.system('cls')
                logger.info(f"\nNow begin get dataframe (dataframe= H4) from Mt5 and save to .csv")
                task_3 = asyncio.create_task(get_save_history_prices(symbol=symbols, count_bars=250, timeframe='H4', day=current_day, month=current_month, year=current_year))
                await task_3


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except ValueError:
        logger.info(f"error")
