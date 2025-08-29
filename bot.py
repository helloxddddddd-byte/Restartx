import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
from flask import Flask
from threading import Thread

# ---------------- CONFIG ---------------- #
CONFIG_FILE = "config.json"
TOKEN = os.getenv("DISCORD_TOKEN")  # put your bot token in environment vars
WHITELIST = [123456789012345678]  # whitelist user IDs (replace with yours)

# ---------------- HELPERS ---------------- #
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

config = load_config()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

active_tasks = {}  # guild_id -> task


async def fetch_game_stats(universe_id: str):
    """Fetches live Roblox game stats (playing + visits)."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
            async with session.get(url) as resp:
                data = await resp.json()
                visits = data["data"][0]["visits"]
                playing = data["data"][0]["playing"]
                return playing, visits
        except Exception:
            return 0, 0


async def spam_stats(guild_id, channel_id, universe_id):
    """Loop that spams stats every 65 seconds."""
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    while True:
        playing, visits = await fetch_game_stats(universe_id)
        milestone = visits + 100
        try:
            await channel.send(
                f"🎮 **Game Stats** 🎮\n"
                f"👥 Players Online: **{playing}**\n"
                f"👀 Visits: **{visits:,}**\n"
                f"🎯 Next Milestone: **{milestone:,} visits**"
            )
        except Exception:
            pass
        await asyncio.sleep(65)


# ---------------- COMMANDS ---------------- #

def is_whitelisted():
    async def predicate(ctx):
        return ctx.author.id in WHITELIST
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"🔗 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")


@bot.hybrid_command(name="setgame")
@is_whitelisted()
async def setgame(ctx, universe_id: str):
    """Set which Roblox game (universe_id) to track."""
    gid = str(ctx.guild.id)
    if gid not in config:
        config[gid] = {}
    config[gid]["universe_id"] = universe_id
    save_config(config)
    await ctx.reply(f"✅ Game set to **{universe_id}**")


@bot.hybrid_command(name="setchannel")
@is_whitelisted()
async def setchannel(ctx):
    """Set the current channel for stats spam."""
    gid = str(ctx.guild.id)
    if gid not in config:
        config[gid] = {}
    config[gid]["channel_id"] = ctx.channel.id
    save_config(config)
    await ctx.reply(f"✅ Channel set to {ctx.channel.mention}")


@bot.hybrid_command(name="start")
@is_whitelisted()
async def start(ctx):
    """Start sending stats in this server."""
    gid = str(ctx.guild.id)
    if gid not in config or "universe_id" not in config[gid] or "channel_id" not in config[gid]:
        await ctx.reply("⚠️ Please run `/setgame <id>` and `/setchannel` first.")
        return

    if gid in active_tasks:
        await ctx.reply("⚠️ Stats are already running here.")
        return

    task = asyncio.create_task(spam_stats(int(gid), config[gid]["channel_id"], config[gid]["universe_id"]))
    active_tasks[gid] = task
    await ctx.reply("✅ Stats updates **started**!")


@bot.hybrid_command(name="stop")
@is_whitelisted()
async def stop(ctx):
    """Stop sending stats in this server."""
    gid = str(ctx.guild.id)
    if gid in active_tasks:
        active_tasks[gid].cancel()
        del active_tasks[gid]
        await ctx.reply("🛑 Stats updates **stopped**!")
    else:
        await ctx.reply("⚠️ No stats running in this server.")


@bot.hybrid_command(name="commands")
@is_whitelisted()
async def commands_list(ctx):
    """Show available bot commands."""
    cmds = [
        "/setgame <universe_id> - Set which Roblox game to track",
        "/setchannel - Choose channel for stats",
        "/start - Start sending stats",
        "/stop - Stop sending stats",
        "/commands - Show this list"
    ]
    await ctx.reply("📜 **Available Commands:**\n" + "\n".join(cmds))


# ---------------- FLASK KEEP-ALIVE ---------------- #
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# ---------------- RUN ---------------- #
bot.run(TOKEN)
