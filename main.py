import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(funcName)s] %(message)s")
logging.getLogger('aiohttp').setLevel(logging.WARNING)
import os
import json
import asyncio
import urllib.parse
import aiohttp
import asyncio_redis
from dataclasses import dataclass
from aiohttp import web

# Get configs from env
DISCORD_CLIENT_ID = int(os.getenv('WUBBY_EVENTS_OAUTH_DISCORD_CLIENT_ID'))
DISCORD_CLIENT_SECRET = os.getenv('WUBBY_EVENTS_OAUTH_DISCORD_SECRET')
REDIS_HOST = os.getenv('WUBBY_EVENTS_OAUTH_REDIS_HOST')
REDIS_PASSWORD = os.getenv('WUBBY_EVENTS_OAUTH_REDIS_PASSWORD')

# Build redirect url
DISCORD_CALLBACK_URL = 'https://events.wubby.tv/oauth/callback'
DISCORD_REDIRECT_URL = 'https://discord.com/api/oauth2/authorize?client_id={}&redirect_uri={}&response_type=code&scope=identify%20connections'.format(DISCORD_CLIENT_ID, urllib.parse.quote(DISCORD_CALLBACK_URL))

# Result page suffixes
RESULT_BASE_URL = 'https://events.wubby.tv/result'
RESULT_PAGE_SUCCESS = '/success.html'
RESULT_PAGE_INTERNAL_ERROR = '/internal_error.html'
RESULT_PAGE_NO_TWITCH = '/twitch_not_linked.html'
RESULT_PAGE_JOINING_DISABLED = '/joining_disabled.html'

redis = None

@dataclass
class GenericAccount:
    id: int
    username: str

async def log_request(resp):
    logFunction = logging.debug
    if not resp.ok:
        logFunction = logging.warning
    logFunction('Made {} request to url {}, got response code {} with text {}'.format(resp.method, resp.url, resp.status, await resp.text()))

async def fetch_discord_token(code):
    url = 'https://discord.com/api/v8/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_CALLBACK_URL
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as resp:
            await log_request(resp)
            if not resp.ok:
                return None
            responseData = await resp.json()
            return responseData['access_token']

async def fetch_discord_account(token):
    if not token:
        return None
    url = 'https://discord.com/api/v8/users/@me'
    headers = {'Authorization': 'Bearer ' + token}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            await log_request(resp)
            if not resp.ok:
                return None
            responseData = await resp.json()
            id = int(responseData.get('id', '0'))
            username = responseData.get('username', 'UNKNOWN_USER') + '#' + responseData.get('discriminator', '0000')
            return GenericAccount(id, username)

async def fetch_twitch_account(token):
    if not token:
        return None
    url = 'https://discord.com/api/v8/users/@me/connections'
    headers = {'Authorization': 'Bearer ' + token}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            await log_request(resp)
            if not resp.ok:
                return None
            responseData = await resp.json()
            for connection in responseData:
                if connection.get('type') == 'twitch':
                    id = int(connection.get('id', '0'))
                    username = connection.get('name', 'UNKNOWN_USER')
                    return GenericAccount(id, username)
            return None

async def handle_callback(request):
    logging.info('New request to /callback from IP {}'.format(request.headers.get('CF-Connecting-IP')))

    if not redis or not redis.connections_connected:
        logging.error('No active redis connections!')
        return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_INTERNAL_ERROR)

    code = request.query.get('code')
    if not code:
        logging.warning('No `code` query parameter!')
        return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_INTERNAL_ERROR)
    token = await fetch_discord_token(code)
    if not token:
        logging.error('Unable to fetch token with code!')
        return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_INTERNAL_ERROR)
    discordAccount = await fetch_discord_account(token)
    if not discordAccount:
        logging.error('Unable to fetch discord account with token!')
        return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_INTERNAL_ERROR)
    twitchAccount = await fetch_twitch_account(token)
    if not twitchAccount:
        logging.info('No Twitch accounts found.')
        return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_NO_TWITCH)

    keyName = 'wubby_events_' + str(discordAccount.id)
    key = await redis.get(keyName)
    if key:
        keyData = json.loads(key)
        logging.info('Discord account already registered. Old/New Discord: {}/{} | Old/New Twitch: {}/{}'.format(keyData['discordUsername'], discordAccount.username, keyData['twitchUsername'], twitchAccount.username))
    else:
        logging.info('Discord account {} registered as Twitch user {} successfully.'.format(discordAccount.username, twitchAccount.username))

    newKeyData = {'discordUsername': discordAccount.username, 'twitchId': twitchAccount.id, 'twitchUsername': twitchAccount.username}
    await redis.set(keyName, json.dumps(newKeyData))

    return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_SUCCESS)

async def handle_redirect(request):
    logging.info('New request to /redirect from IP {}'.format(request.headers.get('CF-Connecting-IP')))
    #logging.debug('Returning joining disabled result...')
    # return web.HTTPFound(RESULT_BASE_URL + RESULT_PAGE_JOINING_DISABLED)
    return web.HTTPFound(DISCORD_REDIRECT_URL)

async def on_startup(app):
    global redis
    redis = await asyncio_redis.Pool.create(host=REDIS_HOST, port=6379, password=REDIS_PASSWORD, poolsize=5)
    logging.info('Finished starting.')

async def on_shutdown(app):
    global redis
    if redis:
        redis.close()
        redis = None
    logging.info('Finished shutting down.')

app = web.Application()
app.add_routes([web.get('/redirect', handle_redirect), web.get('/callback', handle_callback)])
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    web.run_app(app, port=6900)
