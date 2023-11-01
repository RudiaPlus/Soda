import asyncio
import discord
from discord.ext import tasks
import json
import time
import os
from extentions import log, config, JSTTime
from extentions.aclient import client
from datetime import datetime

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
json_dir = "jsons/maintenances.json"
tz_JST = JSTTime.tz_JST

async def write_json(dic):
    with open(os.path.join(dir, json_dir), "w", encoding = "UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)

async def read_json():
    with open(os.path.join(dir, json_dir), encoding = "UTF-8") as f:
        maintenances = json.load(f)
    return(maintenances)

async def maintenance_list():
    maintenances = await read_json()
    maint_list = []
    for entry in range(len(maintenances)):
        now = datetime.now(tz_JST)
        startTime = datetime.fromtimestamp(maintenances[entry]["startTime"])
        if now.month == startTime.month and now.day == startTime.day:
            if maintenances[entry]["type"] == "DATA":
                maint_name = "データ更新"
                    
            elif maintenances[entry]["type"] == "MAINTENANCE":
                maint_name = "メンテナンス"
                    
            elif maintenances[entry]["type"] == "EMERGENCY":
                maint_name = "緊急メンテナンス"
                
            link = maintenances[entry]["link"]
                        
            maint_start = "<t:{0}:F>( <t:{0}:R> )".format(maintenances[entry]["startTime"])
            maint_end = "<t:{0}:F>( <t:{0}:R> )".format(maintenances[entry]["endTime"])
            maint_list.append({"name": maint_name, "time": f"開始:{maint_start}\n終了:{maint_end}", "link": link})
    
    return maint_list
    
async def maintenance_end(maint_name: str, entry: int):
    channel = client.get_channel(config.maintenance)
    maintenances = await read_json()
    link = maintenances[entry]["link"]
    embed = discord.Embed(title = f"{maint_name}が終了しました！",
                                      description = "サーバーに入れる状態です！",
                                      color = 0x8dbf9d,
                                      url = link
                                      )
    await channel.send("<@&1090976873774854177>", embed = embed)
    del maintenances[entry]
    await write_json(maintenances)
    
async def maintenance_ruined(entry):
    maintenances = await read_json()
    del maintenances[entry]
    await write_json(maintenances)

@tasks.loop(seconds=60)
async def maintenance_timer():
    maintenances = await read_json()
    while len(maintenances) != 0:
        for entry in range(len(maintenances)):
            if maintenances[entry]["type"] == "DATA":
                maint_name = "データ更新"
                
            elif maintenances[entry]["type"] == "MAINTENANCE":
                maint_name = "メンテナンス"
                
            elif maintenances[entry]["type"] == "EMERGENCY":
                maint_name = "臨時メンテナンス"
                    
            maint_start = maintenances[entry]["startTime"]
            maint_end = maintenances[entry]["endTime"]
            link = maintenances[entry]["link"]
                
            if maintenances[entry]["doing"] == False and maint_start < time.time():
                #メンテナンス開始
                channel = client.get_channel(config.maintenance)
                start = "<t:{0}:F>( <t:{0}:R> )".format(maint_start)
                end = "<t:{0}:F>( <t:{0}:R> )".format(maint_end)
                embed = discord.Embed(title = f"{maint_name}が開始されました！",
                                      description = f"開始:{start}\n終了:{end}",
                                      color = 0xf5b642,
                                      url = link
                                      )
                await channel.send("<@&1090976873774854177>", embed = embed)    
                    
                #ここまで
                maintenances[entry]["doing"] = True
                await write_json(maintenances)
                                    
            if maint_end < time.time():
                #メンテナンス終了
                await maintenance_end(maint_name, entry)    
                    
                #ここまで
                               
        logger.debug("メンテナンスがあります")
        await asyncio.sleep(5)
        maintenances = await read_json()
    logger.debug("メンテナンスはありません！")