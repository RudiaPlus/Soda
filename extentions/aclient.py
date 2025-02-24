import discord
from discord import app_commands
from extentions import config
from typing import List


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
    
class VoiceModule(discord.Client):
    
    def __init__(self) -> None:

        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        intents.members = True
        intents.voice_states = True
        super().__init__(intents=intents)
        self.activity = discord.CustomActivity(name = "/joinで読み上げを開始します")
        self.status = discord.Status.online
    
    async def join_voice_channel(self, channel: discord.VoiceChannel):
        if self.voice_clients:
            await self.voice_clients[0].disconnect()
        channel_got = await self.fetch_channel(channel.id)
        await channel_got.connect()
        await self.change_presence(activity=discord.CustomActivity(name = f"読み上げ中　VC: {channel_got.name}"), status = discord.Status.idle)
    

client = Rhodolite()

voice_clients_list: List[VoiceModule] = []
for i in range(config.voice_clients):
    voice_client = VoiceModule()
    voice_clients_list.append(voice_client)