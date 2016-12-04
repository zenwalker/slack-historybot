from sqlalchemy.dialects.postgresql import insert
from aiopg.sa import create_engine
from datetime import datetime
import sqlalchemy as sa
import logging
import asyncio
import uvloop

from .models import channels_table, users_table, messages_table
from .utils import get_config, truncate
from .slackbot import SlackBot

config = get_config()
logger = logging.getLogger()
bot = SlackBot(config['slack']['token'])
ts = lambda x: datetime.fromtimestamp(float(x))


@bot.handler('rtm_start')
async def on_rtm_strat(rtm):
    insert_channel = sa.text("""
        INSERT INTO channels (id, name) VALUES (:id, :name)
        ON CONFLICT (id) DO UPDATE SET name = :name """)

    insert_user = sa.text("""
        INSERT INTO users (id, name, real_name) VALUES (:id, :name, :real_name)
        ON CONFLICT (id) DO UPDATE SET name = :name, real_name = :real_name """)

    logger.info('Loading channels')
    for channel in rtm['channels']:
        await bot.db.execute(insert_channel,
            id=channel['id'], name=channel['name'])

    logger.info('Loading users')
    for user in rtm['users']:
        await bot.db.execute(insert_user,
            id=user['id'], name=user['name'],
            real_name=user.get('real_name'))

    logger.info('Bot started')


@bot.handler('message', subtype=None)
async def on_message_sent(event):
    channel_exists = await bot.db.execute(channels_table.select(
        sa.exists([1]).where(channels_table.c.id == event['channel'])))

    if not await channel_exists.scalar():
        return

    await bot.db.execute(insert(messages_table).values(
        channel_id=event['channel'], user_id=event['user'],
        text=event['text'], timestamp=ts(event['ts'])
        ).on_conflict_do_nothing())

    logger.info('New message: ' + truncate(event['text'], 50))


@bot.handler('message', subtype='message_changed')
async def on_message_edited(event):
    query = sa.text("""
        UPDATE messages SET text = :text
        WHERE channel_id = :channel_id AND user_id = :user_id
        AND timestamp = :timestamp """)

    prev_msg = event['previous_message']
    msg = event['message']

    await bot.db.execute(query,
        text=msg['text'], channel_id=event['channel'],
        user_id=prev_msg['user'], timestamp=ts(prev_msg['ts']))

    logger.info('Message edited: ' + truncate(msg['text'], 50))


@bot.handler('channel_joined')
async def on_channel_joined(event):
    channel = event['channel']
    logger.info('Join into channel ' + channel['name'])
    insert_stmt = insert(messages_table).on_conflict_do_nothing()
    payload = {'channel': channel['id'], 'count': 1000, 'inclusive': 0}

    await bot.send_message(channel['id'], (
        'Здорова. Отныне я записываю всю историю в этом канале '
        'и сохраняю в надёжном месте, чтобы не проебалась.'))

    while True:
        history = await bot.api_call('channels.history', payload)
        payload['latest'] = history['messages'][-1]['ts']

        for message in history['messages']:
            if message['type'] == 'message' and message.get('subtype') is None:
                await bot.db.execute(insert_stmt.values(
                    channel_id=channel['id'], user_id=message['user'],
                    text=message['text'], timestamp=ts(message['ts'])))

        if not history['has_more']:
            break


@bot.handler('channel_rename')
async def on_channel_rename(event):
    channel = event['channel']
    await bot.db.execute(channels_table.update()
        .where(id=channel['id']).values(name=channel['name']))

    logger.info('Rename channel ' + channel['name'])


@bot.handler('team_join')
async def on_user_join(event):
    user = event['user']

    insert_user = users_table.insert().values(
        id=user['id'], name=user['name'],
        real_name=user['real_name'])

    await bot.db.execute(insert_user)
    logger.info('New user joined: ' + user['name'])


@bot.handler('user_change')
async def on_user_change(event):
    user = event['user']
    await bot.db.execute(users_table.update().where(id=user['id'])
        .values(name=user['name'], real_name=user['real_name']))

    logger.info('User change ' + user['name'])


async def main():
    engine = await create_engine(**config['database'])

    async with engine.acquire() as connection:
        bot.db = connection
        await bot.start_bot()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        if loop.is_running():
            loop.close()
