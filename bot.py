import discord
from discord.ext import commands, tasks
import aiohttp
import os
import json

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

WHITELIST_FILE = "whitelist.json"
SETTINGS_FILE = "serversettings.json"

# --- Persistent Whitelist ---
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist = json.load(f)
else:
    whitelist = [893232409489866782]  # your ID always whitelisted
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)

# --- Persistent Server Settings ---
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        server_settings = json.load(f)
else:
    server_settings = {}
    with open(SETTINGS_FILE, "w") as f:
        json.dump(server_settings, f)

active_servers = set()

def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(server_settings, f)

def is_whitelisted(user_id: int) -> bool:
    return user_id in whitelist

# --- Roblox Game Stats ---
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
            await channel.send(msg)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    spam_stats.start()

# --- WHITELIST COMMANDS ---
@bot.command()
async def whitelist_add(ctx, user_id: int):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    if user_id not in whitelist:
        whitelist.append(user_id)
        save_whitelist()
        await ctx.send(f"✅ Added {user_id} to whitelist.")
    else:
        await ctx.send("⚠️ That user is already whitelisted.")

@bot.command()
async def whitelist_remove(ctx, user_id: int):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    if user_id in whitelist and user_id != 893232409489866782:
        whitelist.remove(user_id)
        save_whitelist()
        await ctx.send(f"✅ Removed {user_id} from whitelist.")
    else:
        await ctx.send("⚠️ Cannot remove that user.")

@bot.command()
async def whitelist_list(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    await ctx.send(f"👑 Whitelisted users: {', '.join(map(str, whitelist))}")

# --- SERVER SETTINGS ---
@bot.command()
async def setgame(ctx, place_id: int):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["place_id"] = place_id
    save_settings()
    await ctx.send(f"✅ Game set to `{place_id}` for this server.")

@bot.command()
async def setchannel(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["channel_id"] = ctx.channel.id
    save_settings()
    await ctx.send(f"✅ Stats will now be sent in {ctx.channel.mention}")

# --- CONTROL ---
@bot.command()
async def start(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    active_servers.add(ctx.guild.id)
    await ctx.send("▶️ Started sending game stats for this server.")

@bot.command()
async def stop(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    active_servers.discard(ctx.guild.id)
    await ctx.send("⏹️ Stopped sending game stats for this server.")

# --- COMMAND LIST ---
@bot.command()
async def commands_list(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted.")
    cmds = [
        "!whitelist_add <user_id>",
        "!whitelist_remove <user_id>",
        "!whitelist_list",
        "!setgame <place_id>",
        "!setchannel",
        "!start",
        "!stop",
    ]
    await ctx.send("📜 Available commands:\n" + "\n".join(cmds))

bot.run(TOKEN)
