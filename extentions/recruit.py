import discord
import json
import os
from extentions import log, config
from extentions.aclient import client
from typing import List
from itertools import combinations

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

async def find_common_operator(reference_tags: list, operators: list):
    if not reference_tags:
        return

    matching_sort = sorted(
        (ope_d for ope_d in operators if any(tag_d in ope_d["tags"] for tag_d in reference_tags)),
        key = lambda x: (x["rarity"], len(set(x["tags"]) & set(reference_tags))),
        reverse=True
        )
    i = 0
    while i < len(matching_sort):
        match_tags = list(set(matching_sort[i]["tags"]) & set(reference_tags))
        matching_sort[i]["matching_tags"] = match_tags
        for tag_a in matching_sort[i]["tags"]:
            if (matching_sort[i]["rarity"] == 5 and not any(taga == "上級エリート" for taga in reference_tags )) or (matching_sort[i]["rarity"] == 0 and not any(taga == "ロボット" for taga in reference_tags )):
                matching_sort.remove(matching_sort[i])
                i -= 1
                break
        i += 1
    return matching_sort
             


async def find_high_rarity(reference_tags: list, operators: list):
    result = []
    for r in range(1, len(reference_tags) + 1):
        for tag_combination in combinations(reference_tags, r):
            rarity_dict_list = [{"name": d["name"], "rarity": d["rarity"]} for d in operators if all(tag in d["tags"] for tag in tag_combination)]
            if rarity_dict_list and all((d["rarity"] >= 3 or d["rarity"] == 0) for d in rarity_dict_list) and len(tag_combination) <= 3:
                result.append({"tag": tag_combination, "operator": rarity_dict_list})
    return result

async def output_results(selected_tags):
    try:
        operators_list = await recruit_operators()
        result_operators = await find_common_operator(reference_tags=selected_tags, operators = operators_list)
        high_rarity_results = await find_high_rarity(reference_tags = selected_tags, operators = operators_list)
        
        goodresult_list = ""
        list_tags = []
        
        for result in high_rarity_results:
            logger.debug(result)

            goodresult_tags = ""
            maximum = 0
            can_not = 0
            
            for tagb in result["tag"]:
                
                if not set(result["tag"]) & set(config.tag_rarity):
                    goodresult_tags += f"{tagb} "
                else:
                    if not any(set(result["tag"]) & set(tagsa) for tagsa in list_tags):
                        goodresult_tags += f"{tagb} "
                
            for high_ope in result["operator"]:
                if (high_ope["rarity"] == 5 and not any(taga == "上級エリート" for taga in list(result["tag"]))) or (high_ope["rarity"] == 0 and not any(taga == "ロボット" for taga in list(result["tag"]))):
                    can_not += 1
                maximum = high_ope["rarity"] if high_ope["rarity"] < maximum or maximum == 0 else maximum
                logger.debug(high_ope["name"])
                logger.debug(high_ope["rarity"])
                logger.debug(maximum)
                logger.debug(can_not)
                    
            if len(goodresult_tags) > 0 and not can_not == len(result["operator"]):
                goodresult_list += f"{goodresult_tags}: ☆{maximum+1}確定\n"

            list_tags.append(result["tag"])
            
        over_20 = False
        
        result_list = []
        if result_operators:

            for ope in result_operators:
                duplicate = 0
                rarity = ope["rarity"]
                name = ope["name"]
                matching_tag = ope["matching_tags"]
                tag = "、".join(ope["tags"])
                for index in result_list:
                    
                    if index[0]["matching_tags"] == ope["matching_tags"]:
                        index.append({
                            "name": name,
                            "rarity": rarity,
                            "tag": tag,
                            "matching_tags": matching_tag
                        })
                        duplicate = 1
                        break
                if duplicate == 0:
                    result_list.append([
                            {
                                "name": name,
                                "rarity": rarity,
                                "tag": tag,
                                "matching_tags": matching_tag
                            }
                        ])
            
            if len(result_list)>20:
                while len(result_list)>20:
                    result_list.popitem()
                over_20 = True
        
        logger.info(f"公開求人シミュレートを行います：{selected_tags}")        
        return result_list, goodresult_list, over_20
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
            for index in result_list:
                value = ""
                field_name = ""
                for ope in index:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "   
                for  matching_tag in index[0]["matching_tags"]:
                    field_name += f"{matching_tag} "
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
            for index in result_list:
                value = ""
                field_name = ""
                for ope in index:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "   
                for  matching_tag in index[0]["matching_tags"]:
                    field_name += f"{matching_tag} "
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
            for index in result_list:
                value = ""
                field_name = ""
                for ope in index:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "   
                for  matching_tag in index[0]["matching_tags"]:
                    field_name += f"{matching_tag} "
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
            for index in result_list:
                value = ""
                field_name = ""
                for ope in index:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "   
                for  matching_tag in index[0]["matching_tags"]:
                    field_name += f"{matching_tag} "
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
            for index in result_list:
                value = ""
                field_name = ""
                for ope in index:
                    rarity = ope["rarity"]
                    name = ope["name"]
                    value += f"☆{rarity+1}{name} "   
                for  matching_tag in index[0]["matching_tags"]:
                    field_name += f"{matching_tag} "
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
                for index in result_list:
                    value = ""
                    field_name = ""
                    for ope in index:
                        rarity = ope["rarity"]
                        name = ope["name"]
                        value += f"☆{rarity+1}{name} "   
                    for  matching_tag in index[0]["matching_tags"]:
                        field_name += f"{matching_tag} "
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
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)

@client.tree.context_menu(name = "公開求人シミュレーター")
async def recruit_menu(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    
    selected_tags = []
    view = TagSelectView(selected_tags=selected_tags)
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)