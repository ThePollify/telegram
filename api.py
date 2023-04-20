from asyncio import CancelledError, Task, create_task
from typing import Callable, Coroutine

import aiohttp
from websockets.client import connect
from yarl import URL

import models
from settings import settings

client = aiohttp.ClientSession()


class HTTPException(Exception):
    pass


async def listen_questions(
    poll_id: int,
    on_message: Callable[[str | bytes], Coroutine[None, None, None]],
) -> Task[None]:
    url = str(
        (URL(settings.websocket_url) / "answers/listen/questions").with_query(
            {"poll_id": poll_id}
        )
    )

    async def listener() -> None:
        async with connect(url) as websocket:
            try:
                while True:
                    data = await websocket.recv()
                    await on_message(data)
            except CancelledError:
                pass

    return create_task(listener())


async def answers_add_value(
    poll_id: int,
    value: models.answers.Value,
) -> models.answers.Answer:
    url = str(
        (URL(settings.api_url) / "answers/add/value").with_query({"poll_id": poll_id})
    )
    async with client.post(url, json=value.serializable()) as request:
        if request.status != 200:
            raise HTTPException(request.status, await request.text())
        return models.answers.Answer.parse_raw(await request.text())
