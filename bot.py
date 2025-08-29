import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os

TOKEN = os.getenv("DISCORD_TOKEN")

# persistent whitelist file
WHITELIST_FILE = "whitelist.json"

if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist = json.load(f)
else:
    whitelist = ["893232409489866782"]  # your ID by default
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)

# per-server settings
server_settings = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# remove default help so we can override
bot.remove_command("help")


async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None


def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist, f)


def is_whitelisted():
    async def predicate(ctx):
        if str(ctx.author.id) in whitelist:
            return True
        await ctx.send("❌ You are not whitelisted.")
        return False
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# ---------------- Commands ----------------

@bot.command()
@is_whitelisted()
async def whitelist_add(ctx, user_id: str):
    if user_id not in whitelist:
        whitelist.append(user_id)
        save_whitelist()
        await ctx.send(f"✅ Added <@{user_id}> to whitelist.")
    else:
        await ctx.send("⚠️ That user is already whitelisted.")


@bot.command()
@is_whitelisted()
async def whitelist_remove(ctx, user_id: str):
    if user_id in whitelist:
        whitelist.remove(user_id)
        save_whitelist()
        await ctx.send(f"✅ Removed <@{user_id}> from whitelist.")
    else:
        await ctx.send("⚠️ That user is not whitelisted.")


@bot.command()
@is_whitelisted()
async def setgame(ctx, place_id: str):
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["place_id"] = place_id
    await ctx.send(f"🎮 Tracking game with Place ID `{place_id}`")


@bot.command()
@is_whitelisted()
async def setchannel(ctx):
    gid = str(ctx.guild.id)
    if gid not in server_settings:
        server_settings[gid] = {}
    server_settings[gid]["channel_id"] = ctx.channel.id
    await ctx.send(f"📡 Stats will now post in {ctx.channel.mention}")


@bot.command()
@is_whitelisted()
async def start(ctx):
    gid = str(ctx.guild.id)
    if gid not in server_settings or "place_id" not in server_settings[gid] or "channel_id" not in server_settings[gid]:
        await ctx.send("⚠️ Use `!setgame <place_id>` and `!setchannel` first.")
        return

    await ctx.send("✅ Stats updates **started**!")
    track_data.start(gid)


@bot.command()
async def help(ctx):
    help_text = """
**Available Commands (Whitelist only):**
!whitelist_add <user_id> – Add a user to whitelist  
!whitelist_remove <user_id> – Remove a user from whitelist  
!setgame <place_id> – Set the Roblox game to track  
!setchannel – Set current channel for tracking updates  
!start – Begin tracking game stats in the set channel  
"""
    await ctx.send(help_text)


# ---------------- Loop for tracking ----------------

@tasks.loop(seconds=65)
async def track_data(gid):
    settings = server_settings.get(gid)
    if not settings:
        return

    channel = bot.get_channel(settings["channel_id"])
    place_id = settings["place_id"]

    # fetch player count
    url = f"https://games.roblox.com/v1/games?universeIds={place_id}"
    data = await fetch_json(url)
    if not data or "data" not in data or len(data["data"]) == 0:
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

    await channel.send(msg)


bot.run(TOKEN)
