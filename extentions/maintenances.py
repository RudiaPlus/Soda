import asyncio
import json
import os
import time
from datetime import datetime

import discord
from discord.ext import tasks

from extentions import JSTTime, log, data_update
from extentions.aclient import client
from extentions.config import config

codes_path = os.path.abspath("C:\\Users\\Siratama\\Documents\\codes")
logger = log.setup_logger()
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
            pic = maintenances[entry]["pic"] if "pic" in maintenances[entry] else None
                        
            maint_start = "<t:{0}:F>( <t:{0}:R> )".format(maintenances[entry]["startTime"])
            maint_end = "<t:{0}:F>( <t:{0}:R> )".format(maintenances[entry]["endTime"])
            maint_list.append({"name": maint_name, "time": f"開始:{maint_start}\n終了:{maint_end}", "link": link, "pic": pic})
    
    return maint_list

async def announce_and_delete(entry: int):
    channel = client.get_channel(config.maintenance)
    maintenances = await read_json()
    link = maintenances[entry]["link"]
    embed = discord.Embed(title = "メンテナンスが終了しました！", description = "サーバーに入れる状態です！", color = 0x8dbf9d, url = link)
    
    await channel.send("<@&1090976873774854177>", embed = embed)
    
    del maintenances[entry]
    await write_json(maintenances)

async def maintenance_end(maint_name: str, entry: int):
    await announce_and_delete(entry)
    
    channel_announcement = client.get_channel(config.announcement)
    start_time = datetime.now()
    await channel_announcement.send("botのリソース更新を行います！完了するまでbotの動作が不安定になる可能性がありますので、ご注意ください！")
    result = await data_update.update_data()
    if result is True:
        result_time = datetime.now()
        result_delta = result_time - start_time
        logger.info(f"データ更新に成功しました！\n経過した時間: {result_delta.total_seconds()}秒")
        await channel_announcement.send("botのリソース更新が完了しました！現在、botの動作は安定しています！")
    else:
        await logger.warn("更新に失敗しました......")
    
async def maintenance_ruined(entry):
    maintenances = await read_json()
    del maintenances[entry]
    await write_json(maintenances)
    
# メンテナンス終了時間変更
async def change_maint_end(entry: int, new_end: int):
    maintenances = await read_json()
    maintenances[entry]["endTime"] = new_end
    await write_json(maintenances)
    logger.info(f"メンテナンス終了時間を変更しました: {entry} -> {new_end}")
    channel = client.get_channel(config.maintenance)
    end = "<t:{0}:F>( <t:{0}:R> )".format(new_end)
    embed = discord.Embed(title = "メンテナンス終了時間が変更されました！", description = f"終了:{end}", color = 0xf5b642, url = maintenances[entry]["link"])
    await channel.send("<@&1090976873774854177>", embed = embed)

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
            pic = maintenances[entry]["pic"] if "pic" in maintenances[entry] else None
                
            if maintenances[entry]["doing"] is False and maint_start < time.time():
                #メンテナンス開始
                channel = client.get_channel(config.maintenance)
                start = "<t:{0}:F>( <t:{0}:R> )".format(maint_start)
                end = "<t:{0}:F>( <t:{0}:R> )".format(maint_end)
                embed = discord.Embed(title = f"{maint_name}が開始されました！",
                                      description = f"開始:{start}\n終了:{end}",
                                      color = 0xf5b642,
                                      url = link,
                                      )
                embed.set_image(url=pic)
                await channel.send("<@&1090976873774854177>", embed = embed)    
                    
                #ここまで
                maintenances[entry]["doing"] = True
                await write_json(maintenances)
                                    
            if maint_end < time.time():
                #メンテナンス終了
                await maintenance_end(maint_name, entry)    
                    
                #ここまで
                               
        await asyncio.sleep(5)
        maintenances = await read_json()