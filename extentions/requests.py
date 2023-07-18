import discord
from discord import app_commands
import json
import os
from extentions import JSTTime, log, config
from extentions.aclient import client
import asyncio
from typing import List

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
request_json = "jsons/requests.json"
operators_json = "jsons/operators.json"
doctors_json = "jsons/doctors.json"


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
                    description=f"[あなたのリクエスト]({self.original_message.jump_url})に{interaction.user.mention}さんが応じてくれるようです！\n戦友に追加していない場合サポートを借りれませんので、戦友になっていない場合はこれを機に戦友になるのは如何でしょうか？\n・ドクターネーム：{doctor}",
                    url=self.original_message.jump_url)
                user_embed.set_footer(
                    text=f"作戦を無事に終わらせたら、リンク先から「リクエスト終了」ボタンを押してリクエストの終了をお願いします！")
                user_embed.set_author(
                    name=str(interaction.user), icon_url=interaction.user.avatar)

                thread = await self.original_message.create_thread(
                    name=f"{request_user.name}さんのリクエスト #{self.original_message.id}",
                    auto_archive_duration=1440)

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
                                                  description=f"{str(request_user)}さんのサポートリクエストが終了しました！ ご協力頂きありがとうございます！\nリクエストされていたオペレーター：{operator} | {skill}")
                    respond_embed.set_author(
                        name=str(request_user), icon_url=request_user.avatar)
                    respond_embed.set_footer(text="これからも宜しくお願い致します！")
                    await respond_user.send(embed=respond_embed)

        if interaction.user.id == request_user.id or interaction.user.guild_permissions.manage_messages == True:
            embed = discord.Embed(title="リクエストを終了しました！",
                                  description="この投稿は5秒後に削除されます！")
            embed.set_author(name=interaction.user.name,
                             icon_url=interaction.user.avatar)
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


async def doctor_check(user):
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


async def send_request(user, operator, skill, skillLevel, module: str = None, module_rank: str = None, lv: int = None):
    if module == None:
        module_name = ""
        module_rank = ""
    else:
        module_name = f"・{module}/{module_rank}"
    lv_name = "" if lv == None else f"・昇進2/レベル{lv}以上"
    requests = await request_load()
    id = 0 if not requests else (requests[-1]["id"] + 1)
    request = {
        "id": id,
        "userID": user.id,
        "operator": operator,
        "skill": skill,
        "skillLevel": skillLevel,
        "module": module,
        "module_rank": module_rank,
        "lv": lv,
        "messageID": None,
        "respondUserID": None
    }

    channel = client.get_channel(config.request)
    embed = discord.Embed(
        title=f"サポートオペレーター「{operator}」のリクエスト",
        description=f"リクエスト者：{user.mention}\n\n**希望条件**\n{lv_name}\n・{skill}/{skillLevel}\n{module_name}\n\n**是非ご協力ください！**"
    )
    embed.set_author(name=str(user), icon_url=user.avatar)
    embed.set_footer(
        text="・対象のオペレーターをサポートに出せる場合、「リクエストに応える」ボタンを押してください！\n・【リクエスト者のみ可能】リクエストを終了したい場合は「リクエスト終了」ボタンを押してください！"
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

    def __init__(self, operators, skills, operator, lv):
        self.lv = lv
        self.operators = operators
        self.operator = operator
        super().__init__(timeout=300)
        for i in skills:
            self.add_buttons(f"スキル{i}：{skills[i]}")

    def add_buttons(self, label):
        button_skill = discord.ui.Button(label=label,
                                         style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト", description=f"「{label}」を選択しました。\nスキルレベルの条件を選んでください。")
            await interaction.response.edit_message(embed=embed, view=OperatorLevelButton(self.operators, label, self.operator, self.lv))

        button_skill.callback = button_callback
        self.add_item(button_skill)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorLevelButton(discord.ui.View):

    def __init__(self, operators, skill, operator, lv):
        self.operator = operator
        self.lv = lv
        self.skill = skill
        super().__init__(timeout=300)
        self.modules = {
            k: v
            for k, v in operators["modules"].items() if v is not None
        }
        self.module_name = ""
        for n in self.modules:
            self.module_name += f"・モジュール{n}: {self.modules[n]}\n"

    @discord.ui.button(label="レベル7", style=discord.ButtonStyle.primary)
    async def lv7(self, interaction: discord.Interaction,
                  button: discord.ui.Button):
        skillLevel = "レベル7"
        if self.modules:
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=f"「{self.skill}/レベル7」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleButton(self.skill, skillLevel, self.operator,
                                          self.modules, self.lv))
        else:
            if self.lv == 0:
                level = ""
            else:
                level = f"昇進2/レベル{self.lv}"
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト", description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/レベル7\n")
            # リクエスト
            await send_request(user=interaction.user,
                               operator=self.operator,
                               skill=self.skill,
                               skillLevel=skillLevel,
                               lv=self.lv)
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="特化3", style=discord.ButtonStyle.success)
    async def m3(self, interaction: discord.Interaction,
                 button: discord.ui.Button):
        skillLevel = "特化3"
        if self.modules:
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=f"「{self.skill}/特化3」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleButton(self.skill, skillLevel, self.operator,
                                          self.modules, self.lv))
        else:
            if self.lv == 0:
                level = ""
            else:
                level = f"昇進2/レベル{self.lv}"
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト", description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/特化3\n")
            # リクエスト
            await send_request(user=interaction.user,
                               operator=self.operator,
                               skill=self.skill,
                               skillLevel=skillLevel,
                               lv=self.lv)
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorModuleButton(discord.ui.View):

    def __init__(self, skill, skillLevel, operator, modules, lv):
        self.operator = operator
        self.lv = lv
        self.skill = skill
        self.skillLevel = skillLevel
        self.modules = modules
        super().__init__(timeout=300)

        for n in modules:
            self.add_buttons(f"モジュール{n}：{modules[n]}")

    def add_buttons(self, label):
        button_module = discord.ui.Button(label=label,
                                          style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=f"「{label}」を選択しました。\nモジュールランクの条件を選んでください。")
            await interaction.response.edit_message(
                embed=embed,
                view=OperatorModuleLevelButton(self.skill, self.skillLevel,
                                               self.operator, label, self.lv))

        button_module.callback = button_callback
        self.add_item(button_module)

    @discord.ui.button(label="無し", row=1, style=discord.ButtonStyle.secondary)
    async def none(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skillLevel=self.skillLevel,
                           lv=self.lv)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"リクエストをキャンセルしました。",
                              color=0xf45d5d)
        await interaction.response.edit_message(embed=embed, view=None)


class OperatorModuleLevelButton(discord.ui.View):

    def __init__(self, skill, skillLevel, operator, module, lv):
        self.operator = operator
        self.skill = skill
        self.skillLevel = skillLevel
        self.module = module
        self.lv = lv
        super().__init__(timeout=300)

    @discord.ui.button(label="ランク1以上", style=discord.ButtonStyle.primary)
    async def mod1(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク1以上")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skillLevel=self.skillLevel,
                           module=self.module,
                           module_rank="ランク1以上",
                           lv=self.lv)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="ランク2以上", style=discord.ButtonStyle.primary)
    async def mod2(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク2以上")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skillLevel=self.skillLevel,
                           module=self.module,
                           module_rank="ランク2以上",
                           lv=self.lv)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="ランク3", style=discord.ButtonStyle.primary)
    async def mod3(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if self.lv == 0:
            level = ""
        else:
            level = f"昇進2/レベル{self.lv}"
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                              description=f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク3")
        # リクエスト
        await send_request(user=interaction.user,
                           operator=self.operator,
                           skill=self.skill,
                           skillLevel=self.skillLevel,
                           module=self.module,
                           module_rank="ランク3",
                           lv=self.lv)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="キャンセル", row=1, style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
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


@client.tree.command(
    name="request",
    description="サポートのリクエストを送信します。詳しくはチャンネル「#サポートリクエスト」のピン留めメッセージをご覧ください")
@discord.app_commands.describe(operator="リクエストするオペレーター",
                               level="リクエストするオペレーターのレベル(最大昇進で数字のみ、任意)")
@discord.app_commands.autocomplete(operator=operator_autocomplete)
async def support_request(interaction: discord.Interaction,
                          operator: str,
                          level: int = 0):
    if interaction.user == client.user:
        return
    await interaction.response.defer(ephemeral=True)
    operators = await operators_load()
    correct = 0
    for index in operators:
        if operators[index]["name"] == operator:
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
                skill_name += f"・スキル{i}: {skills[i]}\n"

            embed = discord.Embed(title=f"サポートオペレーター「{operator}」のリクエスト",
                                  description=f"スキルの選択をしてください\n{skill_name}")
            await interaction.followup.send(embed=embed, view=OperatorSkillButton(operators=operator_dic, skills=skills, operator=operator, lv=level), ephemeral=True)
    if correct == 0:
        await interaction.followup.send(
            "正しいオペレーター名、またはレアリティごとの最大値を超えないレベルを入力してください！", ephemeral=True)
