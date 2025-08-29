import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os
from flask import Flask
from threading import Thread

# ===== Flask Keep-Alive for Render =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run).start()

# ===== Discord Bot Setup =====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Default game (Vixen Hood)
tracked_game = 125760703264498
update_interval = 65
tracking = False
channel_id = None

# ===== Helper: Get Roblox Game Data =====
async def fetch_game_data(place_id):
    async with aiohttp.ClientSession() as session:
        # Fetch active players
        async with session.get(f"https://games.roblox.com/v1/games?universeIds={place_id}") as r:
            if r.status != 200:
                return None
            data = await r.json()
            if not data.get("data"):
                return None
            info = data["data"][0]
            return {
                "playing": info["playing"],
                "visits": info["visits"]
            }

# ===== Background Task =====
@tasks.loop(seconds=65)
async def send_game_stats():
    global channel_id, tracked_game
    if not channel_id or not tracked_game:
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        return

    data = await fetch_game_data(tracked_game)
    if not data:
        await channel.send("⚠️ Failed to fetch game data.")
        return

    players = data["playing"]
    visits = data["visits"]
    milestone = ((visits // 100) + 1) * 100

    message = (
        "--------------------------------------------------\n"
        f"👤🎮 Active players: **{players}**\n"
        "--------------------------------------------------\n"
        f"👥 Visits: **{visits}**\n"
        f"🎯 Next milestone: **{milestone}/{visits}**\n"
        "--------------------------------------------------"
    )
    await channel.send(message)

# ===== Commands =====
@bot.command()
async def start(ctx):
    global tracking, channel_id
    if tracking:
        await ctx.send("⚠️ Tracking is already running!")
        return
    channel_id = ctx.channel.id
    tracking = True
    send_game_stats.change_interval(seconds=update_interval)
    send_game_stats.start()
    await ctx.send("✅ Tracking **started**!")

@bot.command()
async def stop(ctx):
    global tracking
    if not tracking:
        await ctx.send("⚠️ Tracking is not running.")
        return
    tracking = False
    send_game_stats.stop()
    await ctx.send("🛑 Tracking **stopped**!")

@bot.command()
async def setinterval(ctx, seconds: int):
    global update_interval
    if seconds < 30:
        await ctx.send("⚠️ Interval too short! Must be 30s or more.")
        return
    update_interval = seconds
    if tracking:
        send_game_stats.change_interval(seconds=update_interval)
    await ctx.send(f"⏱️ Update interval set to **{seconds} seconds**")

@bot.command()
async def setgame(ctx, place_id: int):
    global tracked_game
    tracked_game = place_id
    await ctx.send(f"🎮 Now tracking game with placeId: **{place_id}**")

# ===== Run Bot =====
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
