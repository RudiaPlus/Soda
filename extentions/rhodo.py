import discord
from extentions import (responses, config, evjson, JSTTime, modmails, log,
                        maintenances, requests)
from extentions.aclient import client
import re
import datetime
import unicodedata
import os
import json
from discord import app_commands
from discord.ext import tasks
from typing import List

logger = log.setup_logger(__name__)


async def send_message(message, user_message):
    try:
        response = await responses.get_response(user_message, reset=False)
        logger.info(f"返信を取得しました「{response}」")

        if len(response) > 1900:
            await message.channel.send("文字数制限を超えてしまいました！すみませんがもう一度お願いします！")
        else:
            await message.channel.send(response)

    except Exception as e:
        logger.exception(f"[send_message]にてエラー：{e}")


def run_discord_bot():

    dir = os.path.abspath(__file__ + "/../")

    @client.event
    async def on_ready():
        logger.info("準備を始めます")
        try:
            doctorname = DoctorNameCommand(name="doctorname",
                                           description="ドクターネームに関するコマンド")
            client.tree.add_command(doctorname)
            synced = await client.tree.sync()
            await client.tree.sync(guild=config.testserverid)
            logger.info(f"{len(synced)}個のコマンドを同期しました。")
            client.add_view(requests.RequestComplete())
        except Exception as e:
            logger.exception(f"[on_ready]にて エラー：{e}")
        logger.info(f"{client.user} 、準備完了です！")

    @client.event
    async def setup_hook() -> None:
        morning.start()
        maintenances.maintenance_timer.start()
        logger.info("タスクを開始しました")

    class ModmailButton(discord.ui.View):

        @discord.ui.button(label="開始する",
                           style=discord.ButtonStyle.success,
                           emoji="✅")
        async def button_callback(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
            channel = client.get_channel(config.modchannnel)
            user = interaction.user
            if await modmails.modmail_queue(user) == "Ready":
                embed = discord.Embed(
                    title="あしたはこぶね・お問い合わせ",
                    description=
                    "お問い合わせありがとうございます！\nこのDMにメッセージを送ることで、スタッフとの会話を開始できます",
                    color=0x696969)
                embed.set_author(name="あしたはこぶねスタッフ",
                                 icon_url=config.server_icon)
                embed_mod = discord.Embed(
                    title="Modmailが開始されました！",
                    description=
                    f"ニックネーム : {user.display_name}\nid : {user.id}\nアカウント作成日 : {user.created_at}",
                    color=user.accent_color)
                embed_mod.set_author(name=user.name, icon_url=user.avatar.url)
                await channel.send(embed=embed_mod)
                if interaction.message.guild:
                    await user.send(embed=embed)
                    await interaction.response.send_message(
                        "DMをお送りしました。ご確認ください！", ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed)

            elif await modmails.modmail_queue(user) == "False":
                await interaction.response.send_message(
                    "DMを既にお送りしております。ご確認ください！", ephemeral=True)

            else:
                embed = discord.Embed(
                    title="あしたはこぶね・お問い合わせ",
                    description=
                    "お問い合わせありがとうございます！\n現在問い合わせが立て込んでおり、今すぐに会話を開始できない状態となっております。\n順番になり次第こちらから連絡致します。今しばらくお待ちください",
                    color=0x696969)
                embed.set_author(name="あしたはこぶねスタッフ",
                                 icon_url=config.server_icon)
                embed_mod = discord.Embed(
                    title="Modmailの予約が入りました！",
                    description=
                    f"ニックネーム : {user.display_name}\nid : {user.id}\nアカウント作成日 : {user.created_at}",
                    color=user.accent_color)
                embed_mod.set_author(name=user.name, icon_url=user.avatar.url)
                await channel.send(embed=embed_mod)
                if interaction.message.guild:
                    await user.send(embed=embed)
                    await interaction.response.send_message(
                        "DMをお送りしました。ご確認ください！", ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed)

    @client.tree.command(name="help",
                         description="現在実装されているコマンドの使い方を簡単に説明します！")
    async def help(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="コマンドヘルプ",
                              description="以下が現在実装されているコマンドになります。",
                              color=0x696969)
        embed.add_field(
            name="「ドクターネーム」",
            value=
            "ゲーム内のドクターネーム(Dr.xxxx#0000の形のゲーム内ID)を紐づけします\n・**/doctorname set**：ドクターネームを登録/変更します\n・**/doctorname show**：指定した人のドクターネームを表示します\n・**/doctorname delete**：登録したドクターネームを削除します",
            inline=False)
        embed.add_field(
            name="「サポートリクエスト」",
            value=
            "チャンネルを使ってサポートオペレーターのリクエストができます。攻略に詰まったら是非使ってください！\n・**/request**：サポートのリクエストを送信します",
            inline=False)
        embed.add_field(
            name="「Modmail」",
            value="運営スタッフへの問い合わせが簡単にできます\n・**/modmail**：運営スタッフへの問い合わせを開始します",
            inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @client.tree.command(name="modmail",
                         description="サーバースタッフと会話を開始することが出来ます！お気軽にご利用ください！")
    async def modmail(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        embed = discord.Embed(
            title="あしたはこぶね・お問い合わせ",
            description="以下のボタンを押すと、スタッフとの会話が開始されます\nよろしいですか？",
            color=0x696969)
        embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
        await interaction.response.send_message(embed=embed,
                                                ephemeral=True,
                                                view=ModmailButton())

    @client.tree.command(name="rechat",
                         description="for dev only",
                         guild=config.testserverid)
    async def rechat(interaction: discord.Interaction):
        if interaction.user == client.user:
            return

        await interaction.response.defer()
        await responses.get_response("reset", reset=True)
        await interaction.followup.send("完了しました！")

    @client.tree.command(name="imakita",
                         description="指定された時間内の会話をロードが適当に要約します。出来ない時もあります",
                         guild=config.testserverid)
    async def imakita(interaction: discord.Interaction, hour: int):
        if interaction.user == client.user:
            return

        await interaction.response.defer()
        end_time = JSTTime.timeJST("raw")
        start_time = end_time - datetime.timedelta(hours=hour)

        text = []
        async for message in interaction.channel.history(limit=None,
                                                         after=start_time,
                                                         before=end_time):
            text.append(f"{message.author}: {message.content}")

        reply = discord.Embed(title=f"{str(hour)}時間分の会話を要約しました",
                              description=await
                              responses.imakita_response(text),
                              color=0x00ffff)
        await interaction.followup.send(embed=reply)

    @client.tree.command(name="maintenance",
                         description="メンテナンスについて",
                         guild=config.testserverid)
    async def maintenance(interaction: discord.Interaction,
                          number: int,
                          status: str,
                          name: str = "メンテナンス"):
        if status == "ruined":
            await interaction.response.defer()
            await maintenances.maintenance_ruined(number)
            await interaction.followup.send("完了しました")

        if status == "end":
            await interaction.response.defer()
            await maintenances.maintenance_end(name, number)
            await interaction.followup.send("完了しました")

    @client.tree.command(name="remind",
                         description="リマインドを送ります",
                         guild=config.testserverid)
    async def remind(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        await morning()
        await interaction.followup.send("完了しました！")

    @client.tree.command(name="eventtest",
                         description="イベントリストのテストを行います",
                         guild=config.testserverid)
    async def eventtest(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        events = evjson.eventget()
        await interaction.followup.send(events)

    @client.tree.command(name="send",
                         description="dev only",
                         guild=config.testserverid)
    async def send(interaction: discord.Interaction, text: str):
        channel = client.get_channel(1019202000975560754)
        await channel.send(text)
        await interaction.response.send_message("完了しました")

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
                    title=f"サポートオペレーター「{self.operator}」のリクエスト",
                    description=f"「{label}」を選択しました。\nスキルレベルの条件を選んでください。")
                await interaction.response.edit_message(
                    embed=embed,
                    view=OperatorLevelButton(self.operators, label,
                                             self.operator, self.lv))

            button_skill.callback = button_callback
            self.add_item(button_skill)

        @discord.ui.button(label="キャンセル",
                           row=1,
                           style=discord.ButtonStyle.danger)
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
                    description=
                    f"「{self.skill}/レベル7」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}"
                )
                await interaction.response.edit_message(
                    embed=embed,
                    view=OperatorModuleButton(self.skill, skillLevel,
                                              self.operator, self.modules,
                                              self.lv))
            else:
                if self.lv == 0:
                    level = ""
                else:
                    level = f"昇進2/レベル{self.lv}"
                embed = discord.Embed(
                    title=f"サポートオペレーター「{self.operator}」のリクエスト",
                    description=
                    f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/レベル7\n"
                )
                #リクエスト
                await requests.send_request(user=interaction.user,
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
                    description=
                    f"「{self.skill}/特化3」を選択しました。\nモジュールに条件はありますか？\n{self.module_name}"
                )
                await interaction.response.edit_message(
                    embed=embed,
                    view=OperatorModuleButton(self.skill, skillLevel,
                                              self.operator, self.modules,
                                              self.lv))
            else:
                if self.lv == 0:
                    level = ""
                else:
                    level = f"昇進2/レベル{self.lv}"
                embed = discord.Embed(
                    title=f"サポートオペレーター「{self.operator}」のリクエスト",
                    description=
                    f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/特化3\n"
                )
                #リクエスト
                await requests.send_request(user=interaction.user,
                                            operator=self.operator,
                                            skill=self.skill,
                                            skillLevel=skillLevel,
                                            lv=self.lv)
                await interaction.response.edit_message(embed=embed, view=None)

        @discord.ui.button(label="キャンセル",
                           row=1,
                           style=discord.ButtonStyle.danger)
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
            button_module = discord.ui.Button(
                label=label, style=discord.ButtonStyle.primary)

            async def button_callback(interaction: discord.Interaction):
                embed = discord.Embed(
                    title=f"サポートオペレーター「{self.operator}」のリクエスト",
                    description=f"「{label}」を選択しました。\nモジュールランクの条件を選んでください。")
                await interaction.response.edit_message(
                    embed=embed,
                    view=OperatorModuleLevelButton(self.skill, self.skillLevel,
                                                   self.operator, label,
                                                   self.lv))

            button_module.callback = button_callback
            self.add_item(button_module)

        @discord.ui.button(label="無し",
                           row=1,
                           style=discord.ButtonStyle.secondary)
        async def none(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
            if self.lv == 0:
                level = ""
            else:
                level = f"昇進2/レベル{self.lv}"
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=
                f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n"
            )
            #リクエスト
            await requests.send_request(user=interaction.user,
                                        operator=self.operator,
                                        skill=self.skill,
                                        skillLevel=self.skillLevel,
                                        lv=self.lv)
            await interaction.response.edit_message(embed=embed, view=None)

        @discord.ui.button(label="キャンセル",
                           row=1,
                           style=discord.ButtonStyle.danger)
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
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=
                f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク1以上"
            )
            #リクエスト
            await requests.send_request(user=interaction.user,
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
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=
                f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク2以上"
            )
            #リクエスト
            await requests.send_request(user=interaction.user,
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
            embed = discord.Embed(
                title=f"サポートオペレーター「{self.operator}」のリクエスト",
                description=
                f"サポートのリクエストを送信しました！\n・{self.operator} {level}\n・{self.skill}/{self.skillLevel}\n・{self.module}/ランク3"
            )
            #リクエスト
            await requests.send_request(user=interaction.user,
                                        operator=self.operator,
                                        skill=self.skill,
                                        skillLevel=self.skillLevel,
                                        module=self.module,
                                        module_rank="ランク3",
                                        lv=self.lv)
            await interaction.response.edit_message(embed=embed, view=None)

        @discord.ui.button(label="キャンセル",
                           row=1,
                           style=discord.ButtonStyle.danger)
        async def cancel(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
            embed = discord.Embed(title=f"サポートオペレーター「{self.operator}」のリクエスト",
                                  description=f"リクエストをキャンセルしました。",
                                  color=0xf45d5d)
            await interaction.response.edit_message(embed=embed, view=None)

    async def operator_autocomplete(
            interaction: discord.Interaction,
            current: str) -> List[discord.app_commands.Choice[str]]:

        operators = await requests.operators_load()
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
        operators = await requests.operators_load()
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

                embed = discord.Embed(
                    title=f"サポートオペレーター「{operator}」のリクエスト",
                    description=f"スキルの選択をしてください\n{skill_name}")
                await interaction.followup.send(embed=embed,
                                                view=OperatorSkillButton(
                                                    operators=operator_dic,
                                                    skills=skills,
                                                    operator=operator,
                                                    lv=level),
                                                ephemeral=True)
        if correct == 0:
            await interaction.followup.send(
                "正しいオペレーター名、またはレアリティごとの最大値を超えないレベルを入力してください！", ephemeral=True)

    class DoctorNameCommand(app_commands.Group):

        @app_commands.command(
            name="set", description="ドクターネーム(Dr.****#0000の形のゲーム内ID)を登録/変更します")
        @discord.app_commands.describe(name="IDの前半の名前の部分(「Dr.」を含まない)",
                                       tag="IDの後半の数字の部分(「#」を含まない)")
        async def doctorname_set(self, interaction: discord.Interaction,
                                 name: str, tag: str):
            if interaction.user == client.user:
                return

            num_tag = unicodedata.normalize("NFKC", tag)

            if len(tag) > 6 or len(name) > 16:
                embed = discord.Embed(
                    title="名前が長すぎます！",
                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                    color=0xf45d5d)
                await interaction.response.send_message(embed=embed)
                return

            if tag.isdecimal() == False or re.match(r"[0-9]{1,6}$",
                                                    num_tag) is None:
                embed = discord.Embed(
                    title="タグは数字のみを入力してください！",
                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                    color=0xf45d5d)
                await interaction.response.send_message(embed=embed)
                return

            await interaction.response.defer()
            added = await requests.doctor_add(interaction.user, name, num_tag)
            embed = discord.Embed(
                title="ドクターネームの登録が完了しました！",
                description=f"新しく設定された貴方のドクターネームは「{added}」です！",
                color=0x5cb85c)

            embed.set_author(name=interaction.user.name,
                             icon_url=interaction.user.avatar)
            embed.set_footer(
                text=
                "変更する場合はもう一度「/doctorname_set」、登録を削除する場合は「/doctorname_delete」をご利用ください"
            )
            await interaction.followup.send(embed=embed)

        @app_commands.command(name="show", description="指定された人のドクターネームを表示します")
        @discord.app_commands.describe(
            user="ドクターネームを知りたい人を選択してください(設定していない人も選択肢に表示されます)")
        async def doctorname_show(self, interaction: discord.Interaction,
                                  user: discord.Member):
            if interaction.user == client.user:
                return
            await interaction.response.defer()
            name_full = await requests.doctor_check(user)
            if name_full is None:
                embed = discord.Embed(
                    title=f"ドクターネームが見つかりません！",
                    description=f"{user.name}さんのドクターネームは見つかりませんでした！",
                    color=0xf45d5d)
                embed.set_author(name=user.name, icon_url=user.avatar)
                await interaction.followup.send(embed=embed)
                return
            else:
                embed = discord.Embed(
                    title=f"ドクターネームが見つかりました！",
                    description=
                    f"{user.name}さんのドクターネームは以下になります！\n「{name_full}」",
                    color=0x5cb85c)
                embed.set_author(name=user.name, icon_url=user.avatar)
                await interaction.followup.send(embed=embed)

        @app_commands.command(name="delete",
                              description="設定された自分のドクターネームを削除します")
        async def doctorname_delete(self, interaction: discord.Interaction):
            if interaction.user == client.user:
                return
            await interaction.response.defer()
            delete = await requests.doctor_delete(interaction.user)
            if delete == "success":
                embed = discord.Embed(
                    title=f"ドクターネームの登録を削除しました！",
                    description=f"登録しなおす場合は、「/doctorname_set」をご利用ください！",
                    color=0x5cb85c)
                embed.set_author(name=interaction.user.name,
                                 icon_url=interaction.user.avatar)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title=f"ドクターネームの登録を削除できませんでした。",
                    description=
                    f"ドクターネームの登録を削除できませんでした！既に登録が削除されている場合があります！\nもし削除されているか確認したい場合は「/modmail」にてお問い合わせください！",
                    color=0xf45d5d)
                embed.set_author(name=interaction.user.name,
                                 icon_url=interaction.user.avatar)
                await interaction.followup.send(embed=embed, ephemeral=True)

    @client.tree.command(name="mainttest",
                         description="メンテナンスリストのテストを行います",
                         guild=config.testserverid)
    async def mainttest(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        maintenance = await maintenances.maintenance_list()
        await interaction.followup.send(maintenance)

        @client.event
        async def on_message(message):

            if message.author == client.user:
                return

            messageuser = await modmails.modmail_get_user()
            username = str(message.author)
            user_message = str(message.content)
            channel = str(message.channel)
            channelID = int(message.channel.id)

            if messageuser and message.channel.id == config.modchannnel:
                if message.content == "終了":
                    await modmails.modmail_finish(messageuser)
                else:
                    mail = discord.Embed(
                        title=f"【スタッフ】{message.author.name}からのメッセージ",
                        description=message.content)
                    mail.set_author(name="あしたはこぶねスタッフ",
                                    icon_url=config.server_icon)
                    await messageuser.send(embed=mail)

            if not message.guild:
                logger.info(f"{username}に「{user_message}」と言われました。")
                if message.author == messageuser:
                    channel = client.get_channel(config.modchannnel)
                    mail = discord.Embed(
                        title=f"{message.author.name}からのメッセージ",
                        description=message.content)
                    mail.set_footer(text="Modmailを終わらせるには「終了」と送信してください")
                    await channel.send(embed=mail)

                else:
                    mail = discord.Embed(
                        title="お問い合わせの場合は、/modmailをご利用ください！",
                        description=
                        "DMありがとうございます！\nスタッフと個別で会話をしたい場合は、コマンド/modmailをご利用ください！\n私とお話ししたい場合は、<#1072158278634713108>までどうぞ！"
                    )
                    mail.set_author(name="あしたはこぶねスタッフ",
                                    icon_url=config.server_icon)
                    await message.author.send(embed=mail)

            if channelID == config.chat:
                clean_message = re.sub('<.*?>', '', user_message)
                logger.info("返事をします")
                await send_message(message, clean_message)

            else:
                return

    @tasks.loop(time=config.morningtime)
    async def morning():
        try:
            logger.info("時間になりました。モーニングルーティンを始めます")

            if config.morning == True:
                events = evjson.eventget()
                eventcount = evjson.eventcount()
                maintenance = await maintenances.maintenance_list()
                channel = client.get_channel(config.announce)

                if eventcount[0] == 0:
                    if eventcount[3] != 0:
                        eventnow = "本日からイベントが開催されます！"
                    else:
                        eventnow = "本日は少し休める日ですね！"
                elif eventcount[0] == 1:
                    eventnow = f"\n・イベントが進行中です:sparkles: 頑張りましょう！"
                else:
                    eventnow = f"\n・本日は{eventcount[0]}個のイベントが進行中です:sparkles: 頑張りましょう！"

                if eventcount[1] == 0:
                    eventend = ""
                elif eventcount[1] == 1:
                    eventend = f"\n・終了したイベントがあります！ 報酬の受け取りを忘れずに！:eyes:"
                else:
                    eventend = f"\n・{eventcount[1]}個のイベントが終了しています。報酬の受け取りを忘れずに！:eyes:"

                if eventcount[2] == 0:
                    eventfuture = ""
                elif eventcount[2] == 1:
                    eventfuture = f"\n・開催予定のイベントがあります！ 楽しみですね！:star2:"
                else:
                    eventfuture = f"\n・{eventcount[2]}個のイベントがこの先やってきます！準備は出来ていますか？"

                if JSTTime.timeJST("weekday") == "日":
                    weekday = "\n・本日は日曜日です！ 殲滅作戦は終わらせましたか？"
                else:
                    weekday = ""

                json_name = "jsons/birthday.json"
                with open(os.path.join(dir, json_name), encoding="utf-8") as f:
                    birthday = json.load(f)
                    today = JSTTime.timeJST("m/d")
                    if today in birthday:
                        bdayop = f"\n・本日は{birthday[today]}が誕生日です:birthday: おめでとうございます！"
                    else:
                        bdayop = ""

                await channel.send(
                    f"<@&1076155144363851888>\nおはようございます:sunny: ロードです！  {eventnow}{eventend}{eventfuture}{weekday}{bdayop}"
                )

                for i in range(len(maintenance)):
                    embed = discord.Embed(title=maintenance[i]["name"],
                                          description=maintenance[i]["time"],
                                          color=0xf5b642)
                    embed.set_author(name="メンテナンス")
                    await channel.send(embed=embed)

                for i in range(len(events)):
                    if events[i]["dif"] == "present":
                        if events[i]["type"] == "CRISIS":
                            if events[i]["contractAdd"] == False:
                                try:
                                    link = events[i]["link"]
                                    eventpic = events[i]["pic"]
                                except Exception:
                                    pass

                                png_name = "images/contingencycontract.png"
                                file = discord.File(os.path.join(
                                    dir, png_name),
                                                    filename="image.png")
                                embed = discord.Embed(
                                    title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0x6d2727,
                                    url=link)
                                embed.set_author(
                                    name="危機契約",
                                    icon_url="attachment://image.png")
                                embed.add_field(name="・常設ステージ",
                                                value=events[i]["permStage"],
                                                inline=False)
                                embed.add_field(name="・本日のデイリーステージ",
                                                value=events[i]["todaysDaily"]
                                                ["stageName"],
                                                inline=False)
                                embed.add_field(
                                    name="・契約追加日",
                                    value=events[i]["contractAddTime"],
                                    inline=False)
                                embed.set_image(url=eventpic)
                                await channel.send(files=file, embed=embed)

                            else:
                                try:
                                    link = events[i]["link"]
                                    eventpic = events[i]["pic"]
                                except Exception:
                                    pass

                                png_name = "images/contingencycontract.png"
                                file = discord.File(os.path.join(
                                    dir, png_name),
                                                    filename="image.png")
                                embed = discord.Embed(
                                    title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0x6d2727,
                                    url=link)
                                embed.set_author(
                                    name="危機契約",
                                    icon_url="attachment://image.png")
                                embed.add_field(name="・常設ステージ",
                                                value=events[i]["permStage"],
                                                inline=False)
                                embed.add_field(name="・本日のデイリーステージ",
                                                value=events[i]["todaysDaily"]
                                                ["stageName"],
                                                inline=False)
                                embed.add_field(
                                    name="・契約が追加されています！",
                                    value="危機契約も後半戦です！一緒に頑張りましょう！！",
                                    inline=False)
                                embed.set_image(url=eventpic)
                                await channel.send(file=file, embed=embed)

                        elif events[i]["type"] == "SIDESTORY":
                            if events[i]["stageAdd"] == "True":
                                try:
                                    nextStageName = events[i]["nextStageName"]
                                    nextAddTime = events[i]["nextAddTime"]
                                    link = events[i]["link"]
                                    eventpic = events[i]["pic"]
                                except Exception:
                                    pass

                                embed = discord.Embed(
                                    title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0x24ab12,
                                    url=link)
                                embed.set_author(name="サイドストーリー")
                                embed.add_field(
                                    name=f"次のステージ追加 「{nextStageName}」",
                                    value=nextAddTime)
                                embed.set_image(url=eventpic)
                                await channel.send(embed=embed)
                            else:
                                try:
                                    link = events[i]["link"]
                                    eventpic = events[i]["pic"]
                                except Exception:
                                    pass

                                embed = discord.Embed(
                                    title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0x368ad9,
                                    url=link)
                                embed.set_author(name="サイドストーリー")
                                embed.set_image(url=eventpic)
                                await channel.send(embed=embed)

                        elif events[i]["type"] == "MINISTORY":
                            try:
                                link = events[i]["link"]
                                eventpic = events[i]["pic"]
                            except Exception:
                                pass

                            embed = discord.Embed(
                                title=events[i]["name"],
                                description=events[i]["time"],
                                color=0xCAC531,
                                url=link)
                            embed.set_author(name="オムニバスストーリー")
                            embed.set_image(url=eventpic)
                            await channel.send(embed=embed)

                        else:
                            embed = discord.Embed(
                                title=events[i]["name"],
                                description=events[i]["time"],
                                color=0xf29382)
                            embed.set_author(name="イベント")
                            await channel.send(embed=embed)

                    elif events[i]["dif"] == "past":
                        eventpic = events[i]["pic"]
                        rewardEndTime = events[i]["rewardEndTime"]
                        embed = discord.Embed(
                            title=events[i]["name"],
                            description=f"報酬受取期限：{rewardEndTime}",
                            color=0x454545)
                        embed.set_author(name="終了したイベント")
                        embed.set_image(url=eventpic)
                        await channel.send(embed=embed)

                    else:
                        eventpic = events[i]["pic"]
                        embed = discord.Embed(title=events[i]["name"],
                                              description=events[i]["time"],
                                              color=0xba80ea)
                        embed.set_author(name="開催予定のイベント")
                        embed.set_image(url=eventpic)
                        await channel.send(embed=embed)

            await responses.get_response("reset", reset=True)

            guild = client.get_guild(config.main_server)
            threads = guild.threads
            for index in range(len(threads)):
                if threads[index].parent.id == config.request and threads[
                        index].archived == True:

                    logger.info(f"「{threads[index].name}」を削除します。")
                    await threads[index].delete()

        except Exception as e:
            logger.exception(f"[morning]にてエラー：{e}")

    TOKEN = config.token
    client.run(TOKEN)
