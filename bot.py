import os
import discord
import asyncio
import aiohttp
from discord.ext import commands
from flask import Flask
from threading import Thread

# ==== Flask keep-alive ====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==== Discord Bot ====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Default game (hardcoded)
current_game_id = "125760703264498"  # Vixen Hood
tracking_enabled = False
tracking_task = None
interval_seconds = 65
channel_id = None  # set when !start is used

# ==== Roblox API Helpers ====
async def fetch_game_data():
    global current_game_id
    url = f"https://games.roblox.com/v1/games?universeIds={current_game_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if "data" not in data or not data["data"]:
                return None
            game = data["data"][0]
            return {
                "active": game["playing"],
                "visits": game["visits"],
                "max": game["maxPlayers"]
            }

# ==== Background Task ====
async def track_game():
    global tracking_enabled, interval_seconds, channel_id
    await bot.wait_until_ready()
    while True:
        if tracking_enabled and channel_id:
            try:
                channel = bot.get_channel(channel_id)
                if channel:
                    data = await fetch_game_data()
                    if data:
                        milestone = ((data["visits"] // 1000) + 1) * 1000
                        msg = (
                            "--------------------------------------------------\n"
                            f"👤🎮 Active players: **{data['active']}**\n"
                            "--------------------------------------------------\n"
                            f"👥 Visits: **{data['visits']}**\n"
                            f"🎯 Next milestone: **{data['visits']}/{milestone}**\n"
                            "--------------------------------------------------"
                        )
                        await channel.send(msg)
                    else:
                        await channel.send("⚠️ Failed to fetch game data.")
            except Exception as e:
                print(f"[ERROR] Game tracking loop: {e}")
        await asyncio.sleep(interval_seconds)

# ==== Commands ====
@bot.command()
async def start(ctx):
    global tracking_enabled, channel_id
    tracking_enabled = True
    channel_id = ctx.channel.id
    await ctx.send("✅ Started tracking game stats in this channel!")

@bot.command()
async def stop(ctx):
    global tracking_enabled
    tracking_enabled = False
    await ctx.send("🛑 Stopped tracking game stats.")

@bot.command()
async def setinterval(ctx, seconds: int):
    global interval_seconds
    if seconds < 30:
        await ctx.send("⚠️ Interval must be at least 30 seconds.")
        return
    interval_seconds = seconds
    await ctx.send(f"⏱ Interval set to {seconds} seconds.")

@bot.command()
async def setgame(ctx, game_id: str):
    global current_game_id
    current_game_id = game_id
    await ctx.send(f"🎮 Game changed to ID: {game_id}")

# ==== On Ready ====
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    global tracking_task
    if tracking_task is None:
        tracking_task = asyncio.create_task(track_game())

# ==== Start ====
keep_alive()
bot.run(DISCORD_TOKEN)
