import discord
import json
import os
from extentions import log, config
from extentions.aclient import client
from typing import List
import itertools

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
operators_json = "jsons/operators.json"

tag_select = discord.ui.Select(placeholder = "タグを選択してください")
tag_list = config.tagList
tag_rarity_list = []
tag_prof_list = []
tag_range_list = []
tag_type_list = []

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
    
async def recruit_operators():
    recruitList = config.recruitList
    with open(os.path.join(dir, operators_json), "r", encoding="UTF-8") as f:
        operators = json.load(f)
        
    operators_list = []
        
    for index in operators:
        if operators[index]["name"] in recruitList:
            dict_add = {"name": operators[index]["name"], "rarity": operators[index]["rarity"], "tags": operators[index]["tags"]}
            operators_list.append(dict_add)
            
    return operators_list

async def find_common_tags(reference_tags, operators):
    
    all_combinations = []
    for r in range(1, len(reference_tags) + 1):
        combinations = itertools.combinations(reference_tags, r)
        all_combinations.extend(combinations)
    
    matching_combinations = []
    for combination in all_combinations:
        for ope in range(len(operators)):
            if set(operators[ope]["tags"]) & set(combination):
                matchtag = set(operators[ope]["tags"]) & set(combination)
                
                if (operators[ope]["rarity"] == 0 and not "ロボット" in combination) or (operators[ope]["rarity"] == 4 and not "エリート" in combination) or (operators[ope]["rarity"] == 5 and not "上級エリート" in combination) or (operators[ope]["name"] == "アーミヤ"):
                    pass
                
                else:
                                        
                    there = False
                    for collection in matching_combinations:
                        if collection["tags"] == list(matchtag):
                            there = True
                            if not operators[ope] in collection["operators"]:
                                collection["operators"].append(operators[ope])
                            break
                    if there == False:   
                        matching_combinations.append({"tags": list(matchtag), "operators": [operators[ope]]})
        for i in range(len(matching_combinations)):
            matching_combinations[i]["operators"] = sorted(matching_combinations[i]["operators"], key = lambda x: x["rarity"])
    
    for tag in matching_combinations:
        rarity = 99
        for operator in tag["operators"]:
            rarity = operator["rarity"] if rarity > operator["rarity"] else rarity
        tag["min_rarity"] = rarity
        
    sorted_match = sorted(matching_combinations, key = lambda item: (-item["min_rarity"], len(item["operators"])))
                
    return sorted_match 

async def output_results(selected_tags):
    try:
        operators_list = await recruit_operators()
        result_operators = await find_common_tags(reference_tags=selected_tags, operators = operators_list)
        
        goodresult_list = ""
        list_tags = []
        
        for result in result_operators:

            tag_rarity = result["min_rarity"]
            
            tag_str = " ".join(result["tags"])
            
            
            if tag_rarity == 0 or tag_rarity > 2:
                goodresult_list += f"{tag_str}: ☆{tag_rarity+1}確定\n"
            
        over_20 = False
            
        if len(result_operators)>20:
            while len(result_operators)>20:
                result_operators.popitem()
            over_20 = True
        
        logger.info(f"公開求人シミュレートを行います：{selected_tags}")        
        return result_operators, goodresult_list, over_20
    except Exception as e:
        logger.exception(f"[output_results]にてエラー：{e}")

class TagUndoOnly(discord.ui.View):
    def __init__(self, selected_tags: List):
        self.selected_tags = selected_tags
        super().__init__(timeout=300)
    @discord.ui.button(label = "戻る", style = discord.ButtonStyle.secondary, emoji = "↩️")  
    async def button_undo_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_tags.pop()
        
        embeds = []
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        if result_list:
            embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
            for tag in result_list:
                value = ""
                field_name = " ".join(tag["tags"])
                for ope in tag["operators"]:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "
                embed_ope.add_field(name = field_name, value = value, inline = False)
        
            if over_20 == True:
                embed_ope.add_field(name="……")
                
            embeds.append(embed_ope)
        
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        view = TagSelectView(self.selected_tags)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    
class TagSelectView(discord.ui.View):
    def __init__(self, selected_tags: List):
        self.selected_tags = selected_tags
        super().__init__(timeout=300)
        if self.selected_tags:
            self.add_undo_button()
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "レアタグ(エリート等)", options=tag_rarity_list)
    async def tagRaritySelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        if result_list:
            embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
            for tag in result_list:
                value = ""
                field_name = " ".join(tag["tags"])
                for ope in tag["operators"]:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "
                embed_ope.add_field(name = field_name, value = value, inline = False)
        
            if over_20 == True:
                embed_ope.add_field(name="……")
                
            embeds.append(embed_ope)
                 
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags)
        else:
            view = TagSelectView(self.selected_tags)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "職業タグ(前衛タイプ等)", options=tag_prof_list)
    async def tagProfessionSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        if result_list:
            embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
            for tag in result_list:
                value = ""
                field_name = " ".join(tag["tags"])
                for ope in tag["operators"]:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "
                embed_ope.add_field(name = field_name, value = value, inline = False)
        
            if over_20 == True:
                embed_ope.add_field(name="……")
                
            embeds.append(embed_ope)

        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)                 
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags)
        else:
            view = TagSelectView(self.selected_tags)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "攻撃範囲タグ(近距離等)", options=tag_range_list)
    async def tagRangeSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        if result_list:
            embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
            for tag in result_list:
                value = ""
                field_name = " ".join(tag["tags"])
                for ope in tag["operators"]:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "
                embed_ope.add_field(name = field_name, value = value, inline = False)
        
            if over_20 == True:
                embed_ope.add_field(name="……")
                
            embeds.append(embed_ope)
                 
        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags)
        else:
            view = TagSelectView(self.selected_tags)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
        
    @discord.ui.select(cls = discord.ui.Select, placeholder = "特性タグ(治療、火力等)", options=tag_type_list)
    async def tagTypeSelect(self, interaction: discord.Interaction, select: discord.ui.Select):
        
        if any(value in self.selected_tags for value in select.values):
            await interaction.response.send_message("タグが重複しています！", ephemeral=True)
            return
        self.selected_tags += select.values
        embeds = []
        
        tags_view = "、 ".join(self.selected_tags)
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

        result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
        
        embeds.append(embed)
        
        if result_list:
            embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
            for tag in result_list:
                value = ""
                field_name = " ".join(tag["tags"])
                for ope in tag["operators"]:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "
                embed_ope.add_field(name = field_name, value = value, inline = False)
        
            if over_20 == True:
                embed_ope.add_field(name="……")
                
            embeds.append(embed_ope)

        embed_tags = discord.Embed(title = "タグ")
            
        if goodresult_list:
            embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
        
        embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
        
        embeds.append(embed_tags)                 
        
        if len(self.selected_tags) > 4:
            view = TagUndoOnly(self.selected_tags)
        else:
            view = TagSelectView(self.selected_tags)
        
        await interaction.response.edit_message(embeds = embeds, view = view)
    
    def add_undo_button(self):
        button_undo = discord.ui.Button(label = "戻る", style = discord.ButtonStyle.secondary, emoji = "↩️")
        
        async def button_undo_callback(interaction: discord.Interaction):
            self.selected_tags.pop()
            
            embeds = []
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

            result_list, goodresult_list, over_20 = await output_results(selected_tags=self.selected_tags)
            
            embeds.append(embed)
            
            if result_list:
                embed_ope = discord.Embed(title = "獲得できるオペレーター", color = discord.Color.blue())
                for tag in result_list:
                    value = ""
                    field_name = " ".join(tag["tags"])
                    for ope in tag["operators"]:
                        rarity = ope["rarity"]
                        name = ope["name"]
                        value += f"☆{rarity+1}{name} "
                    embed_ope.add_field(name = field_name, value = value, inline = False)
            
                if over_20 == True:
                    embed_ope.add_field(name="……")
                    
                embeds.append(embed_ope)
            
            embed_tags = discord.Embed(title = "タグ")
                
            if goodresult_list:
                embed_tags.add_field(name = "レア確定タグ", value = goodresult_list)
            
            embed_tags.add_field(name = "選択中のタグ", value = tags_view, inline=False)        
            
            embeds.append(embed_tags)            
            
            view = TagSelectView(self.selected_tags)
            
            await interaction.response.edit_message(embeds = embeds, view = view)
            
        button_undo.callback = button_undo_callback
        self.add_item(button_undo)

@client.tree.command(name="recruit", description="公開求人のタグから雇用できるオペレーターが分かります")
async def recruit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    selected_tags = []
    view = TagSelectView(selected_tags=selected_tags)
    
    logger.info(f"{interaction.user.name}がコマンド/recruitを使用しました")
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)

@client.tree.context_menu(name = "公開求人シミュレーター")
async def recruit_menu(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    
    selected_tags = []
    view = TagSelectView(selected_tags=selected_tags)
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)