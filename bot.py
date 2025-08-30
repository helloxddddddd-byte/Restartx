import os
import asyncio
import discord
from discord.ext import commands, tasks
import aiohttp
from flask import Flask
from threading import Thread

TOKEN = os.getenv("DISCORD_TOKEN")

# Intents
intents = discord.Intents.default()
intents.message_content = True

# Prefix commands + slash commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Game defaults
DEFAULT_GAME_URL = "https://www.roblox.com/games/125760703264498/Vixen-Hood-8-26-UPDATE"
current_game_url = DEFAULT_GAME_URL
tracking = False
interval_seconds = 65
tracking_task = None
tracking_channel = None

# Flask server for UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---- ROBLOX GAME DATA FETCH ----
async def fetch_game_data():
    place_id = current_game_url.split("/")[-2] if "/games/" in current_game_url else None
    if not place_id:
        return None

    url = f"https://games.roblox.com/v1/games?universeIds={place_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if "data" in data and len(data["data"]) > 0:
                    game = data["data"][0]
                    return {
                        "playing": game.get("playing", 0),
                        "visits": game.get("visits", 0)
                    }
    return None

# ---- MESSAGE LAYOUT ----
async def send_tracking_message(channel):
    data = await fetch_game_data()
    if not data:
        await channel.send("⚠️ Failed to fetch game data.")
        return
    visits = data["visits"]
    milestone = ((visits // 100) + 1) * 100
    msg = (
        "--------------------------------------------------\n"
        f"👤🎮 Active players: **{data['playing']}**\n"
        "--------------------------------------------------\n"
        f"👥 Visits: **{visits}**\n"
        f"🎯 Next milestone: **{visits}/{milestone}**\n"
        "--------------------------------------------------"
    )
    await channel.send(msg)

# ---- TRACKING LOOP ----
async def tracking_loop():
    global tracking
    while tracking:
        if tracking_channel:
            await send_tracking_message(tracking_channel)
        await asyncio.sleep(interval_seconds)

# ---- COMMANDS ----
@bot.command()
async def start(ctx):
    """Start game data tracking"""
    global tracking, tracking_task, tracking_channel
    if tracking:
        await ctx.send("⚠️ Tracking is already running.")
        return
    tracking = True
    tracking_channel = ctx.channel
    tracking_task = asyncio.create_task(tracking_loop())
    await ctx.send("✅ Started game data tracking.")

@bot.command()
async def stop(ctx):
    """Stop game data tracking"""
    global tracking, tracking_task
    tracking = False
    if tracking_task:
        tracking_task.cancel()
        tracking_task = None
    await ctx.send("🛑 Stopped game data tracking.")

@bot.command()
async def setinterval(ctx, seconds: int):
    """Set the interval between messages"""
    global interval_seconds
    interval_seconds = max(30, seconds)  # minimum 30s safety
    await ctx.send(f"⏱ Interval set to {interval_seconds} seconds.")

@bot.command()
async def setgame(ctx, url: str):
    """Change the tracked Roblox game"""
    global current_game_url
    if "roblox.com/games/" not in url:
        await ctx.send("⚠️ Invalid Roblox game URL.")
        return
    current_game_url = url
    await ctx.send(f"🎮 Now tracking: {url}")

# 
@bot.tree.command(name="ping", description="Ping command (needed for Active Developer Badge)")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("ping pong faggit")

#
@bot.event
async def on_ready():
    await bot.tree.sync()  # sync slash commands
    print(f"✅ Logged in as {bot.user}")

#
keep_alive()
bot.run(TOKEN)
