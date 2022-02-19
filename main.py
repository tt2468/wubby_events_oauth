import logging
logging.basicConfig(level=logging.DEBUG)
import os
from dataclasses import dataclass
import asyncio
import aiohttp
from aiohttp import web

DISCORD_CLIENT_ID = os.getenv('WUBBY_EVENTS_OAUTH_DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('WUBBY_EVENTS_OAUTH_DISCORD_SECRET')
DISCORD_REDIRECT_URI = os.getenv('WUBBY_EVENTS_OAUTH_DISCORD_REDIRECT_URI') # 'https://events.wubby.tv/oauth'

# https://discord.com/api/oauth2/authorize?client_id=489538588120449039&redirect_uri=https%3A%2F%2Fevents.wubby.tv%2Foauth&response_type=code&scope=identify%20connections

@dataclass
class GenericAccount:
    id: int
    username: str

async def log_request(resp):
    print('Made {} request to url {}, got response code {} with text {}'.format(resp.method, resp.url, resp.status, await resp.text()))

async def fetch_discord_token(code):
    url = 'https://discord.com/api/v8/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
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

async def handle_oauth(request):
    code = request.query.get('code')
    if not code:
        return web.Response(text='No code!')
    token = await fetch_discord_token(code)
    if not token:
        return web.Response(text='Failed to get token!')
    discordAccount = await fetch_discord_account(token)
    if not discordAccount:
        return web.Response(text='Failed to get Discord account!')
    twitchAccount = await fetch_twitch_account(token)
    if not twitchAccount:
        return web.Response(text='Failed to get Twitch account!')

    text = 'Your Discord account is {} and your twitch account is {}'.format(discordAccount.username, twitchAccount.username)
    return web.Response(text=text)

app = web.Application()
app.add_routes([web.get('/', handle_oauth)])

if __name__ == '__main__':
    web.run_app(app, port=6900)
