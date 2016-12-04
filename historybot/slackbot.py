from collections import defaultdict
import aiohttp
import websockets
import json


class SlackBot:
    def __init__(self, token):
        self.handlers = defaultdict(list)
        self.token = token
        self.ws = None

        self.handler('goodbye', func=self.on_goodbye)

    def handler(self, event_type, func=None, **filters):
        def wrapper(func):
            handler = EventHandler(func, filters)
            self.handlers[event_type].append(handler)
            return func
        return wrapper(func) if func else wrapper

    async def api_call(self, method, data={}):
        with aiohttp.ClientSession() as session:
            form = aiohttp.FormData(data)
            form.add_field('token', self.token)

            method_url = 'https://slack.com/api/{0}'.format(method)
            async with session.post(method_url, data=form) as response:
                assert response.status == 200
                data = await response.json()
                assert data['ok'], data['error']
                return data

    async def send_message(self, channel, text, **kwargs):
        params = {'channel': channel, 'text': text, 'as_user': True}
        params.update(kwargs)

        return await self.api_call('chat.postMessage', params)

    async def connect(self):
        rtm = await self.api_call('rtm.start')
        self.ws = await websockets.connect(rtm['url'])
        await self.invoke_event('rtm_start', rtm)

    async def start_bot(self):
        await self.connect()

        while self.ws:
            msg = await self.ws.recv()
            event = json.loads(msg)
            await self.invoke_event(event['type'], event)

    async def invoke_event(self, event_type, event_data):
        for handler in self.handlers[event_type]:
            if handler.match(event_data):
                await handler.call(event_data)

    async def on_goodbye(self, event):
        self.connect()


class EventHandler:
    def __init__(self, fn, filters):
        self.filters = filters
        self.fn = fn

    def match(self, event):
        return all(event.get(k) == v for k, v in self.filters.items())

    async def call(self, event):
        return await self.fn(event)
