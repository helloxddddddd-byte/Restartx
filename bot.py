import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests, random, os, json, asyncio
from flask import Flask
from threading import Thread

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = 893232409489866782  # your Discord ID

# === Persistent Files ===
WHITELIST_FILE = "whitelist.json"
CONFIG_FILE = "config.json"

def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

whitelist = load_json(WHITELIST_FILE, [OWNER_ID])
CONFIG = load_json(CONFIG_FILE, {"game_id": 12345678, "interval": 65})

# === Bot Setup ===
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# === Flask Keepalive ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# === Whitelist Decorator ===
def whitelist_only():
    async def predicate(ctx_or_inter):
        user_id = ctx_or_inter.user.id if isinstance(ctx_or_inter, discord.Interaction) else ctx_or_inter.author.id
        if user_id in whitelist:
            return True
        if isinstance(ctx_or_inter, discord.Interaction):
            await ctx_or_inter.response.send_message("❌ You are not whitelisted.", ephemeral=True)
        else:
            await ctx_or_inter.send("❌ You are not whitelisted.")
        return False
    return commands.check(predicate)

# === Roblox Stats Task ===
stats_channel = None

@tasks.loop(seconds=CONFIG["interval"])
async def stats_loop():
    global stats_channel
    if not stats_channel:
        return
    try:
        url = f"https://games.roblox.com/v1/games?universeIds={CONFIG['game_id']}"
        data = requests.get(url).json()
        if "data" not in data or not data["data"]:
            return
        game = data["data"][0]
        players = game["playing"]
        visits = game["visits"]
        milestone = visits + 100

        msg = (
            "--------------------------------------------------\n"
            f"👤🎮 Active players: **{players}**\n"
            "--------------------------------------------------\n"
            f"👥 Visits: **{visits}**\n"
            f"🎯 Next milestone: **{visits}/{milestone}**\n"
            "--------------------------------------------------"
        )
        await stats_channel.send(msg)
    except Exception as e:
        print(f"[ERROR] {e}")

# === On Ready ===
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# === HELP Command ===
@tree.command(name="help", description="Show available commands")
async def slash_help(interaction: discord.Interaction):
    help_text = (
        "**📚 Available Commands:**\n"
        "`/start` `/stop` `/restart` `/status`\n"
        "`/setinterval <seconds>` `/setgameid <id>` `/showconfig`\n"
        "`/whitelist <id>` `/unwhitelist <id>` `/whitelistlist`\n"
        "All also work with `!` prefix."
    )
    await interaction.response.send_message(help_text)

@bot.command(name="help")
async def prefix_help(ctx):
    help_text = (
        "**📚 Available Commands:**\n"
        "`!start` `!stop` `!restart` `!status`\n"
        "`!setinterval <seconds>` `!setgameid <id>` `!showconfig`\n"
        "`!whitelist <id>` `!unwhitelist <id>` `!whitelistlist`\n"
        "All also work with `/` slash commands."
    )
    await ctx.send(help_text)

# === CORE COMMANDS ===
@tree.command(name="start", description="Start stats loop")
@whitelist_only()
async def start(interaction: discord.Interaction):
    global stats_channel
    stats_channel = interaction.channel
    if not stats_loop.is_running():
        stats_loop.start()
    await interaction.response.send_message("✅ Stats loop started in this channel.")

@bot.command(name="start")
@whitelist_only()
async def start_prefix(ctx):
    global stats_channel
    stats_channel = ctx.channel
    if not stats_loop.is_running():
        stats_loop.start()
    await ctx.send("✅ Stats loop started in this channel.")

@tree.command(name="stop", description="Stop stats loop")
@whitelist_only()
async def stop(interaction: discord.Interaction):
    if stats_loop.is_running():
        stats_loop.stop()
    await interaction.response.send_message("🛑 Stats loop stopped.")

@bot.command(name="stop")
@whitelist_only()
async def stop_prefix(ctx):
    if stats_loop.is_running():
        stats_loop.stop()
    await ctx.send("🛑 Stats loop stopped.")

@tree.command(name="restart", description="Restart the bot")
@whitelist_only()
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("♻️ Restarting...")
    await bot.close()

@bot.command(name="restart")
@whitelist_only()
async def restart_prefix(ctx):
    await ctx.send("♻️ Restarting...")
    await bot.close()

@tree.command(name="status", description="Show bot status")
@whitelist_only()
async def status(interaction: discord.Interaction):
    loop_status = "✅ Running" if stats_loop.is_running() else "🛑 Stopped"
    await interaction.response.send_message(f"🔧 Stats loop: {loop_status}\nGame ID: {CONFIG['game_id']}\nInterval: {CONFIG['interval']}s")

@bot.command(name="status")
@whitelist_only()
async def status_prefix(ctx):
    loop_status = "✅ Running" if stats_loop.is_running() else "🛑 Stopped"
    await ctx.send(f"🔧 Stats loop: {loop_status}\nGame ID: {CONFIG['game_id']}\nInterval: {CONFIG['interval']}s")

@tree.command(name="setinterval", description="Change stats loop interval")
@whitelist_only()
async def setinterval(interaction: discord.Interaction, seconds: int):
    CONFIG["interval"] = seconds
    save_json(CONFIG_FILE, CONFIG)
    if stats_loop.is_running():
        stats_loop.change_interval(seconds=seconds)
    await interaction.response.send_message(f"⏱ Interval set to {seconds}s")

@bot.command(name="setinterval")
@whitelist_only()
async def setinterval_prefix(ctx, seconds: int):
    CONFIG["interval"] = seconds
    save_json(CONFIG_FILE, CONFIG)
    if stats_loop.is_running():
        stats_loop.change_interval(seconds=seconds)
    await ctx.send(f"⏱ Interval set to {seconds}s")

@tree.command(name="setgameid", description="Set the Roblox game universe ID")
@whitelist_only()
async def setgameid(interaction: discord.Interaction, universe_id: int):
    CONFIG["game_id"] = universe_id
    save_json(CONFIG_FILE, CONFIG)
    await interaction.response.send_message(f"🎮 Game ID set to {universe_id}")

@bot.command(name="setgameid")
@whitelist_only()
async def setgameid_prefix(ctx, universe_id: int):
    CONFIG["game_id"] = universe_id
    save_json(CONFIG_FILE, CONFIG)
    await ctx.send(f"🎮 Game ID set to {universe_id}")

@tree.command(name="showconfig", description="Show current config")
@whitelist_only()
async def showconfig(interaction: discord.Interaction):
    await interaction.response.send_message(f"📊 Config: Game ID={CONFIG['game_id']}, Interval={CONFIG['interval']}s")

@bot.command(name="showconfig")
@whitelist_only()
async def showconfig_prefix(ctx):
    await ctx.send(f"📊 Config: Game ID={CONFIG['game_id']}, Interval={CONFIG['interval']}s")

# === WHITELIST COMMANDS ===
@tree.command(name="whitelist", description="Add a user ID to whitelist")
@whitelist_only()
async def whitelist_add(interaction: discord.Interaction, user_id: int):
    if user_id not in whitelist:
        whitelist.append(user_id)
        save_json(WHITELIST_FILE, whitelist)
    await interaction.response.send_message(f"✅ {user_id} whitelisted")

@bot.command(name="whitelist")
@whitelist_only()
async def whitelist_add_prefix(ctx, user_id: int):
    if user_id not in whitelist:
        whitelist.append(user_id)
        save_json(WHITELIST_FILE, whitelist)
    await ctx.send(f"✅ {user_id} whitelisted")

@tree.command(name="unwhitelist", description="Remove a user ID from whitelist")
@whitelist_only()
async def whitelist_remove(interaction: discord.Interaction, user_id: int):
    if user_id in whitelist:
        whitelist.remove(user_id)
        save_json(WHITELIST_FILE, whitelist)
    await interaction.response.send_message(f"❌ {user_id} removed from whitelist")

@bot.command(name="unwhitelist")
@whitelist_only()
async def whitelist_remove_prefix(ctx, user_id: int):
    if user_id in whitelist:
        whitelist.remove(user_id)
        save_json(WHITELIST_FILE, whitelist)
    await ctx.send(f"❌ {user_id} removed from whitelist")

@tree.command(name="whitelistlist", description="Show all whitelisted IDs")
@whitelist_only()
async def whitelist_list(interaction: discord.Interaction):
    await interaction.response.send_message("👥 Whitelist: " + ", ".join(map(str, whitelist)))

@bot.command(name="whitelistlist")
@whitelist_only()
async def whitelist_list_prefix(ctx):
    await ctx.send("👥 Whitelist: " + ", ".join(map(str, whitelist)))

# === Run Bot ===
bot.run(TOKEN)
