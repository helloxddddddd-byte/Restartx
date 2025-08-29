import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import json
from flask import Flask
from threading import Thread

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
intents = discord.Intents.default()
intents.message_content = True  # Needed for ! commands

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree  # for slash commands

# ----------------- Flask Keep-Alive -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()

# ----------------- Whitelist -----------------
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"whitelist": [], "servers": {}}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

config = load_config()

def is_whitelisted(user_id):
    return str(user_id) in config["whitelist"]

# ----------------- Roblox Fetching -----------------
async def fetch_game_data(place_id):
    async with aiohttp.ClientSession() as session:
        # visits
        async with session.get(f"https://games.roblox.com/v1/games?universeIds={place_id}") as r:
            data = await r.json()
            visits = data["data"][0]["visits"] if "data" in data else 0

        # active players (sum across servers)
        active = 0
        async with session.get(f"https://games.roblox.com/v1/games/{place_id}/servers/Public?sortOrder=Asc&limit=100") as r:
            servers = await r.json()
            if "data" in servers:
                for s in servers["data"]:
                    active += s.get("playing", 0)

        return active, visits

# ----------------- Background Task -----------------
tasks_running = {}

@tasks.loop(seconds=65)
async def stats_loop(guild_id):
    cfg = load_config()
    server_cfg = cfg["servers"].get(str(guild_id))
    if not server_cfg:
        return
    channel_id = server_cfg.get("channel_id")
    place_id = server_cfg.get("place_id")

    channel = bot.get_channel(channel_id)
    if not channel:
        return

    active, visits = await fetch_game_data(place_id)
    milestone = visits + 100

    msg = (
        "--------------------------------------------------\n"
        f"👤🎮 Active players: {active}\n"
        "--------------------------------------------------\n"
        f"👥 Visits: {visits}\n"
        f"🎯 Next milestone: {milestone}\n"
        "--------------------------------------------------"
    )
    await channel.send(msg)

# ----------------- Commands -----------------
@bot.event
async def on_ready():
    await bot.tree.sync()  # force sync slash commands
    print(f"✅ Logged in as {bot.user} and synced commands")

# start
@bot.command()
async def start(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted!")
    guild_id = ctx.guild.id
    if guild_id not in tasks_running:
        tasks_running[guild_id] = stats_loop.start(guild_id)
        await ctx.send("✅ Stats updates started!")

@tree.command(name="start", description="Start tracking stats")
async def start_slash(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        return await interaction.response.send_message("❌ You are not whitelisted!", ephemeral=True)
    guild_id = interaction.guild.id
    if guild_id not in tasks_running:
        tasks_running[guild_id] = stats_loop.start(guild_id)
        await interaction.response.send_message("✅ Stats updates started!")

# stop
@bot.command()
async def stop(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted!")
    guild_id = ctx.guild.id
    if guild_id in tasks_running:
        tasks_running[guild_id].cancel()
        del tasks_running[guild_id]
        await ctx.send("🛑 Stats updates stopped!")

@tree.command(name="stop", description="Stop tracking stats")
async def stop_slash(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        return await interaction.response.send_message("❌ You are not whitelisted!", ephemeral=True)
    guild_id = interaction.guild.id
    if guild_id in tasks_running:
        tasks_running[guild_id].cancel()
        del tasks_running[guild_id]
        await interaction.response.send_message("🛑 Stats updates stopped!")

# set channel
@bot.command()
async def setchannel(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted!")
    cfg = load_config()
    cfg["servers"][str(ctx.guild.id)] = cfg["servers"].get(str(ctx.guild.id), {})
    cfg["servers"][str(ctx.guild.id)]["channel_id"] = ctx.channel.id
    save_config(cfg)
    await ctx.send(f"✅ Channel set to {ctx.channel.mention}")

# set game
@bot.command()
async def setgame(ctx, place_id: int):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted!")
    cfg = load_config()
    cfg["servers"][str(ctx.guild.id)] = cfg["servers"].get(str(ctx.guild.id), {})
    cfg["servers"][str(ctx.guild.id)]["place_id"] = place_id
    save_config(cfg)
    await ctx.send(f"✅ Game set to place ID: {place_id}")

# whitelist
@bot.command()
async def whitelist(ctx, user_id: int):
    if ctx.author.id != 893232409489866782:
        return await ctx.send("❌ Only the owner can whitelist users!")
    config = load_config()
    if str(user_id) not in config["whitelist"]:
        config["whitelist"].append(str(user_id))
        save_config(config)
    await ctx.send(f"✅ User <@{user_id}> whitelisted!")

# commands list
@bot.command()
async def commandslist(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ You are not whitelisted!")
    cmds = [
        "!start / /start - Start tracking",
        "!stop / /stop - Stop tracking",
        "!setchannel - Set channel for updates",
        "!setgame <place_id> - Set game to track",
        "!whitelist <user_id> - Add a user to whitelist",
        "!commandslist - Show all commands"
    ]
    await ctx.send("📜 **Commands:**\n" + "\n".join(cmds))

bot.run(TOKEN)
