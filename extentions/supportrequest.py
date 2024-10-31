import discord
import json
import os
import datetime
from discord.ext import tasks
from extentions import JSTTime, log, config
from extentions.aclient import client
import asyncio
from typing import List

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")
request_json = "jsons/requests.json"
operators_json = "jsons/operators.json"
doctors_json = "jsons/doctors.json"

with open(os.path.join(dir, "jsons\\operator_emojis.json"), "r", encoding="utf-8") as f:
    operator_emojis = json.load(f)

class RequestConfirm(discord.ui.View):
    def __init__(self, original_message, request_index):
        super().__init__(timeout=300)
        self.original_message = original_message
        self.request_index = request_index

    @discord.ui.button(label="確認",
                       style=discord.ButtonStyle.success,
                       emoji="✅")
    async def button_confirm(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            requests = await request_load()

            for index in range(len(requests)):
                if requests[index]["messageID"] == self.original_message.id:
                    request_user = client.get_user(requests[index]["userID"])

            doctor = await doctor_check(interaction.user)

            if doctor is None:
                await interaction.followup.send("先に/doctorname setにてドクターネームの登録をお願いします！", ephemeral=True)
                return

            else:
                user_embed = discord.Embed(
                    title="リクエストへの応答が来ました！",
                    description=f"[あなたのリクエスト]({self.original_message.jump_url})に{interaction.user.mention}さんが応じてくれるようです！\n戦友に追加していない場合サポートを借りれませんので、戦友になっていない場合はこれを機に戦友になるのは如何でしょうか？\n- ドクターネーム：{doctor}",
                    url=self.original_message.jump_url)
                user_embed.set_footer(
                    text=f"作戦を無事に終わらせたら、リンク先から「リクエスト終了」ボタンを押してリクエストの終了をお願いします！")
                user_embed.set_author(
                    name=interaction.user.display_name, icon_url=interaction.user.display_avatar)

                thread = await self.original_message.create_thread(
                    name=f"{request_user.display_name}さんのリクエスト #{self.original_message.id}",
                    auto_archive_duration=1440)
                
                channel = self.original_message.channel
                thread_create_message = await channel.fetch_message(channel.last_message_id)
                if thread_create_message.id != self.original_message.id and thread_create_message.author.id != config.me:
                    await thread_create_message.delete()
                else:
                    logger.warn("スレッド作成のメッセージが送信されていませんので、削除しませんでした。")

                requests = await request_load()
                requests[self.request_index]["respondUserID"] = interaction.user.id
                await request_write(requests)

                await thread.send(content=request_user.mention, embed=user_embed)
                await interaction.delete_original_response()
                await interaction.followup.send("スレッドを作成しました！リクエスト者との会話にご利用ください！", embed=None, ephemeral=True)

        except Exception as e:
            logger.error(f"[button_confirm]にてエラー：{e}")

    @discord.ui.button(label="キャンセル",
                       style=discord.ButtonStyle.danger)
    async def button_cancel(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await interaction.response.edit_message(content="キャンセルしました。", embed=None, view=None)


class RequestComplete(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="リクエストに応える",
                       custom_id="button_respond",
                       style=discord.ButtonStyle.success,
                       emoji="✅")
    async def button_respond(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            requests = await request_load()
            original_message = interaction.message

            for index in range(len(requests)):
                if requests[index]["messageID"] == original_message.id:
                    request_index = index
                    request_user = client.get_user(requests[index]["userID"])
                    if requests[index]["respondUserID"]:
                        await interaction.followup.send("申し訳ありません。既にリクエストに応えている方が居ます！", ephemeral=True)
                        return

            if interaction.user.id == request_user.id:
                await interaction.followup.send(
                    "リクエストを終了するには「リクエスト終了」ボタンを押してください！", ephemeral=True)

            else:
                embed = discord.Embed(title="リクエストに応えます！",
                                      description=f"[こちらのリクエスト]({original_message.jump_url})に応えます！よろしいですか？")
                await interaction.followup.send(embed=embed, view=RequestConfirm(original_message=original_message, request_index=request_index), ephemeral=True)

        except Exception as e:
            logger.error(f"[button_respond]にてエラー：{e}")

    @discord.ui.button(label="リクエスト終了",
                       custom_id="button_complete",
                       style=discord.ButtonStyle.danger)
    async def button_complete(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        await interaction.response.defer()
        requests = await request_load()
        original_message = interaction.message

        for index in range(len(requests)):
            if requests[index]["messageID"] == original_message.id:
                request_id = requests[index]["id"]
                messageID = requests[index]["messageID"]
                request_user = client.get_user(requests[index]["userID"])
                respond_user = None
                if requests[index]["respondUserID"]:
                    respond_user = client.get_user(
                        requests[index]["respondUserID"])
                    operator = requests[index]["operator"]
                    skill = requests[index]["skill"]

                    respond_embed = discord.Embed(title="リクエストに応えていただきありがとうございます！",
                                                  description=f"{request_user.display_name}さんのサポートリクエストが終了しました！ ご協力頂きありがとうございます！\nリクエストされていたオペレーター：{operator_emojis[operator]}{operator} | {skill}")
                    respond_embed.set_author(
                        name=request_user.display_name, icon_url=request_user.display_avatar)
                    respond_embed.set_footer(text="これからも「あしたはこぶね」を宜しくお願い致します！")
                    await respond_user.send(embed=respond_embed)

        if interaction.user.id == request_user.id or interaction.user.guild_permissions.manage_messages == True:
            embed = discord.Embed(title="リクエストを終了しました！",
                                  description="この投稿は5秒後に削除されます！")
            embed.set_author(name=interaction.user.display_name,
                             icon_url=interaction.user.display_avatar)
            await original_message.edit(embed=embed, view=None)

            await request_complete(request_id)
            thread = interaction.guild.get_thread(messageID)
            await asyncio.sleep(5)
            if respond_user:
                await thread.delete()
            await interaction.delete_original_response()
        else:
            await interaction.followup.send("リクエストはリクエストした本人だけが終了できます！",
                                            ephemeral=True)


async def request_write(dic):
    with open(os.path.join(dir, request_json), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"requests.jsonに新しく書き込みを行いました")


async def request_load():
    with open(os.path.join(dir, request_json), encoding="UTF-8") as f:
        requests = json.load(f)
    return (requests)


async def operators_load():
    with open(os.path.join(dir, operators_json), encoding="UTF-8") as f:
        operators = json.load(f)
    return (operators)


async def doctors_load():
    with open(os.path.join(dir, doctors_json), encoding="UTF-8") as f:
        doctors = json.load(f)
    return (doctors)


async def doctors_write(dic):
    with open(os.path.join(dir, doctors_json), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"doctors.jsonに新しく書き込みを行いました")


async def doctor_check(user: discord.User):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            name_full = doctors[index]["full"]
    if include == False:
        name_full = None
    return (name_full)


async def doctor_delete(user):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            del doctors[index]
            await doctors_write(doctors)
            return ("success")
    if include == False:
        return


async def doctor_add(user, name, tag):
    doctors = await doctors_load()
    include = False
    for index in range(len(doctors)):
        if doctors[index]["id"] == user.id:
            include = True
            doctors[index] = {
                "id": user.id,
                "name": name,
                "tag": tag,
                "full": f"Dr. {name}#{tag}"
            }
    if include == False:
        doctors.append({
            "id": user.id,
            "name": name,
            "tag": tag,
            "full": f"Dr. {name}#{tag}"
        })
    await doctors_write(doctors)
    return (f"Dr. {name}#{tag}")


async def send_request(user, operator, skill = None, skill_level = None, module: str = None, module_rank: str = None, lv: int = 0, rarity = None, remarks = None, doctorname = None):
    if module == None:
        module_name = ""
        module_rank = ""
    else:
        module_name = f"- ***{module}***/{module_rank}\n"
        
    if remarks == None or remarks =="無し":
        remarks_name = ""
    else:
        remarks_name = f"- 備考: {remarks}\n"
        
    if skill == None:
        skill_name = ""
        skill_level = ""

    else:
        skill_name = f"- ***{skill}***/{skill_level}\n"
        
    lv_name = "" if lv == 0 else f"- **昇進2**/レベル**{lv}以上**\n"
    if rarity == 2:
        lv_name = "" if lv == 0 else f"- **昇進1**/レベル**{lv}以上**\n"
        
    if doctorname == None:
        doctorname_display = "ドクターネーム：**未設定**\n"
    else:
        doctorname_display = f"ドクターネーム：**{doctorname}**\n" 
    requests = await request_load()
        
    id = 0 if not requests else (requests[-1]["id"] + 1)
    request = {
        "id": id,
        "userID": user.id,
        "operator": operator,
        "skill": skill,
        "skillLevel": skill_level,
        "module": module,
        "module_rank": module_rank,
        "lv": lv,
        "remarks": remarks,
        "doctorname": doctorname,
        "messageID": None,
        "respondUserID": None
    }

    channel = client.get_channel(config.request)
    embed = discord.Embed(
        title=f"サポートオペレーター「{operator_emojis[operator]}{operator}」のリクエスト",
        description=f"リクエスト者：{user.mention}\n{doctorname_display}\n__**希望条件**__\n{lv_name}{skill_name}{module_name}{remarks_name}\n**是非ご協力ください！**"
    )
    embed.set_author(name=user.display_name, icon_url=user.display_avatar)
    embed.set_footer(
        text="- 対象のオペレーターをサポートに出せる場合、「リクエストに応える」ボタンを押してください！\n- 【リクエスト者のみ可能】リクエストを終了したい場合は「リクエスト終了」ボタンを押してください！"
    )
    message = await channel.send(embed=embed, view=RequestComplete())
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


class OperatorSkillButton(discord.ui.View):

    def __init__(self, operators, skills, operator, lv, rarity, remarks = None, doctorname = None):
        self.lv = lv
        self.rarity = rarity
        self.operators = operators
        self.operator = operator
        self.remarks = remarks if remarks else "無し"
        self.doctorname = doctorname
        super().__init__(timeout=300)
        for i in skills:
            self.add_buttons(f"スキル{i}：{skills[i]}")

    def add_buttons(self, label):
        button_skill = discord.ui.Button(label=label,
                                         style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            
            if self.rarity == 2:
                if self.lv == 0:
                    level = ""
                else:
                    level = f"昇進1/レベル{self.lv}"
                embed = discord.Embed(
                    title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト", description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {label}/レベル7\n")
                embed.set_footer(text=f"入力した備考：{self.remarks}")
                # リクエスト
                await send_request(user=interaction.user,
                                operator=self.operator,
                                skill=label,
                                skill_level="レベル7",
                                lv=self.lv,
                                rarity = 2,
                                remarks = self.remarks)
                await interaction.response.edit_message(embed=embed, view=None)
            
            else:
                embed = discord.Embed(
                    title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト", description=f"「{label}」を選択しました。\nスキルレベルの条件を選んでください。")
                embed.set_footer(text=f"入力した備考：{self.remarks}")
                await interaction.response.edit_message(embed=embed, view=OperatorLevelButton(self.operators, label, self.operator, self.lv, remarks = self.remarks, doctorname = self.doctorname))

        button_skill.callback = button_callback
        
        self.add_item(button_skill)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorLevelButton(discord.ui.View):

    def __init__(self, operators, skill, operator, lv, remarks = None, doctorname = None):
        self.operator = operator
        self.lv = lv
        self.skill = skill
        self.remarks = remarks if remarks else "無し"
        self.doctorname = doctorname
        super().__init__(timeout=300)
        self.modules = {
            k: v
            for k, v in operators["modules"].items() if v is not None
        }
        self.module_name = ""
        for n in self.modules:
            self.module_name += f"- モジュール{n}: {self.modules[n]}\n"

    @discord.ui.button(label="レベル7", style=discord.ButtonStyle.primary)
    async def lv7(self, interaction: discord.Interaction,
                  button: discord.ui.Button):
        skillLevel = "レベル7"
        if self.modules:
            embed = discord.Embed(
                title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                description=f"「{self.skill}/レベル7」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}")
            embed.set_footer(text=f"入力した備考：{self.remarks}")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleButton(self.skill, skillLevel, self.operator,
                                          self.modules, self.lv, remarks = self.remarks, doctorname = self.doctorname))
        else:
            if self.lv == 0:
                level = ""
            else:
                level = f"昇進2/レベル{self.lv}"
            embed = discord.Embed(
                title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト", description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/レベル7\n")
            embed.set_footer(text=f"入力した備考：{self.remarks}")
            # リクエスト
            await send_request(user=interaction.user,
                               operator=self.operator,
                               skill=self.skill,
                               skill_level=skillLevel,
                               lv=self.lv,
                               remarks = self.remarks,
                               doctorname = self.doctorname)
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="特化3", style=discord.ButtonStyle.success)
    async def m3(self, interaction: discord.Interaction,
                 button: discord.ui.Button):
        skillLevel = "特化3"
        if self.modules:
            embed = discord.Embed(
                title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                description=f"「{self.skill}/特化3」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}")
            embed.set_footer(text=f"入力した備考：{self.remarks}")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleButton(self.skill, skillLevel, self.operator,
                                          self.modules, self.lv, remarks = self.remarks, doctorname = self.doctorname))
        else:
            if self.lv == 0:
                level = ""
            else:
                level = f"昇進2/レベル{self.lv}"
            embed = discord.Embed(
                title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト", description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/特化3\n")
            embed.set_footer(text=f"入力した備考：{self.remarks}")
            # リクエスト
            await send_request(user=interaction.user,
                               operator=self.operator,
                               skill=self.skill,
                               skill_level=skillLevel,
                               lv=self.lv,
                               remarks = self.remarks, 
                               doctorname = self.doctorname)
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorModuleButton(discord.ui.View):

    def __init__(self, skill, skillLevel, operator, modules, lv, remarks = None, doctorname = None):
        self.operator = operator
        self.lv = lv
        self.skill = skill
        self.skillLevel = skillLevel
        self.modules = modules
        self.remarks = remarks if remarks else "無し"
        self.doctorname = doctorname
        super().__init__(timeout=300)

        for n in modules:
            self.add_buttons(f"モジュール{n}：{modules[n]}")

    def add_buttons(self, label):
        button_module = discord.ui.Button(label=label,
                                          style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                description=f"「{label}」を選択しました。\nモジュールランクの条件を選んでください。")
            embed.set_footer(text=f"入力した備考：{self.remarks}")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleLevelButton(self.skill, self.skillLevel,
                                               self.operator, label, self.lv, remarks = self.remarks, doctorname = self.doctorname))

        button_module.callback = button_callback
        self.add_item(button_module)

    @discord.ui.button(label="無し", row=1, style=discord.ButtonStyle.secondary)
    async def none(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/{self.skillLevel}\n")
        embed.set_footer(text=f"入力した備考：{self.remarks}")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skill_level=self.skillLevel,
                           lv=self.lv,
                           remarks = self.remarks, 
                           doctorname = self.doctorname)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorModuleLevelButton(discord.ui.View):

    def __init__(self, skill, skillLevel, operator, module, lv, remarks = None, doctorname = None):
        self.operator = operator
        self.skill = skill
        self.skillLevel = skillLevel
        self.module = module
        self.lv = lv
        self.remarks = remarks if remarks else "無し"
        self.doctorname = doctorname
        super().__init__(timeout=300)

    @discord.ui.button(label="ランク1以上", style=discord.ButtonStyle.primary)
    async def mod1(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/{self.skillLevel}\n- {self.module}/ランク1以上")
        embed.set_footer(text=f"入力した備考：{self.remarks}")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skill_level=self.skillLevel,
                           module=self.module,
                           module_rank="ランク1以上",
                           lv=self.lv,
                           remarks = self.remarks, 
                           doctorname = self.doctorname)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="ランク2以上", style=discord.ButtonStyle.primary)
    async def mod2(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/{self.skillLevel}\n- {self.module}/ランク2以上")
        embed.set_footer(text=f"入力した備考：{self.remarks}")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skill_level=self.skillLevel,
                           module=self.module,
                           module_rank="ランク2以上",
                           lv=self.lv,
                           remarks = self.remarks, 
                           doctorname = self.doctorname)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="ランク3", style=discord.ButtonStyle.primary)
    async def mod3(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n- {self.operator} {level}\n- {self.skill}/{self.skillLevel}\n- {self.module}/ランク3")
        embed.set_footer(text=f"入力した備考：{self.remarks}")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skill_level=self.skillLevel,
                           module=self.module,
                           module_rank="ランク3",
                           lv=self.lv,
                           remarks = self.remarks, 
                           doctorname = self.doctorname)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[self.operator]}{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


async def operator_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:

    operators = await operators_load()
    name_list = []
    for index in operators:
        name_list.append(operators[index]["name"])
    choices = name_list
    return [
        discord.app_commands.Choice(name=choice, value=choice)
        for choice in choices if current.lower() in choice.lower()
    ][:25]

async def delete_old_request():
    
    request_list = await request_load()
    for item in request_list:
        request_message: discord.TextChannel = await client.get_channel(item["messageID"])
        if request_message.threads:
            time_delta = datetime.datetime.now() - request_message.threads[0].created_at
            if time_delta.days > 3:
                await request_complete(item["id"])
                await request_message.threads[0].delete()
                await request_message.delete()
                request_user = client.get_user(item["userID"])

                respond_user = client.get_user(
                    item["respondUserID"])
                operator = item["operator"]
                skill = item["skill"]

                respond_embed = discord.Embed(title="リクエストに応えていただきありがとうございます！",
                                                description=f"リクエストから一定時間が経ったため、{request_user.display_name}さんのサポートリクエストを終了しました！ ご協力頂きありがとうございます！\nリクエストされていたオペレーター：{operator_emojis[operator]}{operator} | {skill}")
                respond_embed.set_author(
                    name=request_user.display_name, icon_url=request_user.display_avatar)
                respond_embed.set_footer(text="これからも「あしたはこぶね」を宜しくお願い致します！")
                await respond_user.send(embed=respond_embed)
                
                requester_embed = discord.Embed(title="リクエストを終了しました！",
                                                description=f"リクエストから一定時間が経ったため、{request_user.display_name}さんのサポートリクエストを終了しました！\nリクエストされていたオペレーター：{operator_emojis[operator]}{operator} | {skill}")
                respond_embed.set_author(
                    name=request_user.display_name, icon_url=request_user.display_avatar)
                requester_embed.set_footer(text="これからも「あしたはこぶね」を宜しくお願い致します！")
                await request_user.send(embed=requester_embed)
            


@client.tree.command(
    name="request",
    description="サポートのリクエストを送信します。詳しくはチャンネル「#サポートリクエスト」のピン留めメッセージをご覧ください")
@discord.app_commands.describe(operator="リクエストするオペレーター",
                               level="リクエストするオペレーターのレベル(最大昇進で数字のみ、任意)",
                               remarks = "リクエストするときの備考(潜在など)")
@discord.app_commands.autocomplete(operator=operator_autocomplete)
async def support_request(interaction: discord.Interaction,
                          operator: str,
                          level: int = 0,
                          remarks: str = None):
    if interaction.user == client.user:
        return
    await interaction.response.defer(ephemeral=True)
    remarks = remarks if remarks else "無し"
    operators = await operators_load()
    correct = 0
    for index in operators:
        if operators[index]["name"] == operator:
            if operators[index]["rarity"] <= 1:
                break
            if operators[index]["rarity"] == 2 and level > 55:
                break
            if operators[index]["rarity"] == 3 and level > 70:
                break
            if operators[index]["rarity"] == 4 and level > 80:
                break
            if operators[index]["rarity"] == 5 and level > 90:
                break

            operator_dic = operators[index]
            correct = 1

            skills = {
                k: v
                for k, v in operator_dic["skills"].items() if v is not None
            }
            skill_name = ""
            for i in skills:
                skill_name += f"- スキル{i}: {skills[i]}\n"
            requests = await request_load()
            for item in requests:
                if item["userID"] == interaction.user.id:
                    await interaction.followup.send(f"あなたは既にリクエストを送信しています！<#{config.request}>をご覧ください！")
                    return

            embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[operator]}{operator}」のリクエスト",
                                  description=f"スキルの選択をしてください\n{skill_name}")
            embed.set_footer(text=f"入力した備考：{remarks}")
            logger.info(f"{interaction.user.name}がコマンド/requestを使用しました")
            await interaction.followup.send(embed=embed, view=OperatorSkillButton(operators=operator_dic, skills=skills, operator=operator, lv=level, rarity = operators[index]["rarity"], remarks = remarks), ephemeral=True)
            return
    if correct == 0:
        await interaction.followup.send(
            "正しいオペレーター名、またはレアリティごとの最大値を超えないレベルを入力してください！\nまた、☆1、☆2のオペレーターは対応していません！", ephemeral=True)
