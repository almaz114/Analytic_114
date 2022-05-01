""" Основной класс для работы с торговым терминалом для работы с биржей"""

import datetime
import itertools
import json
import os.path
# import colorama
# from colorama import Fore, Back, Style
# colorama.init()
import re
import time
import urllib.request
from datetime import datetime
from datetime import timedelta

import MetaTrader5 as mt5
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
import requests
from loguru import logger
from tqdm import trange
from tqdm import tqdm
import sys
from alive_progress import alive_bar

step = [6 / 10000, 10 / 10000, 20 / 10000, 30 / 10000, 34 / 10000, 45 / 10000,
        56 / 10000]  # 10/ - кол-во пунктов (10 pips)
Multiplier = 1.5  # множитель лота

# -- > логирование ошибок/нужной информации в определенные файлы < -- #
logger.add("config_files//logs//errors.log", format="{time} {level} {message}", rotation="10:00", retention="4 days",
           level="ERROR", compression="zip", enqueue=True)


class Meta_Trader():
    "Класс для работы с торговым терминалом и данными: Класс Meta_Trader login и password, server\
    данные эти берем в последующем из файла конфигурации json"

    def __init__(self, login_user, password_user, server_user):
        self.login = login_user
        self.password = password_user
        self.server = server_user

    def connect(self):
        " Метод для подключения к терминалу MT5 "
        #  print(" Сейчас будет запущен Терминал ")
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            logger.warning(f"initialize() failed, error code = {mt5.last_error()}")
            # print("initialize() failed, error code =", mt5.last_error())
        else:
            pass
        #  print('Подключение к торговому терминалу/счету успешно')

    def account_info(self):
        "Метод для получения информации об торговом счете из терминала"
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            # print("initialize() failed, error code =", mt5.last_error())
            logger.warning(f"initialize() failed, error code = {mt5.last_error()}")
        else:
            print('Подключение к торговому счету успешно')
            account_info_dict = mt5.account_info()._asdict()
            df = pd.DataFrame(account_info_dict.items(), columns=['Key', 'Value'])  # конвертация из словаря dict
            account_df = df.loc[[0, 24, 10, 12, 13, 25, 27, 5, 6], ['Key', 'Value']]  # в df - датафрейм panda
            return account_df

    def check_open_orders(self, symbol: str, magic_number: int):
        """
        метод показывает все открытые ордера, кол-во покупок, продаж
        """
        usd_positions = mt5.positions_get(symbol=symbol)
        if usd_positions in (None, ()):
            logger.warning(f"initialize() failed, error code = {mt5.last_error()}")
            usd_positions, CountTrades = None, 0
            return usd_positions, usd_positions, usd_positions, usd_positions, CountTrades
        elif len(usd_positions) > 0:
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)

            df_new = df[['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current',
                         'sl', 'tp', 'profit', 'magic', 'comment']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == magic_number][
                ['time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]
            # обшее кол-во сделок открытых ордером
            CountTrades = len(df_robot)  # обшее кол-во сделок
            BuyCount = len(df_robot[df_robot.type == 0])  # кол-во покупок
            SellCount = len(df_robot[df_robot.type == 1])  # кол-во продаж
            return df_new, df_robot, BuyCount, SellCount, CountTrades

    def pending_orders(self, symbol: str, magic_number):  # показ отложенных ордеров
        """ метод показывает отложенные ордера для данного symbol и magic_number """
        orders = mt5.orders_get(symbol=symbol)  # отбор данных по symbol

        if orders in (None, ()):  # проверка не пустой ли массив данных
            # print("No pending orders with group=\"**\", error code={}".format(mt5.last_error()))
            df_robot, tickets_Buy, tickets_Sell, len_df = None, None, None, None  # переменным присвоим None new
            return df_robot, tickets_Buy, tickets_Sell, len_df  # возврашаем значения new
        else:
            # print("orders_get(group=\"**\")={}".format(len(orders)))
            # выведем эти ордеры в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())
            df.drop(['time_done', 'time_done_msc', 'position_id', 'position_by_id', 'reason', 'volume_initial',
                     'price_stoplimit'], axis=1, inplace=True)  # удаляем ненужные поля
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            # print(df)
            df_new = df[['ticket', 'symbol', 'type', 'magic', 'comment']]  # отбор по magic_number
            df_robot = df_new[df_new.magic == magic_number][['ticket', 'symbol', 'type', 'magic', 'comment']]
            logger.info(f"все отложенные ордера : {df_robot}")
            # -- получаем список tickets for buy_limits and sell_limits-- #
            df_robot_Buy_tickets = df_robot[df_robot.type == 2][['ticket', 'type']]  # for buy_limits
            df_robot_Buy_tickets_1 = df_robot[df_robot.type == 4][['ticket', 'type']]  # for buy_stops

            tickets_Buy = df_robot_Buy_tickets['ticket'].tolist()  # list of buy tickets
            tickets_Buy_1 = df_robot_Buy_tickets_1['ticket'].tolist()  # list of buy tickets
            buy_tickets = tickets_Buy + tickets_Buy_1  # обьединили два списка тикетов for buys
            logger.info(f"полученные : {buy_tickets=}")

            df_robot_Sell_tickets = df_robot[df_robot.type == 3][['ticket', 'type']]  # for sell_limits
            df_robot_Sell_tickets_1 = df_robot[df_robot.type == 5][['ticket', 'type']]  # for sell_stop

            tickets_Sell = df_robot_Sell_tickets['ticket'].tolist()  # list of sell tickets
            tickets_Sell_1 = df_robot_Sell_tickets_1['ticket'].tolist()  # list of sell tickets
            sell_tickets = tickets_Sell + tickets_Sell_1  # обьединили два списка тикетов for sells
            # len_df = len(df_robot.index)  # len of df_robot
            len_df = len(buy_tickets)  # len of df_robot
            # print(str(tickets_Buy) + "\n" + str(tickets_Sell))
            return df_robot, buy_tickets, sell_tickets, len_df

    def pending_orders_new(self, symbol: str, magic_number: int, type_order: int):  # показ отложенных ордеров
        """ метод показывает отложенные ордера для данного symbol и magic_number и типа ордера """
        if not mt5.initialize():
            logger.warning(f"initialize() failed, error code ={mt5.last_error()}")
            quit()
        orders = mt5.orders_get(symbol=symbol)  # отбор данных по symbol

        if orders in (None, ()):  # проверка не пустой ли массив данных
            # print("No pending orders with group=\"**\", error code={}".format(mt5.last_error()))
            df_robot, tickets_Buy, tickets_Sell, len_df = None, None, None, None  # переменным присвоим None new
            return df_robot, tickets_Buy  # возврашаем значения new
        else:
            # print("orders_get(group=\"**\")={}".format(len(orders)))
            df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())
            df.drop(['time_done', 'time_done_msc', 'position_id', 'position_by_id', 'reason', 'volume_initial',
                     'price_stoplimit'], axis=1, inplace=True)  # удаляем ненужные поля
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            df_new = df[['ticket', 'symbol', 'type', 'magic', 'comment', "price_open"]]  # отбор по magic_number
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'symbol', 'type', 'magic', 'comment', "price_open"]]
            # logger.info(f"все отложенные ордера : {df_robot}")

            # -- получаем список tickets for sell_tickets and sell_limits-- #
            df_robot_tickets = df_robot[df_robot.type == type_order][['ticket', 'type', "price_open"]]  # for sell_stop
            tickets_list = df_robot_tickets['ticket'].tolist()  # list of sell tickets
            # print(f"tickets: {tickets}")

            if df_robot_tickets.empty:
                # logger.info(f"DataFrame is empty/ Сделок {symbol=} и :{type_order=} и {magic_number=} нет !")
                df_robot_tickets, tickets_Buy = None, None
                return df_robot_tickets, tickets_Buy
            else:
                # b = df_robot_tickets.nlargest(1, 'time')
                logger.info(f"Found opened pending_orders {tickets_list=} of type_order: {type_order}")
                last_price = round(df_robot_tickets.price_open.values[0], 5)
                # logger.info(f"Сделки по :{symbol} и type_order:{type_order} by {magic_number=} и цен. открытия {last_price} ")
                return tickets_list, last_price

    def find_last_pending_orders(self, symbol: str, magic: int, type_order: int):
        """ метод показывает цену открытия отложенных ордеров для данного symbol и magic_number и типа ордера
        buy = 0, sell=  1, buy_limit=2, sell_limit=3, buy_stop=4, sell_stop=5 """
        orders = mt5.orders_get(symbol=symbol)  # отбор данных по symbol
        if orders is None or orders == ():  # проверка не пустой ли массив данных
            # print("No pending orders with group=\"**\", error code={}".format(mt5.last_error()))
            df_robot, tickets_Buy, tickets_Sell, len_df = None, None, None, None  # переменным присвоим None new
            return df_robot, tickets_Buy, tickets_Sell, len_df  # возврашаем значения new
        else:
            # выведем эти ордеры в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())
            df.drop(['time_done', 'time_done_msc', 'position_id', 'position_by_id', 'reason', 'volume_initial',
                     'price_stoplimit'], axis=1, inplace=True)  # удаляем ненужные поля
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            # print(f"df: {df}")

            df_new = df[['ticket', 'symbol', 'type', 'magic', 'comment', "price_open"]]
            # print(f"\ndf_new: {df_new}")

            # -- отбор по magic_number --
            df_robot = df_new[df_new.magic == magic][['ticket', 'symbol', 'type', 'magic', 'comment', "price_open"]]
            # print(f"все отобранные отложенные ордера : {df_robot}")

            # -- отбор по type_order -- 
            df_robot_new = df_robot[df_robot.type == type_order][['ticket', 'symbol', 'type', "price_open"]]
            # print(f"полученные df_robot_new: {df_robot_new}")

            if df_robot_new.empty:
                print(f'DataFrame is empty/ Сделок symbol={symbol} и type_order:{type_order} и magic: {magic} нет !')
            else:
                # b = df_robot_new.nlargest(1, 'time')
                last_price = round(df_robot_new.price_open.values[0], 5)
                # print(type(last_price))
                print(f"Сделка/и symbol={symbol} и type_order:{type_order} "
                      f"и magic: {magic} с \nценой открытия {last_price}")
                return last_price

    def history_deals(self, symbol: str, magic_number: int):  #
        """ метод ко-й показывает закрытые сделки за определенный период времени """
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # получим количество сделок в истории
        from_date = datetime.datetime(2021, 4, 28)
        date_to = datetime.datetime.now()
        # получим  в указанном интервале сделки по символам, имена которых содержат symbol
        deals = mt5.history_deals_get(from_date, date_to, group=symbol)
        # print(f"deals : {deals}")
        if deals == None or deals == ():
            print("No deals with, error code={}, symbol: {}".format(mt5.last_error(), symbol))
        elif len(deals) > 0:
            print("history_deals_get({}, {}, )={}, {}".format(from_date, date_to, len(deals), symbol))
            df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            print(df.info())
            df_new = df[
                ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'reason', 'volume', 'price', 'profit',
                 'symbol', 'comment']]
            df_robot = df_new[df_new.magic == magic_number]['ticket', 'order', 'time', 'type', 'magic', 'volume',
                                                            'reason', 'volume', 'price', 'profit', 'symbol', 'comment']
            print(df_robot)

    def copy_rates_from(self, symbol: str, count_bars):
        """ метод ко-й показывает цены определенный период времени выбранного timeframe"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # установим таймзону в UTC
        timezone = pytz.timezone("Etc/UTC")
        # создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
        # from_date = datetime.datetime(2021, 5, 28, tzinfo=timezone)

        from_date = datetime.datetime.now() - timedelta(days=1)  # вчерашний день
        to_date = datetime.datetime.now()

        # получим 10 баров с EURUSD H4 начиная с 01.10.2020 в таймзоне UTC
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_D1, from_date, count_bars)

        rates_frame = pd.DataFrame(rates)
        # сконвертируем время в виде секунд в формат datetime
        rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
        print(f"rates_frame: {rates_frame}")
        # rates_frame.to_csv("rates_frame_eurusd_day.csv", sep='\t', encoding='utf-8')
        #
        df_new = rates_frame[['time', 'open', 'close', 'low', 'high']]
        # df = df_new.round(3)  # Округление dataframe 3 - кол-во знаков после запятой
        # print(len(df_new))
        if df_new.empty:
            print('DataFrame is empty / Сделок на покупок нет !')
        elif len(df_new) > 0:
            low, high = df_new.low.values[0], df_new.high.values[0]
            # print(f"low: {low}")

            return df_new, low, high

    def copy_rates_from_new(self, symbol: str, timeframe=str, count_bars=int):
        """ метод ко-й показывает исторические цены по определенной валютной паре symbol
        за определенный период времени count_bars по выбранному timeframe"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # установим таймзону в UTC
        timezone = pytz.timezone("Etc/UTC")
        # создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
        # from_date = datetime.datetime(2021, 5, 28, tzinfo=timezone)

        from_date = datetime.datetime.now() - timedelta(days=1)  # вчерашний день
        to_date = datetime.datetime.now()

        # выбор timeframe
        if timeframe == "D1" or "d1":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_D1, from_date, count_bars)
        elif timeframe == "H4" or "h4":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H4, from_date, count_bars)
        elif timeframe == "H1" or "h1":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, from_date, count_bars)
        elif timeframe == "M15" or "m15":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M15, from_date, count_bars)

        rates_frame = pd.DataFrame(rates)
        # сконвертируем время в виде секунд в формат datetime
        rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
        print(f"rates_frame: {rates_frame}")
        # rates_frame.to_csv("rates_frame_eurusd_day.csv", sep='\t', encoding='utf-8')

        df_new = rates_frame[['time', 'open', 'close', 'low', 'high']]
        # df = df_new.round(3)  # Округление dataframe 3 - кол-во знаков после запятой

        if df_new.empty:
            print('DataFrame is empty / Dataframe Пустой !')
        elif len(df_new) > 0:
            low, high = df_new.low.values[0], df_new.high.values[0]
            # print(f"low: {low}")

            return df_new, low, high

    def history_loss_deals(self, symbol: str, magic_number: int, days: int):
        """ метод ко-й показывает закрытые сделки за определенный период времени;
        days - сколько дней назад смотрим историю сделок начиная с текущего дня; symbol можно
        выбрать опрделенную валюту или же бырать все : symbol= all """
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # получим количество сделок в истории
        yesterday = datetime.datetime.now() - timedelta(days=days)  # вчерашний день
        # from_date = datetime.datetime(2021, 4, 29)
        to_date = datetime.datetime.now()
        # получим  в указанном интервале сделки по символам, имена которых содержат symbol
        # deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
        # print(f"deals : {deals}")

        if symbol != "all":  # если выбрана опредленная валютная пара
            deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
            # print(f"deals : {deals}")
            if deals == None or deals == ():
                print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                len_loss_position, loss_summ = 0, 0  #
                return len_loss_position, loss_summ
            elif len(deals) > 0:
                print("history_deals_get({}, {}, )={}".format(yesterday, to_date, len(deals)))
                df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                df['time'] = pd.to_datetime(df['time'], unit='s')
                #  print(df.info())
                df_new = df[
                    ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'reason', 'volume', 'price', 'profit',
                     'symbol', 'comment']]
                df_robot = df_new[df_new.magic == magic_number]['ticket', 'order', 'time', 'type', 'magic', 'volume',
                                                                'reason', 'volume', 'price', 'profit', 'symbol', 'comment']

                loss_df = df_robot[df_robot.profit < 0]  # ОТБОР ОРДЕРОВ ПО его profit (убытку)
                if loss_df.empty:
                    print('DataFrame is empty / Сделок убыточных нет !')
                    len_loss_position = 0  # кол-во убыточных позиций
                    loss_summ = 0
                    return len_loss_position, loss_summ
                else:
                    print(f"len of loss df: {len(loss_df)}")
                    print(loss_df)
                    # ГРУППИРУЕМ ПО КОЛОНКАМ symbol и суммируем по profit
                    loss_df_group = loss_df.groupby(['symbol']).agg({"profit": "sum"})  # summ of loss
                    loss_summ = loss_df_group.profit.values[0]  # пулочаем нужное значение
                    print(f"loss_summ : {loss_summ}")

                    return len(loss_df), loss_summ  # return - общий убыток по этим сделкам usd
                # print(df_robot)
        elif symbol == "all":  # если выбрали все валютные пары
            deals = mt5.history_deals_get(yesterday, to_date)  # -- > убрал symbol
            # print(f"yesterday and to_date: {yesterday} and {to_date}, len_deals = {len(deals)}, symbol: {symbol}")
            # print(f"deals : {deals}")
            if deals == None or deals == ():
                print("error code={}, No deals with symbol: {}".format(mt5.last_error(), symbol))
                len_loss_position, loss_summ = 0, 0  #
                return len_loss_position, loss_summ
            elif len(deals) > 0:
                # print("history_deals:{}, {}, выборка по всем валютам ={}".format(yesterday, to_date, len(deals)))
                df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df_new = df[
                    ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'reason', 'volume', 'price', 'profit',
                     'symbol', 'comment']]
                # print(f"df_new : {df_new}")
                df_robot = df_new[df_new.magic == magic_number]['ticket', 'order', 'time', 'type', 'magic', 'volume',
                                                                'reason', 'volume', 'price', 'profit', 'symbol', 'comment']
                loss_df = df_robot[df_robot.profit < 0]  # ОТБОР ОРДЕРОВ ПО его полю profit (убытку < 0)
                if loss_df.empty:
                    print('DataFrame is empty / Сделок убыточных нет !')
                    len_loss_position = 0  # кол-во убыточных позиций
                    loss_summ = 0
                    return len_loss_position, loss_summ
                else:
                    # print(f"len of loss df: {len(loss_df)}")
                    #  print(loss_df)
                    # ГРУППИРУЕМ ПО КОЛОНКАМ magic и суммируем по profit
                    loss_df_group = loss_df.groupby(['magic']).agg({"profit": "sum"})  # summ of loss
                    loss_summ = loss_df_group.profit.values[0]  # get нужное значение
                    # print(f"loss_summ : {loss_summ}")

                    return len(loss_df), loss_summ  # return - общий убыток по этим сделкам usd
                # print(df_robot)

    def history_all_deals(self, symbol: str, days: int = None, magic_number: int = 0):
        """ метод ко-й показывает закрытые сделки за определенный период времени;
        days - сколько дней назад смотрим историю сделок начиная с текущего дня; symbol можно
        выбрать опрделенную валюту или же бырать все : symbol= all , или по magic_number;
         """
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # получим количество сделок в истории
        #   yesterday = datetime.datetime.now() - timedelta(days=days)  # вчерашний день
        # from_date = datetime.datetime(2021, 4, 29)
        to_date = datetime.datetime.now()
        # получим  в указанном интервале сделки по символам, имена которых содержат symbol
        # deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
        # print(f"deals : {deals}")
        if magic_number == 0 and days != None:  # если не выбран magic_number
            yesterday = datetime.datetime.now() - timedelta(days=days)  # вчерашний день
            if symbol != "all":  # если выбрана опредленная валютная пара
                deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals_get({}, {}, )={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    #  print(df.info())
                    df_robot = df[['ticket', 'order', 'time', 'type', 'magic', 'volume', 'volume', 'price', 'profit',
                                   'symbol', 'comment']]
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок убыточных нет !')
                        df_robot, len_df = 0, 0  # кол-во позиций
                        return df_robot, len_df
                    else:
                        # print(f"len of df_robot: {len(df_robot)}")
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ symbol и суммируем по profit
                        df_group = df_robot.groupby(['symbol']).agg({"profit": "sum"})  # summ of loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")
                        print(f"\ndf_group : {df_group}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd
                    # print(df_robot)
            elif symbol == "all":  # если выбрали все валютные пары
                deals = mt5.history_deals_get(yesterday, to_date)  # -- > убрал symbol
                print(f"yesterday and to_date: {yesterday} and {to_date}, len_deals = {len(deals)}, symbol: {symbol}")
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals:{}, {}, выборка по всем валютам ={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df_robot = df[
                        ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'reason', 'volume', 'price', 'profit',
                         'symbol', 'comment']]
                    print(f"df_new : {df_robot}")
                    # loss_df = df_robot[df_robot.profit < 0]  # ОТБОР ОРДЕРОВ ПО его полю profit (убытку)
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок убыточных нет !')
                        df_robot, len_df = 0, 0  # кол-во позиций
                        return df_robot, len_df
                    else:
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ type и суммируем по profit
                        df_group = df_robot.groupby(['type']).agg({"profit": "sum"})  # profit_loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd

        if magic_number != 0 and days != None:  # если выбран magic_number - кокретный
            yesterday = datetime.datetime.now() - timedelta(days=days)  # вчерашний день
            if symbol != "all":  # если выбрана опредленная валютная пара
                deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol: {}".format(mt5.last_error(), symbol))
                    deals, len_deals = None, None
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals_get {}, {}, ={}".format(yesterday, to_date, len(deals)))
                    # print(f"deals : {deals}")
                    # выведем эти сделки   в виде таблицы с помощью pandas.DataFrame
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')

                    df_new = df[['ticket', 'order', 'time', 'type', 'magic',
                                 'volume', 'price', 'profit', 'symbol', 'comment']]
                    # print(f"df_new: {df_new.info()}")
                    # print(f"magic : {magic_number}")
                    df_robot = df_new[df_new.magic == magic_number][['ticket', 'order', 'time', 'type', 'magic',
                                                                     'volume', 'price', 'profit', 'symbol', 'comment']]
                    # print(f"df_new : {df_robot}")
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок нет !')
                        df_robot, len_df_robot = 0, 0  # кол-во позиций
                        return df_robot, len_df_robot
                    else:
                        print(f"len of df_robot: {len(df_robot)}")
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ symbol и суммируем по profit
                        df_group = df_robot.groupby(['magic', 'symbol']).agg({'magic': 'unique', 'symbol': 'unique',
                                                                              "profit": "sum"})  # summ of deals
                        df_group_new = df_group[['magic', 'symbol', 'profit']]
                        profit_loss = df_group.profit.values[0]  # получаем нужное значение
                        print(f"df_group_new: \n{df_group_new.info()}\n")
                        # print(f"profit_loss : {profit_loss}, \ndf_group: {df_group}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd
            elif symbol == "all":  # если выбрали все валютные пары
                deals = mt5.history_deals_get(yesterday, to_date)  # -- > убрал symbol
                print(f"yesterday and to_date: {yesterday} and {to_date}, len_deals = {len(deals)}, symbol: {symbol}")
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals:{}, {}, выборка по всем валютам ={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df_new = df[
                        ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'volume', 'price', 'profit',
                         'symbol', 'comment']]
                    df_robot = df_new[df_new.magic == magic_number][
                        'ticket', 'order', 'time', 'type', 'magic', 'volume',
                        'volume', 'price', 'profit', 'symbol', 'comment']
                    print(f"df_new : {df_robot}")
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок нет !')
                        df_robot, len_df_robot = 0, 0  # кол-во позиций
                        return df_robot, len_df_robot
                    else:
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ magic и суммируем по profit
                        df_group = df_robot.groupby(['magic']).agg({"profit": "sum"})  # summ of loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")

                        return df_robot, profit_loss  # return - общий итог по этим сделкам usd

        # если выбираем диапазон дат (между определнными датами)
        if magic_number == 0 and days == None:  # если не выбран magic_number
            yesterday = datetime.date(2021, 4, 20)  # за дату
            if symbol != "all":  # если выбрана опредленная валютная пара
                deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals_get({}, {}, )={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    #  print(df.info())
                    df_robot = df[['ticket', 'order', 'time', 'type', 'magic', 'volume', 'volume', 'price', 'profit',
                                   'symbol', 'comment']]
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок убыточных нет !')
                        df_robot, len_df = 0, 0  # кол-во позиций
                        return df_robot, len_df
                    else:
                        # print(f"len of df_robot: {len(df_robot)}")
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ symbol и суммируем по profit
                        df_group = df_robot.groupby(['symbol']).agg({"profit": "sum"})  # summ of loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")
                        print(f"\ndf_group : {df_group}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd
                    # print(df_robot)
            elif symbol == "all":  # если выбрали все валютные пары
                deals = mt5.history_deals_get(yesterday, to_date)  # -- > убрал symbol
                print(f"yesterday and to_date: {yesterday} and {to_date}, len_deals = {len(deals)}, symbol: {symbol}")
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals:{}, {}, выборка по всем валютам ={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df_robot = df[
                        ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'reason', 'volume', 'price', 'profit',
                         'symbol', 'comment']]
                    print(f"df_new : {df_robot}")
                    # loss_df = df_robot[df_robot.profit < 0]  # ОТБОР ОРДЕРОВ ПО его полю profit (убытку)
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок убыточных нет !')
                        df_robot, len_df = 0, 0  # кол-во позиций
                        return df_robot, len_df
                    else:
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ type и суммируем по profit
                        df_group = df_robot.groupby(['type']).agg({"profit": "sum"})  # profit_loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd
            print("будем выбирать между датами")

        if magic_number != 0 and days == None:  # если выбран magic_number - кокретный
            yesterday = datetime.datetime(2021, 4, 28)  # за дату конкртеную ------ > вставиить дату из виджета
            # yesterday = datetime.datetime.now() - timedelta(days=4)
            to_date = datetime.datetime.now()
            if symbol != "all":  # если выбрана опредленная валютная пара
                deals = mt5.history_deals_get(yesterday, to_date, group=symbol)
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals, error={}, symbol: {}, yesterday:{} and to_date:{} ".format(mt5.last_error(),
                                                                                                symbol, yesterday,
                                                                                                to_date))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals_get {}, {}, ={}".format(yesterday, to_date, len(deals)))
                    # print(f"deals : {deals}")
                    # выведем эти сделки в виде таблицы с помощью pandas.DataFrame
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')

                    df_new = df[['ticket', 'order', 'time', 'type', 'magic',
                                 'volume', 'price', 'profit', 'symbol', 'comment']]
                    # print(f"df_new: {df_new.info()}")
                    # print(f"magic : {magic_number}")
                    df_robot = df_new[df_new.magic == magic_number][['ticket', 'order', 'time', 'type', 'magic',
                                                                     'volume', 'price', 'profit', 'symbol', 'comment']]
                    # print(f"df_new : {df_robot}")
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок нет !')
                        df_robot, len_df_robot = 0, 0  # кол-во позиций
                        return df_robot, len_df_robot
                    else:
                        print(f"len of df_robot: {len(df_robot)}")
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ symbol и суммируем по profit
                        df_group = df_robot.groupby(['magic', 'symbol']).agg({'magic': 'unique', 'symbol': 'unique',
                                                                              "profit": "sum"})  # summ of deals
                        df_group_new = df_group[['magic', 'symbol', 'profit']]
                        profit_loss = df_group.profit.values[0]  # получаем нужное значение
                        print(f"df_group_new: \n{df_group_new.info()}\n")
                        # print(f"profit_loss : {profit_loss}, \ndf_group: {df_group}")

                        return df_robot, profit_loss  # return - общий убыток по этим сделкам usd
            elif symbol == "all":  # если выбрали все валютные пары
                deals = mt5.history_deals_get(yesterday, to_date)  # -- > убрал symbol
                print(f"yesterday and to_date: {yesterday} and {to_date}, len_deals = {len(deals)}, symbol: {symbol}")
                # print(f"deals : {deals}")
                if deals == None or deals == ():
                    print("No deals with , error code={}, symbol {}".format(mt5.last_error(), symbol))
                    deals, len_deals = 0, 0
                    return deals, len_deals
                elif len(deals) > 0:
                    print("history_deals:{}, {}, выборка по всем валютам ={}".format(yesterday, to_date, len(deals)))
                    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df_new = df[
                        ['ticket', 'order', 'time', 'type', 'magic', 'volume', 'volume', 'price', 'profit',
                         'symbol', 'comment']]
                    df_robot = df_new[df_new.magic == magic_number][
                        'ticket', 'order', 'time', 'type', 'magic', 'volume',
                        'volume', 'price', 'profit', 'symbol', 'comment']
                    print(f"df_new : {df_robot}")
                    if df_robot.empty:
                        print('DataFrame is empty / Сделок нет !')
                        df_robot, len_df_robot = 0, 0  # кол-во позиций
                        return df_robot, len_df_robot
                    else:
                        print(df_robot)
                        # ГРУППИРУЕМ ПО КОЛОНКАМ magic и суммируем по profit
                        df_group = df_robot.groupby(['magic']).agg({"profit": "sum"})  # summ of loss
                        profit_loss = df_group.profit.values[0]  # пулочаем нужное значение
                        print(f"profit_loss : {profit_loss}")

                        return df_robot, profit_loss  # return - общий итог по этим сделкам usd

    def get_tick(self, symbol: str):
        """ получение тиковой цены по конкретной валютной паре symbol, например "EURUSD" """
        symbol_info_tick_dict = mt5.symbol_info_tick(symbol)._asdict()  # проверить ненужная строка -- >
        info_ticket = mt5.symbol_info_tick(symbol)._asdict()  # получение инфы по symbol
        ask_price = info_ticket.get('ask', 0)  # цена из ask
        return ask_price  # возврат значения ask (текущая цена)

    def find_last_price(self, order_type: int, magic: int):
        """ метод для поиска последней цены указанного типа ордера buy или sell
         по-умолчанию Buy == 0 , Sell == 1 """
        usd_positions = mt5.positions_get(symbol="EURUSD")
        if usd_positions is None or usd_positions == ():
            print("No positions with group=\"EURUSD, error code={}".format(mt5.last_error()))
            usd_positions = None
            return usd_positions
        elif len(usd_positions) > 0:
            # Meta_Trader.connect()
            # df_robot, BuyCount, SellCount, CountTrades = Meta_Trader().check_open_orders()
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())

            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic',
                 'comment']]
            df_robot = df_new[df_new.magic == magic][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]

            a = df_robot[df_robot.type == order_type]  # ОТБОР ОРДЕРОВ ПО его типу
            if a.empty:
                print('DataFrame is empty / Сделок на покупок нет !')
            else:
                b = a.nlargest(1, 'time')
                #   print(b.info())
                x = b.price_open.values[0]
                # print(type(x))
                # print("это значение последней цены ордера :" + str(x))
                time.sleep(2)
                return x

    def find_open_price(self, order_type: int, symbol: str, magic_number: int):
        """ метод для поиска цены открытия указанного типа ордера buy или sell
         по-умолчанию Buy == 0 , Sell == 1 """
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            # print("No positions with , error code={}".format(mt5.last_error()))
            return positions
        elif len(positions) > 0:
            # Meta_Trader.connect()
            # df_robot, BuyCount, SellCount, CountTrades = Meta_Trader().check_open_orders()
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())

            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic', 'comment']]
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'price_current', 'magic', 'comment']]

            a = df_robot[df_robot.type == order_type]  # ОТБОР ОРДЕРОВ ПО его типу
            if a.empty:
                print(f'DataFrame is empty / Сделок по type_order ={order_type} нет, magic={magic_number} !')
            else:
                time.sleep(2)
                b = a.nlargest(1, 'time')  # -- > проверить нужен ли отбор nlargest или иной метод
                open_price_value = b.price_open.values[0]  # значение price_open из одноименной колонки
                # print(f"type open_price_value: {type(open_price_value)}, value:{open_price_value}")
                return open_price_value

    def find_last_lots(self, order_type: int, magic_number: int, symbol: str):
        """поиск последнего лота открытой позции по данной валюте
        по данному magic_number и типу ордера"""
        df_new, df_robot, BuyCount, SellCount, CountTrades = \
            Meta_Trader.check_open_orders(self, magic_number=magic_number, symbol=symbol)
        a = df_robot[df_robot.type == order_type]
        if a.empty:
            print('DataFrame is empty! / Сделок на покупку нет !')
            return a
        else:
            #  b = a.nlargest(1,'time')   # было
            b = a.nlargest(1, 'volume')  # стало
            last_lot = b.volume.values[0]
            print("last lot: " + str(last_lot))
            return last_lot

    def TRADE_ACTION_SLTP(self, symbol, position_ticket, take_profit, order_type):
        """ метод для изменения Take_Profit у открытых ордеров"""
        usd_positions = mt5.positions_get(symbol="EURUSD")
        if usd_positions is None:
            print("No positions with group=\"EURUSD, error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df_new = df[['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'tp', 'magic']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == 114000][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'magic']]
            # -- получаем список tickets -- #
            df_robot_tickets = df_robot[df_robot.type == order_type][['ticket', 'type']]
            tickets_Buy = df_robot_tickets['ticket'].tolist()
            #    print(str(tickets_Buy))

            ##### -- #####    ДЛЯ ПОКУПОК
            df_robot = df_robot[df_robot.type == order_type][['type', 'price_open', 'volume']]
            df_robot['price_lot'] = df_robot['price_open'] * df_robot['volume']
            #        print(df_robot)
            df_robot_group = df_robot.groupby('type', as_index=False).sum()
            #        print(df_robot_group_Buy)
            price_sum = df_robot_group.price_lot.values[0]
            lots_sum = df_robot_group.volume.values[0]
            avg_price = price_sum / lots_sum
            temp_avg = round(avg_price, 5)
            avg_price = temp_avg
            print("avg_price : " + str(avg_price))
            # print(price_sum, lots_sum, avg_price)
            # ---------------------------------------------------------------------------------------- #
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:  # проверка есть ли такая валют пара
                print(symbol, "not found, can not call order_check()")
                mt5.shutdown()
                quit()
            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            price = mt5.symbol_info_tick(symbol).ask
            deviation = 20  # отклонение в пунктах
            request = {
                "action": mt5.TRADE_ACTION_SLTP,  # изменение tp у открытой позиции
                "position": position_ticket,  # ticket позиции у ко-й б/т изменен TP
                "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                #    "sl": price + stop_loss * point,        # Установка стоп-лосса
                "tp": avg_price,  # Установка тейк-профита
                "magic": 114000,  # Magic number
                #         "deviation": deviation,           # Установка максимальной цены отклонения
                #         "comment": "Take_profit edited ",      # Установка коментария к сделке
            }

            # отправим торговый запрос
            result = mt5.order_send(request)
            # проверим результат выполнения
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print("2. order_send failed, retcode={}".format(
                    result.retcode))  # вывод кода ошибки если не произведены изменения
                if result.retcode == 10016:
                    print("Средняя цена уже в прибыли, поэтому все ордера можно уже закрыть в прибыли")
                    return result.retcode
            else:
                print("1. order_send Good(): by {} position_ticket, Take_profit edited good ".format(symbol))

    def open_trade_buy(self, symbol, edit_lots, magic: int, stop_loss: int, take_profit: int):

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()
        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()
        lot = edit_lots  # Установка начального лота
        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        price = mt5.symbol_info_tick(symbol).ask
        deviation = 20  # отклонение в пунктах
        request = {
            "action": mt5.TRADE_ACTION_DEAL,  # поставить рыночный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_BUY,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price - stop_loss * point,  # Установка стоп-лосса            # ------ > вопрос как поставить SL hedge
            "tp": price + take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic,  # Magic number
            "comment": "algo",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        time.sleep(2)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            time.sleep(2)
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good (Buy) (): by {} {} lots at {} with "
                  "deviation={}".format(symbol, lot, price, deviation))

    def open_trade_sell(self, symbol: str, edit_lots: float, magic: int, stop_loss: int, take_profit: int):
        #  symbol = "EURUSD"                      # выбор валют. пары
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        lot = edit_lots  # Установка начального лота
        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        price = mt5.symbol_info_tick(symbol).ask
        deviation = 20  # отклонение в пунктах
        request = {
            "action": mt5.TRADE_ACTION_DEAL,  # поставить рыночный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_SELL,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price + stop_loss * point,  # Установка стоп-лосса
            "tp": price - take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic,  # Magic number
            "comment": "algo",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        time.sleep(2)
        # проверим результат выполнения
        print(f"result : {result}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            time.sleep(2)
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                               deviation))

    def check_robots_orders(self, symbol: str, magic_number: int):
        """проверка открытых роботом позиций
        magic_number - по магическому номеру, symbol- допустим 'eurusd' """

        usd_positions = mt5.positions_get(symbol=symbol)
        # if usd_positions:
        #     df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())

        if usd_positions in (None, ()):  # проверка не пустой ли массив
            # df_robot, BuyCount, SellCount, CountTrades = None, None, None, None  # переменным присвоим None new
            logger.info(f"not found opened deals for symbol = {symbol}")
            return None, None, None, None  # возврашаем значения new

        elif usd_positions:  # если позиции есть
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic', 'comment']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == magic_number][
                ['time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]
            if df_robot.empty:  # проверка а не пустой ли df
                df_robot, CountTrades, BuyCount, SellCount = None, None, None, None
                logger.info(f"DataFrame is empty / Сделок по :{symbol} нет, magic_number: {magic_number}")
                return df_robot, BuyCount, SellCount, CountTrades
            else:  # если df не пустой то выводим данные
                # обшее кол-во сделок открытых ордером
                temp = df_robot
                df_robot = temp
                CountTrades = len(df_robot)  # обшее кол-во сделок
                BuyCount = len(df_robot[df_robot.type == 0])  # кол-во покупок
                SellCount = len(df_robot[df_robot.type == 1])  # кол-во продаж
                logger.info(f"{df_robot=}, {BuyCount=}, {SellCount=}, {CountTrades=}")
                return df_robot, BuyCount, SellCount, CountTrades

    def check_param_order(self, symbol, magic_number):
        df_robot, BuyCount, SellCount, CountTrades = Meta_Trader.check_robots_orders(self, symbol, magic_number)
        a = df_robot  # ОТБОР ОРДЕРОВ ТИПА TYPE 0 - BUY
        if a.empty:
            print('DataFrame is empty Сделок нет !')
        else:
            # print(f"a : \n{a}")
            # b = a.nlargest(1, 'time')
            # print(f"b : {b}")
            open_price = a.price_open.values[0]
            lot_order = a.volume.values[0]  # ---    ???
            stop_loss = a.sl.values[0]
            take_profit = a.tp.values[0]
            type_order = a.type.values[0]
            # print("это значение последней цены ордера : " + str(open_price))
            # print("это значение последней type_order ордера : " + str(type_order))
            # print("это значение последней volume ордера : " + str(lot_order))
            # print("это значение последней stop_loss ордера : " + str(stop_loss))
            # print("это значение последней take_profit ордера : " + str(take_profit))
            return open_price, lot_order, type_order, stop_loss, take_profit

    def open_buy_limit(self, symbol: str, lot: float, stop_loss, take_profit, price: float, magic_number: int):
        """выставляем лимитный ордер buy/sell/limit по указанному символу,
        лоту, размеру stop loss/take profit, указанной цене входа, указанному magic"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        # lot = 0.14  # Установка начального лота
        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        deviation = 20  # отклонение в пунктах
        # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
        request = {
            "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_BUY_LIMIT,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price - stop_loss * point,  # Установка стоп-лосса
            "tp": price + take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic_number,  # Magic number
            "comment": "робот_Umbrella",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                               deviation))

    def open_sell_limit(self, symbol: str, lot: float, stop_loss: int, take_profit: int, price: int, magic_number: int):
        """выставляем лимbтный ордер sell_limit"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        deviation = 20  # отклонение в пунктах
        # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
        request = {
            "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_SELL_LIMIT,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price + stop_loss * point,  # Установка стоп-лосса
            "tp": price - take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic_number,  # Magic number
            "comment": "робот_Umbrella",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                               deviation))

    def open_sell_stop(self, symbol: str, lot: float, stop_loss: float, take_profit: float, price: float,
                       magic_number: int):
        """выставляем лимитный ордер stop sell_order на пробой соответственно"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        deviation = 20  # отклонение в пунктах
        # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
        request = {
            "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_SELL_STOP,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price + stop_loss * point,  # Установка стоп-лосса
            "tp": price - take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic_number,  # Magic number
            "comment": "робот_Umbrella",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                            deviation))

    # --- new methods

    def open_sell_stop_new(self, symbol: str, lot: float, stop_loss: float, take_profit: float,
                           price: float, magic_number: int, cascade: 0 | 1):
        """выставляем лимитный ордер stop sell_order на пробой соответственно допольнительно проверяем 
        есть ли уже открытые отложки по этой же цене или их отсутсвие"""
        # установим подключение к терминалу MetaTrader 5
        if not mt5.initialize():
            logger.info(f"initialize() failed, error code = {mt5.last_error()}")
            # print("initialize() failed, error code =",mt5.last_error())
            quit()

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        # эсперимент - удаляем ненужные ордера другого типа (противоположного)
        # были допустим limit_order, а теперь stop_order поэтому delete all
        tickets_del_1, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=2)
        time.sleep(0.8)
        tickets_del_2, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=3)
        time.sleep(0.8)
        if tickets_del_1:
            for ticket in tickets_del_1:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket)
                time.sleep(0.8)
        if tickets_del_2:
            for ticket_1 in tickets_del_2:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket_1)
                time.sleep(0.8)

        # обьявим фукнцию для открытия ордера
        def my_order_send(cascade: 0 | 1):
            # get take profits for cascase orders
            full_distance = round(abs(price - take_profit))
            half_distance = full_distance / 2  # take_profit for first cascade order
            half_quarter = half_distance + half_distance / 2  # take_profit for second cascade order
            values_distance = (full_distance, half_distance, half_quarter)
            """лот уменьшили в три раза от начального"""
            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            deviation = 80  # отклонение в пунктах
            # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
            new_lot = round(lot / 3, 2)
            print(f"new_lot: {new_lot}")

            if cascade == 1:
                # запуск цикла для отправки запросов на сделку
                for i, val in enumerate(values_distance):
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "volume": new_lot,  # Установка лота
                        "type": mt5.ORDER_TYPE_SELL_STOP,  # Указание тип сделки Buy или Sell
                        "price": price,  # Установка цены Buy или Sell
                        "sl": price + stop_loss * point,  # Установка стоп-лосса
                        "tp": price - val * point,  # Установка тейк-профита
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # Magic number
                        "comment": "Umbrella/cascade",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(
                            "2. order_send failed, retcode={}".format(
                                result.retcode))  # вывод кода ошибки если не открылась сделка
                    else:
                        print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, new_lot,
                                                                                                        price,
                                                                                                        deviation))
                    time.sleep(3)
            elif cascade == 0:
                point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
                deviation = 80  # отклонение в пунктах
                # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "volume": lot,  # Установка лота
                    "type": mt5.ORDER_TYPE_SELL_STOP,  # Указание тип сделки Buy или Sell
                    "price": price,  # Установка цены Buy или Sell
                    "sl": price + stop_loss * point,  # Установка стоп-лосса
                    "tp": price - take_profit * point,  # Установка тейк-профита
                    "deviation": deviation,  # Установка максимальной цены отклонения
                    "magic": magic_number,  # Magic number
                    "comment": "робот_Umbrella",  # Установка коментария к сделке
                    "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                    "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(
                        "2. order_send failed, retcode={}".format(
                            result.retcode))  # вывод кода ошибки если не открылась сделка
                else:
                    print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                                    deviation))

        # новые условия проверки ранее открытых отложек
        tickets, last_price = Meta_Trader.pending_orders_new(self, symbol=symbol, magic_number=magic_number,
                                                             type_order=5)
        if tickets:
            print(f"обнаружены след ордера : {tickets} с ценой открытия: {last_price} !")
            # если цены разные
            if last_price != price:
                print(f"цена открытия: {last_price} старых ордеров отличается от новой цены: {price}")

                # надо удалить эти ордера
                for ticket in tickets:  # цикл по all ticket of pend_orders and delete after
                    self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                               order_ticket=ticket)
                    time.sleep(0.8)

                # затем выставить новый ордер
                my_order_send(cascade=cascade)
                time.sleep(.7)
            # если цены совпадают
            elif last_price == price:
                logger.info(f"цена открытия: {last_price} старых ордеров совпадает с новой ценой: {price}")
        else:
            # если открытых отложен не обнаружено
            if tickets in (None, [], ()):
                logger.info(f"открытых отложенных ордеров по symbol:{symbol} и magic: {magic_number} не обнаружено !")
                my_order_send(cascade=cascade)
                time.sleep(.7)

    def open_sell_limit_new(self, symbol: str, lot: float, stop_loss: float, take_profit: float,
                            price: float, magic_number: int, cascade: 0 | 1):
        """выставляем лимитный ордер sell_limit"""
        # установим подключение к терминалу MetaTrader 5
        if not mt5.initialize():
            logger.info(f"initialize() failed, error code = {mt5.last_error()}")
            # print("initialize() failed, error code =",mt5.last_error())
            quit()
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            logger.info(f"{symbol}, not found, can not call order_check()")
            # print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        # обьявим функцию для открытия ордера
        def my_order_send(cascade: 0 | 1):
            # get take profits for cascase orders
            full_distance = round(abs(price - take_profit))
            half_distance = full_distance / 2  # take_profit for first cascade order
            half_quarter = half_distance + half_distance / 2  # take_profit for second cascade order
            values_distance = (full_distance, half_distance, half_quarter)
            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            deviation = 80  # отклонение в пунктах
            # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
            new_lot = round(lot / 3, 2)

            if cascade == 1:
                # запуск цикла для отправки запросов на сделку
                for i, val in enumerate(values_distance):
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "volume": new_lot,  # Установка лота
                        "type": mt5.ORDER_TYPE_SELL_LIMIT,  # Указание тип сделки Buy или Sell
                        "price": price,  # Установка цены Buy или Sell
                        "sl": price + stop_loss * point,  # Установка стоп-лосса
                        "tp": price - val * point,  # Установка тейк-профита
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # Magic number
                        "comment": "Umbrella/cascade",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(
                            "2. order_send failed, retcode={}".format(
                                result.retcode))  # вывод кода ошибки если не открылась сделка
                    else:
                        print("1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol,
                                                                                                           new_lot,
                                                                                                           price,
                                                                                                           deviation))
                    time.sleep(3)

            elif cascade == 0:
                point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
                deviation = 80  # отклонение в пунктах
                # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "volume": lot,  # Установка лота
                    "type": mt5.ORDER_TYPE_SELL_LIMIT,  # Указание тип сделки Buy или Sell
                    "price": price,  # Установка цены Buy или Sell
                    "sl": price + stop_loss * point,  # Установка стоп-лосса
                    "tp": price - take_profit * point,  # Установка тейк-профита
                    "deviation": deviation,  # Установка максимальной цены отклонения
                    "magic": magic_number,  # Magic number
                    "comment": "робот_Umbrella",  # Установка коментария к сделке
                    "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                    "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(
                        "2. order_send failed, retcode={}".format(
                            result.retcode))  # вывод кода ошибки если не открылась сделка
                else:
                    print(
                        "1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                                     deviation))

        # эсперимент - удаляем ненужные ордера другого типа (противоположного)
        # были допустим limit_order, а теперь stop_order поэтому delete all
        tickets_del_1, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=4)
        time.sleep(0.8)
        tickets_del_2, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=5)
        time.sleep(0.8)
        if tickets_del_1:
            for ticket in tickets_del_1:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket)
                time.sleep(0.8)
        if tickets_del_2:
            for ticket_2 in tickets_del_2:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket_2)
                time.sleep(0.8)

        # новые условия проверки ранее открытых отложек 
        tickets, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=3)
        if tickets:
            logger.info(f"обнаружены след ордера : {tickets} с ценой открытия: {last_price} !")
            # если цены разные
            if last_price != price:
                logger.info(f"цена открытия: {last_price} старых ордеров отличается от новой цены: {price}")
                time.sleep(0.8)

                # надо удалить эти ордера
                for ticket in tickets:  # цикл по all ticket of pend_orders and delete after
                    Meta_Trader.remove_pending_orders(self, symbol=symbol, magic_number=magic_number,
                                                      order_ticket=ticket)
                    time.sleep(0.8)

                my_order_send(cascade=cascade)
                time.sleep(.7)
            # если цены совпадают
            elif last_price == price:
                logger.info(f"цена открытия: {last_price} старых ордеров совпадает с новой ценой: {price}")
        else:
            # если открытых отложек не обнаружено
            if tickets in (None, [], ()):
                logger.info(f"opened pending_orders :{symbol=} и {magic_number=} not find !")
                my_order_send(cascade=cascade)
                time.sleep(.7)

    def open_buy_limit_new(self, symbol: str, lot: float, stop_loss: float, take_profit: float,
                           price: float, magic_number: int, cascade: 0 | 1):
        """выставляем лимитный ордер buy/sell/limit по указанному символу,
        лоту, размеру stop loss/take profit, указанной цене входа, указанному magic"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        # обьявим фукнцию для открытия ордера
        def my_order_send(cascade: 0 | 1):
            # -- get take_profits for cascade orders
            # full_distance = round(abs((price - take_profit) * 100000))    # full  distance between high and low
            full_distance = round(abs(price - take_profit))
            half_distance = full_distance / 2  # take_profit for first cascade order
            half_quarter = half_distance + half_distance / 2  # take_profit for second cascade order
            values_distance = (full_distance, half_distance, half_quarter)
            # take_profit_list = [half_distance, half_quarter, full_distance]

            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            deviation = 80  # отклонение в пунктах
            # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
            new_lot = round(lot / 3, 2)

            if cascade == 1:
                # запуск цикла для отправки запросов на сделку
                for i, val in enumerate(values_distance):
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "volume": new_lot,  # Установка лота
                        "type": mt5.ORDER_TYPE_BUY_LIMIT,  # Указание тип сделки Buy или Sell
                        "price": price,  # Установка цены Buy или Sell
                        "sl": price - stop_loss * point,  # Установка стоп-лосса
                        "tp": price + val * point,  # Установка тейк-профита
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # Magic number
                        "comment": "Umbrella/cascade",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(
                            "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки 
                    else:
                        print("1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol,
                                                                                                           new_lot,
                                                                                                           price,
                                                                                                           deviation))
                    time.sleep(3)
            elif cascade == 0:
                point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
                deviation = 80  # отклонение в пунктах
                # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "volume": lot,  # Установка лота
                    "type": mt5.ORDER_TYPE_BUY_LIMIT,  # Указание тип сделки Buy или Sell
                    "price": price,  # Установка цены Buy или Sell
                    "sl": price - stop_loss * point,  # Установка стоп-лосса
                    "tp": price + take_profit * point,  # Установка тейк-профита
                    "deviation": deviation,  # Установка максимальной цены отклонения
                    "magic": magic_number,  # Magic number
                    "comment": "робот_Umbrella",  # Установка коментария к сделке
                    "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                    "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logger.error(f"order_send failed, retcode= {result.retcode}")
                    # print(
                    #     "2. order_send failed, retcode={}".format(
                    #         result.retcode))  # вывод кода ошибки если не открылась сделка
                else:
                    print(
                        "1. order_send good (): by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                                     deviation))

        # эсперимент - удаляем ненужные ордера другого типа (противоположного)
        # были допустим limit_order, а теперь stop_order поэтому delete all
        tickets_del_1, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=4)
        time.sleep(0.8)
        tickets_del_2, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=5)
        time.sleep(0.8)
        if tickets_del_1:
            for ticket in tickets_del_1:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket)
                time.sleep(0.8)
        if tickets_del_2:
            for ticket_3 in tickets_del_2:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket_3)
                time.sleep(0.8)

        # новые условия проверки ранее открытых отложек 
        tickets, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=2)
        if tickets:
            print(f"обнаружены след ордера : {tickets} с ценой открытия: {last_price} !")

            # если цены разные
            if last_price != price:
                print(f"цена открытия: {last_price} старых ордеров отличается от новой цены: {price}")

                # надо удалить эти ордера
                for ticket in tickets:  # цикл по all ticket of pend_orders and delete after
                    self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                               order_ticket=ticket)
                    time.sleep(0.8)
                # затем выставить новый ордер
                my_order_send(cascade=cascade)
                time.sleep(.7)

            # если цены совпадают
            elif last_price == price:
                print(f"цена открытия: {last_price} старых ордеров совпадает с новой ценой: {price}")
        else:
            # если открытых отложен не обнаружено
            if tickets in (None, [], ()):
                logger.info(f"opened pending_orders for :{symbol} и magic: {magic_number} not find !")
                my_order_send(cascade=cascade)
                time.sleep(.7)

    def open_buy_stop_new(self, symbol: str, lot: float, stop_loss: float, take_profit: float,
                          price: float, magic_number: int, cascade: 0 | 1):
        """выставляем лимитный ордер buy_stop по указанному символу,
        лоту, размеру stop loss/take profit, указанной цене входа, указанному magic, jhlthf  на пробой 
        соответственно допольнительно проверяем 
        есть ли уже открытые отложки по этой же цене или их отсутсвие"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        # обьявим фукнцию для открытия ордера      
        def my_order_send(cascade: 0 | 1):
            # get take profits for cascade orders
            full_distance = round(abs(price - take_profit))
            half_distance = full_distance / 2  # take_profit for first cascade order
            half_quarter = half_distance + half_distance / 2  # take_profit for second cascade order
            values_distance = (full_distance, half_distance, half_quarter)
            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            deviation = 80  # отклонение в пунктах
            # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
            new_lot = round(lot / 3, 2)

            if cascade == 1:
                # запуск цикла для отправки запросов на сделку
                for i, val in enumerate(values_distance):
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "volume": new_lot,  # Установка лота
                        "type": mt5.ORDER_TYPE_BUY_STOP,  # Указание тип сделки Buy или Sell
                        "price": price,  # Установка цены Buy или Sell
                        "sl": price - stop_loss * point,  # Установка стоп-лосса
                        "tp": price + val * point,  # Установка тейк-профита
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # Magic number
                        "comment": "Umbrella/cascade",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(
                            "2. order_send failed, retcode={}".format(
                                result.retcode))  # вывод кода ошибки если не открылась сделка
                    else:
                        print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, new_lot,
                                                                                                        price,
                                                                                                        deviation))
                    time.sleep(3)
            if cascade == 0:
                point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
                deviation = 80  # отклонение в пунктах
                # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "volume": lot,  # Установка лота
                    "type": mt5.ORDER_TYPE_BUY_STOP,  # Указание тип сделки Buy или Sell
                    "price": price,  # Установка цены Buy или Sell
                    "sl": price - stop_loss * point,  # Установка стоп-лосса
                    "tp": price + take_profit * point,  # Установка тейк-профита
                    "deviation": deviation,  # Установка максимальной цены отклонения
                    "magic": magic_number,  # Magic number
                    "comment": "робот_Umbrella",  # Установка коментария к сделке
                    "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                    "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(
                        "2. order_send failed, retcode={}".format(
                            result.retcode))  # вывод кода ошибки если не открылась сделка
                else:
                    print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                                    deviation))

        # эсперимент - удаляем ненужные ордера другого типа (противоположного)
        # были допустим limit_order, а теперь stop_order поэтому delete all
        tickets_del_1, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=2)
        time.sleep(0.8)
        tickets_del_2, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=3)
        time.sleep(0.8)
        if tickets_del_1:
            for ticket in tickets_del_1:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket)
                time.sleep(0.8)
        if tickets_del_2:
            for ticket in tickets_del_2:  # цикл по all ticket of pend_orders and delete after
                self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                           order_ticket=ticket)
                time.sleep(0.8)

        # условия проверки ранее открытых отложек
        tickets, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=4)
        if tickets:
            logger.info(f"обнаружены след ордера : {tickets} с ценой открытия: {last_price} !")
            # если цены разные
            if last_price != price:
                logger.info(f"цена открытия: {last_price} старых ордеров отличается от новой цены: {price}")
                # надо удалить эти ордера
                for ticket in tickets:  # цикл по all ticket of pend_orders and delete after
                    self.remove_pending_orders(symbol=symbol, magic_number=magic_number,
                                               order_ticket=ticket)
                    time.sleep(0.8)
                my_order_send(cascade=cascade)
                time.sleep(.7)
            # если цены совпадают
            elif last_price == price:
                print(f"цена открытия: {last_price} старых ордеров совпадает с новой ценой: {price}")

        else:
            # если открытых отложен не обнаружено
            if tickets is None or tickets == []:
                logger.info(f"opened pending_orders symbol:{symbol} и magic: {magic_number} not find !")
                my_order_send(
                    cascade=cascade)  # --> выполняем

    # ---

    def open_buy_stop(self, symbol: str, lot: float, stop_loss: float, take_profit: float, price: float,
                      magic_number: int):
        """выставляем лимитный ордер buy/sell/limit по указанному символу,
        лоту, размеру stop loss/take profit, указанной цене входа, указанному magic"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
        deviation = 20  # отклонение в пунктах
        # ordertype = ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT"]
        request = {
            "action": mt5.TRADE_ACTION_PENDING,  # поставить отложенный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "volume": lot,  # Установка лота
            "type": mt5.ORDER_TYPE_BUY_STOP,  # Указание тип сделки Buy или Sell
            "price": price,  # Установка цены Buy или Sell
            "sl": price - stop_loss * point,  # Установка стоп-лосса
            "tp": price + take_profit * point,  # Установка тейк-профита
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic_number,  # Magic number
            "comment": "робот_Umbrella",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                "2. order_send failed, retcode={}".format(result.retcode))  # вывод кода ошибки если не открылась сделка
        else:
            print("1. order_send good: by {} {} lots at {} with deviation={} points".format(symbol, lot, price,
                                                                                            deviation))

    def remove_pending_orders(self, symbol: str, magic_number: int, order_ticket: int):
        """удаляем лимитные ордера, symbol (str)- по его символу, magicNumber(int), тикету (int)  """
        symbol_info = mt5.symbol_info(symbol)  # отбор по symbol
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        deviation = 90  # отклонение в пунктах
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,  # удалить рыночный ордер
            "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
            "order": order_ticket,  # получение номера тикета
            "deviation": deviation,  # Установка максимальной цены отклонения
            "magic": magic_number,  # отбор по его Magic number
            "comment": "робот_Umbrella",  # Установка коментария к сделке
            "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
            "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                "2. order_send failed, retcode={}; "
                "symbol:{}, ticket:{}".format(result.retcode, symbol, order_ticket))  # вывод кода ошибки
        else:
            print("1. Order delete good: for symbol: {}, magic_number at {} "
                  "with ticket: {}".format(symbol, magic_number, order_ticket))

    def remove_pending_orders_new(self, symbol: str, magic_number: int):
        """удаляем лимитные ордера, symbol (str)- по его символу, magicNumber(int), тикету (int)  """
        symbol_info = mt5.symbol_info(symbol)  # отбор по symbol
        if symbol_info is None:  # проверка есть ли такая валют пара
            logger.info(f"{symbol=} not found, can not call order_check")
            mt5.shutdown()
            quit()

        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            logger.info(f"{symbol=} is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                logger.info(f"symbol_select({symbol}) failed, exit")
                mt5.shutdown()
                quit()

        deviation = 90  # отклонение в пунктах

        # new code
        tickets_buy_limit, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=2)
        time.sleep(1)
        tickets_sell_limit, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=3)
        time.sleep(1)
        tickets_buy_stop, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=4)
        time.sleep(1)
        tickets_sell_stop, last_price = self.pending_orders_new(symbol=symbol, magic_number=magic_number, type_order=5)
        time.sleep(1)
        # logger.debug(f"{tickets_sell_limit=}")

        tickets_list = [tickets_buy_limit, tickets_sell_limit, tickets_buy_stop,
                        tickets_sell_stop]  # new list for tickets
        tickets_new = []
        for i, val in enumerate(tickets_list):
            # logger.debug(f"{val=}, {type(val)}")
            if val is not None and isinstance(val, list):
                for j in val:
                    tickets_new.append(j)
                    # logger.debug(f"{j=}")
        # logger.debug(f"{tickets_new=}")
        tickets_all = list(itertools.chain(tickets_new))
        temp_list = []  # для хранения резултатов выполнения сделок
        if tickets_all is not None and len(tickets_all) > 0:
            for order_ticket in tickets_all:  # цикл по all ticket of pend_orders and delete after
                request = {
                    "action": mt5.TRADE_ACTION_REMOVE,  # удалить рыночный ордер
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "order": order_ticket,  # получение номера тикета
                    "deviation": deviation,  # Установка максимальной цены отклонения
                    "magic": magic_number,  # отбор по его Magic number
                    "comment": "робот_Umbrella",  # Установка коментария к сделке
                    "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                    "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                time.sleep(.4)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logger.warning(f"\n2. order_send failed, retcode={result.retcode}; {symbol=}, {order_ticket=}")
                    temp_list.append(False)
                else:
                    temp_list.append(True)
                    logger.info(f"1. Order delete good: for: {symbol}, {magic_number=} with ticket {order_ticket}")
        if isinstance(temp_list, list) and len(temp_list) > 0 and True in (temp_list):
            return True
        if isinstance(temp_list, list) and len(temp_list) > 0 and False in (temp_list):
            return False

    def money_management(self):
        """инфо об капитале на счете: тип счета currency (int): usd/rub, balance (int), equity (int), margin_level (float)"""
        Terminal = Meta_Trader(self.login, self.password, self.server)  # create object of class MetaTrader with args
        Terminal.connect()  # method connect
        account_info = mt5.account_info()  # get account info
        if account_info is not None:  # if not empty data
            # print(account_info)
            # выведем данные о торговом счете в виде словаря
            # print("Show account_info()._asdict():")
            account_info_dict = mt5.account_info()._asdict()
            # print(f" type account_info :{type(account_info_dict)}")
            # df = pd.DataFrame(list(account_info_dict.items()), columns=['property', 'value'])
            # logger.info(f"{account_info_dict=}")
            # print(df)
            balance, currency, equity, margin_level = account_info_dict["balance"], account_info_dict["currency"], \
                                                      account_info_dict["equity"], account_info_dict["margin_level"]
            #  print(balance, currency, equity, margin_level)
            return balance, equity, margin_level, currency  # margin_level - level of margin, currency - валюта счета usd/rub

        else:  # if data empty
            logger.warning(
                f"failed to connect error code ={mt5.last_error()}, login: {self.login}, passw:{self.server}")

    def find_last_order(self, symbol, magic_number):
        """ метод для поиска последнего открытого ордера buy или sell
         по-умолчанию Buy == 0 , Sell == 1 ; symbol: str , magic_number: int """
        usd_positions = mt5.positions_get(symbol=symbol)  # отбор по symbol
        if usd_positions == None:  # если нет позиций
            print("No positions with group=\", error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:  # если есть открытые позиции
            # Meta_Trader.connect()
            # df_robot, BuyCount, SellCount, CountTrades = Meta_Trader().check_open_orders()
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic', 'comment']]

            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]  # ОТБОР ПО magic_number
            # a = df_robot[df_robot.type == order_type]  # ОТБОР ОРДЕРОВ ПО его order_type
            a = df_robot  #
            if a.empty:
                print('DataFrame is empty / Сделок на покупок нет !')
            else:
                b = a.nlargest(1, 'time')  # отбор по последнему по времени открытому ордеру
                open_price = b.price_open.values[0]  # price_open last order
                stop_loss, type_order = b.sl.values[0], b.type.values[0]  # last stop and type_order
                # print(f"это последняя цена ордера :{open_price}, stop_loss {stop_loss}, type_order: {type_order}")
                return open_price, stop_loss, type_order

    def TRADE_ACTION_SLTP_NEW(self, symbol: str, magic_number: int, position_ticket: int,
                              stop_loss: float, take_profit: int, order_type: int):
        """метод для изменения Sl /Take_profit у открытых позиций po его symbol, magic_number, 
        position_ticket, type_order"""
        usd_positions = mt5.positions_get(symbol=symbol)
        if usd_positions == None:
            print("No positions with group=\", error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df_new = df[['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'tp', 'magic']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'magic']]
            # -- получаем список tickets -- #
            df_robot_tickets = df_robot[df_robot.type == order_type][['ticket', 'type']]
            tickets_Buy = df_robot_tickets['ticket'].tolist()

            # --> ДЛЯ ПОКУПОК
            df_robot = df_robot[df_robot.type == order_type][['type', 'price_open', 'volume']]
            df_robot['price_lot'] = df_robot['price_open'] * df_robot['volume']
            #        print(df_robot)
            df_robot_group = df_robot.groupby('type', as_index=False).sum()
            # ---------------------------------------------------------------------------------------- #
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:  # проверка есть ли такая валют пара
                print(symbol, "not found, can not call order_check()")
                mt5.shutdown()
                quit()

            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            # price = mt5.symbol_info_tick(symbol).ask
            deviation = 20  # отклонение в пунктах
            if order_type == 0:  # если выбран type_order = 0 (Buy), то выполняем
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменнение Stop loss /Take profit
                    "position": position_ticket,  # номер тикета
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "sl": stop_loss,  # Установка стоп-лосса                        ------- > подумать над stop loss
                    "tp": take_profit + 0.0002,  # Установка тейк-профита + небольшой плюс
                    # "tp": price + take_profit * point,  # Установка тейк-профита    ------- > подумать над take profit
                    "magic": magic_number,
                    # Magic number                          --------> тк у sell ниже TP, а тут + take profit
                    #         "deviation": deviation,           # Установка максимальной цены отклонения
                    #         "comment": "робот_Umbrella",      # Установка коментария к сделке
                }

                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:

                    print("2. order_send failed, retcode={}".format(
                        result.retcode))  # вывод кода ошибки если не произведены изменения
                    if result.retcode == 10016:
                        print(f"Неправильные стопы в запросе, fot ticket: {position_ticket}, "
                              f"stop_loss: {stop_loss}, Take_profit: {take_profit}")
                        return result.retcode
                else:
                    print("1. order_send Good(): by {}, position_ticket {} ".format(symbol, position_ticket))
                    print(f"Все TP-уровни у каждого ордера изменены успешно, TP: {take_profit}")
            if order_type == 1:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменнение Stop loss /Take profit
                    "position": position_ticket,  # номер тикета
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "sl": stop_loss,  # Установка стоп-лосса                        ------- > подумать над stop loss
                    "tp": take_profit - 0.0002,  # Установка тейк-профита
                    # "tp": price - take_profit * point,  # Установка тейк-профита    ------- > подумать над take profit
                    "magic": magic_number,
                    # Magic number                          --------> тк у sell ниже TP, а тут + take profit
                    #         "deviation": deviation,           # Установка максимальной цены отклонения
                    #         "comment": "робот_Umbrella",      # Установка коментария к сделке
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:

                    print("2. order_send failed, retcode={}".format(
                        result.retcode))  # вывод кода ошибки если не произведены изменения
                    if result.retcode == 10016:
                        print(f"Неправильные стопы в запросе, fot ticket: {position_ticket}, "
                              f"stop_loss: {stop_loss}, Take_profit: {take_profit}")
                        return result.retcode
                else:
                    print("1. order_send Good(): by {}, position_ticket {} ".format(symbol, position_ticket))
                    print(f"Все TP-уровни у каждого ордера изменены успешно, TP: {take_profit}")

    def new_trade_action_sltp(self, symbol: str, magic_number: int,
                              order_type: int, stop_loss: float = 0):
        """метод для изменения Sl /Take_profit у открытых позиций po его symbol, magic_number, 
        position_ticket, type_order"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:  # проверка есть ли такая валют пара
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        usd_positions = mt5.positions_get(symbol=symbol)
        if usd_positions is None:
            print("No positions with group=\", error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            # logger.debug(f"\n\n{df.columns}")
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'magic']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'sl', 'tp', 'price_current', 'magic']]

            # -- получаем список tickets для Buy , type_order = 0
            df_robot_tickets = df_robot[df_robot.type == 0][['ticket', 'type', 'sl', 'tp', 'price_open']]
            tickets_Buy = df_robot_tickets['ticket'].tolist()
            tickets_prices = df_robot_tickets['price_open'].tolist()
            tickets_prices_sl = df_robot_tickets['sl'].tolist()
            tickets_prices_tp = df_robot_tickets['tp'].tolist()

            logger.info(f"{tickets_prices_tp=}")

            # logger.info(f"\n{tickets_Buy=}, \n {df_robot_tickets=}n, \n{tickets_prices=}, \n\n{tickets_prices_sl=}")

            def find_avg_sl(open_prices: list, sl_stops: list, deviation: float):
                """ метод для получения средней цены стопа, цены открытия позиций, уровня take_profit
                deviation - погрешность в разнице цен """
                if sl_stops:
                    avg_sl = np.average(sl_stops)
                    # logger.debug(f"\n{avg_sl=}")
                if open_prices:
                    avg_open = np.average(open_prices)
                    # logger.debug(f"\n{avg_open=}")
                razniza = abs((round(avg_sl, 5)) - (round(avg_open, 5)))
                # logger.debug(f"{razniza=}")
                if razniza < deviation:
                    return None
                elif razniza > deviation:
                    return round(razniza, 5)

            razniza = find_avg_sl(open_prices=tickets_prices, sl_stops=tickets_prices_sl, deviation=0.0001)
            # logger.debug(f"\n\n{razniza=}")

            # -- получаем список tickets для Sell , type_order = 1
            df_robot_tickets_2 = df_robot[df_robot.type == 1][['ticket', 'type', 'price_open', 'sl', 'tp']]
            tickets_Sell = df_robot_tickets_2['ticket'].tolist()
            tickets_prices_sell = df_robot_tickets_2['price_open'].tolist()
            tickets_prices_sell_sl = df_robot_tickets_2['sl'].tolist()
            tickets_prices_sell_tp = df_robot_tickets_2['tp'].tolist()
            # logger.info(f"\n{tickets_Sell=}, \n {df_robot_tickets_2=}n, \n{tickets_prices_sell=}, \n{tickets_prices_sell_sl}")

            razniza_2 = find_avg_sl(open_prices=tickets_prices_sell, sl_stops=tickets_prices_sell_sl, deviation=0.0001)
            # logger.info(f"{razniza_2=}")

            # --> ДЛЯ ПОКУПОК
            df_robot = df_robot[df_robot.type == order_type][['type', 'price_open', 'volume']]
            df_robot['price_lot'] = df_robot['price_open'] * df_robot['volume']

            # df_robot_group = df_robot.groupby('type', as_index=False).sum()
            # ---------------------------------------------------------------------------------------- #
            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            # price = mt5.symbol_info_tick(symbol).ask
            deviation = 70  # отклонение в пунктах

            # 1. if avg_stoploss buys_deals different with avg_open_price is big, then change stop_loss
            if razniza is None:
                logger.info(f"avg_price not much different with avg_open_price")
            elif razniza is not None:
                logger.info(f"avg_price is different with avg_open_price, then change stop_loss for breakeven\n")
                j = -1  # для начала списка
                for ticket in tickets_Buy:
                    j += 1
                    # logger.info(f"\n{tickets_prices_tp[j]=}")
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменнение Stop loss /Take profit
                        "position": ticket,  # номер тикета
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "sl": tickets_prices[0],  # Установка стоп-лосса
                        "tp": tickets_prices_tp[j],  # Установка тейк-профита
                        "magic": magic_number,
                        # Magic number                          
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        # "comment": "робот_Umbrella",      # Установка коментария к сделке
                    }

                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    time.sleep(.3)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print("2. order_send failed, retcode={}".format(result.retcode))
                        # вывод кода ошибки если не произведены изменения
                        # if result.retcode == 10016:
                        #     print(f"Неправильные стопы в запросе, fot ticket: {position_ticket}, "
                        #           f"stop_loss: {stop_loss}")
                        #     return result.retcode
                    else:
                        print("1. order_send good(): by {}, ticket {} ".format(symbol, ticket))
                        print(f"Все TP-уровни у каждого ордера изменены успешно")
                    time.sleep(.5)

            # 2. if avg_stoploss sell_deals different with avg_open_price is big, then change stop_loss
            if razniza_2 is None:
                logger.info(f"avg_price not much different with avg_open_price")
            elif razniza_2 is not None:
                logger.info(f"avg_price is different with avg_open_price, then change stop_loss for breakeven\n")
                j = -1
                for ticket in tickets_Sell:
                    j += 1
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменение Stop loss /Take profit
                        "position": ticket,  # номер тикета
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "sl": tickets_prices_sell[0],  # Установка стоп-лосса
                        "tp": tickets_prices_sell_tp[j],  # Установка тейк-профита
                        "magic": magic_number,
                        # Magic number                          --------> тк у sell ниже TP, а тут + take profit
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        #     "comment": "робот_Umbrella",      # Установка коментария к сделке
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    time.sleep(.3)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print("2. order_send failed, retcode={}".format(
                            result.retcode))  # вывод кода ошибки если не произведены изменения
                        if result.retcode == 10016:
                            print(f"Неправильные стопы в запросе, fot ticket: {ticket}, "
                                  f"stop_loss: {stop_loss}")
                            return result.retcode
                    else:
                        print("1. order_send Good(): by {}, ticket {} ".format(symbol, ticket))
                        print(f"Все TP-уровни у каждого ордера изменены успешно")

    def avg_price_new(self, symbol: str, magic_number: int, order_type: int):
        """ метод для нахождения средней цены buy или sell
         для перекрытия убыточной серии/сетки ордеров данного типа
         по умолчанию buy = 0, sell = 1 """
        avg_price = 0
        usd_positions = mt5.positions_get(symbol=symbol)
        if usd_positions == None or usd_positions == ():  # проверка не пустой ли массив
            print("No positions with group=\"EURUSD, error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:  # если массив не пустой
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            # открытые только роботом позиции с его magic- номером
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic', 'comment']]
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]
            # -- получаем список tickets -- #
            df_robot_Buy_tickets = df_robot[df_robot.type == 0][['ticket', 'type']]  # df of Buy
            tickets_Buy = df_robot_Buy_tickets['ticket'].tolist()  # лист buy тикетов
            df_robot_Sell_tickets = df_robot[df_robot.type == 1][['ticket', 'type']]  # df of Sell
            tickets_Sell = df_robot_Sell_tickets['ticket'].tolist()  # лист sell тикетов
            #    print(str(tickets_Buy) + "\n" + str(tickets_Sell))
            ##### -- #####    ДЛЯ ПОКУПОК
            df_robot = df_robot[df_robot.type == order_type][['type', 'price_open', 'volume']]
            df_robot['price_lot'] = df_robot['price_open'] * df_robot['volume']
            df_robot_group = df_robot.groupby('type', as_index=False).sum()
            if df_robot_group.empty:  # проверка на пустой df
                print('df_robot_group is empty/ Пустой Дата_фрейм!')
            else:
                price_sum = df_robot_group.price_lot.values[0]
                lots_sum = df_robot_group.volume.values[0]
                avg_price = price_sum / lots_sum
                temp_avg = round(avg_price, 5)
                avg_price = temp_avg
            # print(price_sum, lots_sum, avg_price_Buy)
            return avg_price, tickets_Buy, tickets_Sell

    def remove_open_position(self, symbol: str = "all", magic_number: int = "all"):
        """удаляем открытые сделки, symbol (str)- по его символу, magicNumber(int)"""
        if not mt5.initialize():
            logger.info(f"initialize() failed, error code =, {mt5.last_error()}")
            quit()
        symbol_info = mt5.symbol_info(symbol)  # отбор по symbol
        if symbol_info is None:  # проверка есть ли такая валют пара
            logger.info(f"{symbol}, not found, can not call order_check()")
            mt5.shutdown()
            quit()
        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            logger.info(f"{symbol}, is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                logger.info(f"symbol_select({symbol}) failed, exit")
                mt5.shutdown()
                quit()

        usd_positions = mt5.positions_get(symbol=symbol)  # получим данные по данному symbol
        # logger.debug(f"{usd_positions=}")
        if usd_positions in (None, ()):  # проверка не пустой ли массив
            logger.info(f"\nNot found opened deals for {symbol}, error code ={mt5.last_error()}\n")
        elif len(usd_positions) > 0:  # если не пустой
            deviation = 90  # отклонение в пунктах
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            # открытые только роботом позиции с его magic- номером
            df_new = df[
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                 'magic', 'comment']]
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                 'tp', 'profit', 'magic', 'comment']]
            # print(f"df_new : {df_new}, df_robot : {df_robot}")
            # -- получаем список tickets -- #

            # for buy #
            df_robot_Buy_tickets = df_robot[df_robot.type == 0][['ticket', 'type', 'volume']]  # ticket - volume
            tickets_Buy = df_robot_Buy_tickets['ticket'].tolist()  # list of buy tickets
            tickets_Volume_Buy = df_robot_Buy_tickets['volume'].tolist()  # list volume tickets_Buy
            price = mt5.symbol_info_tick(symbol).ask
            # print(f"len(tickets_Buy) : {len(tickets_Buy)}")
            if len(tickets_Buy) > 0:  # если есть buy позиции
                for tiket_buy, buy_volume in zip(tickets_Buy,
                                                 tickets_Volume_Buy):  # перебор по двум спискам ticket / volume
                    # logger.debug(f"\n{tiket_buy=}, {buy_volume=}\n")  # ticket -- > volume
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,  # поставить рыночный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "type": mt5.ORDER_TYPE_SELL,  # если открыта покупка, то выбираем ORDER_TYPE_SELL, и наоборот
                        "position": tiket_buy,  # тикет(ticket) позиции
                        "price": price,
                        "volume": buy_volume,  # обьем закрываемой позиции
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # отбор по его Magic number
                        "comment": "робот_Umbrella",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    time.sleep(0.4)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE or result.retcode != 10009:
                        logger.warning(f"order_send failed: {result.retcode=}; {symbol=}, {tiket_buy=}, {buy_volume=}\n")
                    else:
                        logger.info(f"Order by ticket: {tiket_buy} delete good : for symbol: {symbol}, magic_number: {magic_number} at volume {buy_volume}\n")

            # for sell #
            df_robot_Sell_tickets = df_robot[df_robot.type == 1][['ticket', 'type', 'volume']]
            tickets_Sell = df_robot_Sell_tickets['ticket'].tolist()  # list of sell tickets
            tickets_Volume_Sell = df_robot_Sell_tickets['volume'].tolist()  # list volume tickets_Sell
            time.sleep(0.8)
            if len(tickets_Sell) > 0:  # если есть открытые позиции
                for tiket_sell, sell_volume in zip(tickets_Sell, tickets_Volume_Sell):
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,  # поставить рыночный ордер
                        "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                        "type": mt5.ORDER_TYPE_BUY,  # если открыта покупка то выбираем ORDER_TYPE_SELL, и наоборот
                        "position": tiket_sell,
                        "volume": sell_volume,  # обьем закрываемой позиции
                        "deviation": deviation,  # Установка максимальной цены отклонения
                        "magic": magic_number,  # отбор по его Magic number
                        "comment": "робот_Umbrella",  # Установка коментария к сделке
                        "type_time": mt5.ORDER_TIME_GTC,  # время сделки формат
                        "type_filling": mt5.ORDER_FILLING_FOK,  # тип ордера
                    }
                    # отправим торговый запрос
                    result = mt5.order_send(request)
                    time.sleep(0.2)
                    # проверим результат выполнения
                    if result.retcode != mt5.TRADE_RETCODE_DONE or result.retcode != 10009:
                        logger.warning(f"order_send failed: {result.retcode=}; {symbol=}, {tiket_sell=}, {sell_volume=}\n")
                    else:
                        logger.info(f"Order by ticket: {tiket_sell} delete good : for symbol: {symbol}, magic_number: {magic_number} at volume {sell_volume}\n")

    def close_opened_deals(self, symbol: str, magic_number: int):
        """"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # подготовим структуру запроса для покупки
        # symbol = "USDJPY"
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()
        # если символ недоступен в MarketWatch, добавим его
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
                mt5.shutdown()
                quit()

        lot = 0.19
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask
        deviation = 20
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": price - 100 * point,
            "tp": price + 100 * point,
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol, lot, price, deviation));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # запросим результат в виде словаря и выведем поэлементно
            result_dict = result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field, result_dict[field]))
                # если это структура торгового запроса, то выведем её тоже поэлементно
                if field == "request":
                    traderequest_dict = result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed, traderequest_dict[tradereq_filed]))
            print("shutdown() and quit")
            mt5.shutdown()
            quit()

        print("2. order_send done, ", result)
        print("   opened position with POSITION_TICKET={}".format(result.order))
        print("   sleep 2 seconds before closing position #{}".format(result.order))
        time.sleep(2)
        # создадим запрос на закрытие
        position_id = result.order
        price = mt5.symbol_info_tick(symbol).bid
        deviation = 20
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "position": position_id,
            "price": price,
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        # отправим торговый запрос
        result = mt5.order_send(request)
        # проверим результат выполнения
        print("3. close position #{}: sell {} {} lots at {} with deviation={} points".format(position_id, symbol, lot,
                                                                                             price, deviation));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("4. order_send failed, retcode={}".format(result.retcode))
            print("   result", result)
        else:
            print("4. position #{} closed, {}".format(position_id, result))
            # запросим результат в виде словаря и выведем поэлементно
            result_dict = result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field, result_dict[field]))
                # если это структура торгового запроса, то выведем её тоже поэлементно
                if field == "request":
                    traderequest_dict = result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed, traderequest_dict[tradereq_filed]))

        # завершим подключение к терминалу MetaTrader 5

    def order_calculator(self, symbol: str, pips: int):
        """расчет стоимости в деньгах для валютной пары (symbol) ,
        для данного количества пунктов (pips): возврашает значение stop_loss в суммовом выражении """
        # установим подключение к терминалу MetaTrader 5
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # получим валюту счета
        account_currency = mt5.account_info().currency
        print("Account сurrency:", account_currency)
        # оценим значения прибыли для покупок и продаж
        lot = 0.1
        #    distance = 300
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(symbol, "not found, skipped")
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, skipped", symbol)
        point = mt5.symbol_info(symbol).point
        symbol_tick = mt5.symbol_info_tick(symbol)
        ask = symbol_tick.ask
        bid = symbol_tick.bid
        buy_profit = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, lot, ask, ask + pips * point)
        if buy_profit != None:
            print("   buy {} {} lot: profit on {} points => {} {}".format(symbol, lot, pips, buy_profit,
                                                                          account_currency))
        else:
            print("order_calc_profit(ORDER_TYPE_BUY) failed, error code =", mt5.last_error())
        sell_profit = mt5.order_calc_profit(mt5.ORDER_TYPE_SELL, symbol, lot, bid, bid - pips * point)
        if sell_profit != None:
            print("   sell {} {} lots: profit on {} points => {} {}".format(symbol, lot, pips, sell_profit,
                                                                            account_currency))
        stop_loss_usd = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, lot, ask, ask - pips * point)
        if stop_loss_usd != None:  # для расчета стоп-лосса в деньгах счета
            print("   buy {} {} lot: stop_loss on {} pips => {} {}".format(symbol, lot, pips, stop_loss_usd,
                                                                           account_currency))
            return stop_loss_usd
        else:
            print("order_calc_profit(ORDER_TYPE_SELL) failed, error code =", mt5.last_error())
        print()

    def find_lot_management(self, symbol: str, pips: int, percent: float):
        """
        поиск подходящего размера лота для указанных рисков percent, для заданного symbol,
        для данного размера стопа (pips/пунктах): return stop_loss in usd, lot, percent, pips 
        """
        if not mt5.initialize():
            logger.warning(f"initialize() failed, error code = {mt5.last_error()}")
            quit()
        # Terminal = Meta_Trader(self.login, self.password, self.server)  # create object of class MetaTrader with args
        balance, equity, margin_level, currency = self.money_management()
        # logger.warning(f"xx: {balance, equity, margin_level, currency}\n")

        # 1. generate massiv lots: 0.02-min value, 3.9-max value, 0.01-step
        time.sleep(1)
        array_np = np.arange(0.02, 3.5, 0.01)
        list_lots = list(array_np)  # massiv to list
        lots = [round(value, 2) for value in list_lots]  # list округляем значения in list_lots
        percent_deposit = equity / 100 * percent  # percent- процент от депозита, в денежной еденице счета
        # получим валюту счета
        # account_currency = mt5.account_info().currency
        # print("Валюта счета :", account_currency)
        # logger.debug(f"{percent_deposit=}, {pips=}")

        # -- code -- > поиск лота удовлетворяющего условиям риска в процентах и pips/пунктах, т.е Stop_loss
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"not found symbol_info for money_management, skipped : {symbol=}")
        point = mt5.symbol_info(symbol).point
        symbol_tick = mt5.symbol_info_tick(symbol)
        ask = symbol_tick.ask

        for lot in lots:
            stop_loss_usd = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, lot, ask, ask + pips * point)
            # time.sleep(0.2)
            # logger.debug(f"{stop_loss_usd=}, what: {pips * point}")

            if stop_loss_usd is not None and stop_loss_usd >= percent_deposit:  # для расчета стоп-лосса в валюте счета
                logger.info(f"\nFind params: {symbol=}, {lot=}, stop_loss = {pips} pips, ==> {stop_loss_usd} usd")
                return stop_loss_usd, lot, symbol, pips
            else:
                if stop_loss_usd in (None, ()):
                    # print(f"идет поиск подходящего лота для риска: {percent}, и стопа = {pips}, "
                    #       f"для symbol: {symbol}, тек.лот={lot}")  # new code
                    logger.warning("Не найден подходящий лот для отложек либо другая причина")
                    logger.warning("order_calc_profit(ORDER_TYPE_SELL) failed, error code =", mt5.last_error())
            time.sleep(0.1)

    def find_sma_prices(self, symbol: str, timeframe: str, counts_bars: int):
        """ метод для поиска Sma - скользяшей цены для данного symbol,
         timeframe - выбор нужного таймфрема типо H4, counts_bars - кол-во баров начиная с текушего дня"""
        # установим подключение к терминалу MetaTrader 5
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()

        # установим таймзону в UTC
        timezone = pytz.timezone("Etc/UTC")
        # создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
        today = datetime.datetime.now()
        # utc_from = datetime.datetime(2021, 5, 1, tzinfo=timezone)   # ранее был этот код
        # получим 22 баров с symbol H4 начиная с 2021, 4, 30 в таймзоне UTC
        if timeframe == "h4":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H4, today, counts_bars)
            # завершим подключение к терминалу MetaTrader 5
            mt5.shutdown()

            # создадим из полученных данных DataFrame
            rates_frame = pd.DataFrame(rates)
            # сконвертируем время в виде секунд в формат datetime
            rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')

            df_new = rates_frame[['time', 'close']]  #
            sma_h4_price = df_new['close'].mean()  # получим среднее значение по колонке "close"
            # выведем данные
            print("\nВыведем датафрейм с данными")
            print(rates_frame)
            print(f"sma_h4_price : {sma_h4_price}, {type(sma_h4_price)}")
            return round(sma_h4_price, 5)  # return sma_h1_price
        elif timeframe == "h1":
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, today, counts_bars)
            # завершим подключение к терминалу MetaTrader 5
            mt5.shutdown()
            # создадим из полученных данных DataFrame
            rates_frame = pd.DataFrame(rates)
            # сконвертируем время в виде секунд в формат datetime
            rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
            df_new = rates_frame[['time', 'close']]  #
            sma_h1_price = df_new['close'].mean()  # получим среднее значение по колонке "close"
            # выведем данные
            print("\nВыведем датафрейм с данными")
            #     print(rates_frame)
            print(f"sma_h1_price : {sma_h1_price}, {type(sma_h1_price)}")
            return round(sma_h1_price, 5)  # return sma_h1_price

    def get_atr_symbol(self, symbol: str, count: int):
        """ метод ко-й показывает величину ATR-cреднего хода цены(по symbol) на дневном timeframe,
        вовзвращает само средне ATR , текущий ATR - в пунктах и %-процентах; count-кол-во дней для ATR"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            quit()
        # установим таймзону в UTC
        timezone = pytz.timezone("Etc/UTC")
        # создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
        # from_date = datetime.datetime(2021, 4, 1, tzinfo=timezone)
        current_day = datetime.datetime.today()  # Получим тек дату
        # получим 10 баров с EURUSD H4 начиная с 01.10.2020 в таймзоне UTC
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_D1, current_day, count)

        rates_frame = pd.DataFrame(rates)
        # сконвертируем время в виде секунд в формат datetime
        rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
        # print(f"rates_frame: {rates_frame}")

        # -- > get current atr day value < -- #
        df_temp = rates_frame[['open', 'close']]  # создали df для поиска ATR тек дня
        df_open_close = df_temp.iloc[-1:]  # получим самую последную строку снизу, там тек дневка
        df_open_close["day_atr"] = df_open_close['open'] - df_open_close['close']
        today_atr_value = round(abs(df_open_close.day_atr.values[0]), 5)  # получим абс значение разницы

        # -- > для получения среднего ATR (high-low) < -- #
        df_new = rates_frame[['time', 'high', 'low']]  # create new df
        df_new['raznica'] = df_new['high'] - df_new['low']  # создадим новый столбец разница
        df_new.round(5)  # Округлим dataframe
        df_raznica = df_new[["raznica"]]  # df c разницей
        sredne_atr = round(df_raznica.mean(), 5)  # округлим значение
        sredne_atr_value = sredne_atr[0].tolist()  # cреднее значение из series sredne_atr
        # print(f"numbers_list: {sredne_atr_value}, type:{type(sredne_atr_value)}")
        df_reverse = df_raznica.iloc[::-1]  # новый df идем с конца(переворачиваем df, тк внизу самый новые даты)
        print(f"df_raznica revere:{df_reverse}")
        time.sleep(0.5)

        a_massiv = np.array([])  # создаем пустой массив
        counts_values = []  # список где будут хранится все значения ока-ся рядом(соседи)
        for i in trange(len(df_reverse)):  # цикл по столбцу "df_close" from df_list сверху/вниз
            # value = df.iloc[i][df.columns[j]]            # get value_df; i - номер строки, j - номер столбца
            value = df_reverse.iloc[i][df_reverse.columns[0]]  # get value from df
            #  print(i, value)
            if value >= sredne_atr_value / 2 and value <= sredne_atr_value * 2:  # добавить условие пока i <= 5
                for i in range(1, 5):  # берем только 5-элементов
                    a_massiv = np.append(a_massiv, value)  # добавляем каждое новое value from df_column в массив array
        # five_elements = a_massiv[0:5]                   # получим первые 5 элементов массива
        five_elements = a_massiv  # массив из значений atr за последние 5-дней
        mean_value_atr = np.mean(five_elements)  # получим среднее значение ATR из 5 дней
        distance_atr = today_atr_value / (
            round(mean_value_atr, 5)) * 100  # расстояние(%) ко-е уже пройдено отно-но ATR-среднего
        print(f"a_massiv: \n{a_massiv}, \nmean_value_atr: {mean_value_atr}, {five_elements}")
        print(f"\ndf_high_low: \n{df_open_close}, \natr value :{today_atr_value}")

        return round(mean_value_atr, 5), today_atr_value, distance_atr

    def Change_SLTP(self, symbol: str, magic_number: int, position_ticket: int,
                    stop_loss: float, take_profit: int, order_type: int):
        """метод для изменения Sl /Take_profit у открытых позиций po его symbol, 
        magic_number, position_ticket, type_order"""
        usd_positions = mt5.positions_get(symbol=symbol)
        if usd_positions is None:
            print("No positions with group=\", error code={}".format(mt5.last_error()))
        elif len(usd_positions) > 0:
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df_new = df[['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'tp', 'magic']]
            # открытые только роботом позиции с его magic- номером
            df_robot = df_new[df_new.magic == magic_number][
                ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'magic']]
            # -- получаем список tickets -- #
            df_robot_tickets = df_robot[df_robot.type == order_type][['ticket', 'type']]
            # tickets_Buy = df_robot_tickets['ticket'].tolist()

            # --> ДЛЯ ПОКУПОК
            df_robot = df_robot[df_robot.type == order_type][['type', 'price_open', 'volume']]
            df_robot['price_lot'] = df_robot['price_open'] * df_robot['volume']
            #        print(df_robot)
            # df_robot_group = df_robot.groupby('type', as_index=False).sum()
            # ---------------------------------------------------------------------------------------- #
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:  # проверка есть ли такая валют пара
                print(symbol, "not found, can not call order_check()")
                mt5.shutdown()
                quit()

            point = mt5.symbol_info(symbol).point  # кол-во пунктов после запятой ( point=0.0001)
            # price = mt5.symbol_info_tick(symbol).ask
            deviation = 20  # отклонение в пунктах
            if order_type == 0:  # если выбран type_order = 0 (Buy), то выполняем
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменнение Stop loss /Take profit
                    "position": position_ticket,  # номер тикета
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "sl": stop_loss,  # Установка стоп-лосса                        ------- > подумать над stop loss
                    "tp": take_profit,  # Установка тейк-профита + небольшой плюс
                    # "tp": price + take_profit * point,  # Установка тейк-профита    ------- > подумать над take profit
                    "magic": magic_number,
                    # Magic number                          --------> тк у sell ниже TP, а тут + take profit
                    #         "deviation": deviation,           # Установка максимальной цены отклонения
                    #         "comment": "робот_Umbrella",      # Установка коментария к сделке
                }

                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                print(f"result.retcode: {result, type(result)}")
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print("2. order_send failed, retcode={}".format(
                        result.retcode))  # вывод кода ошибки если не произведены изменения
                    if result.retcode == 10016:
                        print(f"Неправильные стопы в запросе, fot ticket: {position_ticket}, "
                              f"stop_loss: {stop_loss}, Take_profit: {take_profit}")
                        return result.retcode
                else:
                    print("1. order_send Good(): by {}, position_ticket {} ".format(symbol, position_ticket))
                    print(f"Все TP-уровни у каждого ордера изменены успешно, TP: {take_profit}")
            if order_type == 1:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,  # поставить рыночный ордер изменнение Stop loss /Take profit
                    "position": position_ticket,  # номер тикета
                    "symbol": symbol,  # УКАЗАНИЕ ВАЛЮТ ПАРЫ
                    "sl": stop_loss,  # Установка стоп-лосса                        ------- > подумать над stop loss
                    "tp": take_profit - 0.0002,  # Установка тейк-профита
                    # "tp": price - take_profit * point,  # Установка тейк-профита    ------- > подумать над take profit
                    "magic": magic_number,
                    # Magic number                          --------> тк у sell ниже TP, а тут + take profit
                    #         "deviation": deviation,           # Установка максимальной цены отклонения
                    #         "comment": "робот_Umbrella",      # Установка коментария к сделке
                }
                # отправим торговый запрос
                result = mt5.order_send(request)
                # проверим результат выполнения
                if result.retcode != mt5.TRADE_RETCODE_DONE:

                    print("2. order_send failed, retcode={}".format(
                        result.retcode))  # вывод кода ошибки если не произведены изменения
                    if result.retcode == 10016:
                        print(f"Неправильные стопы в запросе, fot ticket: {position_ticket}, "
                              f"stop_loss: {stop_loss}, Take_profit: {take_profit}")
                        return result.retcode
                else:
                    print("1. order_send Good(): by {}, position_ticket {} ".format(symbol, position_ticket))
                    print(f"Все TP-уровни у каждого ордера изменены успешно, TP: {take_profit}")

    def get_tickets(self, magic_number: int = "all", symbol: str = "all"):
        """ метод для получения тикетов/тикета открытой/ых позиций по указанной валютной паре/либо всем парам
        а также по указанному magic_number """
        if symbol == "all":
            usd_positions = mt5.positions_get()
        elif symbol != "all":
            usd_positions = mt5.positions_get(symbol=symbol)

        if usd_positions in (None, ()):  # проверка не пустой ли массив
            print("No positions with  , error code={}".format(mt5.last_error()))
            usd_positions, ticket = None, None
            return usd_positions, ticket
        elif len(usd_positions) > 0:  # если массив не пустой
            # выведем эти позиции в виде таблицы с помощью pandas.DataFrame
            # print(f"{usd_positions}")
            if symbol == "all" and magic_number == "all":

                df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
                # открытые только роботом позиции с его magic- номером
                df_new = df[
                    ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                     'magic', 'comment']]
                df_Buy_tickets = df_new[df_new.type == 0][['ticket', 'type', 'volume']]  # ticket - volume
                tickets_Buy = df_Buy_tickets['ticket'].tolist()  # list of buy tickets
                tickets_Volume_Buy = df_Buy_tickets['volume'].tolist()  # list volume tickets_Buy 
                logger.info(f"\n{tickets_Buy=}, {tickets_Volume_Buy=}")

                tickets_list = []
                for i, val in enumerate(usd_positions, start=0):
                    # logger.info(f"\n{val=}")
                    tickets_list.append(val[0])
                return tickets_list, symbol

            elif symbol != "all":
                df = pd.DataFrame(list(usd_positions), columns=usd_positions[0]._asdict().keys())
                # открытые только роботом позиции с его magic- номером
                df_new = df[
                    ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl', 'tp', 'profit',
                     'magic', 'comment']]

                if magic_number != "all":
                    df_robot = df_new[df_new.magic == magic_number][
                        ['ticket', 'time', 'symbol', 'type', 'price_open', 'volume', 'price_current', 'sl',
                         'tp', 'profit', 'magic', 'comment']]
                    # -- получаем список tickets -- #
                    df_robot_Buy_tickets = df_robot[df_robot.type == 0][['ticket', 'type']]  # df of Buy
                    tickets_Buy = df_robot_Buy_tickets['ticket'].tolist()  # лист buy тикетов
                    df_robot_Sell_tickets = df_robot[df_robot.type == 1][['ticket', 'type']]  # df of Sell
                    tickets_Sell = df_robot_Sell_tickets['ticket'].tolist()  # лист sell тикетов
                    return tickets_Buy, tickets_Sell
                elif magic_number == "all":
                    # -- получаем список tickets -- #
                    df_new_Buy_tickets = df_new[df_new.type == 0][['ticket', 'type']]  # df of Buy
                    tickets_Buy = df_new_Buy_tickets['ticket'].tolist()  # лист buy тикетов
                    df_new_Sell_tickets = df_new[df_new.type == 1][['ticket', 'type']]  # df of Sell
                    tickets_Sell = df_new_Sell_tickets['ticket'].tolist()  # лист sell тикетов
                    return tickets_Buy, tickets_Sell

    def kovach_open_deal(self, symbol: str, magic_number: int, cascade: 0 | 1, take_profit: float,
                         open_price: float, stop_loss: float, percent_risk: float,
                         limit_order: int = 0, stop_order: int = 0):
        """ ОТКРЫТИЕ ПОЗИЦИ/ИЙ ДЛЯ АЛГОРИТМА SIGNALS ОТ KOVACH """
        # global count_down  # переменная счетчик для уведомлений telegram_bot
        # count_down = 1
        # count_down += 1

        Terminal = Meta_Trader(self.login, self.password, self.server)
        df_robot, BuyCount, SellCount, CountTrades = self.check_robots_orders(magic_number=magic_number,
                                                                              symbol=symbol)
        stop_loss_pips = round(abs((open_price - stop_loss) * 100000))  # проверить размер стопа обязательно!!!
        take_profit_pips = round(abs((open_price - take_profit) * 100000))  # проверить размер стопа обязательно!!!

        # logger.debug(f"{stop_loss_pips=}")
        stop_loss_usd, lot, symbol, pips = self.find_lot_management(symbol=symbol,
                                                                    pips=stop_loss_pips, percent=percent_risk)
        # 1. C H E C K  O P E N E D  S E L L  D E A L S
        if SellCount is not None:
            logger.info(f"Find opened {SellCount=} deals for this {symbol=} and {magic_number=}, trade off")
        elif SellCount in (None, 0):
            # logger.info(f"Not find opened deals, can begin to trade on !")

            price_current = self.get_tick(symbol)
            time.sleep(1)

            # 1.1 --> for sell_limit order type | 
            if price_current < open_price and limit_order == 1:
                Terminal.open_sell_limit_new(price=open_price, magic_number=magic_number, take_profit=take_profit_pips,
                                             symbol=symbol, stop_loss=stop_loss_pips, lot=lot, cascade=cascade)
                time.sleep(1)

            # 1.2 --> for sell_stop order type  | 
            if open_price < price_current and limit_order == 0:
                Terminal.open_sell_stop_new(price=open_price, magic_number=magic_number, take_profit=take_profit_pips,
                                            symbol=symbol, stop_loss=stop_loss_pips, lot=lot, cascade=cascade)
                time.sleep(1)

        # 2 --> C H E C K  O P E N E D  B U Y  D E A L S  (подобно верхней логике)
        if BuyCount is not None:
            logger.info(f"Find opened {BuyCount=} deals for this {symbol=} and {magic_number=}, trade off")
        elif BuyCount in (None, 0):
            # logger.info(f"Not find open buy deals, can begin to trade on !")
            time.sleep(1)
            price_current = Terminal.get_tick(symbol)
            time.sleep(.3)

            # --> 2.1 buy_limit order type     
            if open_price < price_current and limit_order == 1:
                self.open_buy_limit_new(price=open_price, magic_number=magic_number, take_profit=take_profit_pips,
                                        symbol=symbol, stop_loss=stop_loss_pips, lot=lot, cascade=cascade)
                time.sleep(1)

            # -->  buy_stop order type         
            if open_price > price_current and limit_order == 0:
                self.open_buy_stop_new(price=open_price, magic_number=magic_number, take_profit=take_profit_pips,
                                       symbol=symbol, stop_loss=stop_loss_pips, lot=lot, cascade=cascade)
                time.sleep(1)

    def kovach_change_sltp(self, symbol: str, magic_number: int, stop_loss: float = 0):
        """ изменение стоп-лосса у открытых позиций/сделок и take_profit 
        параметры: по его symbol, magic_number, указанной цене stop_loss 
        параметр stop_loss_price - цена по ко-й выставиться stop_loss, а если ее значение равно
        нулю т.е  stop_loss_price = 0 ==> то безлимит выставиться"""
        if stop_loss == 0:
            logger.debug(f"{stop_loss=}, {type(stop_loss)}")
            self.new_trade_action_sltp(symbol=symbol, magic_number=magic_number, stop_loss=stop_loss, order_type=0)
        elif stop_loss != 0:
            logger.debug(f"{symbol=}, {stop_loss}")

    def kovach_close_positions(self, symbol=str, magic_number=int):
        """ режим закрытия всех позиций открытых сделок + отложенных ордеров по данному символу, если есть они """
        self.remove_open_position(symbol=symbol, magic_number=magic_number)
        time.sleep(2)

        result = self.remove_pending_orders_new(symbol=symbol, magic_number=magic_number)
        # self.remove_pending_orders(symbol=symbol, magic_number=magic_number, order_ticket=ticket)
        # logger.info(f"\n{result=}, {type(result)=}")
        return result


def find_near_levels(name_list: list, price: float):
    """ищем двух ближайщих соседей(ближайщих значений)
                  name_list - имя списка, содержащего массив значений, price (float)- цена возле которой ищем соседей"""
    # new_dict = name_dict.values()          # получаем список всех значений словаря
    # b = list(new_dict)                      # преобразуем его в список list
    b = name_list
    len_list = len(b)  # длина списка
    #  print(f"len b : {len_list}")
    levels_find = b[0:len_list]  # новый список только из значений levels
    levels_find.sort()  # сортируем наш список по возрастанию
    print(f"new_list : \n{levels_find}")

    if len(levels_find) == 2:
        if levels_find[0] < price < levels_find[1]:
            print(f"подходит условия !!! price:{price} , {levels_find[0], levels_find[1]} ")
            buy_limit = levels_find[0]
            sell_limit = levels_find[1]
            return buy_limit, sell_limit
        else:
            buy_limit, sell_limit = None, None
            return buy_limit, sell_limit

    elif len(levels_find) >= 3:
        new_levels = np.array(levels_find)  # преврашаем наш список list в массив numpy array
        # print(f"type levels: {type(levels_find)} and type new_levels : {type(new_levels)}")
        # -------------------------
        price_tick = round(price, 5)  # round текушая цена tick
        index = np.searchsorted(new_levels, price)  # Так я нашел индекс

        print(f"index : {index, type(index)}")

        buy_limit, sell_limit = new_levels[index - 1], new_levels[index]
        # print(f"almax : {buy_limit, sell_limit}")
        # Получил два нужных мне числа из массива/списка чисел
        print(f"текущая цена : {price_tick}, buy_limit: {buy_limit}, sell_limit: {sell_limit}")

        return buy_limit, sell_limit


def find_protorgovok(name_df, delta: float):
    """"поиск сильных проторговок, name_df - имя dataframe, в ко-м будем искать проторговки, delta - параметр погрешность
    в пунктах для поиска соседей рядом"""
    df = name_df[["time", 'open', 'high', 'low', 'close']]

    df_open = df[['open']].round(5)
    df_close = df[['close']].round(5)
    df_low = df[['low']].round(5)
    df_high = df[['high']].round(5)

    # delta = 0.0005  # погрешность в пунктах

    a_massiv = np.array([])  # создаем пустой массив
    # near_values = []
    counts_values = []  # список где будут хранится все значения ока-ся рядом(соседи)

    # цикл по столбцу "df_close" from df_list сверху/вниз
    for i in trange(len(df_close)):
        # value = df.iloc[i][df.columns[j]]            # get value_df; i - номер строки, j - номер столбца
        value = df_close.iloc[i][df_close.columns[0]]  # get value from df_close
        #  print(i, value)
        a_massiv = np.append(a_massiv, value)  # добавляем каждое новое value from df_column в массив array
        minElement = np.amin(a_massiv)  # находим min- элемент массива [a_massiv] с добавленными элементами
        #  print(f"a_massiv: {a_massiv}")
        #  print(f"minElement: {minElement}")

        # ---- start my_function --
        distance_high = minElement + delta  # значение рядом (сверху) со минимльным значением
        distance_low = minElement - delta  # значение рядом (снизу) со минимльным значением

        # df_list = [df_close, df_low, df_high]        # список столбцов нашего df для iterate for columns from df_list
        #  near_values = []                            # create empty list

        if distance_low < value < distance_high:  # если значение value находится рядом с нашим minimum of a_massiv
            #  print(f"номер строки i: {i}, from: {df_close.columns[0]}")  # df_item.columns[0] - str(имя колонки)
            b = value
            #  print(f"найден сосед рядом b: {b}, min= {minElement}")
            #    near_values.append(b)
            counts_values.append(minElement)  # добавляем нужные значения в список counts_values
        time.sleep(0.1)

    # print(f"near_values: {len(near_values)}")
    # print(f"counts_values: {counts_values}, len counts_values: {len(counts_values)}")
    b_list = []  # создаем пустой массив для цены
    d_list = []  # создаем пустой массив для кол-ва появлений
    # поиск максимально встречющегося элемента в списке counts_values - содержащем все значения которые были рядом
    for i in range(len(df_close)):  # проверка счетчика появлений значения до 45 - раз
        new_list = [e for e in set(counts_values) if counts_values.count(e) == i]
        if new_list:
            if i > 3 and len(new_list) == 1:  # выводим только если появления более > 3 раз
                b_list.append(i)
                d_list.append(new_list[0])
                print(f"price : {new_list[0]}, кол-во появлений: {i}")  # [1, 3]
    dict_df = dict(zip(d_list, b_list))
    # print(f"dict : {dict_df}")
    df = pd.DataFrame(dict_df.items(), columns=['Цена', 'кол-во_появлений'])
    print(f"df : \n{df}")
    return df


def analiz_dataframe(name_df, len_df: int, timeframe: str, symbol: str = None):
    """
    Метод для анализа заданного dataframe(временного ряда) для заданного финан.инструмента (symbol= aka "EURUSD"),
    выбранного time_frame, len_df - задаем длину dataframe. Итогом будет отчет о текушей ситуации (определении тренда/флэта) 
    на основании статистического анализа dataframe, инфо о волатильности инструмента 
    """
    df = name_df
    if df.empty:
        print("dataframe не сушествует/либо пустой !!!")
        return

    df['SMA_22'] = df.close.rolling(22).mean()
    df["up"] = np.where(df.low > df["SMA_22"], True, False)
    df["high_new"] = ""

    for i in range(1, len(df)):
        if df.high[i] > df.high[i - 1]:
            # print(f"найдены подходящие условия: {df.high[i], df.high[i-1],  i, df.time[i]}")
            df.high_new[i] = "True"
        if df.high[i] < df.high[i - 1]:
            df.high_new[i] = "False"

    df_temp = df.iloc[-20:]  # фильтр последние 20 элементов
    df = df_temp

    print(df)

    max_val = df['up'].value_counts()  # подсчет кол-ва свечей выше SMA
    max_high_new = df['high_new'].value_counts()  # подсчет кол-ва свеяей выше SMA

    # 1. Определение тренда по кол-ву свечей над/под SMA
    if len(max_val) == 2:
        up_sma = max_val[1]  # получим значения count
        down_sma = max_val[0]
        if up_sma > down_sma:
            print("Тренд восходящий так как: свечей выше SMA больше, чем ко-х ниже")
            print(f"свечей выше SMA больше, чем ко-х ниже на: {up_sma / down_sma * 100} % ")
            print(f"кол-во свечей выше SMA : {up_sma} из всего свечей = {len(df)}")
            print(f"кол-во свечей ниже SMA : {down_sma} из всего свечей = {len(df)}")
        elif up_sma < down_sma:
            print("Тренд нисходящий так как: свечей ниже SMA больше, чем ко-х выше Sma")
            print(f"свечей ниже SMA больше, чем ко-х выше на: {round(down_sma / up_sma * 100, 1)} % ")
            print(f"кол-во свечей ниже SMA : {down_sma} из всего свечей = {len(df)}")

    z = [1, 11, 5, 7]

    # ------ В И З У А Л И З А Ц И Я ------------------
    plt.figure(figsize=(14, 6))
    plt.scatter(x=3, y=1.19, marker="^", color="red")  # рисование маркером на графике
    plt.scatter(x=5, y=1.18, marker="^", color="green")  # рисование маркром на графике

    plt.plot(df[["low", "high", "SMA_22"]])
    plt.grid()  # сетка
    plt.xlabel('длина dataframe / кол-во записей', fontsize=14)  # добавляем подпись к оси абцисс "ось х"
    plt.ylabel('ценовой диапазон', fontsize=14)  # добавляем подпись к оси ординат "ось y"
    # plt.scatter(df.index[df.SMA_22], df[df.SMA_22].low, marker ="^", color="g")
    plt.legend(["low", "high", "SMA_22"])
    plt.title(r'Ценовой график eurusd', fontsize=16, y=1.05)  # добавляем заголовок к графику

    # experiment
    # plt.text(1.18, 3, 'Минимум',fontsize=12); # добавляем подпись к графику в точке (-2.5, 10)
    plt.annotate("Минимум", xy=(0., 1.18), xytext=(0., 1.17), fontsize=12,
                 arrowprops=dict(arrowstyle='->', color='red'))

    plt.subplot(z)
    # plt.plot(x, y1, '-')
    # plt.show()
    # plt.savefig('files/delete.jpeg', bbox_inches='tight')


def get_history_price(symbol: str, count_bars: int, filename_path: str, timeframe: str, day: int, month: int, year:int):
    """получаем исторические данные временного ряда для выбранного валютной пары
    и кол-во баров для выбранного timeframe"""
    from datetime import datetime
    import MetaTrader5 as mt5
    import pytz
    pd.set_option('display.max_columns', 500)  # сколько столбцов показываем
    pd.set_option('display.width', 1500)  # макс. ширина таблицы для показа
    # импортируем модуль pytz для работы с таймзоной

    # установим подключение к терминалу MetaTrader 5
    if not mt5.initialize():
        logger.info(f"initialize() failed, error code = {mt5.last_error()}")
        quit()

    # установим таймзону в UTC
    timezone = pytz.timezone("Etc/UTC")
    # создадим объект datetime в таймзоне UTC, чтобы не применялось смещение локальной таймзоны
    utc_from = datetime(year, month, day, tzinfo=timezone)
    # logger.info(f"{utc_from=}, {type(utc_from)}")

    # выбор timeframe
    if timeframe in ("D1", 'd1'):
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_D1, utc_from, count_bars)
    elif timeframe in ("H4", "h4"):
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H4, utc_from, count_bars)
    elif timeframe in ("H1", "h1"):
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, utc_from, count_bars)

    # получим 10 баров с EURUSD H4 начиная с 01.10.2020 в таймзоне UTC
    # rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H4, utc_from, count_bars)
    # завершим подключение к терминалу MetaTrader 5
    mt5.shutdown()
    # создадим из полученных данных DataFrame
    rates_frame = pd.DataFrame(rates)
    # сконвертируем время в виде секунд в формат datetime
    rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
    rates_frame.to_csv(filename_path + "//dataframes//rates_frame_eurusd_" + timeframe.upper() + ".csv", sep='\t', encoding='utf-8')
    # logger.info(f"\nДатафрейм с данными по {symbol}: \n {rates_frame}")
    if rates_frame.empty:
        return None
    else:
        return rates_frame


def check_expire_date(url: str, account_numer: str):
    """Проверка даты действия робота для заданного торгового счета
    и возврат соответствующей даты для найденного счета"""
    # adress = "http://127.0.0.1:8000/test/1"
    # url = "http://127.0.0.1:8000/test/1"

    response = requests.get(url, timeout=60)
    response.encoding = 'utf-8'
    if not response.status_code == 200:
        logger.info(f"Not connecting to this url: {url}")
        logger.info(f"response: {type(response)}, response= {response}")
    elif response.status_code == 200:  # if connection its ok
        # print(f"response: {type(response)}, response= {response}")
        # print(f"Connected good for url: {url}")
        result = response.json()
        res = result.get(account_numer)
        if res is None:
            logger.error(f"account number not find: {account_numer}, because will exit program")
            sys.exit()
            time.sleep(3)
            return res
        elif res:
            data_expire = res["expire_data"]
            # print(res, type(res), "\n")
            # data = datetime.fromisoformat(data_expire)
            return data_expire


def get_data_from_url(url: str):
    """ Получение данных/сигналов в виде json from http_url """
    # adress = "http://127.0.0.1:8000/test/1"
    # url = "http://127.0.0.1:8000/test/1"

    response = requests.get(url, timeout=60)
    response.encoding = 'utf-8'
    if not response.status_code == 200:
        logger.warning(f"\nNot connecting to this url: {url}")
        logger.warning(f"\nresponse: {type(response)}, response= {response}")
    elif response.status_code == 200:  # if connection its ok
        # print(f"Connected good for url: {url}")
        full_result = response.json()
        # print(f"{full_result=}")
        last_data = full_result.get('last_update')  # передача параметра в json
        if last_data is None:
            logger.warning(f"\nnot find data from url = {url}")
            return last_data
        elif last_data:
            # logger.info(f"{last_data=}")
            # data_expire = res["'last_update'"]
            # print(res, type(res), "\n")
            return full_result, last_data


def read_json_file(filename: str):
    """
    функция для чтения файлов json и возврата соотвествующего json в виде словаря
    """
    if not os.path.isfile(filename):
        logger.error(f"файл не сушествует по пути: {filename}")
        return None
    else:
        with open(filename) as f:
            base_dict = json.load(f)
            # logger.info(f"{base_dict=}")
            return base_dict

# x = read_json_file("files/kovach_signals.json")
# print(f"\n{x=}")


# data = check_expire_date(url="http://80.85.158.162/test/1", account_numer="50988330")
# print(f"expire data: {data}, {type(data)}")
# full_result, result_for_data = get_data_from_url(url="http://80.85.158.162/kovach/kovach_data")
# print(f"{result_for_data=}")

# ----------------------------------------------

