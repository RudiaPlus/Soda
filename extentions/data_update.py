import base64
import json
import os
import re
from datetime import datetime

import arkprts
import discord
import requests

from extentions import log
from extentions.aclient import client
from extentions.config import config

logger = log.setup_logger()

dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.abspath("C:\\Users\\Siratama\\Documents\\arknights_data_excel")
repo_name_resource = "ArknightsGameResource"
excel_path = os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel")

rhodo_json_path = os.path.join(dir, "extentions\\jsons") 

def list_all_file_paths(dir):
    file_paths = []
    for root, _, files in os.walk(dir):
        for file in files:
            file_paths.append(os.path.join(root, file))
    
    return file_paths

async def char_table_analyze():
    with open(os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel\\skill_table.json"), encoding="utf-8") as f:
        skill_json = json.load(f)
    with open(os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel\\char_patch_table.json"), encoding="utf-8") as f:
        patch_json = json.load(f)   
    with open(os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel\\character_table.json"), encoding="utf-8") as f:
        raw_json = json.load(f)
    with open(os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel\\uniequip_table.json"), encoding="utf-8") as f:
        module_json = json.load(f)

    #アーミヤのみ昇格対応
    amiya_chars = {}
    default_amiya = patch_json["infos"]["char_002_amiya"]["default"]
    for amiya_id in patch_json["infos"]["char_002_amiya"]["tmplIds"]:
        if amiya_id == default_amiya:
            continue
        amiya_data = patch_json["patchChars"][amiya_id]
        profession_name = config.profession_id_to_name[amiya_data["profession"]]
        amiya_name = f"{amiya_data["name"]}({profession_name})"
        amiya_chars.update({amiya_id: amiya_name})
        
    charjson = {}
    dic_add = {}
    
    async def make_char_json(char_id: str, char_data: dict, rarity_new: int) -> dict:
        
        name = char_data["name"]
        
        if char_id in amiya_chars:
            name = amiya_chars[char_id]

        number_of_skills = len(char_data["skills"])

        skills_dict = {}
        for i in range(number_of_skills):
            skill_id = char_data["skills"][i]["skillId"]
            skills_dict.update({f"{i+1}": skill_json[skill_id]["levels"][0]["name"]})
            
        if "itemObtainApproach" not in char_data:
            return
                
        dic_add = {
            char_id: {
                "name": name, 
                "class": char_data["profession"],
                "rarity": rarity_new, 
                "skills": skills_dict,
                "tags": char_data["tagList"],
                "obtain": char_data["itemObtainApproach"]
                }
            }
        if char_data["position"] == "MELEE":
            dic_add[char_id]["tags"].append("近距離")
        elif char_data["position"] == "RANGED":
            dic_add[char_id]["tags"].append("遠距離")
        else:
            raise TypeError
        
        dic_add[char_id]["tags"].append(f"{config.profession_id_to_name[char_data['profession']]}タイプ")
            

        if rarity_new == 5:
            dic_add[char_id]["tags"].append("上級エリート")
        elif rarity_new == 4:
            dic_add[char_id]["tags"].append("エリート")
        return dic_add

    for index in raw_json:
        
        rarity_raw = raw_json[index]["rarity"]
        rarity_new = int(rarity_raw[len(rarity_raw)-1]) - 1
        
        if raw_json[index]["profession"] != "TOKEN" and raw_json[index]["profession"] != "TRAP" and raw_json[index]["isNotObtainable"] is False:

            dic_add = await make_char_json(index, raw_json[index], rarity_new)
            if dic_add:
                charjson.update(dic_add)  
            
    for index in patch_json["patchChars"]:
        rarity_raw = patch_json["patchChars"][index]["rarity"]
        rarity_new = int(rarity_raw[len(rarity_raw)-1]) - 1
        dic_add = await make_char_json(index, patch_json["patchChars"][index], rarity_new)
        charjson.update(dic_add)
        
    # モジュール種別コードと表示シンボルのマッピング
    module_type_map = {
        "X": "X",
        "Y": "Y",
        "D": "Δ",
        "A": "α",
    }

    for equip_data in module_json["equipDict"].values():
        char_id = equip_data.get("tmplId", equip_data.get("charId"))

        # エリートオペレーターなどを除外
        if not char_id or char_id not in charjson:
            continue

        module_type_code = equip_data.get("typeName2")
        module_symbol = module_type_map.get(module_type_code)

        if module_symbol:
            modules_dict = charjson[char_id].setdefault("modules", {})
            modules_dict[module_symbol] = equip_data["uniEquipName"]

    with open(os.path.join(dir, "jsons\\operators.json"), "w", encoding = "utf-8") as f:
        json.dump(charjson, f, indent = 2, ensure_ascii = False)

async def birthday_analyze():
    with open(os.path.join(dir, "ArknightsData\\jp\\gamedata\\excel\\handbook_info_table.json"), "r", encoding="utf-8") as f:
        lines = json.load(f)
    def extract_text_between_strings(input_string, start_string, end_string):
        start_index = input_string.find(start_string)
        if start_index == -1:
            return None  # 開始文字列が見つからない場合はNoneを返す

        end_index = input_string.find(end_string, start_index + len(start_string))
        if end_index == -1:
            return None  # 終了文字列が見つからない場合はNoneを返す

        extracted_text = input_string[start_index + len(start_string):end_index]
        return extracted_text

    #name
    start_string_name = "【コードネーム】"
    end_string_name = "\n" 

    #birthday
    pattern = r"\d{1,2}月\d{1,2}日"

    birthdays = {}

    for ope in lines["handbookDict"].values():
        ope_info = ope["storyTextAudio"][0]["stories"][0]["storyText"]
        name = extract_text_between_strings(ope_info, start_string_name, end_string_name)
        if name:
            name = name.replace('”', "")
            name = name.replace('“', "")
            name = name.replace(" ", "")
        matches = re.findall(pattern, ope_info)
        birthdayname = matches[0] if matches else "無効"
        
        try:
            date_obj = datetime.strptime(birthdayname, "%m月%d日")
            birthday = date_obj.strftime("%m/%d")
        except ValueError:
            birthday = None

        if birthday and birthday not in birthdays.keys():
            birthdays.update({birthday: name})
            
        elif birthday and name and name not in birthdays[birthday]:
            birthdays[birthday] += f"、{name}"    

    sorted_birthdays = dict(sorted(birthdays.items(), key = lambda item: datetime.strptime(item[0], "%m/%d")))
        
    with open(os.path.join(dir, "jsons\\birthday.json"), "w", encoding="utf-8") as f:
        json.dump(sorted_birthdays, f, indent = 2, ensure_ascii = False)

async def custom_emoji_upload():
    resource_path = os.path.join(repo_name_resource, "avatar")
    headers = {"Authorization": f"Bot {config.token}", "Content-Type": "application/json"}

    with open(os.path.join(dir, "jsons\\operators.json"), encoding="utf_8") as op:
        operators = json.load(op)
        
    with open(os.path.join(dir, "jsons\\operator_emojis.json"), encoding="utf-8") as f:
        operator_emojis_load = json.load(f)
        
    def upload_emoji(emoji_name, image_path):
        with open(os.path.join(image_dir, image_path), "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        payload = {"name": emoji_name, "image": f"data:image/png;base64,{image_base64}"}
        response = requests.post("https://discord.com/api/v10/applications/1059152664509821009/emojis", headers = headers, json=payload)
        return response.json()
        
    def if_JP_operator(image_path):
        emoji_name = None
        operator_name = None
        operator_name = os.path.splitext(os.path.basename(image_path))[0]
        operator_codename = None
        
        for operator in operators:
            operator_include_alter = f"{operator}_2" if "amiya" in operator else operator
            
            if operator_include_alter == operator_name:
                emoji_name = operator
                operator_codename = operators[operator]["name"]
        if operator_codename not in operator_emojis_load.keys():
            return operator_codename, emoji_name
        else:
            return None, None

    image_dir = os.path.join(data_dir, resource_path)
    file_paths = list_all_file_paths(image_dir)
    for image_path in file_paths:
        operator_name, emoji_name = if_JP_operator(image_path)
        if emoji_name:
            result = upload_emoji(emoji_name, image_path)
            emoji_id = {operator_name: f'<:{result["name"]}:{result["id"]}>'}
            operator_emojis_load.update(emoji_id)

    with open(os.path.join(dir, "jsons\\operator_emojis.json"), "w", encoding="utf-8") as f:
        json.dump(operator_emojis_load, f, indent=2, ensure_ascii=False)

async def update_data() -> bool:

    logger.info("データのアップデートを開始します")
    assets = arkprts.BundleAssets(os.path.join(dir, "ArknightsData"), default_server="jp")
    await assets.update_assets(server = "jp")
    await assets.network.close()
    logger.info("データのアップデートが完了しました")
    logger.info("リソースのアップデートを行います")
    excel_files = list_all_file_paths(excel_path)
    for file in excel_files:
        if not file.endswith(".json"):
            continue
        with open(file, mode="r",encoding="UTF-8") as f:
            json_data = json.load(f)
        with open(file, mode="w", encoding="UTF-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    os.chdir(os.path.join(data_dir, repo_name_resource))
    os.system("git pull origin main")
    logger.info("リソースのアップデートが完了しました")
    
    await char_table_analyze()
    logger.info("キャラテーブルの解析が完了しました")
    await birthday_analyze()
    logger.info("誕生日の解析が完了しました")
    await custom_emoji_upload()
    logger.info("カスタム絵文字のアップロードが完了しました")
            
    return True

@client.tree.command(name="update", description="ゲームデータのアップデート、インデックスの作成を行います", guild=discord.Object(config.testserverid))
async def update(interaction: discord.Interaction):
    await interaction.response.defer()
    start_time = datetime.now()
    result = await update_data()
    if result is True:
        result_time = datetime.now()
        result_delta = result_time - start_time
        await interaction.followup.send(f"更新に成功しました！\n経過した時間: {result_delta.total_seconds()}秒")
    else:
        await interaction.followup.send("更新に失敗しました......")