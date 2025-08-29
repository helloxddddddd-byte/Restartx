import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os

# Token is now read from Render/Heroku secret
TOKEN = os.getenv("DISCORD_TOKEN")

# Always intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

WHITELIST_FILE = "whitelist.json"
SETTINGS_FILE = "serversettings.json"

# Load whitelist
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist = json.load(f)
else:
    whitelist = [893232409489866782]  # your ID always whitelisted
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)

# Load server settings
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        server_settings = json.load(f)
else:
    server_settings = {}
    with open(SETTINGS_FILE, "w") as f:
        json.dump(server_settings, f)

active_servers = set()

async def fetch_game_stats(place_id):
    url = f"https://games.roblox.com/v1/games?universeIds={place_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("data"):
                    game_data = data["data"][0]
                    visits = game_data.get("visits", 0)
                    playing = game_data.get("playing", 0)
                    return {
                        "name": game_data.get("name", "Unknown"),
                        "visits": visits,
                        "playing": playing,
                        "goal": visits + 100
                    }
    return None

@tasks.loop(seconds=65)
async def spam_stats():
    for guild_id in active_servers.copy():
        settings = server_settings.get(str(guild_id), {})
        place_id = settings.get("place_id")
        channel_id = settings.get("channel_id")

        if not place_id or not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        stats = await fetch_game_stats(place_id)
        if stats:
            msg = (
                "--------------------------------------------------\n"
                f"👤🎮 Active players: **{stats['playing']}**\n"
                "--------------------------------------------------\n"
                f"👥 Visits: **{stats['visits']:,}**\n"
                f"🎯 Next milestone: **{stats['visits']:,}/{stats['goal']:,}**\n"
                "--------------------------------------------------"
            )
            try:
                await channel.send(msg)
            except Exception as e:
                print(f"Error sending message in {guild_id}: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    spam_stats.start()

def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(server_settings, f)

def is_whitelisted():
    async def predicate(ctx):
        return ctx.author.id in whitelist
    return commands.check(predicate)

# ===== WHITELIST COMMANDS =====
@bot.command()
@is_whitelisted()
async def whitelist_add(ctx, user_id: int):
    if user_id not in whitelist:
        whitelist.append(user_id)
        save_whitelist()
        await ctx.send(f"✅ Added {user_id} to whitelist.")
    else:
        await ctx.send("⚠️ That user is already whitelisted.")

@bot.command()
@is_whitelisted()
async def whitelist_remove(ctx, user_id: int):
    if user_id in whitelist and user_id != 893232409489866782:
        whitelist.remove(user_id)
        save_whitelist()
        await ctx.send(f"✅ Removed {user_id} from whitelist.")
    else:
        await ctx.send("⚠️ Cannot remove that user.")

@bot.command()
async def whitelist_list(ctx):
    await ctx.send(f"👑 Whitelisted users: {', '.join(map(str, whitelist))}")

# ===== SERVER SETTINGS =====
@bot.command()
@is_whitelisted()
async def setgame(ctx, place_id: int):
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["place_id"] = place_id
    save_settings()
    await ctx.send(f"✅ Game set to `{place_id}` for this server.")

@bot.command()
@is_whitelisted()
async def setchannel(ctx):
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["channel_id"] = ctx.channel.id
    save_settings()
    await ctx.send(f"✅ Stats will now be sent in {ctx.channel.mention}")

# ===== CONTROL =====
@bot.command()
@is_whitelisted()
async def start(ctx):
    active_servers.add(ctx.guild.id)
    await ctx.send("▶️ Started sending game stats for this server.")

@bot.command()
@is_whitelisted()
async def stop(ctx):
    active_servers.discard(ctx.guild.id)
    await ctx.send("⏹️ Stopped sending game stats for this server.")

bot.run(TOKEN)
