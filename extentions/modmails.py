import json
import os
from extentions import log
from extentions.aclient import client

dir = os.path.abspath(__file__ + "/../")
json_name = "jsons/modmail.json"
json_path = os.path.join(dir, json_name)
logger = log.setup_logger(__name__)

async def modmail_get_user():
    with open(json_path, mode = "r", encoding="utf-8") as f:
        modmail_json = json.load(f)
    
    for i in range(len(modmail_json)):
        if modmail_json[i]["isFinished"] == "False":
            user = await client.fetch_user(modmail_json[i]["user_ID"])
            return(user)
    return None

async def modmail_queue(user):
    modmail_dic = {}
    with open(json_path, mode = "r", encoding="utf-8") as f:
        modmail_json = json.load(f)
    
    for i in range(len(modmail_json)):
        if user.id in modmail_json[i].values() and modmail_json[i]["isFinished"] == "False":
                return("False")
    try:
        modmail_dic["ID"] = (modmail_json[-1]["ID"]) + 1
        modmail_dic["user_ID"] = user.id
        modmail_dic["user_name"] = user.name
        modmail_dic["isFinished"] = "False"
        
        if modmail_json[-1]["isFinished"] == "True":
            modmail_dic["isNext"] = "True"
            modmail_json.append(modmail_dic)
            with open(json_path, mode = "w", encoding="utf-8") as f:
                json.dump(modmail_json, f, indent=2, ensure_ascii=False)
            return("Ready")
        
        elif modmail_json[-1]["isFinished"] == "False" and modmail_json[-2]["isFinished"] == "True":
            modmail_dic["isNext"] = "True"
            modmail_json.append(modmail_dic)
            with open(json_path, mode = "w", encoding="utf-8") as f:
                json.dump(modmail_json, f, indent=2, ensure_ascii=False)
            return("notReady")
        
        else:
            modmail_dic["isNext"] = "False"
            modmail_json.append(modmail_dic)
            with open(json_path, mode = "w", encoding="utf-8") as f:
                json.dump(modmail_json, f, indent=2, ensure_ascii=False)
            return("notReady")
    except Exception as e:
        logger.exception(f"[modmail_queue]にてエラー：{e}")
            
async def modmail_finish(user):
        
    with open(json_path, mode = "r", encoding="utf-8") as f:
            modmail_json = json.load(f)
            
    for i in range(len(modmail_json)):
        if user.id in modmail_json[i].values() and modmail_json[i]["isFinished"] == "False":
            modmail_json[i]["isFinished"] = "True"
            this_mail = i
            break

    try:
        for i in range(len(modmail_json)):
            if modmail_json[i]["isNext"] == "False":
                modmail_json[i]["isNext"] == "True"
                break
        with open(json_path, mode = "w", encoding="utf-8") as f:
                json.dump(modmail_json, f, indent=2, ensure_ascii=False)    
                
    except Exception as e:
        pass
        
    return