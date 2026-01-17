import os
import random
import traceback
from re import match
from unicodedata import normalize
from typing import Dict, List, Optional, Tuple

import discord

from extentions import log, recruit, supportrequest, multiplayertool
from extentions.aclient import client
from extentions.config import config

logger = log.setup_logger()
MODULE_DIR = os.path.abspath(__file__ + "/../")

# Common UI timeouts (seconds)
TIMEOUT_SHORT = 300

# ------------------------------
# Helpers / Utilities (internal)
# ------------------------------

async def load_operators() -> Dict[str, dict]:
    return await supportrequest.operators_load()

def load_operator_emojis() -> Dict[str, str]:
    return supportrequest.operator_emoji_load()

def find_operators_by_fragment(operators: Dict[str, dict], fragment: str) -> List[str]:
    """Return operator names containing the fragment (case-insensitive)."""
    fragment_lower = fragment.lower()
    matched: List[str] = []
    for op in operators.values():
        name = op.get("name", "")
        if fragment_lower in name.lower():
            matched.append(name)
    return matched

def build_skills_dict(operator_dict: dict) -> Dict[int, str]:
    skills = operator_dict.get("skills", {}) or {}
    return {int(k): v for k, v in skills.items() if v is not None}

def format_skill_list(skills: Dict[int, str]) -> str:
    text = ""
    for i in skills:
        text += f"- スキル{i}: {skills[i]}\n"
    return text

def parse_doctorname_parts(doctorname: str) -> Tuple[str, str]:
    index_sharp = doctorname.find("#")
    index_dr = doctorname.find("Dr. ")
    before_name = doctorname[index_dr + 4:index_sharp]
    before_number = doctorname[index_sharp + 1:]
    return before_name, before_number

def is_valid_level_for_rarity(rarity: int, level: int) -> bool:
    if rarity <= 1:
        return False
    if rarity == 2 and level > 55:
        return False
    if rarity == 3 and level > 70:
        return False
    if rarity == 4 and level > 80:
        return False
    if rarity == 5 and level > 90:
        return False
    return True

class YaminabeRepeat(discord.ui.View):
    def __init__(self, label, operators_in_class):
        self.operators_in_class = operators_in_class
        self.label = label
        self.classes = config.operator_classes
        super().__init__(timeout = TIMEOUT_SHORT)
        
    @discord.ui.button(label = "引き直す", style = discord.ButtonStyle.primary, emoji = "↩️")
    async def yaminabe_repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await yaminabe(interaction = interaction, label = self.label, operators_in_class=self.operators_in_class)

class YaminabeSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TIMEOUT_SHORT)
        self.classes = config.operator_classes
        for button_class in self.classes:
            self.add_buttons(button_class)

    def add_buttons(self, label):
        button_classes = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
        
        async def button_callback(interaction: discord.Interaction):
            operators_in_class = await return_operators_in_class(label, self.classes)
            await yaminabe(interaction=interaction, label = label, operators_in_class=operators_in_class)
        
        button_classes.callback = button_callback
        self.add_item(button_classes)

async def return_operators_in_class(operator_class: str, classes: dict):
    #先鋒等の職業名に一致するオペレーターのリストを返します。
    operators = await supportrequest.operators_load()
    operators_in_class = []
    for index in operators:
        if operators[index]["class"] == classes[operator_class]:
            operators_in_class.append(operators[index]["name"])
    return operators_in_class

async def yaminabe(interaction: discord.Interaction, label, operators_in_class):

    selected_operator = random.choice(operators_in_class)

    operator_emojis = supportrequest.operator_emoji_load()
    
    embed = discord.Embed(title = "闇鍋招集", color = discord.Color.blue())
    embed.add_field(name = f"招集する{label}オペレーター", value = f"{operator_emojis[selected_operator]}{selected_operator}")
    await interaction.response.edit_message(embed = embed, view = YaminabeRepeat(label = label, operators_in_class=operators_in_class))            

class AddInformationModal(discord.ui.Modal):
    def __init__(self, title, doctorname):
        super().__init__(title = title, timeout=None)
        if doctorname:
            self.before_doctorname = doctorname
            index_sharp = doctorname.find("#")
            index_dr = doctorname.find("Dr. ")
            before_name = doctorname[index_dr+4:index_sharp]
            before_number = doctorname[index_sharp+1:]
            self.name_input = discord.ui.TextInput(label = f"名前(IDの前半, 「Dr. 」を含まない)の変更 変更前「{before_name}」", custom_id = "name_input")
            self.add_item(self.name_input)
            self.number_input = discord.ui.TextInput(label = f"番号(IDの後半, 「#」を含まない)の変更 変更前「{before_number}」", custom_id = "number_input")
            self.add_item(self.number_input)
        else:
            self.before_doctorname = None
            self.name_input = discord.ui.TextInput(label = "名前(IDの前半, 「Dr. 」を含まない)の追加 例「Rudia」", custom_id = "name_input")
            self.add_item(self.name_input)
            self.number_input = discord.ui.TextInput(label = "番号(IDの後半, 「#」を含まない)の追加 例「2726」", custom_id = "number_input")
            self.add_item(self.number_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True, thinking=True)
        tag = self.number_input.value
        name = self.name_input.value
        num_tag = normalize("NFKC", tag)

        if len(tag) > 6 or len(name) > 16:
            embed = discord.Embed(title="ドクター情報登録 - エラー",
                                    description=f"入力された名前「{name}」が長すぎます！\nなにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=discord.Color.red())
            await interaction.followup.send(ephemeral = True, embed=embed)
            return

        if tag.isdecimal() is False or match(r"[0-9]{1,6}$", num_tag) is None:
            embed = discord.Embed(title="ドクター情報登録 - エラー",
                                    description="番号部分には数字のみを入力してください！\nなにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=discord.Color.red())
            await interaction.followup.send(ephemeral = True, embed=embed)
            return
        
        added = await supportrequest.doctor_add(interaction.user, name, num_tag)
        embed = discord.Embed(title="ドクター情報の登録が完了しました！",
                                description=f"新しく設定された貴方のドクターネームは「{added}」です！",
                                color=discord.Color.green())

        embed.set_author(name=interaction.user.display_name,
                            icon_url=interaction.user.display_avatar)
        embed.set_footer(text="変更する場合はもう一度「ドクター名登録」、登録を削除する場合は「/doctorname delete」コマンドをご利用ください")
        await interaction.followup.send(ephemeral= True, embed = embed)
        
        
    async def on_errror(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("エラーが発生しました！")
        traceback.print_exception(type(error), error, error.__traceback__)
        
class OperatorSearchModal(discord.ui.Modal, title="Wiki検索"):
    name_input = discord.ui.TextInput(label = "検索するオペレーター名")
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        operators = await supportrequest.operators_load()
        operator_emojis = supportrequest.operator_emoji_load()
        name = self.name_input.value.lower()
        matched_operators = []
        for op_dict in operators.values():
            if name in op_dict["name"].lower():
                matched_operators.append(op_dict["name"])

        if not matched_operators:
            embed = discord.Embed(title = "Wiki検索 - 不明なオペレーター", description=f"「{name}」を含むオペレーターが見つかりませんでした。", color = discord.Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
            return
        sorted_operators = sorted(matched_operators, key = len)[0:9]
        logger.info(f"{name}を検索しました。結果: {sorted_operators}")   
        embeds = []
        if len(matched_operators) > 9:
            embed = discord.Embed(title = "Wiki検索 - 最大数超過", description=f"「{name}」を含むオペレーターが10名以上居ます。\n検索結果の上位9名のみ表示します。", color = discord.Color.red())
            embeds.append(embed)
        else:
            embed = discord.Embed(title = "Wiki検索", description = f"「{name}」を含むオペレーターは{len(matched_operators)}名います。", color = discord.Color.green())
            embeds.append(embed)
        for operator_name in sorted_operators:
            url = f"https://arknights.wikiru.jp/?{operator_name}"
            embed = discord.Embed(title = f"検索結果 - {operator_emojis[operator_name]}{operator_name}", description=f"{operator_emojis[operator_name]}{operator_name}の詳細・評価: [有志Wiki]({url})", url = url, color = discord.Color.blue())
            embeds.append(embed)
        await interaction.followup.send(embeds = embeds, ephemeral=True)

class OperatorSelectButton(discord.ui.View):
    def __init__(self, operators: list, level: int, remarks: str, doctorname: str = None):
        super().__init__(timeout = 300)
        self.level = level
        self.remarks = remarks
        self.doctorname = doctorname
        for operator in operators:
            self.add_buttons(operator)
            
    def add_buttons(self, label):
        operator_emojis = supportrequest.operator_emoji_load()
        
        button_operator = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, emoji = operator_emojis[label])
        
        async def button_callback(interaction: discord.Interaction):
            
            operator = label
            operators = await supportrequest.operators_load()
            correct = 0
            for index in operators:
                if operators[index]["name"] == operator:
                    if operators[index]["rarity"] <= 1:
                        break
                    if operators[index]["rarity"] == 2 and self.level > 55:
                        break
                    if operators[index]["rarity"] == 3 and self.level > 70:
                        break
                    if operators[index]["rarity"] == 4 and self.level > 80:
                        break
                    if operators[index]["rarity"] == 5 and self.level > 90:
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

                    embed = discord.Embed(title=f"サポートオペレーター「{operator_emojis[operator]}{operator}」のリクエスト",
                                        description=f"スキルの選択をしてください\n{skill_name}")
                    embed.set_footer(text=f"入力した備考：{self.remarks}")
                    logger.info(f"{interaction.user.name}がリクエストを開始しました")
                    await interaction.response.edit_message(embed=embed, view=supportrequest.OperatorSkillButton(operators=operator_dic, skills=skills, operator=operator, lv=self.level, rarity = operators[index]["rarity"], remarks = self.remarks, doctorname = self.doctorname))
                    return
                
            if correct == 0:
                await interaction.response.send_message("正しいオペレーター名、またはレアリティごとの最大値を超えないレベルを入力してください！\nまた、☆1、☆2のオペレーターは対応していません！", ephemeral=True)
        
        button_operator.callback = button_callback
        self.add_item(button_operator)
            

class RequestSendModal(discord.ui.Modal, title = "サポートリクエスト"):
    name_input = discord.ui.TextInput(label = "リクエストするオペレーター(名前の一部のみでも可)", placeholder="アーミヤ")
    level_input = discord.ui.TextInput(label = "昇進2でのレベル条件(省略可、数字のみ)", required=False)
    doctorname_input = discord.ui.TextInput(label = "ドクターネーム(省略可、コミュニティツールで登録した場合はそちらが自動的に使われます)", placeholder="名前#0000", required = False)
    remarks_input = discord.ui.TextInput(label = "備考(省略可、潜在等のその他の条件があれば。スキルやモジュールは後から選択できます)", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        request_loaded = await supportrequest.request_load()
        for item in request_loaded:
            if item["userID"] == interaction.user.id:
                await interaction.followup.send(f"あなたは既にリクエストを送信しています！<#{config.request}>をご覧ください！")
                return
        operators = await supportrequest.operators_load()
        
        name = self.name_input.value.lower()
        if self.level_input.value and self.level_input.value.isdecimal() is False:
            embed = discord.Embed(title = "サポートリクエスト - エラー", description="レベル条件には数字のみを入力してください。", color = discord.Color.red())
            await interaction.followup.send(embed = embed)
            return
        
        level = int(self.level_input.value) if self.level_input.value else 0
        remarks = self.remarks_input.value if self.remarks_input.value else "無し"
        doctorname_from_data = await supportrequest.doctor_check(interaction.user)
        doctorname_split = doctorname_from_data[4:] if doctorname_from_data else None
        doctorname = self.doctorname_input.value if self.doctorname_input.value else doctorname_split
            
        matched_operators = []
        for op_dict in operators.values():
            if name in op_dict["name"].lower():
                matched_operators.append(op_dict["name"])
        
        if not matched_operators:
            embed = discord.Embed(title = "サポートリクエスト - 不明なオペレーター", description=f"「{name}」を含むオペレーターが見つかりませんでした。", color = discord.Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
            return
        sorted_operators = sorted(matched_operators, key = len)[0:5]
        logger.info(f"{name}を検索しました。結果: {sorted_operators}")
        embeds = []
        if len(matched_operators) > 3:
            embed = discord.Embed(title = "サポートリクエスト - 最大数超過", description=f"「{name}」を含むオペレーターが6名以上居ます。\n検索結果の上位5名のみ表示します。リクエストしたいオペレーターを選択してください。", color = discord.Color.red())
            embeds.append(embed)
        else:
            embed = discord.Embed(title = "サポートリクエスト - 検索結果", description = f"「{name}」を含むオペレーターは{len(matched_operators)}名います。リクエストしたいオペレーターを選択してください。", color = discord.Color.green())
            embeds.append(embed)
        
        await interaction.followup.send(embeds = embeds, view = OperatorSelectButton(operators=sorted_operators, level = level, remarks = remarks, doctorname = doctorname))
            

class ToolButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = None)
    
    #ツールの追加
    @discord.ui.button(label = "公開求人ツール", custom_id = "recruitbutton", style = discord.ButtonStyle.primary, emoji = "📄")
    async def recruitbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        selected_tags = []
        view = recruit.TagSelectView(selected_tags=selected_tags, all = True)
        
        embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")
        logger.info(f"{interaction.user.name}がrecruitbuttonを使用しました")
        await interaction.followup.send(embed = embed, view = view, ephemeral=True)
        
    @discord.ui.button(label= "サポートリクエスト", custom_id= "requestsupportbutton", style= discord.ButtonStyle.primary, emoji = "📮")
    async def requestsupportbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RequestSendModal())
        logger.info(f"{interaction.user.name}がrequestsupportbuttonを使用しました")
        
    @discord.ui.button(label = "ドクター情報登録", custom_id = "addinformationbutton", style = discord.ButtonStyle.primary, emoji = "📝")
    async def addinformationbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        doctorname = await supportrequest.doctor_check(user = interaction.user)
        if not doctorname:
            modal = AddInformationModal(title = "ドクター情報の新規登録", doctorname=None)
            await interaction.response.send_modal(modal)
        else:
            modal = AddInformationModal(title = f"ドクター情報({doctorname})の編集", doctorname = doctorname)
            await interaction.response.send_modal(modal)
        logger.info(f"{interaction.user.name}がaddinformationbuttonを使用しました")
        
    @discord.ui.button(label = "Wiki検索", custom_id="searchwikibutton", style = discord.ButtonStyle.primary, emoji = "🔎")
    async def searchwikibutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OperatorSearchModal())
        logger.info(f"{interaction.user.name}がsearchwikibuttonを使用しました")
    
    @discord.ui.button(label = "闇鍋招集", custom_id = "yaminabebutton", style = discord.ButtonStyle.primary, emoji = "🎲")
    async def yaminabebutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title = "闇鍋招集", description="招集したい職業を選択してください", color = discord.Color.blue())
        await interaction.response.send_message(embed = embed, view = YaminabeSelect(), ephemeral = True)
        logger.info(f"{interaction.user.name}がyaminabebuttonを使用しました")
        
    @discord.ui.button(label = "マルチプレイ募集", custom_id = "multicreate_tool", style = discord.ButtonStyle.primary, emoji = "🧑‍🤝‍🧑")
    async def multicreate_tool(self, interaction: discord.Interaction, button: discord.ui.Button):
        await multiplayertool.multi_create(interaction)
        logger.info(f"{interaction.user.name}がmulticreate_toolを使用しました")

@client.tree.command(name="tool_form", description = "ツールのチャットを送信します", guild = discord.Object(config.testserverid))
@discord.app_commands.describe(channelid = "フォームを送信するチャンネル デフォルトはあしたはこぶね/#ツール", edit = "新規送信ではなくメッセージの編集にしたい場合、そのメッセージのID")
async def tool_form(interaction: discord.Interaction, channelid: str = "1142491583757951036", edit: str = None):
    await interaction.response.defer(ephemeral = True)
    
    channelid = normalize("NFKC", channelid)
    if edit:
        message_to_edit = normalize("NFKC", edit)
    
    channel = await client.fetch_channel(channelid)
    embed = discord.Embed(title = "コミュニティツール", description = "下のボタンから私の便利ツールをご利用できます！", color = discord.Color.red())
    
    screenshot_recruit_channel = config.screenshot_recruit_channel_url
    request_channel = config.request_url
    multi_channel = client.get_channel(config.multiplay_request_channel)
    
    #ツールの説明
    embed.add_field(name = "・公開求人ツール", value = f">>> 公開求人のタグから獲得できるオペレーターを表示します。\nスクリーンショット認識ver → {screenshot_recruit_channel}", inline=False)
    embed.add_field(name = "・サポートリクエスト", value = f">>> サポートリクエストを送信します。\n詳しくは{request_channel}をご覧ください！", inline = False)
    embed.add_field(name = "・ドクター情報登録", value = ">>> アークナイツのホーム画面等から確認できるゲーム内ID(○○○○#0000の形式)をサーバーに登録し、「サポートリクエスト」への応答を可能にします。\n削除する場合、任意のチャンネルで ***/doctorname delete*** を実行してください。\n-# ※登録した情報はメンバー全員が閲覧できますのでご注意ください。", inline = False)
    embed.add_field(name = "・Wiki検索", value = ">>> オペレーターを検索し、詳細と評価が載っている有志Wikiのページを表示します。", inline = False)
    embed.add_field(name = "・闇鍋招集", value = ">>> 統合戦略でオペレーターを招集する際、職業ごとにランダムで選んでくれるツールです。", inline = False)
    embed.add_field(name = "・マルチプレイ募集 ", value = f">>> マルチプレイの募集を簡単に行えます！詳しくは{multi_channel.jump_url}をご覧ください！", inline = False)
    
    embed.set_author(name = "ロード", icon_url=client.user.avatar)
    if not edit:
        await channel.send(embed = embed, view = ToolButtons())
    else:
        message = await channel.fetch_message(message_to_edit)
        await message.edit(embed = embed, view = ToolButtons())
    
    await interaction.followup.send("完了しました！")
