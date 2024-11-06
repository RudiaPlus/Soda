import discord
from discord import app_commands


class Rhodolite(discord.Client):

  def __init__(self) -> None:

    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.guilds = True
    intents.members = True
    intents.voice_states = True
    super().__init__(intents=intents)
    self.tree = app_commands.CommandTree(self)
    self.activity = discord.Activity(type=discord.ActivityType.watching,
                                     name="DISCOVERED TERRA")

client = Rhodolite()