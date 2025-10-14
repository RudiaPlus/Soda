import itertools
import json
import os
from difflib import get_close_matches

import cv2
import discord
import re
from PIL import Image

from extentions import log, supportrequest, JSTTime
from extentions.aclient import client
from extentions.aOCR import ocr
from extentions.config import config

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")
image_dir = os.path.join(dir, "images")
operators_json = "jsons/operators.json"

possible_tag_list = config.tagList

tag_select = discord.ui.Select(placeholder = "タグを選択してください")
tag_rarity_list = []
tag_prof_list = []
tag_range_list = []
tag_type_list = []

TOTAL_CHARS_LIMIT = 5500
EMBED_FIELDS_LIMIT = 25
FIELD_VALUE_LIMIT = 1000
MAX_EMBEDS_PER_MESSAGE = 10
ZERO_WIDTH_SPACE = "\u200b"

for tag in config.tag_rarity:
    tag_rarity = discord.SelectOption(label = tag, value = tag)
    tag_rarity_list.append(tag_rarity)
for tag in config.tag_profession:
    tag_prof = discord.SelectOption(label = tag, value = tag)
    tag_prof_list.append(tag_prof)
for tag in config.tag_range:
    tag_range = discord.SelectOption(label = tag, value = tag)
    tag_range_list.append(tag_range)
for tag in config.tag_type:
    tag_type = discord.SelectOption(label = tag, value = tag)
    tag_type_list.append(tag_type)
    
#create operators_list

operators_list = []

async def operators_list_refresh():
    global operators_list
    recruitList = config.dynamic["recruit_list"]
    with open(os.path.join(dir, operators_json), "r", encoding="UTF-8") as f:
        operators = json.load(f)
        
    operators_list = []
        
    for index in operators:
        if operators[index]["name"] in recruitList:
            dict_add = {"name": operators[index]["name"], "rarity": operators[index]["rarity"], "tags": operators[index]["tags"]}
            operators_list.append(dict_add)

async def find_common_tags(reference_tags, operators):
    
    all_combinations = []
    for r in range(1, len(reference_tags) + 1):
        combinations = itertools.combinations(reference_tags, r)
        all_combinations.extend(combinations)
    
    matching_combinations = {}
    
    for combination in all_combinations:
        if len(combination) > 3:
            continue
        combination_set = frozenset(combination)
        for operator in operators:
            matchtags = set(operator["tags"]) & combination_set
            
            if matchtags:
                
                matchtags_str = ", ".join(matchtags)
                
                if (operator["rarity"] == 5 and "上級エリート" not in combination_set) or (operator["name"] == "アーミヤ"):
                    continue
                
                if matchtags_str not in matching_combinations:
                    matching_combinations[str(matchtags_str)] = {"tags": list(matchtags), "operators": []}
                
                if operator not in matching_combinations[matchtags_str]["operators"]:
                    matching_combinations[str(matchtags_str)]["operators"].append(operator)
        
        for result in matching_combinations.values():
            result["operators"] = sorted(result["operators"], key = lambda x: x["rarity"])
    
    for tag in matching_combinations:
        rarity = 99 #99 means only 1 star
        for operator in matching_combinations[tag]["operators"]:
            rarity = operator["rarity"] if rarity > operator["rarity"] and operator["rarity"] != 0 else rarity
        matching_combinations[tag]["min_rarity"] = rarity
        
    sorted_match = sorted(matching_combinations.values(), key = lambda item: (-item["min_rarity"], len(item["operators"])))
    return sorted_match 

async def output_results(selected_tags):
    logger.debug(f"selected_tags type: {type(selected_tags)}")
    try:
        result_operators = await find_common_tags(reference_tags=selected_tags, operators = operators_list)
        
        goodresult_list = ""
        
        for result in result_operators:

            tag_rarity = result["min_rarity"]
            
            tag_str = " ".join(result["tags"])
            
            
            if ("ロボット" in result["tags"]) or tag_rarity > 2:
                tag_rarity = 0 if tag_rarity == 99 else tag_rarity
                goodresult_list += f"{tag_str}: ☆{tag_rarity+1}確定\n"
        
        logger.info(f"公開求人シミュレートを行います：{selected_tags}")        
        return result_operators, goodresult_list
    except Exception as e:
        logger.exception(f"[output_results]にてエラー：{e}")

def get_embed_length(embed: discord.Embed) -> int:
    """Embedオブジェクトの現在の総文字数を計算します。"""
    length = len(embed.title or "") + len(embed.description or "")
    if embed.footer:
        length += len(embed.footer.text or "")
    if embed.author:
        length += len(embed.author.name or "")
    for field in embed.fields:
        length += len(field.name or "") + len(field.value or "")
    return length

async def result_embed_maker(result_list: list, all: bool) -> list:
    """
    結果リストからDiscordの制限を遵守したEmbedのリストを生成します。(最終改善版)
    文字数オーバーの際はフィールド追加を中止し、分割フィールド名を空に見せます。
    """
    # === STEP 1: 表示するフィールドのコンテンツをすべて事前に生成する ===

    if all:
        title = "獲得できる全てのオペレーター"
        show_list = result_list
        use_emoji = False
    else:
        title = "獲得できる高レアなオペレーター"
        show_list = [r for r in result_list if ("ロボット" in r["tags"] or r["min_rarity"] > 2)]
        use_emoji = True
    
    operator_emojis = supportrequest.operator_emoji_load()

    if not show_list and not all:
        embed = discord.Embed(title=title, color=discord.Color.blue())
        embed.add_field(
            name="該当タグ無し",
            value="☆4以上のオペレーターを確定で引ける組み合わせはありません。\n全ての組み合わせを見る場合、「全てのタグを表示する」ボタンを押してください。"
        )
        return [embed]

    field_contents = []
    for tag in show_list:
        field_name = " ".join(tag["tags"])
        
        operator_strings = []
        for ope in tag["operators"]:
            name = ope["name"]
            rarity = ope["rarity"]
            if use_emoji:
                ope_str = f"☆{rarity+1}{operator_emojis.get(name, '')}{name} "
            else:
                ope_str = f"☆{rarity+1}{name} "
            operator_strings.append(ope_str)
        
        if not operator_strings:
            continue
        
        current_chunk = ""
        is_first_chunk = True
        for op_str in operator_strings:
            if len(current_chunk) + len(op_str) > FIELD_VALUE_LIMIT:
                name_to_add = field_name if is_first_chunk else ZERO_WIDTH_SPACE
                field_contents.append((name_to_add, current_chunk))
                is_first_chunk = False
                current_chunk = op_str
            else:
                current_chunk += op_str
        
        if current_chunk:
            name_to_add = field_name if is_first_chunk else ZERO_WIDTH_SPACE
            field_contents.append((name_to_add, current_chunk))

    # === STEP 2: 生成したフィールドを制限に合わせてEmbedに詰めていく ===
    
    embeds = []
    current_embed = discord.Embed(title=title, color=discord.Color.blue())

    # 新しいEmbedが作られる際のタイトルのテンプレート

    for name, value in field_contents:
        # ---- チェックポイント ----
        # 1. 現在のEmbedにフィールドを追加できるか？ (フィールド数と文字数)
        can_add_to_current = (
            len(current_embed.fields) < EMBED_FIELDS_LIMIT and
            get_embed_length(current_embed) + len(name) + len(value) <= TOTAL_CHARS_LIMIT
        )

        if not can_add_to_current:
            # 現在のEmbedに追加できない場合、新しいEmbedを作成する
            if current_embed.fields:
                embeds.append(current_embed)

            # 2. Embedの最大数に達していないか？
            if len(embeds) >= MAX_EMBEDS_PER_MESSAGE:
                logger.warning(f"Embedが{MAX_EMBEDS_PER_MESSAGE}個の上限に達したため、処理を中断しました。")
                embeds[0].title = f"{title} (一部のみ表示)"
                return embeds

            current_embed = discord.Embed(title="(続き)", color=discord.Color.blue())

        # 3.【最重要】このフィールドを追加すると、メッセージ全体の総文字数上限を超えるか？
        total_chars_so_far = sum(get_embed_length(e) for e in embeds)
        predicted_total_chars = total_chars_so_far + get_embed_length(current_embed) + len(name) + len(value)

        if predicted_total_chars > TOTAL_CHARS_LIMIT:
            logger.warning("次のフィールドを追加すると総文字数を超えるため、処理を中断します。")
            embeds[0].title = f"{title} (一部のみ表示)"
            return embeds

        # 全てのチェックをクリアしたので、フィールドを追加
        current_embed.add_field(name=name, value=value, inline=False)
        
    # ループ終了後、作業中のEmbedが残っていればリストに追加
    if current_embed.fields and len(embeds) < MAX_EMBEDS_PER_MESSAGE:
        embeds.append(current_embed)

    return embeds

class TagUndoOnly(discord.ui.View):
    def __init__(self, selected_tags: list, all: bool, rare: bool = False, undo: bool = True):
        self.selected_tags = selected_tags
        self.all = all
        self.rare = rare
        self.undo = undo
        super().__init__(timeout=300)
        
        if undo is True:
            self.add_back_button()
        
        if self.all is True and self.rare is True:
            self.add_rare_only_button()
        elif self.all is False:
            self.add_show_all_button()
            
    async def on_timeout(self):
        if hasattr(self, "message") is False or self.message is None:
            return
        try:
            await self.message.channel.fetch_message(self.message.id)
        except Exception:
            return
            
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)
        
    def add_show_all_button(self):
        button_show_all = discord.ui.Button(label = "全てのタグを表示する", style = discord.ButtonStyle.primary, emoji = "▶️")
        
        async def button_show_all_callback(interaction: discord.Interaction):
            self.all = True
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            else:
                self.rare = False
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagUndoOnly(self.selected_tags,all=self.all,rare = self.rare, undo = self.undo)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
            
            view.message = await interaction.original_response()
        
        button_show_all.callback = button_show_all_callback
        self.add_item(button_show_all)
            
    def add_rare_only_button(self):
        button_rare_only = discord.ui.Button(label = "高レア確定タグのみ表示する", style = discord.ButtonStyle.primary, emoji = "🔽")
        
        async def button_rare_only_callback(interaction: discord.Interaction):
            self.all = False
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            else:
                self.rare = False
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagUndoOnly(self.selected_tags,all=self.all, rare = self.rare, undo = self.undo)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
            
            view.message = await interaction.original_response()
        
        button_rare_only.callback = button_rare_only_callback
        self.add_item(button_rare_only)
    
    def add_back_button(self):
        back_button = discord.ui.Button(label = "戻る", style = discord.ButtonStyle.secondary, emoji = "↩️")    
        async def back_button_callback(interaction: discord.Interaction):
            self.selected_tags.pop()
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")
            embeds.append(embed)
            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            

            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)

                
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            else:
                self.rare = False
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)
            
            view = TagSelectView(self.selected_tags, all = self.all, rare = self.rare, undo = self.undo)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
        
        back_button.callback = back_button_callback
        self.add_item(back_button)
        
    
class TagSelectView(discord.ui.View):
    def __init__(self, selected_tags: list, all: bool, rare: bool = False, undo: bool = True):
        self.selected_tags = selected_tags
        self.all = all
        self.rare = rare
        self.disable = False
        self.undo = undo
        super().__init__(timeout=300)
                    
        if self.selected_tags and self.undo is True:
            self.add_undo_button()
        
        if self.all is True and self.rare is True:
            self.add_rare_only_button()
        elif self.all is False:
            self.add_show_all_button()

            
    @discord.ui.select(cls = discord.ui.Select, placeholder = "レアタグ(エリート等)", options=tag_rarity_list)
    async def tagRaritySelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        view = None
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        #結果があるとき
        if result_list:
            
            embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
            embeds.extend(embeds_ope)
                 
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            self.rare = True
            embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
        else:
            self.rare = False
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags, all=self.all, rare = self.rare)
        else:
            view = TagSelectView(self.selected_tags, all=self.all, rare = self.rare)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "職業タグ(前衛タイプ等)", options=tag_prof_list)
    async def tagProfessionSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        view = None
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        #結果があるとき
        if result_list:
            
            embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
            embeds.extend(embeds_ope)

        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            self.rare = True
            embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
        else:
            self.rare = False
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)                 
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags, all=self.all, rare = self.rare)
        else:
            view = TagSelectView(self.selected_tags, all=self.all, rare = self.rare)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "攻撃範囲タグ(近距離等)", options=tag_range_list)
    async def tagRangeSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        view = None
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        #結果があるとき
        if result_list:
            
            embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
            embeds.extend(embeds_ope)
                 
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            self.rare = True
            embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
        else:
            self.rare = False
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags,all=self.all, rare = self.rare)
        else:
            view = TagSelectView(self.selected_tags, all=self.all, rare = self.rare)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "特性タグ(治療、火力等)", options=tag_type_list)
    async def tagTypeSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        view = None
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        #結果があるとき
        if result_list:
            
            embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
            embeds.extend(embeds_ope)

        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            self.rare = True
            embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
        else:
            self.rare = False
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)                 
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags, all=self.all, rare = self.rare)
        else:
            view = TagSelectView(self.selected_tags,all=self.all, rare = self.rare)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    def add_show_all_button(self):
        button_show_all = discord.ui.Button(label = "全てのタグを表示する", style = discord.ButtonStyle.primary, emoji = "▶️")
        
        async def button_show_all_callback(interaction: discord.Interaction):
            self.all = True
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            else:
                self.rare = False
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagSelectView(self.selected_tags,all=self.all, rare = self.rare)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
        
        button_show_all.callback = button_show_all_callback
        self.add_item(button_show_all)
            
    def add_rare_only_button(self):
        button_rare_only = discord.ui.Button(label = "高レア確定タグのみ表示する", style = discord.ButtonStyle.primary, emoji = "🔽")
        
        async def button_rare_only_callback(interaction: discord.Interaction):
            self.all = False
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagSelectView(self.selected_tags,all=self.all, rare = self.rare)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
        
        button_rare_only.callback = button_rare_only_callback
        self.add_item(button_rare_only)
    
    def add_undo_button(self):
        button_undo = discord.ui.Button(label = "戻る", style = discord.ButtonStyle.secondary, emoji = "↩️")
        
        async def button_undo_callback(interaction: discord.Interaction):
            self.selected_tags.pop()
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list= await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            #結果があるとき
            if result_list:
                
                embeds_ope = await result_embed_maker(result_list = result_list, all = self.all)
                embeds.extend(embeds_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                self.rare = True
                embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
            else:
                self.rare = False
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagSelectView(self.selected_tags, all=self.all, rare = self.rare)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
            
        button_undo.callback = button_undo_callback
        self.add_item(button_undo)

@client.tree.command(name="recruit", description="公開求人のタグから雇用できるオペレーターが分かります")
async def recruit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    selected_tags = []
    view = TagSelectView(selected_tags=selected_tags, all = True)
    
    logger.info(f"{interaction.user.name}がコマンド/recruitを使用しました")
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = "ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)
    
async def ocr_tag_from_screenshot(image_path):
    
    im = Image.open(image_path)
    im_width, im_height = im.size
    
    tags_center_hrz = im_width * 0.48
    tags_center_vrt = im_height * 0.60
    
    tags_height = im_height * 0.20
    tags_width = tags_height * 3.2
    
    im_cropped = im.crop((tags_center_hrz - (tags_width/2), tags_center_vrt - (tags_height/2), 
                          tags_center_hrz + (tags_width/2), tags_center_vrt + (tags_height/2)))
    
    im_cropped.save(os.path.join(image_dir, "image_cropped.png"))
    
    binaryThreshold = 170
    try:
        binary_target = cv2.imread(os.path.join(image_dir, "image_cropped.png"), 0)
        logger.debug(f"binary_target type: {type(binary_target)}")
        ret, binaried = cv2.threshold(binary_target, binaryThreshold, 255, cv2.THRESH_BINARY_INV)
        
        cv2.imwrite(os.path.join(image_dir, "image_binaried.png"), binaried)
        ocr_image =  cv2.imread(os.path.join(image_dir, "image_binaried.png"))
        result = ocr.ocr(ocr_image, cls=False)

    except Exception as e:
        logger.error(f"OCR前処理にてエラー: {e}")
        raise e
    
    
    logger.debug("OCRを実行しました")
    result_tags = []
    if not result or not result[0]:
        logger.warning("OCR結果が空です。")
        return []
    
    recognized_data = result[0]
    logger.debug(f"検出されたタグ: {recognized_data}")
    
    def normalize_tag(tag):
        tag = re.sub(r"(タイ[フブラ])", "タイプ", tag)
        tag = re.sub(r"(.級エリー.)", "上級エリート", tag)
        tag = re.sub(r"(エリー.)", "エリート", tag)
        return tag
    
    for box, (text, score) in recognized_data:
        tag = text.strip()
        logger.debug(f"OCR結果: {tag} (信頼度: {score})")
        tag = normalize_tag(tag)
        if len(tag) <= 1:
            logger.warning(f"OCR結果「{tag}」は1文字のため除外されました。")
            continue
        closest_match = get_close_matches(tag, possible_tag_list, n=1, cutoff=0.1)
        if not closest_match:
            logger.error(f"検出されたタグ「{tag}」は修正されませんでした")
            continue
        else:
            result_tags.append(closest_match[0])
            
        if tag != closest_match[0]:
            filetime = JSTTime.timeJST("file")
            logger.warning(f"OCR結果「{tag}」は「{closest_match[0]}」に修正されました。 デバッグ用画像はimages/debugフォルダに「ocr_debug_{tag}_{filetime}.png」で保存されました。")
            #cv2は日本語ファイル名をサポートしていないため、tempで保存してから改名
            cv2.imwrite(os.path.join(image_dir, "debug\\ocr_debug_temp.png"), binaried)
            os.rename(os.path.join(image_dir, "debug\\ocr_debug_temp.png"), os.path.join(image_dir, f"debug\\ocr_debug_{tag}_{filetime}.png"))
                
    return result_tags

async def recruit_from_screenshot(image_path, message: discord.Message):
    try:
        result_tags = await ocr_tag_from_screenshot(image_path)
        
        if len(result_tags) != 5:
            embed = discord.Embed(title = "公開求人シミュレーター：エラー", description = "タグの認識に失敗しました！他のスクリーンショットをお試しください！\n解像度が出来るだけ高い、画面を直接スクリーンショットした画像を使用してください。")
            await message.reply(embed = embed)
            return
        result_list, goodresult_list= await output_results(selected_tags=result_tags)
        tags_view = "、 ".join(result_tags)
        show_all_tags = False
        embeds = []
        embed = discord.Embed(title = "公開求人シミュレーター")
        embeds.append(embed)
        #結果があるとき
        if result_list:
            
            embeds_ope = await result_embed_maker(result_list = result_list, all = show_all_tags)
            embeds.extend(embeds_ope)
                    
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            rare = True
            embed_tags.add_field(name = "高レア確定タグ", value = goodresult_list)
        else:
            rare = False
        
        embed_tags.add_field(name = "検出されたタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        view = TagUndoOnly(result_tags, all=show_all_tags, rare = rare, undo = False)
        
        view.message = await message.reply(embeds = embeds, view = view)
    
    except Exception as e:
        logger.error(f"タグの認識にエラー: {e}")
        embed = discord.Embed(title = "公開求人シミュレーター：エラー", description = "タグの認識に失敗しました！他のスクリーンショットをお試しください！")
        await message.reply(embed = embed)
    