import sys
import types

# Patch audioop if missing (Render's Python builds often don't include it)
if "audioop" not in sys.modules:
    sys.modules["audioop"] = types.ModuleType("audioop")
    
import os
import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

TOKEN = os.getenv("DISCORD_TOKEN")  # Render secret
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Render secret

intents = discord.Intents.default()
intents.message_content = True  # needed for commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Flask server for uptime pings
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Loop task (disabled by default)
@tasks.loop(seconds=65)
async def send_message():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("⏰ Automated message every 65 seconds.")

# Commands
@bot.command()
async def start(ctx):
    if not send_message.is_running():
        send_message.start()
        await ctx.send("✅ milestone bot started!")
    else:
        await ctx.send("⚠️ milestone bot is already running!")

@bot.command()
async def stop(ctx):
    if send_message.is_running():
        send_message.cancel()
        await ctx.send("🛑 milestone bot stopped!")
    else:
        await ctx.send("⚠️ milestone bot is not running!")

# On ready
@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

def start_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    start_bot()
