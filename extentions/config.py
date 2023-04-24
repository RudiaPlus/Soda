import discord
import datetime
import os

t_delta = datetime.timedelta(hours=9)
JST = datetime.timezone(t_delta, 'JST')

server_invite_link = "https://discord.gg/RgcbYFZfnm"
server_rule_link = "https://discord.com/channels/1018858818345631745/1018858818932842589/1018863690914729986"
community_guideline_link = "https://discord.com/guidelines"
main_server = int(1018858818345631745)
logging = True
token = os.environ["DISCORD_TOKEN"]
openAI_key = os.environ["OPENAI_API_KEY"]
testserverid = discord.Object(id=1059155328584908810)
chat = int(1072158278634713108)  #1072158278634713108
me = int(870729549833465917)
server_icon = "https://cdn.discordapp.com/icons/1018858818345631745/a_8025349dd827dee56db7088ef01ccae7.webp?size=1024"
announce = int(1081251314958344313)  #1081251314958344313
request = int(1093849433621401600) #1093849433621401600
morningtime = datetime.time(hour=6, minute=30, tzinfo=JST)
modchannnel = int(1073151183092457514)
moderatorchannel = int(1093777243601371157) #botmoderate
morning = True
command = False
speechChannel_1 = int(1018908115711836162)  #1018908115711836162
speechChannel_2 = int(1018908446176849992)