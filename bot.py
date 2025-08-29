import discord
from discord.ext import commands, tasks
import aiohttp
import os
import threading
from flask import Flask

TOKEN = os.getenv("DISCORD_TOKEN")

# Default game (Vixen Hood)
DEFAULT_GAME = "125760703264498"
current_game = DEFAULT_GAME
update_interval = 65  # seconds
tracking = False
tracking_channel = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- Flask keep-alive ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# ---------------- Helpers ----------------
async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# ---------------- Commands ----------------
@bot.command()
async def setinterval(ctx, seconds: int):
    global update_interval
    if seconds < 15:
        await ctx.send("⚠️ Interval must be at least 15 seconds.")
        return
    update_interval = seconds
    track_data.change_interval(seconds=update_interval)
    await ctx.send(f"⏱ Interval updated to {seconds} seconds.")


@bot.command()
async def setgame(ctx, place_id: str):
    global current_game
    current_game = place_id
    await ctx.send(f"🎮 Tracking new game with Place ID `{place_id}`")


@bot.command()
async def start(ctx):
    global tracking, tracking_channel
    tracking = True
    tracking_channel = ctx.channel
    if not track_data.is_running():
        track_data.start()
    await ctx.send("✅ Started tracking game stats!")


@bot.command()
async def stop(ctx):
    global tracking
    tracking = False
    if track_data.is_running():
        track_data.stop()
    await ctx.send("🛑 Stopped tracking game stats.")


# ---------------- Loop for tracking ----------------
@tasks.loop(seconds=65)
async def track_data():
    global tracking, tracking_channel, current_game
    if not tracking or not tracking_channel:
        return

    url = f"https://games.roblox.com/v1/games?universeIds={current_game}"
    data = await fetch_json(url)
    if not data or "data" not in data or len(data["data"]) == 0:
        await tracking_channel.send("⚠️ Failed to fetch game data.")
        return

    game_info = data["data"][0]
    players = game_info.get("playing", 0)
    visits = game_info.get("visits", 0)
    milestone = visits + 100

    msg = (
        "--------------------------------------------------\n"
        f"👤🎮 Active players: **{players}**\n"
        "--------------------------------------------------\n"
        f"👥 Visits: **{visits}**\n"
        f"🎯 Next milestone: **{visits}/{milestone}**\n"
        "--------------------------------------------------"
    )

    await tracking_channel.send(msg)


# ---------------- Run bot ----------------
keep_alive()  # start Flask keep-alive
bot.run(TOKEN)
