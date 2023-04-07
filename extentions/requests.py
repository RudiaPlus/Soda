import discord
from discord import app_commands
import json
import os
from extentions import JSTTime, log, config
from extentions.aclient import client
import asyncio

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
request_json = "jsons/requests.json"
operators_json = "jsons/operators.json"
doctors_json = "jsons/doctors.json"

class RequestComplete(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "リクエストに応える",
                       custom_id = "button_respond",
                       style = discord.ButtonStyle.success,
                       emoji = "✅")
    async def button_respond(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            requests = await request_load()
            original_message = interaction.message
            
            for index in range(len(requests)):
                if requests[index]["messageID"] == original_message.id:
                    request_id = requests[index]["id"]
                    request_user = client.get_user(requests[index]["userID"])
            
            if interaction.user.id == request_user.id:
                await interaction.followup.send("リクエストを終了するには「リクエスト終了」ボタンを押してください！", ephemeral = True)
            
            else:
                doctor = await doctor_check(interaction.user)
                if doctor is None:
                    await interaction.followup.send("リクエストに応える前に、「/doctorname set」でドクターネームを登録する必要があります！\nコマンドの実行は<#1093795949064757288>でお願いします！", ephemeral = True)
                else:
                    user_embed = discord.Embed(title = "リクエストへの応答が来ました！",
                                               description = f"[あなたのリクエスト]({original_message.jump_url})に{interaction.user.mention}さんが応じてくれるようです！\n戦友に追加していない場合サポートを借りれませんので、これを機に戦友になるのは如何でしょうか？\n・ドクターネーム：{doctor}",
                                               url = original_message.jump_url)
                    user_embed.set_footer(text=f"作戦を無事に終わらせたら、リンク先から「リクエスト終了」ボタンを押してリクエストの終了をお願いします！")
                    user_embed.set_author(name = interaction.user.name, icon_url = interaction.user.avatar)
                    thread = await original_message.create_thread(name = f"{request_user.name}さんのリクエスト #{request_id}", auto_archive_duration = 1440)
                    await thread.send(content = request_user.mention, embed = user_embed)
                    await interaction.followup.send("スレッドを作成しました！リクエスト者との会話にご利用ください！", ephemeral=True)

        except Exception as e:
            logger.error(f"[button_respond]にてエラー：{e}")
  
    @discord.ui.button(label = "リクエスト終了",
                       custom_id = "button_complete",
                       style = discord.ButtonStyle.danger)
    async def button_complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        requests = await request_load()
        original_message = interaction.message
            
        for index in range(len(requests)):
            if requests[index]["messageID"] == original_message.id:
                request_id = requests[index]["id"]
                request_user = client.get_user(requests[index]["userID"])
                
        if interaction.user.id == request_user.id:
            embed = discord.Embed(title = "リクエストを終了しました！", description = "この投稿は5秒後に削除されます！")
            embed.set_author(name = interaction.user.name, icon_url = interaction.user.avatar)
            await original_message.edit(embed = embed, view = None)
            await request_complete(request_id)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
        else:
            await interaction.followup.send("リクエストはリクエストした本人だけが終了できます！", ephemeral = True)

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
            await doctors_write(doctors)
            return("success")
    if include == False:
        return

async def doctor_add(user, name, tag):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            doctors[index] = {"id": user.id, "name": name, "tag": tag, "full": f"Dr. {name}#{tag}"}
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
    request = {"id": id, "userID": user.id, "operator": operator, "skill": skill, "skillLevel": skillLevel, "module": module, "module_rank": module_rank, "lv": lv}
    
    channel = client.get_channel(config.request)
    embed = discord.Embed(title = f"サポートオペレーター「{operator}」のリクエスト",
                          description = f"**希望条件**\n{lv_name}\n・{skill}/{skillLevel}\n{module_name}\n\n**是非ご協力ください！**")
    embed.set_author(name = user.name, icon_url = user.avatar)
    message = await channel.send(embed = embed, view = RequestComplete())
    request["messageID"] = message.id
    requests.append(request)
    await request_write(requests)

async def request_complete(id):
    requests = await request_load()
    for index in range(len(requests)):
        if requests[index]["id"] == id:
            del requests[index]
            break
    await request_write(requests)