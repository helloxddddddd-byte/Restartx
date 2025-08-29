import sys, types
if "audioop" not in sys.modules:
    sys.modules["audioop"] = types.ModuleType("audioop")

import discord
from discord.ext import commands, tasks
import requests
import json
import os
import random
from flask import Flask
from threading import Thread

# === CONFIG HANDLING ===
CONFIG_FILE = "config.json"

default_config = {
    "whitelist": ["893232409489866782"],  # Owner user ID always whitelisted
    "game_id": 123456789  # replace with your Roblox game ID
}

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=4)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# === DISCORD SETUP ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!", "/"), intents=intents)

tree = bot.tree  # for slash commands

# Track loop state
sending_updates = True

# === BACKGROUND TASK ===
@tasks.loop(seconds=65)
async def send_game_stats():
    if not sending_updates:
        return

    try:
        game_id = config["game_id"]

        r = requests.get(f"https://games.roblox.com/v1/games?universeIds={game_id}")
        data = r.json()

        if "data" not in data or not data["data"]:
            return

        game = data["data"][0]
        active_players = game.get("playing", 0)
        visits = game.get("visits", 0)
        milestone = visits + 100

        msg = (
            "--------------------------------------------------\n"
            f"👤🎮 Active players: **{active_players}**\n"
            "--------------------------------------------------\n"
            f"👥 Visits: **{visits}**\n"
            f"🎯 Next milestone: **{visits}/{milestone}**\n"
            "--------------------------------------------------"
        )

        for guild in bot.guilds:
            for channel in guild.text_channels:
                try:
                    await channel.send(msg)
                    return  # only send once per guild
                except:
                    continue

    except Exception as e:
        print("Error in stats loop:", e)

# === WHITELIST CHECK ===
def is_whitelisted():
    async def predicate(ctx):
        return str(ctx.author.id) in config["whitelist"]
    return commands.check(predicate)

def is_whitelisted_slash(interaction: discord.Interaction):
    return str(interaction.user.id) in config["whitelist"]

# === TEXT COMMANDS (prefix ! or /) ===
@bot.command(name="start")
@is_whitelisted()
async def start_updates(ctx):
    global sending_updates
    sending_updates = True
    await ctx.send("✅ Stats updates **started**!")

@bot.command(name="stop")
@is_whitelisted()
async def stop_updates(ctx):
    global sending_updates
    sending_updates = False
    await ctx.send("⏹️ Stats updates **stopped**!")

@bot.command(name="restart")
@is_whitelisted()
async def restart_bot(ctx):
    await ctx.send("🔄 Restarting bot...")
    os._exit(0)  # force exit so Render restarts it

@bot.command(name="whitelist")
@is_whitelisted()
async def whitelist_user(ctx, user_id: str):
    if user_id not in config["whitelist"]:
        config["whitelist"].append(user_id)
        save_config()
        await ctx.send(f"✅ User `{user_id}` added to whitelist.")
    else:
        await ctx.send("⚠️ That user is already whitelisted.")

@bot.command(name="helpme")
@is_whitelisted()
async def helpme(ctx):
    commands_list = """
📜 **Available Commands**
!start — Start updates
!stop — Stop updates
!restart — Restart bot
!whitelist <id> — Add user to whitelist
!8ball <question> — Ask the magic ball
!roll — Roll a dice
!flip — Flip a coin
    """
    await ctx.send(commands_list)

@bot.command(name="8ball")
@is_whitelisted()
async def eightball(ctx, *, question: str):
    responses = ["Yes!", "No!", "Maybe...", "Definitely!", "Ask again later."]
    await ctx.send(f"🎱 {random.choice(responses)}")

@bot.command(name="roll")
@is_whitelisted()
async def roll(ctx):
    await ctx.send(f"🎲 You rolled a {random.randint(1, 6)}!")

@bot.command(name="flip")
@is_whitelisted()
async def flip(ctx):
    await ctx.send(f"🪙 {random.choice(['Heads', 'Tails'])}!")

# === SLASH COMMANDS ===
@tree.command(name="start", description="Start updates")
async def start_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    global sending_updates
    sending_updates = True
    await interaction.response.send_message("✅ Stats updates **started**!")

@tree.command(name="stop", description="Stop updates")
async def stop_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    global sending_updates
    sending_updates = False
    await interaction.response.send_message("⏹️ Stats updates **stopped**!")

@tree.command(name="restart", description="Restart the bot")
async def restart_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message("🔄 Restarting bot...")
    os._exit(0)

@tree.command(name="whitelist", description="Add a user to whitelist")
async def whitelist_slash(interaction: discord.Interaction, user_id: str):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    if user_id not in config["whitelist"]:
        config["whitelist"].append(user_id)
        save_config()
        await interaction.response.send_message(f"✅ User `{user_id}` added to whitelist.")
    else:
        await interaction.response.send_message("⚠️ That user is already whitelisted.")

@tree.command(name="helpme", description="Show commands")
async def helpme_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    commands_list = """
📜 **Available Commands**
/start — Start updates
/stop — Stop updates
/restart — Restart bot
/whitelist <id> — Add user to whitelist
/8ball <question> — Ask the magic ball
/roll — Roll a dice
/flip — Flip a coin
    """
    await interaction.response.send_message(commands_list)

@tree.command(name="8ball", description="Ask the magic 8-ball")
async def eightball_slash(interaction: discord.Interaction, question: str):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    responses = ["Yes!", "No!", "Maybe...", "Definitely!", "Ask again later."]
    await interaction.response.send_message(f"🎱 {random.choice(responses)}")

@tree.command(name="roll", description="Roll a dice")
async def roll_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message(f"🎲 You rolled a {random.randint(1, 6)}!")

@tree.command(name="flip", description="Flip a coin")
async def flip_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message(f"🪙 {random.choice(['Heads', 'Tails'])}!")

# === FLASK KEEPALIVE ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_web).start()

# === EVENTS ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"📡 Synced {len(synced)} slash commands")
    except Exception as e:
        print("Slash sync error:", e)
    send_game_stats.start()

# === START ===
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
