import asyncio

async def func1():
    print("func1")

async def loop1():
    while True:
        await func1()
        await asyncio.sleep(0)


async def func2():
    print("func2")

async def loop2():
    while True:
        await func2()
        await asyncio.sleep(0)

async def main():
    task1 = asyncio.create_task(loop1())
    task2 = asyncio.create_task(loop2())
    await task1
    await task2

if __name__ == "__main__":
    asyncio.run(main())
