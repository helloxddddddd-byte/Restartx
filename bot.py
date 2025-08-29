import os
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # server where slash cmds sync
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # channel for updates
PLACE_ID = int(os.getenv("PLACE_ID"))  # your game's placeId
UNIVERSE_ID = int(os.getenv("UNIVERSE_ID"))  # your game's universeId
WHITELIST = set(int(x) for x in os.getenv("WHITELIST", "").split(",") if x)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=commands.when_mentioned_or("/", "!"), intents=intents)
tree = bot.tree

sending_updates = False
session: aiohttp.ClientSession = None

# -------- Roblox API Helpers -------- #
async def get_game_stats():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()

    # Visits
    visits = 0
    async with session.get(f"https://games.roblox.com/v1/games?universeIds={UNIVERSE_ID}") as r:
        if r.status == 200:
            data = await r.json()
            if "data" in data and len(data["data"]) > 0:
                visits = data["data"][0]["visits"]

    # Players across all servers
    players = 0
    cursor = ""
    while True:
        url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?sortOrder=Asc&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        async with session.get(url) as r:
            if r.status != 200:
                break
            data = await r.json()
            for server in data.get("data", []):
                players += server.get("playing", 0)
            cursor = data.get("nextPageCursor")
            if not cursor:
                break
        await asyncio.sleep(1)  # ✅ avoid hammering Roblox

    return visits, players

# -------- Background Loop -------- #
@tasks.loop(seconds=65)
async def post_stats():
    if not sending_updates:
        return
    try:
        visits, players = await get_game_stats()
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            milestone = visits + 100
            await channel.send(
                f"📊 **Game Stats**\n"
                f"👥 Players Online: **{players}**\n"
                f"👣 Total Visits: **{visits}**\n"
                f"🎯 Next Milestone: **{milestone}**"
            )
    except Exception as e:
        print(f"Error posting stats: {e}")

# -------- Whitelist Helpers -------- #
def is_whitelisted_slash(interaction: discord.Interaction) -> bool:
    return interaction.user.id in WHITELIST

# -------- Slash Commands -------- #
@tree.command(name="start", description="Start updates")
async def start_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    global sending_updates
    sending_updates = True
    await interaction.response.defer()
    await interaction.followup.send("✅ Stats updates **started**!")

@tree.command(name="stop", description="Stop updates")
async def stop_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    global sending_updates
    sending_updates = False
    await interaction.response.defer()
    await interaction.followup.send("🛑 Stats updates **stopped**.")

@tree.command(name="restart", description="Restart updates")
async def restart_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    global sending_updates
    sending_updates = False
    await asyncio.sleep(1)
    sending_updates = True
    await interaction.response.defer()
    await interaction.followup.send("🔄 Stats updates **restarted**.")

@tree.command(name="whitelist", description="Add a user to whitelist")
async def whitelist_slash(interaction: discord.Interaction, user: discord.User):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    WHITELIST.add(user.id)
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(f"✅ {user.mention} added to whitelist.", ephemeral=True)

@tree.command(name="helpme", description="Show available commands")
async def helpme_slash(interaction: discord.Interaction):
    if not is_whitelisted_slash(interaction):
        await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    cmds = ["/start", "/stop", "/restart", "/whitelist <user>", "/helpme"]
    await interaction.followup.send("📖 **Available Commands:**\n" + "\n".join(cmds), ephemeral=True)

# -------- Startup -------- #
@bot.event
async def on_ready():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    post_stats.start()
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Logged in as {bot.user}")

async def close_session():
    global session
    if session and not session.closed:
        await session.close()

bot.run(TOKEN)
