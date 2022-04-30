import asyncio
import schedule
import datetime
from datetime import datetime
from loguru import logger
import os


async def async_func():
    print('Begin 1 ...')
    # os.system('cls')
    await asyncio.sleep(1)
    print('... End 1!')


async def async_func_2():
    print('Begin 2 ...')
    await asyncio.sleep(1)
    print('... End 2!')


async def main():
    while True:
        task = asyncio.create_task(async_func())
        logger.info(f"{datetime.now()}")
        await asyncio.sleep(60)
        print(datetime.now())
        await task

        date = datetime.today()
        hour_time = date.strftime('%H')
        if hour_time == "18":
            task_2 = asyncio.create_task(async_func_2())
            await task_2


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except:
        pass
