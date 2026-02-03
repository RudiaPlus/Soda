import datetime
import json
import os
import time

import discord
import requests
from extentions import JSTTime, evjson, log, maintenances, supportrequest
from extentions.aclient import client
from extentions.config import config

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger()
test = config.test

@client.tree.command(name="set_remind",
                        description="リマインドを作り直します",
                        guild=discord.Object(config.testserverid))
@discord.app_commands.describe(
    game="ゲーム arknights/endfield (デフォルト: arknights)"
)
async def set_remind(interaction: discord.Interaction, game: str = "arknights"):
    await interaction.response.defer()
    
    # Get appropriate channel based on game
    if game == "endfield":
        channel = client.get_channel(config.efremind)
    else:
        channel = client.get_channel(config.remind) if test is False else client.get_channel(config.remind_TEST)
    
    message = await channel.send(f"{game}リマインダーを作り直します")
    message_key = "endfieldRemindMessage" if game == "endfield" else "remindMessage"
    config.dynamic[message_key] = {"id": message.id, "thread_id": 0}
    config.write_dynamic_config()
    await remind(game)
    await interaction.followup.send("完了しました")
    
async def reminder_message(type: str = "message", game: str = "arknights"):
    """
    Get reminder message ID for specified game
    Args:
        type: "message", "thread", or "last_remind"
        game: "arknights" or "endfield"
    """
    if game == "endfield":
        message_key = "endfieldRemindMessage"
    else:
        message_key = "remindMessage"
    
    if type == "message":
        return(config.dynamic[message_key]["id"])
    elif type == "thread":
        return(config.dynamic[message_key]["thread_id"])
    elif type == "last_remind":
        return(config.dynamic[message_key]["last_remind_id"])
        
async def load_remind_dic(game: str = "arknights") -> dict:
    """
    Load reminder dictionary for specified game
    Args:
        game: "arknights" or "endfield"
    """
    today_timestamp = JSTTime.timeJST("timestamp")
    json_name = "jsons/reminds.json"
    with open(os.path.join(dir, json_name), "r", encoding="utf-8") as f:
        all_reminds = json.load(f)
    
    remind_dic = all_reminds.get(game, {})
    
    # Existing Arknights logic for dailyStageRemind
    if game == "arknights" and "dailyStageRemind" in remind_dic:
        if remind_dic["dailyStageRemind"]["allAvailable"] is False:
            if remind_dic["dailyStageRemind"]["allStartTime"] < today_timestamp and today_timestamp < remind_dic["dailyStageRemind"]["allEndTime"]:
                remind_dic["dailyStageRemind"]["allAvailable"] = True
                all_reminds[game] = remind_dic
                await write_remind_dic(all_reminds)
        else:
            if remind_dic["dailyStageRemind"]["allEndTime"] < today_timestamp:
                remind_dic["dailyStageRemind"]["allAvailable"] = False
                all_reminds[game] = remind_dic
                await write_remind_dic(all_reminds)
       
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
        logger.warning("スレッド作成のメッセージが送信されていませんので、削除しませんでした。")
        
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

# ========== Endfield Reminder Functions ==========

async def endfield_weekly_limit() -> datetime.datetime:
    """Calculate next weekly quest deadline for Endfield (Monday 4:59:59 AM JST)"""
    tz_JST = JSTTime.tz_JST
    now = datetime.datetime.now(tz_JST)
    
    if now.weekday() == 0 and now.hour < 5:  # Monday before 5:00 AM
        next_monday = now
    else:
        next_monday = now + datetime.timedelta(days=(7 - now.weekday() or 7))
    next_monday_limit = datetime.datetime(next_monday.year, next_monday.month, next_monday.day, 4, 59, 59, tzinfo=tz_JST)
    
    return next_monday_limit

async def get_endfield_expiring_redemption_codes() -> list:
    """
    Get redemption codes expiring within 1 day (before next 5:00 AM reset)
    """
    try:
        from extentions.communitytool import load_redemption_codes
        codes = load_redemption_codes()
        
        tz_JST = JSTTime.tz_JST
        now = datetime.datetime.now(tz_JST)
        current_timestamp = int(now.timestamp())
        
        # Calculate the next reset time (tomorrow 5:00 AM)
        if now.hour < 5:
            next_reset = datetime.datetime(now.year, now.month, now.day, 5, 0, 0, tzinfo=tz_JST)
        else:
            tomorrow = now + datetime.timedelta(days=1)
            next_reset = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 5, 0, 0, tzinfo=tz_JST)
        
        next_reset_timestamp = int(next_reset.timestamp())
        
        # Find codes expiring between now and next reset
        expiring_codes = [
            code_data for code_data in codes
            if current_timestamp < code_data["expiration"] <= next_reset_timestamp
        ]
        
        return sorted(expiring_codes, key=lambda x: x["expiration"])
    except Exception as e:
        logger.error(f"Endfield引き換えコード取得中にエラー: {e}")
        return []

async def check_endfield_redemption_codes_expiring_soon() -> str:
    """
    Check if any redemption codes are expiring within 1 day
    Endfield's daily reset is at 5:00 AM JST, so we need to account for that
    """
    try:
        expiring_codes = await get_endfield_expiring_redemption_codes()
        
        if expiring_codes:
            warning = f"\n\n**⚠️ 引き換えコード期限警告**"
            warning += f"\n{len(expiring_codes)}個の引き換えコードが本日中（翌日5:00まで）に期限切れになります！"
            
            # List the codes in markdown format for easy copying
            code_list = "\n```\n"
            for code_data in expiring_codes:
                code_list += f"{code_data['code']}\n"
            code_list += "```"
            warning += code_list
            
            warning += f"\n詳細は<#{config.redemption_code_channel}>をご確認ください！"
            return warning
        
        return ""
    except Exception as e:
        logger.error(f"Endfield引き換えコード期限チェック中にエラー: {e}")
        return ""

async def endfield_daily_message_maker(remind_dic: dict) -> str:
    """Create daily reminder message for Endfield"""
    today = JSTTime.timeJST("raw")
    weekday_today = JSTTime.timeJST("weekday")
    
    first = f"本日は{today.month}月{today.day}日({weekday_today})です。"

    daily_tasks = ""    
    # Weekly quest reminder
    if weekday_today == "日":
        daily_tasks += "\n- **本日は日曜日です！ ウィークリークエストは終わらせましたか？**"
    
    # Get event counts
    event_count = evjson.eventcount("endfield")
    event_now = event_count[0]
    event_today = event_count[3]
    event_end_today = event_count[4]
    
    # Add event information
    if event_now > 0:
        daily_tasks += f"\n- 現在**{event_now}個**のイベントが進行中です"
    if event_today > 0:
        daily_tasks += f"\n- 本日から**{event_today}個**のイベントが開始されます"
    if event_end_today > 0:
        daily_tasks += f"\n- 本日中に**{event_end_today}個**のイベントが終了します"
    
    # Check for redemption codes expiring soon (within 1 day, considering 5:00 AM reset)
    redemption_warning = await check_endfield_redemption_codes_expiring_soon()
    
    content = f"<@&1076155144363851888>\nおはようございます:sunny: ロードです！ {first}{daily_tasks}{redemption_warning}"
    return content

async def send_endfield_remind_to_thread(thread: discord.Thread, remind_dic: dict) -> None:
    """Send Endfield reminders to thread"""
    embeds = []
    
    # Weekly quest reminder
    if "weeklyRemind" in remind_dic:
        weekly = remind_dic["weeklyRemind"]
        next_weekly_limit = await endfield_weekly_limit()
        next_weekly_limit_timestamp = round(next_weekly_limit.timestamp())
        wlimit_embed = "<t:{0}:R>".format(next_weekly_limit_timestamp)
        
        description = weekly["description"].format(wlimit_embed)
        
        embed = discord.Embed(
            title=weekly["name"],
            description=description,
            color=0xD86236  # Same orange as Arknights regular reminders
        )
        embeds.append(embed)
    
    # SKPORT login bonus reminder
    if "skportRemind" in remind_dic:
        skport = remind_dic["skportRemind"]
        embed = discord.Embed(
            title=skport["name"],
            description=f"{skport['description']}\n[SKPORTへ]({skport['link']})",
            color=0x4A90E2  # Endfield blue color
        )
        embeds.append(embed)
    
    # Redemption code warning (if any codes expiring within 1 day)
    expiring_codes = await get_endfield_expiring_redemption_codes()
    if expiring_codes:
        embed = discord.Embed(
            title="⚠️ 引き換えコード期限警告",
            description=f"{len(expiring_codes)}個のコードが本日中（翌日5:00まで）に期限切れになります",
            color=0xFF6B6B  # Warning red
        )
        
        # Show codes in a code block for easy copying
        code_list = "```\n"
        for code_data in expiring_codes[:10]:  # Show max 10
            code_list += f"{code_data['code']}\n"
        code_list += "```"
        
        embed.add_field(
            name="引き換えコード",
            value=code_list,
            inline=False
        )
        
        # Show expiration times
        expiration_list = ""
        for code_data in expiring_codes[:10]:
            expiration_timestamp = code_data["expiration"]
            expiration_list += f"• `{code_data['code']}`: <t:{expiration_timestamp}:R>\n"
        
        embed.add_field(
            name="期限",
            value=expiration_list,
            inline=False
        )
        
        embeds.append(embed)
    
    content = await endfield_daily_message_maker(remind_dic)
    message = await thread.send(content=content, embeds=embeds)
    
    # Update dynamic config with last remind message
    config.dynamic["endfieldRemindMessage"]["last_remind_id"] = message.id
    config.write_dynamic_config()
    
    # Pin the message
    pinned_messages = await thread.pins()
    if pinned_messages:
        for msg in pinned_messages:
            await msg.unpin()
    await message.pin()

async def daily_message_maker(remind_dic: dict):
    eventcount = evjson.eventcount()
    today = JSTTime.timeJST("raw")
    weekday_today = JSTTime.timeJST("weekday")
    first = f"本日は{today.month}月{today.day}日({weekday_today})です。"
    
    if remind_dic["dailyStageRemind"]["allAvailable"] is True:
        first += "\n**危機契約が始まっています！無理せずに頑張りましょう！！**"
    
    if today.day == 1:
        special_day = f"\n今日から{today.month}月が始まりますね！資格証交換が更新されているのでご確認ください！"
        if today.month == 1:
            special_day = f"\nあけましておめでとうございます！{today.year}年もどうかよろしくお願いしますね！"
            
        if today.month == 4:
            special_day = f"\n今日から{today.month}月が始まりますね！資格証交換が更新されているのでご確認ください！ただ、何やら様子がおかしいですね……？"        
            
    elif today.month == 2 and today.day == 14:
        special_day = "\n本日はバレンタインデーです！皆さんはチョコ、好きでしょうか……？"
        
    elif today.month == 2 and today.day == 22:
        special_day = "\n本日は猫の日です！:cat: フェリーンの皆さんにも優しくしてあげましょうね！"
        
    elif today.month == 3 and today.day == 14:
        special_day = "\n本日はホワイトデーらしいですよ！"
        
    elif today.month == 10 and today.day == 31:
        special_day = "\n**ハッピーハロウィン**！何かお菓子が欲しい気分です……あ、いたずらはしませんのでご安心ください！本当ですよ！"
        
    elif today.month == 12 and today.day == 24:
        special_day = "\n本日はクリスマスイヴです！私も良い子にしていたら、何かもらえるでしょうか……？"
        
    elif today.month == 12 and today.day == 25:
        special_day = "\n本日はクリスマス！素敵な日をお過ごし下さい！"
        
    elif today.month == 12 and today.day == 31:
        special_day = "\n大晦日ですね！今年の目標、皆さんは叶えられましたか……？私は……忘れちゃいました……。"
        
    else:
        special_day = ""


    if eventcount[3] != 0:
        eventnow = "\n- **本日からイベントが開催されます！**"
    else:
        eventnow = ""
        
    if eventcount[0] == 1:
        eventnow += "\n- イベントが進行中です:sparkles: 頑張りましょう！"
    elif eventcount[0] > 1:
        eventnow += f"\n- 本日は{eventcount[0]}個のイベントが進行中です:sparkles: 頑張りましょう！"
        
    if eventcount[4] != 0:
        eventendToday = "\n- **本日で終了するイベントがあります！ご注意ください！**"
    else:
        eventendToday = ""

    if eventcount[1] == 0:
        eventend = ""
    elif eventcount[1] == 1:
        eventend = "\n- 終了したイベントがあります！ 報酬の受け取りを忘れずに！:eyes:"
    else:
        eventend = f"\n- {eventcount[1]}個のイベントが終了しています。報酬の受け取りを忘れずに！:eyes:"

    if eventcount[2] == 0:
        eventfuture = ""
    elif eventcount[2] == 1:
        eventfuture = "\n- 開催予定のイベントがあります！ 楽しみですね！:star2:"
    else:
        eventfuture = f"\n- {eventcount[2]}個のイベントがこの先やってきます！準備は出来ていますか？"

    if weekday_today == "日":
        weekday = "\n- **本日は日曜日です！ 殲滅作戦は終わらせましたか？**"
    else:
        weekday = ""
    if today.day == 15:
        monthly = "\n- **保全駐在の報酬期限は今日までです！報酬は受け取りましたか？**"
    else:
        monthly = ""
    
    content = f"<@&1076155144363851888>\nおはようございます:sunny: ロードです！  {first}{special_day}{eventnow}{eventendToday}{eventend}{eventfuture}{weekday}{monthly}\n- イベント情報はこちら！→<#{config.remind}>"
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
        
    next_weekly_limit = await weekly_limit()
    next_weekly_limit_timestamp = round(next_weekly_limit.timestamp())
    wlimit_embed = "<t:{0}:R>".format(next_weekly_limit_timestamp)
    
    next_module_limit = await monthly_limit(limit_day=16)
    next_module_limit_timestamp = round(next_module_limit.timestamp())
    mlimit_embed = "<t:{0}:R>".format(next_module_limit_timestamp)
    
    now_timestamp = JSTTime.timeJST("timestamp")
    today = JSTTime.timeJST("weekday")
    
    for key in remind_dic:
        
        color = 0xffffff
        value = remind_dic[key]

        if key == "dailyStageRemind":
            color = 0xA08A87
            dailyStage = value
            
            material_stages = []
            soc_stages = []
            
            for stage in dailyStage["stage"]:
                if today in stage["available"] or dailyStage["allAvailable"] is True:
                    stageid = stage["id"]
                    type = stage["type"]
                    stagename = stage["name"]
                    
                    if type == "資源調達":
                        material_stages.append(f"**{stageid}**:{stagename}")
                    elif type == "SoC探索":
                        soc_stages.append(f"**{stageid}**:{stagename}")
        
        description = value["description"]
        
        if value["type"] == "regular":
            color = 0xD86236
            description = description.format(wlimit_embed, mlimit_embed)
            
        if value["type"] == "anni" or value["type"] == "sss":
            if now_timestamp > value["endTime"]:
                continue
            color = 0xF65555 if value["type"] == "anni" else 0x669676
            startTime = "<t:{0}:F>( <t:{0}:R> )".format(value["startTime"])
            endTime = "<t:{0}:F>( <t:{0}:R> )".format(value["endTime"])
            eventTime = f"開始: {startTime}\n終了: {endTime}"
            
            if now_timestamp < value["startTime"]:
                description = f"- 実装予定\n{eventTime}"
                
            else:
                link = value["link"]
                description = f"- 攻略情報: [有志Wiki]({link})\n{eventTime}"
        
        embed = discord.Embed(title = value["name"], description=description, color = color)
        
        if key == "dailyStageRemind":
            if material_stages:
                embed.add_field(name = "資源調達", value = "、".join(material_stages), inline=False)
            if soc_stages:
                embed.add_field(name = "SoC探索", value = "、".join(soc_stages), inline=False)
        
        embeds.append(embed)
        
    content = await daily_message_maker(remind_dic=remind_dic)
    last_remind_message = await thread.send(content = content, embeds = embeds)
    config.dynamic["remindMessage"]["last_remind_id"] = last_remind_message.id
    config.write_dynamic_config()
    pinned_messages = await thread.pins()
    if pinned_messages:
        for message in pinned_messages:
            await message.unpin()
    await last_remind_message.pin()

async def remind(game="arknights"):
    """
    Main reminder function - updates both thread and message source
    Args:
        game: "arknights" or "endfield"
    """
    # Get appropriate channel
    if game == "endfield":
        channel = client.get_channel(config.efremind)
    else:
        channel = client.get_channel(config.remind) if test is False else client.get_channel(config.remind_TEST)
    
    # Load appropriate reminder data
    remind_dic = await load_remind_dic(game)
    
    # For Arknights, load events and maintenance
    if game == "arknights":
        events = evjson.eventget()
        maintenance = await maintenances.maintenance_list()
    
    embeds = []
    files = []

    try:
        messageid = await reminder_message("message", game)
        if not messageid:
            logger.error(f"{game}リマインドメッセージが見つかりません。 /set_remindで作り直してください。")
            return
        message = await channel.fetch_message(messageid)
        
    except discord.NotFound:
        logger.error(f"{game}リマインドメッセージが見つかりません。 /set_remindで作り直してください。")
        return
    except ValueError:
        logger.error(f"{game}リマインドメッセージが正しく辞書に登録されていません。 /set_remindで作り直してください。")
        return
    
    # Update thread
    try:
        threadid = await reminder_message("thread", game)
        if not threadid:
            logger.warning(f"{game}リマインドスレッドは作られていません。")
            threadid = 0
            
        thread = channel.get_thread(threadid)
        
        if not thread:
            logger.warning(f"{game}リマインドスレッドが見つかりません。作成します")
            thread = await create_thread(channel, message)
        
            message_key = "endfieldRemindMessage" if game == "endfield" else "remindMessage"
            config.dynamic[message_key]["thread_id"] = thread.id
            config.write_dynamic_config()
        
    except Exception:
        logger.error(f"{game}スレッドの取得と作成に失敗しました")
        return
    
    # Send to thread based on game
    if game == "endfield":
        await send_endfield_remind_to_thread(thread, remind_dic)
    else:
        await send_remind_to_thread(thread, remind_dic, events)
    
    # Update message source (event list)
    logger.info(f"[remind] Starting message source update for {game}")
    if game == "arknights":
        png_name = "images/banner_event.png"
        file = discord.File(os.path.join(dir, png_name), filename="banner.png")
        files.append(file)
        embed = discord.Embed(color = discord.Color.dark_grey())
        embed.set_image(url = "attachment://banner.png")
        embeds.append(embed)
        logger.info(f"[remind] Added banner embed, embeds count: {len(embeds)}")

        for i in range(len(maintenance)):
            title = maintenance[i]["name"]
            eventTime = maintenance[i]["time"]
            url = maintenance[i]["link"]
            description = eventTime if not url else f"- 詳細: [公式サイト]({url})\n{eventTime}"
            embed = discord.Embed(title=title,
                                    description=description,
                                    color=0xf5b642,
                                    url = url)
            embed.set_author(name="メンテナンス")
            embeds.append(embed)

        logger.info(f"[remind] Processed {len(maintenance)} maintenance items")

        for i in range(len(events)):
            if events[i]["dif"] == "present":
                if events[i]["type"] == "CRISIS":
                    
                    try:
                        title =  events[i]["name"]
                        eventTime =  events[i]["time"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                        eventColor = int(events[i]["eventColor"], 16)
                    except Exception:
                        pass

                    embed = discord.Embed(title=title,
                                            description=f"- **高難易度のイベントです！**\n- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=eventColor,
                                            url=link)
                    embed.set_author(name="危機契約")
                    embed.add_field(name="・通常試験区画",
                                    value=f'**{events[i]["permStage"]}**')
                    embed.add_field(name="・特別試験区画",
                                    value=f'**{events[i]["todaysDaily"]["stageName"]}**\n> 賞金獲得期限: <t:{events[i]["dailyEnd"]}:R>',)
                        
                    embed.set_image(url = eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "ROGUELIKE":
                    
                    try:
                        title =  events[i]["name"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass
                    
                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})",
                                            color=0x852B2F,
                                            url=link)
                    embed.set_author(name="統合戦略")
                    
                    if events[i]["month"]:
                        embed.add_field(name=f'・{events[i]["month"]}月の任務',
                                        value=f'{events[i]["content"]}\n> {events[i]["updateTime"]}',
                                        inline=False)
                    
                    if events[i]["nextmonth"]:
                        embed.add_field(name=f'・{events[i]["nextmonth"]}月の任務',
                                        value=f'{events[i]["nextcontent"]}\n> {events[i]["nextUpdateTime"]}',
                                        inline=False)
                    
                    embed.set_image(url = eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "SANDBOX":
                    
                    try:
                        title =  events[i]["name"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass
                    
                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})",
                                            color=0xB0DB34,
                                            url=link)
                    embed.set_author(name="生息演算")
                    
                    if events[i]["month"]:
                        embed.add_field(name=f'・{events[i]["month"]}月の闘争の潮流',
                                        value=f'{events[i]["content"]}\n> {events[i]["updateTime"]}',
                                        inline=False)
                    
                    if events[i]["nextmonth"]:
                        embed.add_field(name=f'・{events[i]["nextmonth"]}月の闘争の潮流',
                                        value=f'{events[i]["nextcontent"]}\n> {events[i]["nextUpdateTime"]}',
                                        inline=False)
                    
                    embed.set_image(url = eventpic)
                    embeds.append(embed)
                    
                elif events[i]["type"] == "BREAK":
                    
                    try:
                        title =  events[i]["name"]
                        eventTime =  events[i]["time"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                        eventColor = int(events[i]["eventColor"], 16)
                    except Exception:
                        pass

                    embed = discord.Embed(title=title,
                                            description=f"- **高難易度のイベントです！**\n- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=eventColor,
                                            url=link)
                    embed.set_author(name="殲滅作戦")
                    embed.add_field(name="・第2段階開放",
                                    value=f'> 開放: {events[i]["phase2StartTime"]}')
                        
                    embed.set_image(url = eventpic)
                    embeds.append(embed)
                    
                else:
                    
                    try:
                        title =  events[i]["name"]
                        eventTime =  events[i]["time"]
                        news =  events[i]["news"]
                        link = events[i]["link"]
                        eventpic = events[i]["pic"]
                    except Exception:
                        pass
                    
                    event_type = events[i]["type"]
                    
                    if event_type == "SIDESTORY":
                        if events[i].get("stageAdd") is True:
                            author_name = "サイドストーリー"
                            color = 0x24ab12
                        else:
                            author_name = "サイドストーリー"
                            color = 0xD94A36
                    elif event_type == "MINISTORY":
                        author_name = "オムニバスストーリー"
                        color = 0xCAC531
                    elif event_type == "BOSS_RUSH":
                        author_name = "導灯の試練"
                        color = 0xFFBA00
                    elif event_type == "MULTIPLAY":
                        author_name = "マルチイベント"
                        color = 0xCAC531
                    elif event_type == "MAIN":
                        author_name = "新章実装キャンペーン"
                        color = 0x353536
                    elif event_type == "SUPPORT":
                        author_name = "新章公開 - 事前準備"
                        color = 0x5C7CA8
                    else:
                        author_name = "イベント"
                        color = 0xf29382
                    
                    embed = discord.Embed(title=title,
                                            description=f"- 詳細: [公式サイト]({news})\n- 攻略情報: [有志Wiki]({link})\n{eventTime}",
                                            color=color,
                                            url=link)
                    embed.set_author(name=author_name)
                    
                    if events[i].get("remark"):
                        remark = events[i]["remark"]
                        embed.description = f"- {remark}\n" + embed.description
                    
                    if events[i].get("stageAdd") is True:
                        embed.add_field(name="・追加ステージ",
                                        value=f'**{events[i]["nextStageName"]}**\n> 追加: {events[i]["nextAddTime"]}',
                                        inline=False)
                    
                    embed.set_image(url = eventpic)
                    embeds.append(embed)
                    
            elif events[i]["dif"] == "past":
                
                try:
                    title =  events[i]["name"]
                    rewardEndTime =  events[i]["rewardEndTime"]
                    link = events[i]["link"]
                    eventpic = events[i]["pic"]
                except Exception:
                    pass
                
                embed = discord.Embed(title=title,
                                        description=f"- 攻略情報: [有志Wiki]({link})\n> 報酬交換期限: {rewardEndTime}",
                                        color=discord.Color.dark_grey(),
                                        url=link)
                embed.set_author(name="終了したイベント")
                embed.set_image(url = eventpic)
                embeds.append(embed)
                
            elif events[i]["dif"] == "future":
                
                try:
                    title =  events[i]["name"]
                    eventTime =  events[i]["time"]
                    news =  events[i]["news"]
                    eventpic = events[i]["pic"]
                except Exception:
                    pass
                
                if events[i]["type"] == "SIDESTORY":
                    author_name = "サイドストーリー"
                    color = discord.Color.blue()
                elif events[i]["type"] == "MINISTORY":
                    author_name = "ミニストーリー"
                    color = discord.Color.green()
                elif events[i]["type"] == "ROGUELIKE":
                    author_name = "統合戦略"
                    color = 0x0096fa
                elif events[i]["type"] == "SANDBOX":
                    author_name = "生息演算"
                    color = 0xffa500
                else:
                    author_name = "イベント"
                    color = discord.Color.orange()
                
                embed = discord.Embed(title=title,
                                        description=f"- 詳細: [公式サイト]({news})\n{eventTime}",
                                        color=color,
                                        url=news)
                embed.set_author(name=f"開催予定の{author_name}")
                embed.set_image(url = eventpic)
                embeds.append(embed)
        
        logger.info(f"[remind] Processed {len(events)} events, added {len(embeds)} embeds so far")
        
        refreshTime = JSTTime.timeJST("raw")
        refreshTime = f"<t:{round(refreshTime.timestamp())}:F>"
        
        logger.info(f"[remind] Starting gacha processing")
        
        # Add scout banner
        png_name = "images/banner_scout.png"
        file = discord.File(os.path.join(dir, png_name), filename="banner_scout.png")
        files.append(file)
        embed = discord.Embed(color = discord.Color.dark_grey())
        embed.set_image(url = "attachment://banner_scout.png")
        embeds.append(embed)
        
        image_dir = os.path.join(dir, "images")
        
        try:
            gacha_dict = await evjson.gachaget()
            logger.info(f"[remind] Got {len(gacha_dict)} gacha items")
            
            k = 0
            for gacha, image_url in gacha_dict.items():
                k += 1
                image_name = f"scout_image_{k}.png"
                
                # Download gacha image
                r = requests.get(image_url)
                gacha_image = r.content
                with open(os.path.join(image_dir, image_name), "wb") as f:
                    f.write(gacha_image)
                
                if "ロドスの道のり" in gacha:
                    author_name = "スペシャルスカウト・ロドスの道のり"
                    color = discord.Color.green()
                elif "中堅" in gacha:
                    author_name = "中堅スカウト"
                    color = discord.Color.blue()
                elif "常設" in gacha:
                    author_name = "常設スカウト"
                    color = discord.Color.yellow()
                else:
                    author_name = "イベントスカウト"
                    color = discord.Color.orange()
                    
                embed = discord.Embed(color = color)
                embed.set_author(name = author_name)
                    
                file = discord.File(os.path.join(image_dir, image_name), filename = image_name)
                files.append(file)
                embed.set_image(url = f"attachment://{image_name}")      
                embeds.append(embed)
            
            logger.info(f"[remind] Processed {len(gacha_dict)} gacha banners")
        except Exception as e:
            logger.error(f"[remind] Error processing gacha: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        
        # Always update, even if no events
        logger.info(f"[remind] Arknights updating message. Embeds: {len(embeds)}, Files: {len(files)}")
        if files:
            await message.edit(content = f"最終更新: {refreshTime}", attachments = files, embeds = embeds)
        else:
            await message.edit(content = f"最終更新: {refreshTime}", attachments = [], embeds=embeds)
        logger.info(f"[remind] Arknights message updated successfully")
    
    else:  # Endfield
        # For Endfield, create event list embeds
        event_dic = evjson.eventget("endfield")
        
        # Version calendar
        for event in event_dic:
            if event.get("type") == "VERSION_CALENDAR" and event.get("dif") == "calendar":
                embed = discord.Embed(
                    title=f"{event['name']}",
                    description=f"**バージョン:** {event['version']}",
                    color=discord.Color.dark_grey()
                )
                embed.set_author(name="バージョンスケジュール")
                if "images" in event and event["images"]:
                    # Ensure Twitter image URLs have proper format
                    image_url = event["images"][0]
                    if "pbs.twimg.com" in image_url and not image_url.endswith((".jpg", ".png", ".webp")):
                        image_url += ":large"  # Add Twitter image size suffix
                    embed.set_image(url=image_url)
                embeds.append(embed)
                
                # Add additional images as separate embeds
                for i, img_url in enumerate(event["images"][1:], start=2):
                    if "pbs.twimg.com" in img_url and not img_url.endswith((".jpg", ".png", ".webp")):
                        img_url += ":large"
                    img_embed = discord.Embed(color=discord.Color.dark_grey())
                    img_embed.set_image(url=img_url)
                    embeds.append(img_embed)
                
                break
        
        # Current events
        current_events = [e for e in event_dic if e.get("dif") == "present"]
        for event in current_events:
            event_type = event.get("type", "")
            
            if event_type == "OPSTORY":
                color = 0x0096fa  # Blue for OPSTORY
                author_name = "物語イベント"
            else:
                color = 0xFFA500  # Orange for all other events
                author_name = "イベント"
            
            embed = discord.Embed(
                title=event['name'],
                description=event.get("description", ""),
                color=color
            )
            embed.set_author(name=author_name)
            
            if "time" in event:
                embed.add_field(name="\u200b", value=event["time"], inline=False)
            
            if event.get("news"):
                embed.add_field(name="ニュース", value=f"[リンク]({event['news']})", inline=True)
            
            if event.get("link"):
                embed.add_field(name="攻略情報", value=f"[リンク]({event['link']})", inline=True)
            
            if event.get("pic"):
                embed.set_image(url=event["pic"])
            
            embeds.append(embed)
        
        # Future events
        future_events = [e for e in event_dic if e.get("dif") == "future"]
        if future_events:
            for event in future_events[:5]:
                event_type = event.get("type", "")
                
                color = discord.Color.orange()
                
                embed = discord.Embed(
                    title=event['name'],
                    color=color
                )
                embed.set_author(name=f"開催予定の{author_name}")
                
                # Add time without label
                if event.get('time'):
                    embed.add_field(name="\u200b", value=event['time'], inline=False)
                
                if event.get("news"):
                    embed.add_field(name="ニュース", value=f"[リンク]({event['news']})", inline=False)
                
                if event.get("pic"):
                    embed.set_image(url=event["pic"])
                
                embeds.append(embed)
        
        refreshTime = JSTTime.timeJST("raw")
        refreshTime = f"<t:{round(refreshTime.timestamp())}:F>"
        
        
        # Always update
        await message.edit(content=f"最終更新: {refreshTime}", embeds=embeds)
    
    return thread
