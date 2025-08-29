import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Default game (Vixen Hood)
current_place_id = 125760703264498
current_universe_id = None
tracking_channel = None
update_interval = 65  # default seconds
tracking_task = None


async def fetch_universe_id(place_id):
    url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("universeId")
    return None


async def fetch_game_data(universe_id):
    async with aiohttp.ClientSession() as session:
        url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if "data" in data and data["data"]:
                    active_players = data["data"][0].get("playing", 0)
                    visits = data["data"][0].get("visits", 0)
                    milestone = visits + 100
                    return active_players, visits, milestone
    return None


async def tracking_loop():
    global tracking_channel, current_universe_id, update_interval
    while True:
        if tracking_channel and current_universe_id:
            data = await fetch_game_data(current_universe_id)
            if data:
                active_players, visits, milestone = data
                msg = (
                    "--------------------------------------------------\n"
                    f"👤🎮 Active players: **{active_players}**\n"
                    "--------------------------------------------------\n"
                    f"👥 Visits: **{visits}**\n"
                    f"🎯 Next milestone: **{visits}/{milestone}**\n"
                    "--------------------------------------------------"
                )
                await tracking_channel.send(msg)
            else:
                await tracking_channel.send("⚠️ Failed to fetch game data.")
        await asyncio.sleep(update_interval)


@bot.event
async def on_ready():
    global current_universe_id
    print(f"✅ Logged in as {bot.user}")
    current_universe_id = await fetch_universe_id(current_place_id)
    if current_universe_id is None:
        print("❌ Failed to fetch universeId for default game.")


@bot.command()
async def start(ctx):
    """Start sending game updates"""
    global tracking_channel, tracking_task
    tracking_channel = ctx.channel
    if tracking_task is None or tracking_task.done():
        tracking_task = asyncio.create_task(tracking_loop())
    await ctx.send("✅ Started tracking game data in this channel.")


@bot.command()
async def stop(ctx):
    """Stop sending game updates"""
    global tracking_task
    if tracking_task:
        tracking_task.cancel()
        tracking_task = None
    await ctx.send("🛑 Stopped tracking game data.")


@bot.command()
async def interval(ctx, seconds: int):
    """Change interval between messages"""
    global update_interval
    if seconds < 30:
        await ctx.send("⚠️ Interval must be at least 30 seconds.")
        return
    update_interval = seconds
    await ctx.send(f"⏱ Interval updated to {update_interval} seconds.")


@bot.command()
async def setgame(ctx, place_id: int):
    """Change the tracked game"""
    global current_place_id, current_universe_id
    universe_id = await fetch_universe_id(place_id)
    if universe_id:
        current_place_id = place_id
        current_universe_id = universe_id
        await ctx.send(f"🎮 Game updated! Now tracking placeId `{place_id}`.")
    else:
        await ctx.send("❌ Failed to fetch universeId for that place.")


# Flask keepalive (for UptimeRobot/Render web service)
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
