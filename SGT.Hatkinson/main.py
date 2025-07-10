import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from config.config import BotConfig

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bot.config = BotConfig()  # Attacher BotConfig au bot

@bot.event
async def on_ready():
    print(f'Bot connecté : {bot.user}')
    print(f'Intents enabled: {bot.intents}')
    try:
        synced = await bot.tree.sync()
        print(f'Synchronisé {len(synced)} commande(s)')
        print(f'Registered prefix commands: {[cmd.name for cmd in bot.commands]}')
    except Exception as e:
        print(f'Erreur lors de la synchronisation des commandes : {e}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f'Received message: {message.content} from {message.author} in channel {message.channel.id}')
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    print(f"Erreur de commande pour {ctx.command} par {ctx.author} ({ctx.author.id}) : {error}")
    try:
        await ctx.send(f"Erreur lors de l'exécution de la commande : {error}")
    except Exception as e:
        print(f"Erreur lors de l'envoi du message d'erreur : {e}")

async def load_extensions():
    extensions = [
        'cogs.message_cog',
        'cogs.webhook_cog'
    ]
    print(f"Loaded extensions before loading: {list(bot.extensions.keys())}")
    for extension in extensions:
        try:
            print(f"Attempting to load extension: {extension}")
            await bot.load_extension(extension)
            print(f"Extension {extension} loaded successfully")
        except Exception as e:
            print(f'Erreur lors du chargement de l\'extension {extension}: {e}')
    print(f"Loaded extensions after loading: {list(bot.extensions.keys())}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f'Erreur lors du démarrage du bot : {e}')