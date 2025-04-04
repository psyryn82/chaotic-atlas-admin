import discord
from discord.ext import commands

TOKEN = "your-token-here"
bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="rcon")
async def rcon(ctx, command):
    await ctx.send(f"Running RCON command: {command}")

bot.run(TOKEN)