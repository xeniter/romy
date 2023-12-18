
import sys
sys.path.append('./romy/')

import logging
import asyncio
import romy

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)

host="192.168.1.181"
password="12345678"

async def main():
    myROMY = await romy.create_romy(host, password)

    if not myROMY.is_initialized:
        print("Could not connect to ROMY. wrong IP provided?")
        exit(1)

    if not myROMY.is_unlocked:
        print("Local http interface is still locked, wrong password provided?")
        exit(2)


    print("device infos:")
    print()

    print(f"name: {myROMY.name}")
    print(f"unique_id: {myROMY.unique_id}")
    print(f"model: {myROMY.model}")
    print(f"firmware: {myROMY.firmware}")

    print()
    await myROMY.async_update()
    print("async_update:")
    print()

    print(f"battery_level: {myROMY.battery_level}")
    print(f"status: {myROMY.status}")

    print(f"robots product name: {myROMY.name}")    
    new_name="NiosHD"
    print(f"robots name given by the user: {myROMY.user_name}")
    print(f"setting robots user_name to: {new_name}")
    await myROMY.set_user_name(new_name)
    print(f"robots name given by the user: {myROMY.user_name}")

    print(f"port: {myROMY.port}")



loop = asyncio.get_event_loop()
coroutine = main()
loop.run_until_complete(coroutine)

