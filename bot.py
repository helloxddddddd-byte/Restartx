import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os
import json
from flask import Flask
import threading

# === Flask webserver to keep Render alive ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")

# === Persistent storage ===
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"whitelist": ["893232409489866782"], "servers": {}, "milestone_step": 100}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

# === Roblox Fetch Helpers ===
async def get_game_stats(place_id):
    async with aiohttp.ClientSession() as session:
        try:
            # Visits
            async with session.get(f"https://games.roblox.com/v1/games?universeIds={place_id}") as r:
                info = await r.json()
                visits = info["data"][0]["visits"]

            # Players
            async with session.get(f"https://games.roblox.com/v1/games/{place_id}/servers/Public?sortOrder=Asc&limit=100") as r:
                servers = await r.json()
                active_players = sum(len(s["playerIds"]) for s in servers.get("data", []))

            milestone_step = data.get("milestone_step", 100)
            milestone = ((visits // milestone_step) + 1) * milestone_step
            return active_players, visits, milestone
        except:
            return None, None, None

# === Background Task ===
@tasks.loop(seconds=65)
async def tracking_loop():
    for guild_id, settings in data["servers"].items():
        channel_id = settings.get("channel")
        place_id = settings.get("place")
        if not channel_id or not place_id:
            continue

        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        players, visits, milestone = await get_game_stats(place_id)
        if players is None:
            continue

        msg = (
            "--------------------------------------------------\n"
            f"👤🎮 Active players: **{players}**\n"
            "--------------------------------------------------\n"
            f"👥 Visits: **{visits}**\n"
            f"🎯 Next milestone: **{visits}/{milestone}**\n"
            "--------------------------------------------------"
        )
        await channel.send(msg)

# === Whitelist Check ===
def is_whitelisted():
    async def predicate(ctx):
        if str(ctx.author.id) in data["whitelist"]:
            return True
        await ctx.send("❌ You are not whitelisted to use this bot.")
        return False
    return commands.check(predicate)

# === Events ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if not tracking_loop.is_running():
        tracking_loop.start()

# === Commands ===
@bot.command()
@is_whitelisted()
async def start(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in data["servers"]:
        data["servers"][guild_id] = {}
    await ctx.send("✅ Tracking started. Use `!setchannel <place_id>` to configure the game.")
    save_data(data)

@bot.command()
@is_whitelisted()
async def stop(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id in data["servers"]:
        del data["servers"][guild_id]
        save_data(data)
    await ctx.send("🛑 Tracking stopped.")

@bot.command()
@is_whitelisted()
async def restart(ctx):
    await ctx.send("🔄 Restarting bot...")
    await bot.close()

@bot.command()
@is_whitelisted()
async def setchannel(ctx, place_id: str):
    guild_id = str(ctx.guild.id)
    if guild_id not in data["servers"]:
        data["servers"][guild_id] = {}
    data["servers"][guild_id]["channel"] = ctx.channel.id
    data["servers"][guild_id]["place"] = place_id
    save_data(data)
    await ctx.send(f"✅ Tracking channel set to {ctx.channel.mention} for game `{place_id}`.")

@bot.command()
@is_whitelisted()
async def milestone(ctx, step: int):
    if step < 10:
        return await ctx.send("⚠️ Milestone step must be at least 10.")
    data["milestone_step"] = step
    save_data(data)
    await ctx.send(f"✅ Milestone step set to **+{step}**.")

@bot.command()
@is_whitelisted()
async def whitelist(ctx, user_id: str):
    if str(ctx.author.id) != "893232409489866782":
        return await ctx.send("❌ Only the owner can whitelist users.")
    if user_id not in data["whitelist"]:
        data["whitelist"].append(user_id)
        save_data(data)
        await ctx.send(f"✅ User `{user_id}` whitelisted.")
    else:
        await ctx.send("⚠️ That user is already whitelisted.")

@bot.command()
@is_whitelisted()
async def unwhitelist(ctx, user_id: str):
    if str(ctx.author.id) != "893232409489866782":
        return await ctx.send("❌ Only the owner can unwhitelist users.")
    if user_id in data["whitelist"]:
        data["whitelist"].remove(user_id)
        save_data(data)
        await ctx.send(f"🗑️ User `{user_id}` removed from whitelist.")
    else:
        await ctx.send("⚠️ That user is not whitelisted.")

@bot.command()
async def help(ctx):
    cmds = [
        "!start - Start tracking",
        "!stop - Stop tracking",
        "!restart - Restart bot",
        "!setchannel <place_id> - Set channel & game to track",
        "!milestone <number> - Set milestone step (default +100)",
        "!whitelist <user_id> - Whitelist a user (owner only)",
        "!unwhitelist <user_id> - Remove a user from whitelist (owner only)",
        "!help - Show this help menu"
    ]
    await ctx.send("📜 **Commands:**\n" + "\n".join(cmds))

# === Run Flask + Bot ===
threading.Thread(target=run_web).start()
bot.run(TOKEN)
