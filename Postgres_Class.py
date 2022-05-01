# =============== Личный класс для работы с БД PostgreSQL ========================

import os
import json
import psycopg2
from psycopg2 import Error
from loguru import logger
from datetime import datetime
import time
from notifiers import get_notifier
# import asyncio


def info_database(database: str, user: str, password: str, host: str, port: str):
    try:
        # Подключение к существующей базе данных
        connection = psycopg2.connect(user=user,
                                      # пароль, который указали при установке PostgreSQL
                                      password=password,
                                      host=host,
                                      port=port,
                                      database=database)

        # Курсор для выполнения операций с базой данных
        cursor = connection.cursor()
        # Распечатать сведения о PostgreSQL
        print("Информация о сервере PostgreSQL")
        print(connection.get_dsn_parameters(), "\n")

        # запуск цикла импорта каждого файла
        # if len(list_csv_files) > 0:
        #     for i, value in enumerate(list_csv_files):
        #         # Выполнение SQL-запроса
        #         with open(base_path + value, 'r', encoding="utf8") as file:
        #             next(file)  # Skip the header row.
        #             cursor.copy_from(file, 'table_1', sep='|')

        #         connection.commit()
        #         time.sleep(2)
        # else:
        #     logger.error(f"len of list_csv_files empty or other !!!")

        # cursor.execute(query)

        # Получить результат
        # record = cursor.fetchone()
        # all = cursor.fetchall()
        # connection.commit()
        # print("Вы подключены к - ", record, "\n")

    except (Exception, Error) as error:
        logger.error(f"Ошибка при работе с PostgreSQL", {error})
        return False
    finally:
        if connection:
            cursor.close()
            connection.close()
            logger.info(f"Соединение с PostgreSQL закрыто")
            return True


def save_zayvka_to_db(database: str, user: str, password: str, host: str, port: str, dict_name: dict):
    """
    Сохранение сообщений/заявок от пользователей сайта Umbrella в таблицы БД
    """
    # dict_name = {}
    try:
        # Подключение к существующей базе данных
        connection = psycopg2.connect(user=user,
                                      # пароль, который указали при установке PostgreSQL
                                      password=password,
                                      host=host,
                                      port=port,
                                      database=database)

        # Курсор для выполнения операций с базой данных
        cursor = connection.cursor()
        # SQL-запрос для создания новой таблицы
        insert_table_query = f""" insert into zayavki (username, email, mentor, message_user, timeupdate)
                                values ('{dict_name['name']}', '{dict_name['email']}', '{dict_name['mentor']}', 
                                '{dict_name['message_user']}', '{dict_name['timeupdate']}') """

        # Выполнение команды: это создает новую таблицу
        cursor.execute(insert_table_query)
        connection.commit()
        print("Данные сохранены успешно в PostgreSQL")

    except (Exception, Error) as error:
        logger.error(f"Ошибка при работе с PostgreSQL", {error})
    finally:
        if connection:
            cursor.close()
            connection.close()
            print("Соединение с PostgreSQL закрыто")


# ========== Примеры функций =====================================
dict_a = {"name": "regina", 'email': 'hinomura@gmail.com', 'mentor': 'facebook',
          'message_user': "buy", 'timeupdate': '2099-01-08 04:05:09'}

# save_zayvka_to_db(database=database, user=user, password=password, host=host, port=port, dict_name=dict_a)
