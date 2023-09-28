import discord
import json
import asyncio
from extentions import log, config, JSTTime, evjson, maintenances
from extentions.aclient import client
import os
import requests
import datetime
import time
import re

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger(__name__)
test = config.test

@client.tree.command(name="set_remind",
                        description="リマインドを作り直します",
                        guild=config.testserverid)
@discord.app_commands.describe(version="リマインドの時間 morning/afternoon/evening")
async def set_remind(interaction: discord.Interaction, version: str):
    await interaction.response.defer()
    channel = client.get_channel(config.remind) if test == False else client.get_channel(config.remind_TEST)
    message = await channel.send("リマインダーを作り直します")
    remind_dic = await load_remind_dic()
    remind_dic["remindMessage"] = {"id": message.id, "thread_id": 0}
    await write_remind_dic(remind_dic)
    await remind(version)
    await interaction.followup.send("完了しました")
    
async def load_remind_dic() -> dict:
    
    json_name = "jsons/reminds.json"
    with open(os.path.join(dir, json_name), "r", encoding="utf-8") as f:
        remind_dic = json.load(f)
    return remind_dic

async def write_remind_dic(dic):
    json_name = "jsons/reminds.json"
    with open(os.path.join(dir, json_name), "w", encoding="utf-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info("reminds.jsonに新しく書き込みを行いました")

async def create_thread(channel: discord.TextChannel, message: discord.Message) -> discord.Thread:
    
    thread = await message.create_thread(name = "毎日のリマインダー", auto_archive_duration=10080)
    
    thread_create_message = await channel.fetch_message(channel.last_message_id)
    if not thread_create_message.id == message.id:
        await thread_create_message.delete()
    else:
        logger.warn("スレッド作成のメッセージが送信されていませんので、削除しませんでした。")
        
    return(thread)

async def weekly_limit() -> datetime.datetime:
    tz_JST = JSTTime.tz_JST
    now = datetime.datetime.now(tz_JST)
    
    if now.weekday() == 0 and now.hour < 4:
        next_monday = now
    else:
        next_monday = now + datetime.timedelta(days = (7-now.weekday() or 7)) 
    next_monday_4h = datetime.datetime(next_monday.year, next_monday.month, next_monday.day, 3, 59, 59, tzinfo=tz_JST)
    
    return next_monday_4h

async def monthly_limit(limit_day: int) -> datetime.datetime:
    tz_JST = JSTTime.tz_JST
    now = datetime.datetime.now(tz_JST)
    
    if now.day < limit_day or (now.day == limit_day and now.hour < 4):
        limit_day = datetime.datetime(now.year, now.month, limit_day, 3, 59, 59, tzinfo=tz_JST)
    else:
        if now.month == 12:
            limit_day = datetime.datetime(now.year + 1, 1, limit_day, 3, 59, 59, tzinfo=tz_JST)
        else:
            limit_day = datetime.datetime(now.year, now.month + 1, limit_day, 3, 59, 59, tzinfo=tz_JST)
            
    return limit_day

async def daily_message_maker():
    eventcount = evjson.eventcount()
    if eventcount[0] == 0:
        if eventcount[3] != 0:
            eventnow = "**本日からイベントが開催されます！**"
        else:
            eventnow = "本日は少し休める日ですね！"
    elif eventcount[0] == 1:
        eventnow = f"\n- イベントが進行中です:sparkles: 頑張りましょう！"
    else:
        eventnow = f"\n- 本日は{eventcount[0]}個のイベントが進行中です:sparkles: 頑張りましょう！"
        
    if eventcount[4] != 0:
        eventendToday = "\n- **本日で終了するイベントがあります！ご注意ください！**"
    else:
        eventendToday = ""

    if eventcount[1] == 0:
        eventend = ""
    elif eventcount[1] == 1:
        eventend = f"\n- 終了したイベントがあります！ 報酬の受け取りを忘れずに！:eyes:"
    else:
        eventend = f"\n- {eventcount[1]}個のイベントが終了しています。報酬の受け取りを忘れずに！:eyes:"

    if eventcount[2] == 0:
        eventfuture = ""
    elif eventcount[2] == 1:
        eventfuture = f"\n- 開催予定のイベントがあります！ 楽しみですね！:star2:"
    else:
        eventfuture = f"\n- {eventcount[2]}個のイベントがこの先やってきます！準備は出来ていますか？"

    if JSTTime.timeJST("weekday") == "日":
        weekday = "\n- **本日は日曜日です！ 殲滅作戦は終わらせましたか？**"
    else:
        weekday = ""
    if JSTTime.timeJST("raw").day == 15:
        monthly = "\n- **保全駐在の報酬期限は今日までです！報酬は受け取りましたか？**"
    else:
        monthly = ""
    
    content = f"<@&1076155144363851888>\nおはようございます:sunny: ロードです！  {eventnow}{eventendToday}{eventend}{eventfuture}{weekday}{monthly}\n- イベント情報はこちら！→<#{config.remind}>"
    return content

async def send_remind_to_thread(thread: discord.Thread, remind_dic: dict, event_dic: dict) -> None:
    
    embeds = []
    
    birthday_json_name = "jsons/birthday.json"
    with open(os.path.join(dir, birthday_json_name), encoding="utf-8") as f:
        birthday = json.load(f)
    today = JSTTime.timeJST("m/d")
    if today in birthday:
        bdayop = f"本日は{birthday[today]}が誕生日です:birthday: おめでとうございます！"
        embed = discord.Embed(title = "ハッピーバースデー！", description=bdayop, color = discord.Color.green())
        embeds.append(embed)
    
    for key in remind_dic:
        
        if key == "remindMessage":
            continue
        
        color = 0xffffff
        value = remind_dic[key]

        if key == "dailyStageRemind":
            color = 0xA08A87
            dailyStage = value
            today = JSTTime.timeJST("weekday")
            
            material_stages = []
            soc_stages = []
            
            for stage in dailyStage["stage"]:
                if today in stage["available"] or dailyStage["allAvailable"] == True:
                    stageid = stage["id"]
                    type = stage["type"]
                    stagename = stage["name"]
                    
                    if type == "資源調達":
                        material_stages.append(f"**{stageid}**:{stagename}")
                    elif type == "SoC探索":
                        soc_stages.append(f"**{stageid}**:{stagename}")
            
        
        next_weekly_limit = await weekly_limit()
        next_weekly_limit_timestamp = round(next_weekly_limit.timestamp())
        wlimit_embed = "<t:{0}:R>".format(next_weekly_limit_timestamp)
        
        next_module_limit = await monthly_limit(limit_day=16)
        next_module_limit_timestamp = round(next_module_limit.timestamp())
        mlimit_embed = "<t:{0}:R>".format(next_module_limit_timestamp)
        
        now = datetime.datetime.now(tz=JSTTime.tz_JST)
        description = value["description"]
        
        if value["type"] == "regular":
            color = 0xD86236
            description = description.format(wlimit_embed, mlimit_embed)
            
        if value["type"] == "anni" or value["type"] == "sss":
            color = 0xF65555 if value["type"] == "anni" else 0x669676
            startTime = "<t:{0}:F>( <t:{0}:R> )".format(value["startTime"])
            endTime = "<t:{0}:F>( <t:{0}:R> )".format(value["endTime"])
            eventTime = f"開始: {startTime}\n終了: {endTime}"
            if now.timestamp() < value["startTime"]:
                description = eventTime
                
            elif value["startTime"] < now.timestamp() and now.timestamp() < value["endTime"]:
                link = value["link"]
                description = f"- 攻略情報: [有志Wiki]({link})\n{eventTime}"
                
            else:
                continue
        
        embed = discord.Embed(title = value["name"], description=description, color = color)
        
        if key == "dailyStageRemind":
            if material_stages:
                embed.add_field(name = "資源調達", value = "、".join(material_stages), inline=False)
            if soc_stages:
                embed.add_field(name = "SoC探索", value = "、".join(soc_stages), inline=False)
        
        embeds.append(embed)
        
    content = await daily_message_maker()
    await thread.send(content = content, embeds = embeds)
                

async def remind(mode = "morning"):
    events = evjson.eventget()
    maintenance = await maintenances.maintenance_list()
    channel = client.get_channel(config.remind) if test == False else client.get_channel(config.remind_TEST)
    embeds = []
    file = None

    remind_dic = await load_remind_dic()
    try:
        
        messageid = remind_dic["remindMessage"]["id"]
        message = await channel.fetch_message(messageid)
        
    except discord.NotFound:
        logger.error("リマインドメッセージが見つかりません。 /set_remindで作り直してください。")
        return
    except ValueError:
        logger.error("リマインドメッセージが正しく辞書に登録されていません。 /set_remindで作り直してください。")
        return
    
    if mode == "thread":
        try:
            threadid = remind_dic["remindMessage"]["thread_id"]
            thread = channel.get_thread(threadid)

        except Exception:
            logger.warn("リマインドスレッドが見つかりません。作成を試みます。")
            thread = await create_thread(channel, message)
            
            remind_dic["remindMessage"]["thread_id"] = thread.id
            await write_remind_dic(remind_dic)
            
        await send_remind_to_thread(thread, remind_dic, events)
        return
        
    else:

        for i in range(len(maintenance)):
            title = maintenance[i]["name"]
            eventTime = maintenance[i]["time"]
            url = maintenance[i]["link"]
            embed = discord.Embed(title=title,
                                    description=f"- 詳細: [公式サイト]({url})\n{eventTime}",
                                    color=0xf5b642,
                                    url = url)
            embed.set_author(name="メンテナンス")
            embeds.append(embed)

        for i in range(len(events)):
            if events[i]["dif"] == "present":
                if events[i]["type"] == "CRISIS":
                    
                    try:
                        title =  events[i]["name"]
                        eventTime =  events[i]["time"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                        eventColor = events[i]["eventColor"]
                    except Exception:
                        pass

                    png_name = "images/contingencycontract.png"
                    file = discord.File(os.path.join(dir, png_name),
                                        filename="image.png")
                    embed = discord.Embed(title=title,
                                            description=f"- **高難易度のイベントです！**\n- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=eventColor,
                                            url=link)
                    embed.set_author(name="危機契約",
                                        icon_url="attachment://image.png")
                    embed.add_field(name="・常設ステージ",
                                    value=events[i]["permStage"],
                                    inline=False)
                    embed.add_field(name="・本日のデイリーステージ",
                                    value=events[i]["todaysDaily"]["stageName"],
                                    inline=False)
                    if events[i]["contractAdd"] == False:
                        embed.add_field(name="・契約追加日",
                                        value=events[i]["contractAddTime"],
                                        inline=False)
                    else:
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
                            eventTime =  events[i]["time"]
                            remark = events[i]["remark"]
                            news = events[i]["news"]
                            link = events[i]["link"]
                            eventpic = events[i]["pic"]
                            remark = f"\n- **{remark}**" if remark else ""
                        except Exception:
                            pass

                        embed = discord.Embed(title=title,
                                                description=f"{remark}- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                                color=0x24ab12,
                                                url=link)
                        embed.set_author(name="サイドストーリー")
                        embed.add_field(name=f"次のステージ追加 「{nextStageName}」",
                                        value=nextAddTime)
                        embed.set_image(url=eventpic)
                        embeds.append(embed)
                    else:
                        try:
                            title = events[i]["name"]
                            eventTime =  events[i]["time"]
                            remark = events[i]["remark"]
                            news = events[i]["news"]
                            link = events[i]["link"]
                            eventpic = events[i]["pic"]
                            remark = f"\n- {remark}" if remark else ""
                        except Exception:
                            pass

                        embed = discord.Embed(title=title,
                                                description=f"{remark}- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                                color=0xD94A36,
                                                url=link)
                        embed.set_author(name="サイドストーリー")
                        embed.set_image(url=eventpic)
                        embeds.append(embed)

                elif events[i]["type"] == "MINISTORY":
                    try:
                        title = events[i]["name"]
                        eventTime =  events[i]["time"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=0xCAC531,
                                            url=link)
                    embed.set_author(name="オムニバスストーリー")
                    embed.set_image(url=eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "BOSS_RUSH":
                    try:
                        title = events[i]["name"]
                        eventTime =  events[i]["time"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=0xFFBA00,
                                            url=link)
                    embed.set_author(name="導灯の試練")
                    embed.set_image(url=eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "SANDBOX":
                    try:
                        title = events[i]["name"]
                        eventTime =  events[i]["time"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass

                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=0xB0DB34,
                                            url=link)
                    embed.set_author(name="生息演算")
                    embed.set_image(url=eventpic)
                    embeds.append(embed)

                elif events[i]["type"] == "MAIN":
                    try:
                        title = events[i]["name"]
                        eventTime =  events[i]["time"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception as e:
                        logger.warn(f"[morning:main]: {e}")

                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 新規メインストーリー攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=0x353536,
                                            url=link)
                    embed.set_author(name="理性保護&物資回収キャンペーン")
                    embed.set_image(url=eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "ROGUELIKE":
                    try:
                        title = events[i]["name"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception as e:
                        logger.warn(f"[morning:main]: {e}")
                        
                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})",
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
                    try:
                        title = events[i]["name"]
                        eventTime =  events[i]["time"]
                        news = events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception as e:
                        logger.warn(f"[morning:main]: {e}")
                    
                    logger.warn(f"{title}は未知のイベントです")
                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
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
                eventTime =  events[i]["time"]
                embed = discord.Embed(title=events[i]["name"],
                                        description=f"- 詳細: [公式サイト]({news})\n{eventTime}",
                                        color=0xba80ea,
                                        url = eventnews)
                embed.set_author(name="開催予定のイベント")
                embed.set_image(url=eventpic)
                embeds.append(embed)
        
        refreshTime = "<t:{0}:F>( <t:{0}:R> )".format(round(time.time()))
            
        if embeds:
            if file:
                await message.edit(content = f"最終更新: {refreshTime}", file = file, embeds = embeds)
            else:
                await message.edit(content = f"最終更新: {refreshTime}", embeds=embeds)
