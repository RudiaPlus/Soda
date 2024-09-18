import discord
import json
import os
import numpy
from extentions import log, config
from extentions.aclient import client
from extentions.aOCR import ocr
from PIL import Image
from difflib import get_close_matches
import cv2
import itertools

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
image_dir = os.path.join(dir, "images")
operators_json = "jsons/operators.json"

possible_tag_list = config.tagList

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
    
#create operators_list
recruitList = config.recruitList
with open(os.path.join(dir, operators_json), "r", encoding="UTF-8") as f:
    operators = json.load(f)
    
operators_list = []
    
for index in operators:
    if operators[index]["name"] in recruitList:
        dict_add = {"name": operators[index]["name"], "rarity": operators[index]["rarity"], "tags": operators[index]["tags"]}
        operators_list.append(dict_add)
        
#load operator_emojis
with open(os.path.join(dir, "jsons\\operator_emojis.json"), "r", encoding="utf-8") as f:
    operator_emojis = json.load(f)

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
                
                if (operators[ope]["rarity"] == 5 and not "上級エリート" in combination) or (operators[ope]["name"] == "アーミヤ"):
                    pass
                
                else:
                                        
                    there = False
                    for collection in matching_combinations:
                        if set(collection["tags"]) == matchtag:
                            there = True
                            if not operators[ope] in collection["operators"]:
                                collection["operators"].append(operators[ope])
                            break
                    if there == False:   
                        matching_combinations.append({"tags": list(matchtag), "operators": [operators[ope]]})
        for i in range(len(matching_combinations)):
            matching_combinations[i]["operators"] = sorted(matching_combinations[i]["operators"], key = lambda x: x["rarity"])
    
    for tag in matching_combinations:
        rarity = 99 #99 means only 1 star
        for operator in tag["operators"]:
            rarity = operator["rarity"] if rarity > operator["rarity"] and operator["rarity"] != 0 else rarity
        tag["min_rarity"] = rarity
        
    sorted_match = sorted(matching_combinations, key = lambda item: (-item["min_rarity"], len(item["operators"])))
                
    return sorted_match 

async def output_results(selected_tags):
    try:
        result_operators = await find_common_tags(reference_tags=selected_tags, operators = operators_list)
        
        goodresult_list = ""
        list_tags = []
        
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
        
async def result_embed_maker(result_list: list, all: bool) -> list:
    embeds = []
    
    if all == True:
        embed_ope = discord.Embed(title = "獲得できる全てのオペレーター", color = discord.Color.blue())
        count = 0
        for tag in result_list:
            value = ""
            field_name = " ".join(tag["tags"])
            inline = False
            i = 1
            for ope in tag["operators"]:
                rarity = ope["rarity"]
                name = ope["name"]
                value += f"☆{rarity+1}{name} "
                if i > 20:
                    count += len(value)
                    embed_ope.add_field(name = field_name, value = value, inline = inline)
                    field_name = ""
                    value = ""
                    i = 0
                i += 1
            count += len(value)
            if value:
                embed_ope.add_field(name = field_name, value = value, inline = inline)
            if count > 2000:
                embeds.append(embed_ope)
                embed_ope = discord.Embed(color = discord.Color.blue())
                count = 0
        if embed_ope.fields:                    
            embeds.append(embed_ope)
            
    else:
        rare_list = []
        for result in result_list:
            if ("ロボット" in result["tags"] or result["min_rarity"] > 2):
                rare_list.append(result)
                
        embed_ope = discord.Embed(title = "獲得できる高レアなオペレーター", color = discord.Color.blue())
        count = 0
        if not rare_list:
            embed_ope.add_field(name = "該当タグ無し", value = "☆4以上のオペレーターを確定で引ける組み合わせはありません。\n全ての組み合わせを見る場合、「全てのタグを表示する」ボタンを押してください。")
        for tag in rare_list:
            value = ""
            field_name = " ".join(tag["tags"])
            inline = False
            i = 1
            for ope in tag["operators"]:
                rarity = ope["rarity"]
                name = ope["name"]
                value += f"☆{rarity+1}{operator_emojis[name]}{name} "
                if i > 20:
                    count += len(value)
                    embed_ope.add_field(name = field_name, value = value, inline = inline)
                    field_name = ""
                    value = ""
                    i = 0
                i += 1
            count += len(value)
            if value:
                embed_ope.add_field(name = field_name, value = value, inline = inline)
            if count > 2000:
                embeds.append(embed_ope)
                embed_ope = discord.Embed(color = discord.Color.blue())
                count = 0
        if embed_ope.fields:                    
            embeds.append(embed_ope)
    
    return(embeds)
        

class TagUndoOnly(discord.ui.View):
    def __init__(self, selected_tags: list, all: bool, rare: bool = False, undo: bool = True):
        self.selected_tags = selected_tags
        self.all = all
        self.rare = rare
        self.undo = undo
        super().__init__(timeout=300)
        
        if undo == True:
            self.add_back_button()
        
        if self.all == True and self.rare == True:
            self.add_rare_only_button()
        elif self.all == False:
            self.add_show_all_button()
        
    def add_show_all_button(self):
        button_show_all = discord.ui.Button(label = "全てのタグを表示する", style = discord.ButtonStyle.primary, emoji = "▶️")
        
        async def button_show_all_callback(interaction: discord.Interaction):
            self.all = True
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
        
        button_show_all.callback = button_show_all_callback
        self.add_item(button_show_all)
            
    def add_rare_only_button(self):
        button_rare_only = discord.ui.Button(label = "高レア確定タグのみ表示する", style = discord.ButtonStyle.primary, emoji = "🔽")
        
        async def button_rare_only_callback(interaction: discord.Interaction):
            self.all = False
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
        
        button_rare_only.callback = button_rare_only_callback
        self.add_item(button_rare_only)
    
    def add_back_button(self):
        back_button = discord.ui.Button(label = "戻る", style = discord.ButtonStyle.secondary, emoji = "↩️")    
        async def back_button_callback(interaction: discord.Interaction):
            self.selected_tags.pop()
            
            embeds = []
            view = None
            
            tags_view = "、 ".join(self.selected_tags)
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
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
    def __init__(self, selected_tags: list, all: bool, rare: bool = False):
        self.selected_tags = selected_tags
        self.all = all
        self.rare = rare
        self.disable = False
        super().__init__(timeout=300)
                    
        if self.selected_tags:
            self.add_undo_button()
        
        if self.all == True and self.rare == True:
            self.add_rare_only_button()
        elif self.all == False:
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
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")

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
    
    embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
    await interaction.followup.send(embed = embed, view = view, ephemeral=True)
    
async def ocr_tag_from_screenshot(image_path):
    
    im = Image.open(image_path)
    im_width, im_height = im.size
    
    tags_center_hrz = im_width * 0.48
    tags_center_vrt = im_height * 0.57
    
    tags_height = im_height * 0.16
    tags_width = tags_height * 4
    
    im_cropped = im.crop((tags_center_hrz - (tags_width/2), tags_center_vrt - (tags_height/2), 
                          tags_center_hrz + (tags_width/2), tags_center_vrt + (tags_height/2)))
    
    im_cropped.save(os.path.join(image_dir, "image_cropped.png"))
    
    binaryThreshold = 170
    binary_target = cv2.imread(os.path.join(image_dir, "image_cropped.png"), 0)
    ret, binaried = cv2.threshold(binary_target, binaryThreshold, 255, cv2.THRESH_BINARY_INV)
    
    cv2.imwrite(os.path.join(image_dir, "image_binaried.png"), binaried)
    
    im_binaried = Image.open(os.path.join(image_dir, "image_binaried.png"))
    np_binaried = numpy.asarray(im_binaried)
    
    result = ocr.ocr(img = np_binaried, cls = False)
    result_tags = []
    
    for i in range(5):
        tag = result[0][i][1][0]
        closest_match = get_close_matches(tag, possible_tag_list, n=1, cutoff=0.1)
        if not closest_match:
            logger.error(f"タグの検出が出来ませんでした: {tag}")
        else:
            result_tags.append(closest_match[0])
            
    return result_tags

async def recruit_from_screenshot(image_path, message: discord.Message):
    try:
        result_tags = await ocr_tag_from_screenshot(image_path)
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
        
        await message.reply(embeds = embeds, view = view)
    
    except Exception as e:
        logger.error(f"タグの認識にエラー: {e}")
        embed = discord.Embed(title = "公開求人シミュレーター：エラー", description = "タグの認識に失敗しました！他のスクリーンショットをお試しください！")
        await message.reply(embed = embed)
    