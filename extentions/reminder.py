import discord
import json
import asyncio
from extentions import log, config, JSTTime, evjson, maintenances
from extentions.aclient import client
import os
import requests
import time
import re

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger(__name__)

async def remind(mode = "morning"):
    events = evjson.eventget()
    eventcount = evjson.eventcount()
    maintenance = await maintenances.maintenance_list()
    channel = client.get_channel(config.announce)
    message = await channel.fetch_message(channel.last_message_id)
    embeds = []
    file = None

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

    for i in range(len(maintenance)):
        embed = discord.Embed(title=maintenance[i]["name"],
                                description=maintenance[i]["time"],
                                color=0xf5b642,
                                url = maintenance[i]["link"])
        embed.set_author(name="メンテナンス")
        embeds.append(embed)

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
                    file = discord.File(os.path.join(dir, png_name),
                                        filename="image.png")
                    embed = discord.Embed(title=events[i]["name"],
                                            description=events[i]["time"],
                                            color=0x6d2727,
                                            url=link)
                    embed.set_author(name="危機契約",
                                        icon_url="attachment://image.png")
                    embed.add_field(name="・常設ステージ",
                                    value=events[i]["permStage"],
                                    inline=False)
                    embed.add_field(name="・本日のデイリーステージ",
                                    value=events[i]["todaysDaily"]["stageName"],
                                    inline=False)
                    embed.add_field(name="・契約追加日",
                                    value=events[i]["contractAddTime"],
                                    inline=False)
                    embed.set_image(url=eventpic)
                    embeds.append(embed)

                else:
                    try:
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    png_name = "images/contingencycontract.png"
                    file = discord.File(os.path.join(dir, png_name),
                                        filename="image.png")
                    embed = discord.Embed(title=events[i]["name"],
                                            description=events[i]["time"],
                                            color=0x6d2727,
                                            url=link)
                    embed.set_author(name="危機契約",
                                        icon_url="attachment://image.png")
                    embed.add_field(name="・常設ステージ",
                                    value=events[i]["permStage"],
                                    inline=False)
                    embed.add_field(name="・本日のデイリーステージ",
                                    value=events[i]["todaysDaily"]["stageName"],
                                    inline=False)
                    embed.add_field(name="・契約が追加されています！",
                                    value="危機契約も後半戦です！一緒に頑張りましょう！！",
                                    inline=False)
                    embed.set_image(url=eventpic)
                    embeds.append(embed)

            elif events[i]["type"] == "SIDESTORY":
                if events[i]["stageAdd"] == "True":
                    try:
                        nextStageName = events[i]["nextStageName"]
                        nextAddTime = events[i]["nextAddTime"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    embed = discord.Embed(title=events[i]["name"],
                                            description=events[i]["time"],
                                            color=0x24ab12,
                                            url=link)
                    embed.set_author(name="サイドストーリー")
                    embed.add_field(name=f"次のステージ追加 「{nextStageName}」",
                                    value=nextAddTime)
                    embed.set_image(url=eventpic)
                    embeds.append(embed)
                else:
                    try:
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    embed = discord.Embed(title=events[i]["name"],
                                            description=events[i]["time"],
                                            color=0x368ad9,
                                            url=link)
                    embed.set_author(name="サイドストーリー")
                    embed.set_image(url=eventpic)
                    embeds.append(embed)

            elif events[i]["type"] == "MINISTORY":
                try:
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception:
                    pass

                embed = discord.Embed(title=events[i]["name"],
                                        description=events[i]["time"],
                                        color=0xCAC531,
                                        url=link)
                embed.set_author(name="オムニバスストーリー")
                embed.set_image(url=eventpic)
                embeds.append(embed)
                
            elif events[i]["type"] == "BOSS_RUSH":
                try:
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception:
                    pass

                embed = discord.Embed(title=events[i]["name"],
                                        description=events[i]["time"],
                                        color=0xFFBA00,
                                        url=link)
                embed.set_author(name="導灯の試練")
                embed.set_image(url=eventpic)
                embeds.append(embed)
                
            elif events[i]["type"] == "SANDBOX":
                try:
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception:
                    pass

                embed = discord.Embed(title=events[i]["name"],
                                        description=events[i]["time"],
                                        color=0xB0DB34,
                                        url=link)
                embed.set_author(name="生息演算")
                embed.set_image(url=eventpic)
                embeds.append(embed)

            elif events[i]["type"] == "MAIN":
                try:
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception as e:
                    logger.warn(f"[morning:main]: {e}")

                embed = discord.Embed(title=events[i]["name"],
                                        description=events[i]["time"],
                                        color=0x353536,
                                        url=link)
                embed.set_author(name="理性保護&物資回収キャンペーン")
                embed.set_image(url=eventpic)
                embeds.append(embed)
                
            elif events[i]["type"] == "ROGUELIKE":
                try:
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception as e:
                    logger.warn(f"[morning:main]: {e}")
                    
                embed = discord.Embed(title=events[i]["name"],
                                        color=0xFFFFFF,
                                        url=link)
                embed.set_author(name="統合戦略")
                embed.set_image(url=eventpic)
                
                if events[i]["month"]:
                    month = events[i]["month"]
                    content = events[i]["content"]
                    updateTime = events[i]["updateTime"]
                    embed.add_field(name = f"{month}月の更新内容", value = f"{content}\n\n{updateTime}", inline = False)
                    
                    if events[i]["nextmonth"]:
                        nextmonth = events[i]["nextmonth"]
                        nextcontent = events[i]["nextcontent"]
                        nextUpdateTime = events[i]["nextUpdateTime"]
                        embed.add_field(name = f"{nextmonth}月の更新内容", value = f"{nextcontent}\n\n{nextUpdateTime}", inline = False)
                
                embeds.append(embed)                

            else:
                embed = discord.Embed(title=events[i]["name"],
                                        description=events[i]["time"],
                                        color=0xf29382)
                embed.set_author(name="イベント")
                embeds.append(embed)

        elif events[i]["dif"] == "past":
            eventpic = events[i]["pic"]
            rewardEndTime = events[i]["rewardEndTime"]
            embed = discord.Embed(title=events[i]["name"],
                                    description=f"報酬受取期限：{rewardEndTime}",
                                    color=0x454545)
            embed.set_author(name="終了したイベント")
            embed.set_image(url=eventpic)
            embeds.append(embed)

        else:
            eventpic = events[i]["pic"]
            eventnews = events[i]["news"]
            embed = discord.Embed(title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0xba80ea,
                                    url = eventnews)
            embed.set_author(name="開催予定のイベント")
            embed.set_image(url=eventpic)
            embeds.append(embed)
    
    refreshTime = "<t:{0}:F>( <t:{0}:R> )".format(round(time.time()))
    
    if mode == "morning":        
        content = f"(最終更新: {refreshTime} )\n\nおはようございます:sunny: ロードです！  {eventnow}{eventend}{eventfuture}{weekday}{bdayop}"
    elif mode == "afternoon":
        content = f"(最終更新: {refreshTime} )\n\nこんにちは:sunny: ロードです！  {eventnow}{eventend}{eventfuture}{weekday}{bdayop}"
    elif mode == "evening":
        content = f"(最終更新: {refreshTime} )\n\nこんばんは:sunny: ロードです！  {eventnow}{eventend}{eventfuture}{weekday}{bdayop}"
        
    if embeds:
        if file:
            await message.edit(content = content, file = file, embeds = embeds)
        else:
            await message.edit(content = content, embeds=embeds)
