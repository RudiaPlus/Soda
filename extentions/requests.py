import discord
from discord import app_commands
import json
import os
from extentions import JSTTime, log, config
from extentions.aclient import client

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
request_json = "jsons/requests.json"
operators_json = "jsons/operators.json"
doctors_json = "jsons/doctors.json"

class RequestComplete(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "リクエストに答える",
                       custom_id = "button_respond",
                       style = discord.ButtonStyle.success,
                       emoji = "✅")
    async def button_respond(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response("テスト")
  
    @discord.ui.button(label = "リクエスト終了",
                       custom_id = "button_complete",
                       style = discord.ButtonStyle.danger)
    async def button_complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed = None, view = None)

async def request_add(message):
    requests = await request_load()
    requests.append(message)
    
async def request_write(dic):
    with open(os.path.join(dir, request_json), "w", encoding = "UTF-8") as f:
        json.dump(dic, f, indent=2)
        logger.info(f"requests.jsonに新しく書き込みを行いました")
    
async def request_load():
    with open(os.path.join(dir, request_json), encoding = "UTF-8") as f:
        requests = json.load(f)
    return(requests)

async def operators_load():
    with open(os.path.join(dir, operators_json), encoding = "UTF-8") as f:
        operators = json.load(f)
    return(operators)

async def doctors_load():
    with open(os.path.join(dir, doctors_json), encoding = "UTF-8") as f:
        doctors = json.load(f)
    return(doctors)

async def doctors_write(dic):
    with open(os.path.join(dir, doctors_json), "w", encoding = "UTF-8") as f:
        json.dump(dic, f, indent = 2)
        logger.info(f"doctors.jsonに新しく書き込みを行いました")
        
async def doctor_check(user):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            name_full = doctors[index]["full"]
    if include == False:
        name_full = None
    return(name_full)

async def doctor_delete(user):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            del doctors[index]["full"]
            doctors_write(doctors)
            return("success")
    if include == False:
        return

async def doctor_add(user, name, tag):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            doctors[index] = {"id": user.id, "name": name, "tag": tag, "full": f"Dr.{name}#{tag}"}
    if include == False:
        doctors.append({"id": user.id, "name": name, "tag": tag, "full": f"Dr. {name}#{tag}"})
    await doctors_write(doctors)
    return(f"Dr. {name}#{tag}")

async def send_request(user, operator, skill, skillLevel, module: str = None, module_rank: str = None, lv: int = None):
    if module == None:
        module_name = ""
        module_rank = ""
    else:
        module_name = f"・{module}/{module_rank}"
    lv_name = "" if lv == None else f"・昇進2/レベル{lv}以上"
    requests = await request_load()
    id = 0 if not requests else (requests[-1]["id"] + 1)
    request = {"id": id, "operator": operator, "skill": skill, "skillLevel": skillLevel, "module": module, "module_rank": module_rank, "lv": lv}
    requests.append(request)
    channel = client.get_channel(config.request)
    embed = discord.Embed(title = f"サポートオペレーター「{operator}」のリクエスト",
                          description = f"**希望条件**\n{lv_name}\n・{skill}/{skillLevel}\n{module_name}\n\n**是非ご協力ください！**")
    embed.set_author(name = user.name, icon_url = user.avatar)
    await request_write(requests)

async def request_complete(id):
    requests = await request_load()
    for index in range(len(requests)):
        if requests[index]["id"] == id:
            del requests[index]
    await request_write(requests)