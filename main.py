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
from datetime import datetime
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
from Class_Meta_Trader import Meta_Trader  # импорт класса работы с Meta Trader 5
from Class_Meta_Trader import get_data_from_url  # для получения данных из Kovach signals
from Class_Meta_Trader import read_json_file  # для чтения json файлов

# import class for workinf with database (Postgre)
from Postgres_Class import info_database
from Postgres_Class import test_db

# -- notification params --
params = {"xxx": 123}
notifier = notifiers.get_notifier("gmail")  # уведомления через "gmail"
handler = NotificationHandler("gmail", defaults=params)  # используем указанные ранее параметры

# -- login / password / server / path_of_algorithms for MT_account
account_dict = read_json_file(filename="config_files/account_info.json")  # read data login/pass/server from json file
base_dict = read_json_file(filename="config_files/settings.json")  # read global_server from json file
database_dict = read_json_file(filename="config_files//settings_database.json")  # get data server for kovach
telegram_dict = read_json_file(filename="config_files/telegram_bot.json")

base_dir = base_dict['Base_dir']   # ||| Главная папка проекта |||

# -- > логирование ошибок/нужной информации в определенные файлы < -- #
logger.add(base_dir + "logs//errors.log", format="{time} {level} {message}", rotation="10:00", retention="4 days",
           level="ERROR", compression="zip", enqueue=True)
# logger.add("files//logs//info_debug.log", format="{time} {level} {message}", rotation="10:00", retention="2 days",
#            level="INFO", compression="zip", enqueue=True)
logger.add(base_dir + "logs//info_warning.log", format="{time} {level} {message}", rotation="10:00", retention="5 days",
           level="WARNING", compression="zip", enqueue=True)

# -- обьявление переменных -- #
symbols = ["EURUSD", "USDCAD", "EURGBP", "NZDUSD", "AUDUSD", "GBPUSD"]  # список валютных пар


# dict_a = list_a[0]  # словарь со значениями Login/Password/Server
login, password, server = account_dict["Login"], account_dict["Password"], account_dict["Server"]  # get data

# -- > обьявим обьект для работы с классом Class_metatrader <--
Terminal = Meta_Trader(login, password, server)

# -- > переменные для работы с БД Postgre_Sql
database, user_name_db = database_dict["database"], database_dict['user_name_db']
password, host, port = database_dict['password'], database_dict['host'], database_dict['port']

# -- Token / Chat_id for telegram_bot ----
token = telegram_dict["Token"]
chat_id = telegram_dict["Chat_id"]

current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
working_days = [1, 2, 3, 4, 5]

# -- Версия программы
version_main = 'Analytic_Center 1.1'


# current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
# current_day_name = datetime.today().strftime('%A')  # проверка текущего дня недели (имя дня недели)
# -- end -- #################


# ||| Check connect to MT5
# установим подключение к терминалу MetaTrader 5
if not mt5.initialize():
    logger.error(f"initialize() failed, error code = {mt5.last_error()}")
    connection_mt5_status = False
    quit()
else:
    connection_mt5_status = True

# ||| Check connect to Data_Base (Postgre_SQL)


# --- set rich table
table_1 = Table(title=version_main)
today = datetime.now()

table_1.add_column("name", justify="center", style="cyan", no_wrap=False)
table_1.add_column("value", style="magenta")
table_1.add_column("datetime", justify="center", style="green")
table_1.add_row("Состояние аналитического центра", "Включено", str(today.strftime("%Y-%m-%d-%H.%M.%S")))
table_1.add_row("Рабочая папка проекта", base_dir, "xx")
table_1.add_row("Текущий день недели", str(current_day), "xx")
table_1.add_row("Connection_mt5_status", str(connection_mt5_status), "xx")
os.system('cls')
console = Console()
console.print(table_1)


# установим таймзону в UTC
timezone = pytz.timezone("Etc/UTC")
# создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
utc_from = datetime(2022, 4, 28, tzinfo=timezone)
# получим 10 баров с EURUSD H4 начиная с 01.10.2020 в таймзоне UTC
rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_H4, utc_from, 4)
# logger.info(f"\n{rates}")
# создадим из полученных данных DataFrame
rates_frame = pd.DataFrame(rates)
# logger.info(f"{rates_frame}")

# завершим подключение к терминалу MetaTrader 5
mt5.shutdown()


# info_database(database=database, user=user_name_db, password=password, host=host, port=port)
test_db(database=database, user=user_name_db, password=password, host=host, port=port)
