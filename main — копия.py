"""
Реализация торговых алгоритмов на GUI App

используется:
Pyqt5 - GUI
asyncio
threading
schedule - для планирования периодических задач
loguru - для отлова ошибок и сохранения ошибок в файлы
notifiers - для работы с telegram (для уведомлений при появлений сигналов)

Class_Meta_Trader - Собственный Класс для работы с биржей

design.ui - файл хранящий основной интерфейс программы

"""

import asyncio
# import pyqtgraph, operator
import datetime
import inspect
import json
import os.path
import re
import sys
from datetime import datetime
from distutils.util import strtobool

# from schedule import every, repeat, run_pending
import MetaTrader5 as mt5
import notifiers  # для получение уведомлений
import schedule
from PyQt5 import QtWidgets
# from PyQt5.QtCore import *
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from asyncqt import QEventLoop, asyncSlot  # для асинхронности pyqt5
# from datetime import datetime
from loguru import logger  # для ведения логов
from notifiers import get_notifier
from notifiers.logging import NotificationHandler
from rich.console import Console
from rich.table import Table

# I M P O R T  C L A S S_M E T A_T R A D E R  A S  C L A S S_MT5
from Class_Meta_Trader import Meta_Trader  # импорт класса работы с Meta Trader 5
# from Class_Meta_Trader import find_protorgovok
# from Class_Meta_Trader import Schedule_Working  # импорт класса для планировщика schedule
from Class_Meta_Trader import check_expire_date  # для проверки дат экспирации
from Class_Meta_Trader import get_data_from_url  # для получения данных из Kovach signals
from Class_Meta_Trader import read_json_file  # для чтения json файлов
from class_json import read_from_json  # для работы с json
from design import Ui_MainWindow  # импорт файла дизайна (design.ui)

# import urllib.request

# -- notification params --
params = {"xxx": 123}
notifier = notifiers.get_notifier("gmail")  # уведомления через "gmail"
handler = NotificationHandler("gmail", defaults=params)  # используем указанные ранее параметры

# -- > логирование ошибок/нужной информации в определенные файлы < -- #
logger.add("files//logs//errors.log", format="{time} {level} {message}", rotation="10:00", retention="4 days",
           level="ERROR", compression="zip", enqueue=True)
# logger.add("files//logs//info_debug.log", format="{time} {level} {message}", rotation="10:00", retention="2 days",
#            level="INFO", compression="zip", enqueue=True)
logger.add("files//logs//info_warning.log", format="{time} {level} {message}", rotation="10:00", retention="5 days",
           level="WARNING", compression="zip", enqueue=True)

# -- обьявление переменных -- #
symbol = ""
symbols = ["EURUSD", "USDCAD", "EURGBP", "NZDUSD", "AUDUSD", "GBPUSD"]  # список валютных пар
magic = 114000  # magic номер для робота Martin
Multiplier = 1.5  # множитель лота
tp = float
BuyCount, SellCount = 0, 0

# -- login / password / server / path_of_algorithms for MT_account
# dict_a = read_from_json(path_file="files/account_info.json")  # read data login/pass/server from json file
# dict_f = read_from_json(path_file="files/settings.json")  # read global_server from json file
dict_a = read_json_file(filename="files/account_info.json")  # read data login/pass/server from json file
dict_f = read_json_file(filename="files/settings.json")  # read global_server from json file
dict_server = read_json_file(filename="files//settings.json")  # get data server for kovach

# dict_a = list_a[0]  # словарь со значениями Login/Password/Server
login, password, server = dict_a["Login"], dict_a["Password"], dict_a["Server"]  # get data

# -- > обьявим обьект для работы с классом Class_metatrader <--
Terminal = Meta_Trader(login, password, server)

# -- Token / Chat_id for telegram_bot ----
# list_a = read_from_json(path_file="files/telegram_bot.json")
list_a = read_json_file(filename="files/telegram_bot.json")

token = list_a["Token"]
chat_id = list_a["Chat_id"]

# -- function risk_control
# balance, equity, margin_level, currency = Terminal.money_management()  # get account balance
name_of_algorithms = [221, 441, 911]  # список magic_numbers


async def control_risk_deposit(risk_deposit: float, symbols_list: list, magic_numbers: list,
                               telegram_notify: bool):
    """ функция контроля депозита при снижении которого на опре-ую сумму будет закрыта работа приложения MT5 
    equity - текуший обьем депозита с учетом открытых позиций, risk_deposit - величина депозита
    ниже которого будет прекрашена торгволя и закрыта MT5
    """
    await asyncio.sleep(1)
    balance, equity, margin_level, currency = Terminal.money_management()  # get account balance
    # logger.info(f"{equity=}, {risk_deposit=}")

    if equity < risk_deposit:  # если наш equity меньше укзанной суммы, то delete all deals
        for magic in magic_numbers:
            for symbol in symbols_list:
                Terminal.remove_open_position(symbol=symbol, magic_number=magic)
                await asyncio.sleep(3)
        logger.warning(f"Ваш счет стал меньше указанной вами суммы ={risk_deposit} в валюте счете !!!")
        await asyncio.sleep(5)
        # оповещение через telegram bot
        if telegram_notify:
            telegram = get_notifier('telegram')
            telegram.notify(message=f'На вашем счете допушено снижение ниже установленной вами суммы в '
                                    f'{risk_deposit} !!!', token=token, chat_id=chat_id)
        logger.warning(f"Ваш торговая система будет закрыта и все открытые роботом позиции будут закрыты")
        sys.exit()


def find_pl(name_dict: dict):
    """
    поиск в словаре kovach_signals соотношения профита к стоп-лоссу
    """
    # await asyncio.sleep(1)
    pattern = r"EURUSD|USDCAD|AUDUSD|NZDUSD|USDJPY|GBPUSD"
    temp_dict = {}
    for i, val in enumerate(name_dict):
        # logger.info(f"{val=}")
        match = re.match(pattern, val)
        if match:
            # logger.info(f"{match=}")
            if name_dict[val]['limit_order_type'] == 1:
                profit = abs(name_dict[val]['open_price_limit'] - name_dict[val]['take_profit_price'])
                stop_loss = abs(name_dict[val]['open_price_limit'] - name_dict[val]['stop_loss_price'])
                pl = profit / stop_loss
                # logger.info(f"profit: {round(profit, 4)}, stop: {round(stop_loss, 4)}, pl= {round(pl,2)}")
                temp_dict[val] = round(pl, 2)
            elif name_dict[val]['limit_order_type'] == 0:
                profit = abs(name_dict[val]['open_price_stop'] - name_dict[val]['take_profit_price'])
                stop_loss = abs(name_dict[val]['open_price_stop'] - name_dict[val]['stop_loss_price'])
                pl = profit / stop_loss
                # logger.info(f"profit: {round(profit, 4)}, stop: {round(stop_loss, 4)}, pl= {round(pl,2)}")
                temp_dict[val] = round(pl, 2)
    return temp_dict


# -- Версия программы
version_main = '1.2'


# current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
# current_day_name = datetime.today().strftime('%A')  # проверка текущего дня недели (имя дня недели)
# -- end -- #################

class MyQMainWindow(QMainWindow):
    """ Класс для реализации хранения настроек виджетов GUI if reopen app """
    companie_name = 'CompanieName'
    software_name = 'SoftwareName'
    settings_ui_name = 'defaultUiwidget'
    settings_ui_user_name = 'user'
    _names_to_avoid = {}

    def __init__(self, parent=None):
        super(MyQMainWindow, self).__init__(parent)
        self.settings = QSettings(self.companie_name, self.software_name)

    def closeEvent(self, e):
        reply = QMessageBox.question(self, 'Внимание !!!',
                                     "Вы уверены, что хотите уйти?",
                                     QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            e.accept()
            pass
        else:
            e.ignore()

        self._gui_save()

    @classmethod
    def _get_handled_types(cls):
        return QSpinBox, QCheckBox, QRadioButton, QTextEdit, QDoubleSpinBox  # !!!

    @classmethod
    def _is_handled_type(cls, widget):
        return any(isinstance(widget, t) for t in cls._get_handled_types())

    def _gui_save(self):
        """ сохранить элементы управления и значения в настройках реестра """
        name_prefix = f"{self.settings_ui_name}/"
        self.settings.setValue(name_prefix + "geometry", self.saveGeometry())

        for name, obj in inspect.getmembers(self):
            if not self._is_handled_type(obj):
                continue

            name = obj.objectName()
            value = None

            if isinstance(obj, QCheckBox):
                value = obj.isChecked()
            elif isinstance(obj, QRadioButton):
                value = obj.isChecked()
            elif isinstance(obj, QSpinBox):
                value = obj.value()
            elif isinstance(obj, QDoubleSpinBox):
                value = obj.value()
            elif isinstance(obj, QTextEdit):  # < --- >
                value = obj.toPlainText()  #

            if value is not None:
                self.settings.setValue(name_prefix + name, value)

    def _gui_restore(self):
        """ восстановить элементы управления со значениями,
        хранящимися в настройках реестра
        """
        name_prefix = f"{self.settings_ui_name}/"
        geometry_value = self.settings.value(name_prefix + "geometry")
        if geometry_value:
            self.restoreGeometry(geometry_value)

        for name, obj in inspect.getmembers(self):
            if not self._is_handled_type(obj):
                continue
            if name in self._names_to_avoid:
                continue

            name = obj.objectName()
            value = None
            if not isinstance(obj, QListWidget):
                value = self.settings.value(name_prefix + name)
                if value is None:
                    continue

            if isinstance(obj, QCheckBox):
                obj.setChecked(strtobool(value))
            elif isinstance(obj, QRadioButton):
                obj.setChecked(strtobool(value))
            elif isinstance(obj, QSpinBox):
                obj.setValue(int(value))
            elif isinstance(obj, QDoubleSpinBox):
                obj.setValue(float(value))
            elif isinstance(obj, QTextEdit):  # <

                obj.setPlainText(value)  # +++

    def _add_setting(self, name, value):
        name_prefix = f"{self.settings_ui_user_name}/"
        self.settings.setValue(name_prefix + name, value)

    def _get_setting(self, name):
        name_prefix = f"{self.settings_ui_user_name}/"
        return self.settings.value(name_prefix + name)


class MainWindow(Ui_MainWindow, MyQMainWindow):
    """ Главный интерфейс программы """

    companie_name = 'Name'
    software_name = 'softName'
    _names_to_avoid = {'my_widget_name_not_to_save'}

    def __init__(self, parent=None, *args, **kwargs):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        # переход на Stacked_widget по его индексу через передачу параметра
        self.Btn_Menu_5.clicked.connect(lambda: self.Pages_Widget.setCurrentIndex(0))  # Торг счет
        # self.pushButton_4.clicked.connect(lambda: self.Pages_Widget.setCurrentIndex(5))  # Настройки
        # self.dateEdit_3.setDateTime(QtCore.QDateTime.currentDateTime())

        self.pushButton_34.clicked.connect(self.kovach_signals_start)  # Запуск стратегии Kovach_signals

        self.pushButton.clicked.connect(self.Hedge_start)  # запуск алгоритма Hedge + Martin
        self.pushButton_29.clicked.connect(self.Martin_algorithm)  # запуск алгоритма Martin for Hedge
        self.pushButton_19.clicked.connect(self.history_deals_start)  # вывод закрытых сделок

        self._gui_restore()  # -- >  восстановить элементы управления со значениями

    @asyncSlot()
    async def kovach_signals(self):
        """ основной код для алгоритма kovach_signals --> Стратегия №221 """
        if not self.checkBox_29.isChecked():  # если не нажата кнопка --> робот выкл
            self.pushButton_34.setStyleSheet("background-color: red;")  # меняем цвет кнопки на "RED"
            self.pushButton_34.setText("Состояние алгоритма:\nВыключен")  # соотв-но меняем текст
        current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
        working_days = [1, 2, 3, 4, 5]

        # 0. Not working/trading days
        if current_day not in working_days:
            print(chr(27) + "[2J", end="", flush=True)  # clear console window
            print(chr(27) + "[H", end="", flush=True)
            # logger.info(f"Today is weekend, because not trading day : day of week = {current_day}")

            # --- set rich table
            table_1 = Table(title="Umbrella SYS.IO" + ' ' + version_main)

            table_1.add_column("name", justify="center", style="cyan", no_wrap=True)
            table_1.add_column("value", style="magenta")
            table_1.add_column("datetime", justify="center", style="green")
            table_1.add_row("Состояние алгоритма", "Включено", str(datetime.now()))
            table_1.add_row("Текущий день недели", str(current_day), "не торговый день")
            console = Console()
            console.print(table_1)

            await asyncio.sleep(60)

            date = datetime.today()
            hour_time = date.strftime('%H')
            now = datetime.now()

            # check expire date for account at 16:00            
            if hour_time == "16":
                my_expire_date = check_expire_date(url=dict_server['expire_data_server'],
                                                   account_numer=str(login))
                my_date = datetime.fromisoformat(my_expire_date)  # convert str_date to datetime_format
                await asyncio.sleep(3)

                if now > my_date:
                    logger.error(f"\nYour account_number is out of expired data: {my_date}, now data: {now}")
                    await asyncio.sleep(2)
                    sys.exit()
                elif now < my_date:
                    print(chr(27) + "[2J", end="", flush=True)  # clear console window
                    print(chr(27) + "[H", end="", flush=True)
                    # logger.info(f"your expire data is ok !")
                    table_1.add_row("your expire data", "valid", "xx")
                    console = Console()
                    console.print(table_1)

        elif self.checkBox_29.isChecked() and current_day in working_days:  # Р О Б О Т  В К Л
            await asyncio.sleep(1)
            self.pushButton_34.setStyleSheet("background-color: green;")  # делаем зеленым цветом кнопку
            self.pushButton_34.setText("Состояние алгоритма:\nВключен")  # присваиваем соот-ий текст       

            # С Ч И Т Ы В А Е М  П А Р А М Е Т Р Ы / Н А С Т Р О Й К И  ДЛЯ А Л Г О Р И Т М А    
            if not os.path.exists("files/kovach_signals.json"):
                logger.info(f"файл не сушествует по пути: files/kovach_signals.json")
                QMessageBox.about(self, "Title", "файл не сушествует по указанному пути files/kovach_signals.json")
            else:
                with open('files/kovach_signals.json') as f:
                    base_dict = json.load(f)
                    # logger.info(f"{base_dict=}")

            print(chr(27) + "[2J", end="", flush=True)  # clear console window
            print(chr(27) + "[H", end="", flush=True)

            # --- set rich table
            table = Table(title="Umbrella SYS.IO" + ' ' + version_main)

            table.add_column("name", justify="center", style="cyan", no_wrap=True)
            table.add_column("value", style="magenta")
            table.add_column("datetime", justify="right", style="green")

            table.add_row("Состояние алгоритма", "Включено", "xx")
            table.add_row("Текущий день недели", str(current_day), "xx")
            # console = Console()
            # console.print(table)

            # --- П Р О В Е Р К А  Н О В Ы Х  С И Г Н А Л О В  П Р И  Н О В О Й  Д А Т Е 
            # logger.info(f"{dict_server['server_main']=}")
            full_result, result_for_data = get_data_from_url(url=dict_server['server_main'])
            last_update_signal = datetime.fromisoformat(result_for_data)
            # convert str_to_datetime --> to datetime_format
            # logger.info(f"{result_for_data=}, {type(result_for_data)}")

            # check params for algorithms from json_file and compare with server signals
            active = full_result["active"]
            last_update_file = datetime.fromisoformat(base_dict['last_update'])
            # logger.info(f"{active=}, {last_update_file=}, {last_update_signal=}")

            # 1. Not find new signal
            if active == '1' and last_update_file >= last_update_signal:
                # logger.warning(f"Not find new signal on signal server !")
                risk_deal = self.doubleSpinBox_40.value()  # percent risk
                depo_rescue = self.doubleSpinBox_44.value()  # risk deposit
                table.add_row("New signal", "not found ", str(datetime.now()))
                table.add_row("Риск на сделку", str(risk_deal) + " %", "xx")
                table.add_row("Подушка безопасности", str(depo_rescue), "x")

                console = Console()
                console.print(table)

                # 1.1 Risk control for deposit
                Terminal.connect()  # method connect
                account_info = mt5.account_info()  # get account info
                if account_info is not None:  # if not empty data
                    print(chr(27) + "[2J", end="", flush=True)  # clear console window
                    print(chr(27) + "[H", end="", flush=True)
                    account_info_dict = mt5.account_info()._asdict()
                    percent_depo = round((account_info_dict['profit'] / account_info_dict['equity']) * 100, 2)
                    table.add_row("Текущая прибыль/убыток", str(account_info_dict['profit']) + ' / ' +
                                  str(percent_depo) + '%', "xx")
                    # console = Console()
                    console.print(table)
                await control_risk_deposit(risk_deposit=depo_rescue, symbols_list=symbols,
                                           magic_numbers=name_of_algorithms,
                                           telegram_notify=self.checkBox_30.isChecked())

                # 1.2 Show signal in rich_table at every time
                date = datetime.today()
                hour_time = date.strftime('%H')
                if hour_time in ("06", "10", "12", "19", "21", "01"):
                    dict_new = read_json_file(filename="files//kovach_signals.json")
                    # dict_a = find_pl(name_dict=dict_new)
                    dict_a = find_pl(name_dict=dict_new)

                    table.add_row("______________", "______p/l_______", str(datetime.now()))
                    for i, val in enumerate(dict_a):
                        table.add_row(str(val), str(dict_a[val]), "xx")

                    console = Console()
                    console.print(table)



            # 2. Get new signal
            elif active == '1' and last_update_file < last_update_signal:
                # logger.warning(f"\nfind new signal from signal server") 
                risk_deal = self.doubleSpinBox_40.value()
                new_base_dict = full_result  # save new dict from server signal
                list_symbols = ["EURUSD", "GBPUSD", "NZDUSD", "USDCAD", "AUDUSD"]
                for symbol in list_symbols:
                    await asyncio.sleep(0.8)
                    dict_symbol = new_base_dict[symbol]
                    new_update_data = datetime.fromisoformat(
                        dict_symbol["last_update"])  # get new update data for symbol

                    old_dict_symbol = base_dict[symbol]
                    old_update_data = datetime.fromisoformat(
                        old_dict_symbol['last_update'])  # get oldupdate data for symbol
                    if old_update_data >= new_update_data:
                        # logger.info(f"for {symbol=}: not find new signal from signal server")
                        pass
                    elif old_update_data < new_update_data:

                        # 2.1 REGIME = OPEN_POSITION
                        if dict_symbol['regime'] == "open_position":
                            logger.info(
                                f"\nFound new enter point for regime 'open_position': of symbol: {symbol} !\n")
                            # temp_dict = base_dict[symbol]
                            Terminal.kovach_open_deal(symbol=symbol, cascade=dict_symbol['cascade_orders'],
                                                      limit_order=dict_symbol['limit_order_type'],
                                                      open_price=dict_symbol['open_price_limit'],
                                                      percent_risk=risk_deal, stop_loss=dict_symbol['stop_loss_price'],
                                                      stop_order=dict_symbol['stop_order_type'],
                                                      take_profit=dict_symbol['take_profit_price'], magic_number=221)

                            base_dict[symbol] = new_base_dict[symbol]  # save new_dict to base_dict
                            base_dict['last_update'] = dict_symbol["last_update"]  # save new_update data to base_dict
                            with open('files/kovach_signals.json', 'w') as file:
                                json.dump(base_dict, file, ensure_ascii=True, indent=4)
                            await asyncio.sleep(3)

                        # 2.2 REGIME = CLOSE POSITIONS/PENDING_ORDERS    
                        elif dict_symbol['regime'] == "close_positions":
                            logger.info(f"\nFound new enter point for regime 'close_positions': of symbol: {symbol} !")
                            result_list = Terminal.kovach_close_positions(symbol=symbol, magic_number=221)
                            logger.info(f"{result_list=}, {type(result_list)=}")
                            await asyncio.sleep(2)
                            # save new dict to file_json
                            if result_list is True or result_list is None:
                                base_dict[symbol] = new_base_dict[symbol]  # save new_dict to base_dict
                                base_dict['last_update'] = dict_symbol[
                                    "last_update"]  # save new_update data to base_dict
                                with open('files/kovach_signals.json', 'w') as file:
                                    json.dump(base_dict, file, ensure_ascii=True, indent=4)
                                await asyncio.sleep(3)

            # Terminal.kovach_close_positions(symbol="EURUSD", magic_number=114)
            # Terminal.kovach_change_sltp(symbol="EURUSD", magic_number=114, stop_loss=0)

    @asyncSlot()
    async def kovach_signals_start(self):  # запуск планировщика schedule
        """ параметры планировщика schedule "kovach_signals" """
        if self.radioButton_34.isChecked():  # Hours - берется периодичность
            input_time = self.doubleSpinBox_43.value()  # значение времени периода
            print(f"datetime.now: {datetime.now()}")
            schedule.every(input_time).hours.do(
                self.kovach_signals)  # задаем периодичность перезапуска функции - 
            while True:
                schedule.run_pending()
                await asyncio.sleep(1)
        elif self.radioButton_33.isChecked():  # Days - берется периодичность
            input_time = self.doubleSpinBox_42.value()  #: значение времени периода
            print(f"datetime.now: {datetime.now()}")
            schedule.every(input_time).seconds.do(
                self.kovach_signals)  # задаем периодичность перезапуска функции -
            while True:
                schedule.run_pending()
                await asyncio.sleep(1)

    @asyncSlot()
    async def Hedge(self):
        "основной код для Hedge Algorithm: включается Hedge - алгоритм"
        # проверка наличия главного файла settings.json настроек
        if os.path.exists("files/settings.json"):
            # print("файл сушествует, все нормально")
            with open('files/settings.json') as f:
                dict_a = json.load(f)
                dict_b = dict_a["path_of_algorithms"]  # словарь с адресами лок файлов настроек
                name_path = dict_b["hedge"]  # адрес содержащий путь к файлу настроек
        else:
            print("файл не сушествует")
            QMessageBox.about(self, "Title", "файл не сушествует по указанному пути files/settings.json")

        current_day = datetime.today().isoweekday()  # текущий день недели (№ дня недели)
        working_days = [1, 2, 3, 4, 5]
        # logger.info(f"today and now: {current_day} ")

        with open(name_path, "r") as file:
            dict_a = json.load(file)
        active = dict_a["active"]  # режим работаем/не работаем

        if not self.checkBox_2.isChecked():  # если не нажата кнопка --> робот выкл
            self.pushButton.setStyleSheet("background-color: red;")  # меняем цвет кнопки на "RED"
            self.pushButton.setText("Состояние алгоритма:\nВыключен")  # соотв-но меняем текст

        elif current_day not in working_days:
            print(f"Today is weekend then not trading day : day of week = {current_day}")
            await asyncio.sleep(60)
        elif self.checkBox_2.isChecked() and current_day in working_days and active == 1:  # Р О Б О Т  В К Л
            await asyncio.sleep(1)

            print(chr(27) + "[2J", end="", flush=True)  # clear console window
            print(chr(27) + "[H", end="", flush=True)

            self.pushButton.setStyleSheet("background-color: green;")  # делаем зеленым цветом кнопку
            self.pushButton.setText("Состояние алгоритма:\nВключен")  # присваиваем соот-ий текст

            # -- load settings from json file --#
            if os.path.exists(name_path):
                print("файл сушествует, все нормально")
            else:
                print("файл не сушествует")
                QMessageBox.about(self, "Title", f"файл не сушествует по указанному пути {name_path}")

            # -- read levels from json file
            # dict_a = read_from_json(path_file=name_path)   ??? убрать   
            with open(name_path, "r") as file:
                dict_a = json.load(file)

            name_of_algorithms = [221]  # список magic_numbers

            vals = dict_a["EURUSD"]  # загружаем значения_список для данного ключа
            limit_order_type, stop_order_type = vals["limit_order_type"], vals["stop_order_type"]  # get type order
            sell_stop_price, buy_stop_price = vals["sell_stop_price"], vals["buy_stop_price"]  # get stop_order price
            high_level, low_level = vals["high_level"], vals["low_level"]  # get high/low levels
            cascade_orders = dict_a["cascade_orders"]  # режим каскадных ордеров
            # active = dict_a["active"]       # режим работаем/не работаем
            close_positions = dict_a["close_positions"]  # режим для закпрытия открытых позиций

            # -- get take_profits for cascade roders
            full_distance = round(abs((high_level - low_level) * 100000))  # full  distance between high and low
            half_distance = full_distance / 2  # take_profit for first cascade order
            half_quarter = half_distance + half_distance / 2  # take_profit for second cascade order
            take_profit_list = [half_distance, half_quarter, full_distance]

            Terminal.connect()  # к обьекту Terminal применили метод connect

            await asyncio.sleep(2)
            input_risk = round(self.doubleSpinBox_26.value(), 1)  # округляем данные , вводим процент риска
            input_pips = self.doubleSpinBox_27.value()
            stop_loss_usd, lot, symbol, pips = Terminal.find_lot_management(symbol="EURUSD",
                                                                            pips=input_pips, percent=input_risk)
            df_robot, BuyCount, SellCount, CountTrades = Terminal.check_robots_orders(magic_number=221,
                                                                                      symbol="EURUSD")
            await asyncio.sleep(.6)

            # ---  О С Н О В Н О Й  Т О Р Г О В Ы Й  А Л Г О Р И Т М  ---

            # 1 --> П Р О Д А Ж И  (проверка наличия уже открытых сделок)
            if SellCount == 0 or SellCount is None:  # проверка нет ли открытых sell- orders

                price_current = Terminal.get_tick("EURUSD")  # получаем текушую цену по "EURUSD"
                sell_limit_price, buy_limit_price = high_level, low_level
                tp = round(abs((sell_limit_price - buy_limit_price) * 100000))  # take_profit - уровень
                df_robot_1, tickets_Buy_1, tickets_Sell_1, length_1 = Terminal.pending_orders(symbol="EURUSD",
                                                                                              magic_number=221)
                await asyncio.sleep(.3)

                # --> for sell_limit order type
                if buy_limit_price < price_current < sell_limit_price and limit_order_type == 1 and cascade_orders == 0:
                    Terminal.open_sell_limit_new(price=sell_limit_price, magic_number=221, take_profit=tp,
                                                 symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=False)
                    await asyncio.sleep(1)

                else:
                    if buy_limit_price < price_current < sell_limit_price and limit_order_type == 1 and cascade_orders == 1:
                        Terminal.open_sell_limit_new(price=sell_limit_price, magic_number=221, take_profit=tp,
                                                     symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=True)
                        print("проверка !!!")
                        await asyncio.sleep(1)
                # --> for sell_stop order type
                if buy_limit_price < price_current < sell_limit_price and stop_order_type == 1 and \
                        cascade_orders == 0 and price_current > sell_stop_price:
                    Terminal.open_sell_stop_new(price=sell_stop_price, magic_number=221, take_profit=tp,
                                                symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=False)
                    await asyncio.sleep(1)
                else:
                    if buy_limit_price < price_current < sell_limit_price and stop_order_type == 1 and \
                            cascade_orders == 1 and price_current > sell_stop_price:
                        Terminal.open_sell_stop_new(price=sell_stop_price, magic_number=221, take_profit=tp,
                                                    symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=True)
                        await asyncio.sleep(1)

            # 2 --> П О К У П К И
            if BuyCount == 0 or BuyCount is None:  # аналогично как сверху только для buy orders
                price_current = Terminal.get_tick("EURUSD")
                #   logger.info(f"price_current : {price_current}")
                sell_limit_price, buy_limit_price = high_level, low_level  # уровни для покупок и продаж
                tp = round(abs((sell_limit_price - buy_limit_price) * 100000))  # take_profit - уровень

                df_robot_2, tickets_Buy_2, tickets_Sell_2, length_2 = Terminal.pending_orders(symbol="EURUSD",
                                                                                              magic_number=221)
                #  logger.info(f"tickets_Buy_2 : {tickets_Buy_2}, {type(tickets_Buy_2)}")
                await asyncio.sleep(.3)

                # --> buy_limit order type
                if buy_limit_price < price_current < sell_limit_price and limit_order_type == 1 and cascade_orders == 0:
                    Terminal.open_buy_limit_new(price=buy_limit_price, magic_number=221, take_profit=tp,
                                                symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=False)
                    await asyncio.sleep(1)
                else:
                    if buy_limit_price < price_current < sell_limit_price and limit_order_type == 1 and cascade_orders == 1:
                        Terminal.open_buy_limit_new(price=buy_limit_price, magic_number=221, take_profit=tp,
                                                    symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=True)
                        await asyncio.sleep(1)
                # --> buy_limit order type
                if buy_limit_price < price_current < sell_limit_price and stop_order_type == 1 and \
                        cascade_orders == 0 and price_current < buy_stop_price:
                    Terminal.open_buy_stop_new(price=buy_stop_price, magic_number=221, take_profit=tp,
                                               symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=False)
                    await asyncio.sleep(1)
                else:
                    if buy_limit_price < price_current < sell_limit_price and stop_order_type == 1 and \
                            cascade_orders == 1 and price_current < buy_stop_price:
                        Terminal.open_buy_stop_new(price=buy_stop_price, magic_number=221, take_profit=tp,
                                                   symbol="EURUSD", stop_loss=input_pips, lot=lot, cascade=True)
                        await asyncio.sleep(1)

            # --- CLOSE POSITIONS IF ACTIVE = 0
            if current_day in working_days and close_positions == 0:
                for magic in name_of_algorithms:
                    # Terminal.remove_open_position(symbol="EURUSD", magic_number=magic)
                    await asyncio.sleep(2)
        elif self.checkBox_2.isChecked() and current_day in working_days and active == 0:  # Р О Б О Т  В Ы К Л
            logger.warning(f"Робот Hedge выключен, т.к параметр active = 0 ")
            await asyncio.sleep(30)

        # --- П Р О В Е Р К А  Э К С П И Р А Ц И И  Д А Т Ы  Т О Р Г  С Ч Е Т А (АРЕНДА РОБОТА)
        if current_day not in working_days:
            print(f"Сегодня выходной день рынок закрыт : день недели= {current_day}")
            now = datetime.now()
            # logger.info(type(now))
            my_expire_date = check_expire_date(url="http://80.85.158.162/test/1", account_numer=str(login))
            my_date = datetime.fromisoformat(my_expire_date)  # convert str_exp_date --> to datetime_format
            await asyncio.sleep(3)

            if now > my_date:
                logger.error(f"\nYour account_number is out of expired data: {my_date}, now data: {now}")
                sys.exit()
                # elif now < my_date:
            #     logger.info(f"now data: {now}, my_date: {my_date}")

    @asyncSlot()
    async def Hedge_start(self):  # запуск планировщика schedule
        """ параметры планировщика schedule "Hedge" """
        if self.radioButton.isChecked():  # Hours - берется периодичность
            input_time = self.doubleSpinBox.value()  # new  : значение времени периода
            print(f"datetime.datetime.now: {datetime.now()}")  # -- new code
            schedule.every(input_time).hours.do(
                self.Hedge)  # задаем периодичность перезапуска функции - hedge_robot
            while True:
                schedule.run_pending()
                await asyncio.sleep(1)
        elif self.radioButton_21.isChecked():  # Days - берется периодичность
            input_time = self.doubleSpinBox_2.value()  # new  : значение времени периода
            print(f"datetime.datetime.now: {datetime.now()}")  # -- new code
            schedule.every(input_time).seconds.do(
                self.Hedge)  # задаем периодичность перезапуска функции - hedge_robot
            while True:
                schedule.run_pending()
                await asyncio.sleep(1)

    @asyncSlot()
    async def Martin_algorithm(self):
        "основной код для Martin Algorithm --> Включается алгоритм Martin"
        if not self.checkBox_24.isChecked():  # если не нажата кнопка --> робот выкл
            self.pushButton_29.setStyleSheet("background-color: red;")  # меняем цвет кнопки на "RED"
            self.pushButton_29.setText("Состояние алгоритма:\nВыключен")  # соотв-но меняем текст
        else:  # если кнопка нажата --> робот вкл
            self.pushButton_29.setStyleSheet("background-color: green;")  # делаем зеленым цветом кнопку
            self.pushButton_29.setText("Состояние алгоритма:\nВключен")  # присваиваем соот-ий текст

            logger.add("logs\\martin.log", format="{time} {level} {message}", rotation="10:00", retention="2 days",
                       level="ERROR", compression="zip", enqueue=True)  # логирование ошибок кода в файл

            current_day = datetime.datetime.today().isoweekday()  # текущий день недели (№ дня недели)
            working_days = [1, 2, 3, 4, 5]

            # Главный запуск: пока checkbox is enabled, then Martin working
            while self.checkBox_24.isChecked() and current_day in working_days:
                self.pushButton_29.setStyleSheet("background-color: green;")
                self.pushButton_29.setText("Состояние алгоритма:\nВключен")

                dict_a = read_from_json(path_file="files/martin.json")  # read levels from json file
                vals = dict_a  # загружаем значения_список для данного ключа
                # ------------- > read high/low prices
                high_level, low_level = vals["high_price"], vals["low_price"]
                # ------------- > read steps/active/close_positions from json file
                step, take_profit = vals["steps"], vals["take_profit"]
                active, close_positions = vals["active"], vals["close_positions"]

                # -------------- >  Connectig to Terminal MT5
                Terminal.connect()
                balance, equity, margin_level, currency = Terminal.money_management()
                await asyncio.sleep(2)

                tick_a = Terminal.get_tick(symbol="EURUSD")

                # -------- О С Н О В Н О Й  Т О Р Г О В Ы Й  А Л Г О Р И Т М -------

                # 1 -- > П Р О В Е Р К А  М Е Ж Д У  H I G H  A N D  L O W 
                if low_level < tick_a < high_level and active == 1:
                    print(chr(27) + "[2J", end="", flush=True)  # clear console window
                    print(chr(27) + "[H", end="", flush=True)

                    tick = Terminal.get_tick(symbol="EURUSD")
                    df_new, df_robot, BuyCount, SellCount, CountTrades = \
                        Terminal.check_open_orders(symbol="EURUSD", magic_number=331)
                    logger.info("df_robot :{}\nBuyCount: {} SellCount :{}", df_robot, BuyCount, SellCount)
                    await asyncio.sleep(3)

                    # 1.1 --- > О Т К Р О Е М  N E W  B U Y  P O S I T I O N  I F  N O T  E X I S T
                    if BuyCount == 0 or BuyCount is None:
                        logger.info("покупок нет открытых, нужно покупать ! ")
                        Terminal.open_trade_buy("EURUSD", edit_lots=0.04,
                                                magic=331, stop_loss=1200, take_profit=take_profit)
                        await asyncio.sleep(1)

                    # 1.2 --- > О Т К Р О Е М  N E W  S E L L  P O S I T I O N  I F  N O T  E X I S T
                    if SellCount == 0 or SellCount is None:
                        Terminal.open_trade_sell("EURUSD", edit_lots=0.04,
                                                 magic=331, stop_loss=1200, take_profit=take_profit)
                        await asyncio.sleep(3)

                    # ---> Е С Л И  У Ж Е  Е С Т Ь  О Т К Р Ы Т Ы Е  П О З И Ц И И
                    if CountTrades > 0:
                        # avg_price, tickets_Buy, tickets_Sell = Terminal.avg_price(order_type=0)
                        Terminal.find_last_lots(order_type=0, magic_number=331, symbol="EURUSD")
                        df_new, df_robot, BuyCount, SellCount, CountTrades = \
                            Terminal.check_open_orders(symbol="EURUSD", magic_number=331)
                        await asyncio.sleep(1)

                        # 1.3 --- > # Б Л О К  О Т К Р Ы Т И Я  Н О В Ы Х  B U Y, ЕСЛИ УЖЕ ЕСТЬ ОТКРЫТЫЕ ПОЗИЦИИ
                        if 0 < BuyCount < 6:
                            steps = 0
                            tick = Terminal.get_tick(symbol="EURUSD")
                            steps = step[BuyCount - 1]
                            last_price = Terminal.find_last_price(order_type=0, magic=331)
                            logger.debug("last_price buy : {}", last_price)
                            if tick < last_price - steps:
                                print("Можно открыть новую покупку с увеличенным лотом")
                                last_lot = Terminal.find_last_lots(order_type=0,
                                                                   magic_number=331, symbol="EURUSD")
                                Terminal.open_trade_buy("EURUSD", edit_lots=round(last_lot * Multiplier, 2),
                                                        magic=331, stop_loss=1500,
                                                        take_profit=take_profit)
                                await asyncio.sleep(5)
                                # --- change take profits of opened position ---
                                avg_price_1, tickets_Buy_1, tickets_Sell_1 = Terminal.avg_price_new(
                                    symbol="EURUSD", magic_number=331, order_type=0)

                                logger.info("tickets buy : {}, avg_price_1: {}", tickets_Buy_1, avg_price_1)
                                await asyncio.sleep(3)
                                for ticket in tickets_Buy_1:  # блок изменения TP у каждого Buy_ордера
                                    Terminal.TRADE_ACTION_SLTP_NEW(symbol="EURUSD", magic_number=331,
                                                                   position_ticket=ticket,
                                                                   stop_loss=low_level,
                                                                   take_profit=avg_price_1, order_type=0)
                                    await asyncio.sleep(5)

                        else:
                            steps = step[5]
                        steps = 0
                        await asyncio.sleep(5)

                        df_new, df_robot, BuyCount, SellCount, CountTrades = \
                            Terminal.check_open_orders(symbol="EURUSD", magic_number=331)
                        last_price_sell = Terminal.find_last_price(order_type=1, magic=331)

                        # 1.4 --- > # Б Л О К  О Т К Р Ы Т И Я  Н О В Ы Х  S E L L, ЕСЛИ УЖЕ ЕСТЬ ОТКРЫТЫЕ ПОЗИЦИИ
                        if 0 < SellCount < 6:  # блок открытия новых Sell
                            steps = step[SellCount - 1]  # заменил step на step_new
                            Terminal.find_last_lots(order_type=1, magic_number=331, symbol="EURUSD")
                            # logger.debug("last_price sell : {}", last_price_sell)
                            if tick > last_price_sell + steps:
                                last_lot_sell = Terminal.find_last_lots(order_type=1,
                                                                        magic_number=331, symbol="EURUSD")
                                logger.info("Можно открыть новую продажу и увеличенным лотом: {}",
                                            last_lot_sell)
                                Terminal.open_trade_sell("EURUSD",
                                                         edit_lots=round(last_lot_sell * Multiplier, 2),
                                                         magic=331, stop_loss=1500,
                                                         take_profit=take_profit)
                                await asyncio.sleep(0.7)
                                tick_c = Terminal.get_tick(symbol="EURUSD")
                                # buy_limit, sell_limit = find_near_levels(name_list=list_c, price=tick_c)
                                await asyncio.sleep(0.5)

                                # --- change take profits of opened position ---
                                avg_price_3, tickets_Buy_3, tickets_Sell_3 = Terminal.avg_price_new(
                                    symbol="EURUSD", magic_number=331, order_type=1)
                                logger.info("tickets sell : {}", tickets_Sell_3)
                                await asyncio.sleep(0.7)
                                for ticket in tickets_Sell_3:  # блок изменения TP у каждого Sell_ордера
                                    Terminal.TRADE_ACTION_SLTP_NEW(symbol="EURUSD", magic_number=331,
                                                                   position_ticket=ticket,
                                                                   stop_loss=high_level,
                                                                   take_profit=avg_price_3, order_type=1)
                                await asyncio.sleep(0.5)

                        else:
                            pass
                            steps = step[5]
                elif low_level < tick_a < high_level and active == 0:
                    print(chr(27) + "[2J", end="", flush=True)  # CLEAR CLI
                    print(chr(27) + "[H", end="", flush=True)
                    logger.warning(f"Алгоритм Martin пока не активен, так как параметр active = 0 (выключен) !!!")
                    await asyncio.sleep(15)
                elif (tick_a > high_level or tick_a < low_level) and close_positions == 1:
                    logger.info(f"Now price out from our high/low price, because close_positions !!!")
                    # --- if opened positions find, then delete them
                    df, df_robot, BuyCount, SellCount, CountTrades = \
                        Terminal.check_open_orders(symbol="EURUSD", magic_number=331)
                    if CountTrades is not None or CountTrades > 0:
                        # Terminal.remove_open_position(symbol="EURUSD", magic_number=331)
                        await asyncio.sleep(60)

            while self.checkBox_24.isChecked() and current_day not in working_days:
                self.label_21.setText("Выходной, не торгуем")
                print(f"Today is weekend, because not trading day : day of week = {current_day}")
                await asyncio.sleep(60)

    @asyncSlot()
    async def history_deals(self):
        """ Отправка статистики через telegram bot """
        Terminal.connect()  # к обьекту Terminal применили метод connect

        # выбран шаблон дат -- #
        if self.radioButton_14.isChecked():  # Выбор по шаблону времени
            value = self.comboBox.currentText()  # выбранное значение из comboBox_2
            if value == "за один день":  # выбранное значение из comboBox_
                print("за один день - выбран")
                time_days = 1
            elif value == "за два дня":  # выбранное значение из comboBox_
                print("за два дня - выбран")
                time_days = 2
            elif value == "за три дня":  # выбранное значение из comboBox_
                print("за три дня - выбран")
                temp_var = self.dateEdit.date()
                var_name = temp_var.toPyDate()
                print(f"date type: {type(var_name)}, {var_name}")
                time_days = 3
            elif value == "за 7 дней":  # выбранное значение из comboBox_
                print("за 7 дней")
                time_days = 7
            elif value == "за 30 дней":  # выбранное значение из comboBox_
                print("за 30 дней")
                time_days = 30
            elif value == "за 90 дней":  # выбранное значение из comboBox_
                print("за 90 дней")
                time_days = 90
            elif value == "за 1 год":  # выбранное значение из comboBox_
                print("за 1 год")
                time_days = 360

        algorithm = self.comboBox_2.currentText()  # выбранное значение из comboBox_2
        if algorithm == "Все":  # выбран все алгоритмы
            print(f"check Vse")
            if self.radioButton_11.isChecked():  # по всем symbols
                print("all magic_number")

            elif self.radioButton_12.isChecked():  # one symbol
                print("one magic_number")
                algorithm = self.comboBox_2.currentText()  # выбранное значение из comboBox_2
                print(f"content: {algorithm}")

        if algorithm != "Все":  # выбран один алгоритм
            print(f"check  Ne Vse")
            if self.radioButton_11.isChecked():  # по всем symbols
                print("all symbols")

            elif self.radioButton_12.isChecked():  # one symbol
                value = self.comboBox.currentText()  # выбранное значение из comboBox_2
                print(f"almaz value : {value}")
                print("one symbol")
                magicNumber = int(self.comboBox_2.currentText())  # выбранное значение из comboBox_2
                symbol = self.comboBox_3.currentText()  # выбранное значение из comboBox_2
                print(f"content: {symbol}, magicNumber: {magicNumber}")
                df, profit_loss = Terminal.history_all_deals(symbol=symbol, magic_number=magicNumber, days=time_days)

                self.label_14.setText(str(profit_loss))

                print(f"df : {df}, type: {type(df)}")
                if not df.empty:
                    self.label_14.setText(str(profit_loss))  # вывод обшей profit_loss
                    self.tableWidget_4.setColumnCount(len(df.columns))  # кол-во колонок
                    self.tableWidget_4.setRowCount(df.shape[0])  # кол-во строк
                    for i, row in df.iterrows():
                        # Добавление строки
                        self.tableWidget_4.setRowCount(self.tableWidget_4.rowCount() + 1)

                        for j in range(self.tableWidget_4.columnCount()):
                            self.tableWidget_4.setItem(i, j, QtWidgets.QTableWidgetItem(str(row[j])))

                    self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
                    self.tableWidget_4.resizeColumnsToContents()  # # делаем ресайз колонок по содержимому

                    headers = df.columns.values.tolist()
                    self.tableWidget_4.setHorizontalHeaderLabels(headers)
                    await asyncio.sleep(1)
                    self.tableWidget_4.show()
                elif df.empty:
                    self.label_14.setText("сделок не обнаружено !!!")

        # -- > Новый функционал < --

        # выбран оповещение через telegram bot -- #
        if self.checkBox_28.isChecked():
            self.pushButton_19.setStyleSheet("background-color: green;")  # меняем цвет кнопки на "RED"
            self.pushButton_19.setText("Обновления:\nВключены")  # соотв-но меняем текст

            balance, equity, margin_level, currency = Terminal.money_management()

            df_7, profit_loss_7 = Terminal.history_all_deals(symbol="all", magic_number=0, days=7)
            await asyncio.sleep(2)
            df_month, profit_loss_month = Terminal.history_all_deals(symbol="all", magic_number=0, days=30)
            await asyncio.sleep(2)

            percent_week = round((profit_loss_7 / equity) * 100, 1)
            percent_month = round((profit_loss_month / equity) * 100, 1)

            # send to telegram_bot
            telegram = get_notifier('telegram')
            telegram.notify(message=f'Profit/loss на счете:\n7 дней: {profit_loss_7} $ ({percent_week}%)\n'
                                    f'Profit/loss на счете:\n1 месяц: {profit_loss_month} $ ({percent_month}%)\n',
                            token=token, chat_id=chat_id)

    @asyncSlot()
    async def history_deals_start(self):
        """ запуск планировщика для отправки статистики через telegram bot """
        pass
        print(f"datetime.datetime.now: {datetime.now()}")

        gettime = self.timeEdit_2.time()  # получаем значения времени часов/минут
        get_hour, get_minut = str(gettime.hour()), str(gettime.minute())  # преоб-ем время в str
        print(f"get_hour: {get_hour}, {get_minut}")
        if len(get_hour) == 1:
            get_hour = "0" + get_hour
        if len(get_minut) == 1:
            get_minut = "0" + get_minut

            get_value = get_hour + ":" + get_minut

            # schedule.every(1).minute.do(
            #   self.history_deals)  # задаем периодичность перезапуска функции
            schedule.every().sunday.at(get_value).do(self.history_deals)
        while True:
            schedule.run_pending()
            await asyncio.sleep(10)

    def find_sma_price(self):
        """ метод для поиска Sma - скользяшей цены для данного symbol,
         timeframe - выбор нужного таймфрема типо H4, counts_bars - кол-во баров начиная с текушего дня"""
        Terminal = Meta_Trader(login, password, server)  # create object from class Meta Trader
        Terminal.connect()  # к обьекту Terminal применили метод connect
        input_text = self.textEdit_15.toPlainText()  # input -ввод валютной пары aka "eurusd"
        input_timeframe = self.textEdit_16.toPlainText()  # input -ввод тайм фрейма
        input_count_bars = round(self.doubleSpinBox_15.value())  # input - кол-во пунктов риска Stop_Loss

        sma_price = Terminal.find_sma_prices(symbol=input_text.upper(), timeframe=input_timeframe,
                                             counts_bars=input_count_bars)
        print(sma_price)
        self.label_38.setText(str(sma_price))  # вывод значения лота в виджет label


if __name__ == "__main__":
    # app = QApplication([])        # было ранее
    app = QApplication(sys.argv)
    app.setApplicationName("Umbrella")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(45, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(12, 100, 238))
    palette.setColor(QPalette.Highlight, QColor(12, 115, 228))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    app.setStyleSheet(
        "QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }"
    )

    # new code
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        # sys.exit(app.exec_())             # ранее был код и без with loop
        sys.exit(loop.run_forever())
