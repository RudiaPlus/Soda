import discord
import datetime
import os

t_delta = datetime.timedelta(hours=9)
JST = datetime.timezone(t_delta, 'JST')

token = os.environ["DISCORD_TOKEN"]
openAI_key = os.environ["OPENAI_API_KEY"]
testserverid = discord.Object(id=1059155328584908810)
chat = int(1072158278634713108)  #1072158278634713108
me = int(870729549833465917)
server_icon = "https://cdn.discordapp.com/icons/1018858818345631745/039c77dd10811cb8e193c8e0cd4be453.webp?size=1024"
announce = int(1081251314958344313)  #1081251314958344313
morningtime = datetime.time(hour=6, minute=30, tzinfo=JST)
modchannnel = int(1073151183092457514)
morning = True
command = False
speechChannel_1 = int(1018908115711836162)  #1018908115711836162
speechChannel_2 = int(1018908446176849992)