import discord
import datetime
import os

t_delta = datetime.timedelta(hours=9)
JST = datetime.timezone(t_delta, 'JST')

server_invite_link = "https://discord.gg/RgcbYFZfnm"
server_rule_link = "https://discord.com/channels/1018858818345631745/1018858818932842589/1018863690914729986"
community_guideline_link = "https://discord.com/guidelines"
main_server = 1018858818345631745
logging = True
token = os.environ["DISCORD_TOKEN"]
openAI_key = os.environ["OPENAI_API_KEY"]
testserverid = discord.Object(1059155328584908810)
chat = 1072158278634713108  #1072158278634713108
me = 870729549833465917
server_icon = "https://cdn.discordapp.com/icons/1018858818345631745/a_8025349dd827dee56db7088ef01ccae7.webp?size=1024"


announce = 1140326740158333048  #1081251314958344313
request = 1093849433621401600 #1093849433621401600

#tasks
morningtime = datetime.time(hour=4, minute=00, tzinfo=JST)
afternoontime = datetime.time(hour=10, minute=00, tzinfo=JST)
eveningtime = datetime.time(hour=16, minute=00, tzinfo=JST)
newdaytime = datetime.time(hour=0, minute=00, tzinfo=JST)


morning = True
command = False


#Role
administrator_role = 1019295385967149057
Moderator_role = 1093773233410547735

#channels
speechChannel_1 = 1018908115711836162  #1018908115711836162
speechChannel_2 = 1018908446176849992

moderatorchannel = 1093777243601371157 #botmoderate
modmail_save_channel = 1108480334024167514 #議事録

#categories
feedback_category = 1108189699715125268

#Voicechat
#アークナイツ1