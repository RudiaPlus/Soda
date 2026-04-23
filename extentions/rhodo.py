import asyncio
import atexit
import datetime
import io
import json
import os
import re
from collections import namedtuple
from math import floor
from typing import Literal
from unicodedata import normalize

import discord
import requests as rq
from discord import app_commands
from discord.ext import tasks

from extentions import (
    JSTTime,
    chat,
    communitytool,
    evjson,
    event_handlers,
    log,
    maintenances,
    makeembed,
    moderates,
    modmails,
    multiplayertool,  # noqa: F401
    recruit,
    reminder,
    supportrequest,
    twitterpost,
    voicechat,
)
from extentions.aclient import client, voice_clients_list
from extentions.config import config

logger = log.setup_logger()

#global変数
remindThreadID = 0
guildID = config.main_server
preset_names = []

test = config.test
dir = os.path.abspath(__file__ + "/../")


def run_discord_bot():
    #ログアウトイベントをループに知らせるためのtuple
    Entry = namedtuple("entry", "client event token")
    token = config.token if config.test is False else config.test_client
    voice_tokens = config.voice_tokens
    entries = [
        Entry(client = client, event = asyncio.Event(), token = token),
        Entry(client = voice_clients_list[0], event = asyncio.Event(), token = voice_tokens[0]), #読み上げ[Α]
        Entry(client = voice_clients_list[1], event = asyncio.Event(), token = voice_tokens[1]), #読み上げ[Β]
        Entry(client = voice_clients_list[2], event = asyncio.Event(), token = voice_tokens[2]), #読み上げ[Γ]
        Entry(client = voice_clients_list[3], event = asyncio.Event(), token = voice_tokens[3]), #読み上げ[Δ]
        Entry(client = voice_clients_list[4], event = asyncio.Event(), token = voice_tokens[4])  #読み上げ[Ε]
    ]

    #全てのbotでログインする場合の接続コール

    loop = asyncio.get_event_loop()

    async def login():
        for e in entries:
            await e.client.login(e.token)
    
    async def logout():
        for e in entries:
            await e.client.close()

    def on_exit():
        loop.run_until_complete(logout())

    atexit.register(on_exit)
            
    async def wrapped_connect(entry):
        try:
            await entry.client.connect()
        except Exception as e:
            await entry.client.close()
            logger.error(f"接続にエラー:{e}")
            entry.event.set()
                    
    #接続のチェック
    async def check_close():
        futures = [asyncio.create_task(e.event.wait()) for e in entries]
        await asyncio.wait(futures)
        
    #ログイン
    loop.run_until_complete(login())

    #クライアントに接続
    for entry in entries:
        loop.create_task(wrapped_connect(entry))
        
    #全てのクライアントが閉じるまで待つ
    loop.run_until_complete(check_close())

    #ループを閉じる
    loop.close()


@client.event
async def on_ready():
    logger.info("準備を始めます")
    try:
        
        #コマンド登録
        doctorname = DoctorNameCommand(
            name="doctorname", description="ドクターネームに関するコマンド")
        client.tree.add_command(doctorname)
        
        moderate = moderates.ModerateCommand(
            name="moderate", description="モデレートに関するコマンド")
        client.tree.add_command(moderate)
        
        synced = await client.tree.sync()
        await client.tree.sync(guild=discord.Object(config.testserverid))
        
        logger.info(f"{len(synced)}個のコマンドを同期しました。")
        logger.debug("以下のコマンドを同期しました。" + ", ".join(map(str, synced)))
        
        #ボタン登録
        client.add_view(supportrequest.RequestComplete())
        client.add_view(modmails.ModmailButton())
        client.add_view(modmails.ModmailFinish())
        client.add_view(modmails.ModmailControl())
        client.add_view(communitytool.ToolButtons())
        client.add_view(multiplayertool.AKMultiJoinButton())
        
        #ルーティン
        maintenances.maintenance_timer.start()
        twitterpost.ake_tweet_retrieve.start()
        communitytool.check_expired_redemption_codes.start()
        await recruit.operators_list_refresh()
        
        #リマインダーチャンネルの確認
        try:
            global remindThreadID
            remindThreadID = await reminder.reminder_message("channel")
            remind_channel = client.get_channel(remindThreadID) if remindThreadID else client.get_channel(config.remind)
            last_remind_id = await reminder.reminder_message("last_remind")
            last_remind = await remind_channel.fetch_message(last_remind_id)
            now_utc = datetime.datetime.utcnow()
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
            now_utc_timestamp = now_utc.timestamp()
            tz_JST = JSTTime.tz_JST
            now_JST = now_utc.astimezone(tz_JST)

            passed_second = floor(now_utc_timestamp - last_remind.created_at.timestamp())               
            logger.info(f"前回のリマインダーは{last_remind.created_at.astimezone(tz_JST)}({passed_second}秒前)に投稿されています")

            if passed_second > 86400:
                logger.warning(f"前回のリマインダー投稿から1日以上({passed_second}秒)が経過していました。リマインダーを投稿します。")
                await reminder.remind()
            
        except Exception as e:
            logger.error(f"リマインダーの確認に失敗しました！\n{e}")
        
        #voice_statusの初期化
        voicechat.write_voice_status({})
        
        #presetの初期化
        presets_dict = load_json("presets.json")
        global preset_names
        preset_names = list(presets_dict.keys())
        
        async def scheduled_task(): 
            await asyncio.sleep(wait_seconds)
            try:
                config.add_recruit_list(operator_list)
                logger.info(f"予約されたadd_recruitタスクを実行しました。オペレーター: {', '.join(operator_list)}")
                # 完了通知を元のチャンネルに送信
                await user.send(
                    f"予約されていた公開求人オペレーターの追加が完了しました！\n対象: `{', '.join(operator_list)}`"
                )
            except Exception as e:
                logger.error(f"予約されたadd_recruitタスクの実行中にエラーが発生しました: {e}")
                await user.send(
                    "予約されていた公開求人オペレーターの追加処理中にエラーが発生しました。"
                )
            finally:
                # タスク完了後はスケジュールから削除
                for task in scheduled_tasks:
                    if task["task_id"] == f"add_recruit_{add_time_dt.strftime('%Y%m%d%H%M%S')}":
                        scheduled_tasks.remove(task)
                        save_json("scheduled_tasks.json", scheduled_tasks)
                        break
        
        #タスク読み込み
        scheduled_tasks = load_json("scheduled_tasks.json")
        for task in scheduled_tasks:
            now = datetime.datetime.now(JSTTime.tz_JST)
            if task["excute_at"] >= now.isoformat():
                # タスクを実行
                wait_seconds = (datetime.datetime.fromisoformat(task["excute_at"]) - now).total_seconds()
                operator_list = task["data"]["operators"]
                add_time_dt = datetime.datetime.fromisoformat(task["excute_at"])
                user = await client.fetch_user(task["user_id"])
                asyncio.create_task(scheduled_task())
            #実行時間が過ぎている場合、待機時間0秒でタスクを実行
            else:
                wait_seconds = 0
                operator_list = task["data"]["operators"]
                add_time_dt = datetime.datetime.fromisoformat(task["excute_at"])
                user = await client.fetch_user(task["user_id"])
                asyncio.create_task(scheduled_task())
        
        save_json("scheduled_tasks.json", scheduled_tasks)
        
        #Twitter検索(5時起動時のみ実行)
        if now_JST.hour == 5:
            await twitterpost.gather_reed_arts(since=datetime.datetime.now(tz=JSTTime.tz_JST))
        
        await chat.init_models()

    except Exception as e:
        logger.exception(f"[on_ready]にて エラー：{e}")
        
    logger.info(f"{client.user} 、準備完了です！")
    
    await asyncio.sleep(60)
    
    #ボイスクライアントのロード
    if voicechat.voicechat is True:
        try:
            logger.info("ボイスクライアントをロードします")
            await voicechat.text_to_speech("ボイスクライアントをロードします")
            logger.info("ボイスクライアントのロードが完了しました")
        except Exception as e:
            logger.warning(f"ボイスクライアントのロードに失敗しました！\n{e}")
            await asyncio.sleep(60)
            await voicechat.text_to_speech("ボイスクライアントをロードします")

@client.event
async def setup_hook() -> None:
    await twitterpost.setup_app()
    voicechat.before_reboot.start()
    morning.start()
    send_remind.start()
    afternoon.start()
    evening.start()
    new_days.start()
    
    logger.info("タスクを開始しました")

# Message handler functions
async def handle_preset_message(message: discord.Message) -> bool:
    """Handle preset commands that start with '.'
    
    Returns:
        bool: True if message was handled, False otherwise
    """
    user_message = message.content
    
    if user_message == ".help":
        presets_dict = load_json("presets.json")
        preset_describe = "\n- **.help**：この一覧を表示します"
        for preset in presets_dict:
            preset_describe += f"\n- **{preset}**：{presets_dict[preset]['description']}"
            
        embed = discord.Embed(
            title="プリセット一覧", 
            description=f"## 以下が現在利用できるプリセットです！\n{preset_describe}", 
            color=discord.Color.green()
        )
        embed.set_footer(text="プリセットを利用する場合は、.(ドット)から始まるプリセット名をメッセージに送信するだけでOKです！")
        await message.reply(embed=embed)
        return True
        
    if user_message in preset_names:
        presets_dict = load_json("presets.json")
        await message.reply(presets_dict[user_message]["bodytext"])
        return True
    
    return False


async def handle_reminder_greeting(message: discord.Message):
    """Handle greeting messages in the reminder thread"""
    greet_pattern = ".*(お(は(よ|ー|～)|早)|こんにち(は|わ)|こんばん(は|わ))|ohayo.*"
    result = re.match(greet_pattern, message.content)
    if result:
        logger.info(f"{message.author.name}さんが挨拶しました！")
        await message.add_reaction("🌟")


async def handle_recruit_screenshot(message: discord.Message):
    """Handle recruit screenshot processing"""
    if not message.attachments:
        return
    
    for attachment in message.attachments:
        if "image" not in attachment.content_type:
            return
        tags_image = io.BytesIO(rq.get(attachment.url).content)
        await recruit.recruit_from_screenshot(image_path=tags_image, message=message)

async def handle_blueprint_message(message: discord.Message):
    """Handle blueprint ID detection and embed creation"""
    # Regex pattern to find blueprint IDs (EFO followed by alphanumeric characters)
    blueprint_pattern = r'EFO[0-9A-Za-z]+'
    blueprint_ids = re.findall(blueprint_pattern, message.content)
    
    if blueprint_ids:
        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(blueprint_ids))
        
        # Check for existing replies to avoid duplicates
        async for history_msg in message.channel.history(limit=50):
            if history_msg.author == client.user and history_msg.reference and history_msg.reference.message_id == message.id:
                if history_msg.embeds and history_msg.embeds[0].title == "工業図面IDのコピーにご利用ください！":
                    if history_msg.embeds[0].description in unique_ids:
                        unique_ids.remove(history_msg.embeds[0].description)
        
        if not unique_ids:
            return
        
        # Create embed for each unique ID
        for blueprint_id in unique_ids:
            embed = discord.Embed(
                title="工業図面IDのコピーにご利用ください！",
                description=blueprint_id,
                color=discord.Color.blue()
            )
            await message.reply(embed=embed, mention_author=False)
        
        logger.info(f"工業図面ID {', '.join(unique_ids)} を検出し、埋め込みを作成しました")


async def handle_modmail_staff_message(message: discord.Message):
    """Handle staff messages in modmail channels"""
    channel = message.channel
    author = message.author
    user_message = message.content
    
    idx = channel.name.find("-") + 1
    userID = int(channel.name[idx:])
    user = await client.fetch_user(userID)

    mail = discord.Embed(
        title=f"【スタッフ】{author.display_name}からのメッセージ", 
        description=user_message, 
        color=0x979C9F
    )
    mail.set_author(name=author.display_name, icon_url=author.avatar)
    
    embeds = [mail]
    videos = []
    
    for attachment in message.attachments:
        if "image" in attachment.content_type:
            embed = discord.Embed(color=discord.Color.yellow())
            embed.set_image(url=attachment.url)
            embeds.append(embed)
        
        if "video" in attachment.content_type:
            videos.append(attachment.url)
    
    await user.send(embeds=embeds)
    for video in videos:
        await user.send(content=f"[ブラウザで開く]({video})")

    await message.add_reaction("✅")
    logger.info(f"Modmailに投稿されたメッセージ(id: {message.id})を正常に転送しました")


async def handle_dm_message(message: discord.Message):
    """Handle direct messages to the bot"""
    author = message.author
    username = str(author)
    user_message = message.content
    
    guild = client.get_guild(config.main_server) if config.test is False else client.get_guild(config.testserverid)
    logger.info(f"{username}に「{user_message}」と言われました。")
    
    mod_channel = await modmails.fetch_mod_channel(guild=guild, user=author)
    if mod_channel is not None:
        mail = discord.Embed(
            title=f"{author.display_name}さんからのメッセージ",
            description=message.content, 
            color=message.author.accent_color
        )
        mail.set_author(name=str(message.author), icon_url=message.author.avatar)
        embeds = [mail]
        videos = []
        
        for attachment in message.attachments:
            if "image" in attachment.content_type:
                embed = discord.Embed(color=discord.Color.yellow())
                embed.set_image(url=attachment.url)
                embeds.append(embed)
            
            if "video" in attachment.content_type:
                videos.append(attachment.url)
        
        await mod_channel.send(embeds=embeds)
        for video in videos:
            await mod_channel.send(content=f"[ブラウザで開く]({video})")
            
        await message.add_reaction("✅")
        logger.info(f"Modmailへ投稿されたメッセージ(id: {message.id})を正常に転送しました")
        
        # AIアシストの呼び出し
        try:
            assist_embed = await chat.analyze_modmail_history(mod_channel)
            if assist_embed:
                await mod_channel.send(embed=assist_embed)
        except Exception as e:
            logger.error(f"AI assist generation failed: {e}")
    else:
        response = await chat.direct_chat(author, message)
        if response:
            logger.info(f"{username}さんのメッセージ{user_message}に対して、{response}と返答しました")


@client.event
async def on_message(message: discord.Message):
    """Main message handler that routes messages to appropriate handlers"""
    
    # Early returns for bot messages
    if message.author == client.user or message.author.bot is True:
        return

    # Handle preset commands (works in both DM and guild)
    if message.content.startswith("."):
        await handle_preset_message(message)
        return

    # Guild message handlers
    if message.guild:
        channel_id = message.channel.id
        
        # Reminder greeting handler
        if channel_id == remindThreadID:
            await handle_reminder_greeting(message)
        
        # Recruit screenshot handler
        if channel_id in [config.screenshot_recruit_channel, config.screenshot_recruit_channel_test]:
            await handle_recruit_screenshot(message)
        
        # Blueprint ID detection handler
        if channel_id == config.blueprint_channel:
            await handle_blueprint_message(message)
        
        # Modmail staff message handler
        is_feedback_category = (message.channel.category_id == config.feedback_category) or (message.channel.category and message.channel.category.name == "────フィードバック────")
        if is_feedback_category and message.channel.name.startswith("mail"):
            await handle_modmail_staff_message(message)
    
    # DM handlers
    else:
        await handle_dm_message(message)

@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Handle message edits"""
    if after.author == client.user or after.author.bot is True:
        return

    if before.content == after.content:
        return

    if after.guild and after.channel.id == config.blueprint_channel:
        await handle_blueprint_message(after)

def load_json(file_name: str) -> dict:
    with open(os.path.join(dir, f"jsons\\{file_name}"), "r", encoding="utf-8") as f:
        return json.load(f)
    
def save_json(file_name: str, data: dict):
    with open(os.path.join(dir, f"jsons\\{file_name}"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_reactions_json() -> dict:
    path = os.path.join(dir, "jsons/reactions.json")
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    # Initialize to empty dict if the file is in an unexpected format.
    return {}
     
async def load_reactions(reaction: discord.Reaction):
    reactions = load_reactions_json()
    JST_timestamp = JSTTime.timeJST("timestamp")
    found = False
    posted = 0
    search_id = str(reaction.message.id)
    for messageid in list(reactions.keys()):
        
        #データベースから除外する日数の閾値
        #86400 = 1日
        if JST_timestamp - reactions[messageid]["created_at"] > config.collect_agree_days:
            del reactions[messageid]
            continue
            
        if messageid == search_id:
            found = True
            if reactions[messageid]["count"] < reaction.count:
                reactions[messageid]["count"] = reaction.count
            reaction_count = reactions[messageid]["count"]
            if reactions[messageid]["posted"]:
                posted = reactions[messageid]["posted"]
                
    if found is False:
        reaction_count = reaction.count
        created_at = floor(reaction.message.created_at.astimezone(tz = JSTTime.tz_JST).timestamp())
        
        #聖堂に新しく刻まない日数の閾値
        #86400 = 1日
        if JST_timestamp - created_at > config.collect_agree_days:
            return 0, 0
        
        reactions[search_id] = {"count": reaction_count, "created_at": created_at, "posted": 0}
        
    with open(os.path.join(dir, "jsons/reactions.json"), "w", encoding="utf-8") as f:
        json.dump(reactions, f, indent=2, ensure_ascii=False)
        
    return reaction_count, posted

async def posted_reaction_message(search_message: int, posted_message: int):
    reactions = load_reactions_json()
    search_id = str(search_message)
    if search_id in reactions:
        reactions[search_id]["posted"] = posted_message
    with open(os.path.join(dir, "jsons/reactions.json"), "w", encoding="utf-8") as f:
        json.dump(reactions, f, indent=2, ensure_ascii=False)
        
@client.event
async def on_raw_reaction_add(reaction_payload: discord.RawReactionActionEvent):
    try:
        agree_emoji_id = 1183255845497229442
        logger.debug(f"[reaction] emoji received: id={reaction_payload.emoji.id}, name={reaction_payload.emoji.name}, message_id={reaction_payload.message_id}")
        if reaction_payload.emoji.id != agree_emoji_id and reaction_payload.emoji.name != "I_agree":
            return
        
        logger.debug(f"[reaction] I_agree detected on message {reaction_payload.message_id}")
        reaction_user = reaction_payload.user_id
        message_channel = client.get_channel(reaction_payload.channel_id)
        if message_channel is None:
            message_channel = await client.fetch_channel(reaction_payload.channel_id)
        message = await message_channel.fetch_message(reaction_payload.message_id)

        if not message.guild:
            logger.debug("[reaction] skipped: not a guild message")
            return
        if message.author.bot is True:
            logger.debug("[reaction] skipped: message author is bot")
            return
        reaction = None
        for item in message.reactions:
            if isinstance(item.emoji, str):
                continue
            if item.emoji.id == agree_emoji_id or item.emoji.name == "I_agree":
                reaction = item
                break
        if reaction is None:
            logger.debug(f"[reaction] skipped: I_agree reaction not found in message.reactions (found: {[str(r.emoji) for r in message.reactions]})")
            return
        
        logger.debug(f"[reaction] calling load_reactions with count={reaction.count}")
        reaction_count, posted = await load_reactions(reaction)
        
        #リアクションの数とポストされたかどうかを確認
        if reaction_count >= 3 and posted == 0:

            message_id = message.id
            message_guild = message.guild
            message_attachments = message.attachments
            message_jump_url = message.jump_url
            message_created_at_JST = message.created_at.astimezone(tz = JSTTime.tz_JST)
            message_content = message.content
            message_author = message.author
            is_private = False
            
            if isinstance(message_channel, discord.Thread):
                is_private = message_channel.is_private()
                if message_channel.parent:
                    parent_overwrites = message_channel.parent.overwrites_for(message_guild.default_role)
                    if parent_overwrites.read_messages is False:
                        is_private = True
            else:
                default_overwrites = message_channel.overwrites_for(message_guild.default_role)
                if default_overwrites.read_messages is False:
                    is_private = True
            if is_private is True:
                logger.info("プライベートチャンネルのため、聖堂入りを中止しました。")
                return
            member_author = message_author if isinstance(message_author, discord.Member) else message_guild.get_member(message_author.id)
            if member_author and member_author.get_role(config.cathedral_NG_role):
                logger.info("聖堂NGのロールを持っているため、聖堂入りを中止しました")
                return
            channel = client.get_channel(config.cathedral)
            if channel is None:
                channel = await client.fetch_channel(config.cathedral)
            
            embeds = []
            embed = discord.Embed(description=message_content, timestamp=message_created_at_JST, color = discord.Color.yellow())
            embed.set_author(name = message_author.display_name, icon_url=message_author.display_avatar, url = message_jump_url)
            embed.set_footer(text = f"ID: {message_id}")
            if message_attachments:
                first_content_type = message_attachments[0].content_type or ""
                if "image" in first_content_type:
                    embed.set_image(url = message_attachments[0].url)
            embeds.append(embed)
            videos = []
            if message_attachments:
                
                for number in range(len(message_attachments)):
                    content_type = message_attachments[number].content_type or ""
                    if "image" in content_type and number != 0:
                        embed = discord.Embed(color = discord.Color.yellow())
                        embed.set_image(url = message_attachments[number].url)
                        embeds.append(embed)
                    
                    if "video" in content_type:
                        videos.append(message_attachments[number].url)

            logger.info(f"メッセージ({message_id})が{reaction_user}の手で聖堂へ刻まれました")                        
            posted_message = await channel.send(content = f"{message_author.mention} さんのメッセージが <:I_agree:1183255845497229442> を{reaction.count}個獲得しました！\nメッセージへのリンク: {message_jump_url}", embeds = embeds)
            for video_url in videos:
                await posted_message.reply(content = f"[ブラウザで開く]({video_url})")
            await posted_reaction_message(message_id, posted_message.id)
        
        if posted != 0:
            channel = client.get_channel(config.cathedral)
            if channel is None:
                channel = await client.fetch_channel(config.cathedral)
            edit_message = await channel.fetch_message(posted)
            message_author = message.author
            message_jump_url = message.jump_url
            await edit_message.edit(content = f"{message_author.mention} さんのメッセージが <:I_agree:1183255845497229442> を{reaction.count}個獲得しました！\nメッセージへのリンク: {message_jump_url}")
    except Exception as e:
        logger.exception(f"[on_raw_reaction_add] error: {e}")

@client.event
async def on_member_join(member: discord.Member):
    embeds = await moderates.moderate_show(member)
    channel = client.get_channel(config.action_logs)
    await channel.send(embeds=embeds)

@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    #beforeとafterの比較
    before_roles = set(before.roles)
    after_roles = set(after.roles)
    
    #追加されたロールの抽出
    if before_roles == after_roles:
        return
    else:
        added_roles = list(after_roles - before_roles)
        
    #botロールの検出
    try:
        is_user_bot_role = False
        for role in added_roles:
            if role.id == config.user_bot_role:
                is_user_bot_role = True
                break
        if is_user_bot_role is False:
            return
        else:
            member_got = after
            roles = []
            
            for index, role in enumerate(member_got.roles):
                role_mention = role.name if index == 0 else role.mention
                roles.append(role_mention)

            role_got = "\n".join(roles)
            
            embed = discord.Embed(title = "botロールを検出しました！", description = f"{member_got.mention}\nユーザー名: {str(member_got)}\nグローバルネーム: {member_got.global_name}", 
                                    color=discord.Color.red())
            embed.set_thumbnail(url=member_got.display_avatar)
            embed.set_author(name=member_got.display_name,
                                icon_url=member_got.avatar)
            embed.add_field(name = "ID", value = member_got.id, inline = False)
            embed.add_field(name = "サーバー参加日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.joined_at.timestamp())), inline = False)
            embed.add_field(name = "アカウント作成日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.created_at.timestamp())), inline = False)
            embed.add_field(name = "所持しているロール", value = role_got, inline = True)
            embed.add_field(name = "最高のロール", value = "<@&{0}>".format(member_got.top_role.id), inline = True)
            if member_got.is_timed_out() is True:
                embed.add_field(name="タイムアウト状態", value="<t:{0}:F>( <t:{0}:R> )まで".format(
                    round(member_got.timed_out_until.timestamp())), inline=False)
                
            channel_action_log = client.get_channel(config.action_logs)
            await channel_action_log.send(embed = embed)
            
    except Exception as e:
        logger.error(f"[on_member_update]にてエラー: {e}")
        
        
class VoiceSpeechButtons(discord.ui.View):
    def __init__(self, join_channel):
        super().__init__(timeout = 60)
        self.join_channel = join_channel
        
    @discord.ui.button(label = "はい", style = discord.ButtonStyle.success, emoji = "✅")
    async def speechstart(self, interaction: discord.Interaction, button: discord.ui.Button):
                
        await voicechat.join_voice(interaction = interaction, channel = self.join_channel)
        await interaction.message.delete()

    @discord.ui.button(label = "いいえ", style = discord.ButtonStyle.danger)
    async def dontspeech(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        await interaction.message.delete()  
    
@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    
    if member == client.user:
        return
    
    #join
    if after.channel and not before.channel:
        logger.info(f"{member.display_name}({str(member)})が{after.channel.name}({after.channel.id})に接続しました。")
    
    #leave
    elif before.channel and not after.channel:
        logger.info(f"{member.display_name}({str(member)})が{before.channel.name}({before.channel.id})から切断しました。")
        
        if len(before.channel.members) < 2 and member.guild.voice_client:
            if member.guild.voice_client.channel == before.channel:
                await member.guild.voice_client.disconnect()
    
    #move
    elif before.channel != after.channel:
        logger.info(f"{str(member)}が{before.channel.name}({before.channel.id})から{after.channel.name}({after.channel.id})に接続しました。")
        
        if len(before.channel.members) < 2 and member.guild.voice_client:
            if member.guild.voice_client.channel == before.channel:
                await member.guild.voice_client.disconnect()
                        
    #vccreate
    vccreate_voice = client.get_channel(config.voicecreate_vc)
        
    
    if after.channel:
        
        vccreate_category = discord.utils.get(after.channel.guild.categories, name = "────VC/個別────")

        if after.channel == vccreate_voice:
            gd = after.channel.guild
            administrator = gd.get_role(config.administrator_role)
            moderator = gd.get_role(config.Moderator_role)
            vc_allowed = gd.get_role(config.vc_allowed_role)
            
            overwrite = {gd.default_role: discord.PermissionOverwrite(view_channel = False, connect = False),
                            moderator: discord.PermissionOverwrite(view_channel = True, connect = True),
                            administrator: discord.PermissionOverwrite(view_channel = True, connect = True),
                            vc_allowed: discord.PermissionOverwrite(view_channel = True, connect = True),
                            member: discord.PermissionOverwrite(manage_channels = True)}
            created_vc = await vccreate_category.create_voice_channel(name = "臨時VC - 名前を変更できます", overwrites=overwrite)
            await member.move_to(created_vc)
            vccreate_channel = client.get_channel(config.voicecreate_channel)
            embed = discord.Embed(title = "ボイスチャット作成成功", description = f"ボイスチャットの作成に成功しました！\n名前の変更、最大人数の設定などは{vccreate_channel.jump_url}をご覧ください！")
            embed.set_footer(text = "VCルールとマナーを厳守してください。このVC内容はログが取られています。")
            await created_vc.send(content = member.mention, embed = embed)
            return
        
    #autodelete_created_vc
    if before.channel:
        vccreate_category = discord.utils.get(before.channel.guild.categories, name = "────VC/個別────")
        if len(before.channel.members) < 1 and before.channel.category == vccreate_category and before.channel != vccreate_voice:
            overwrites = before.channel.overwrites
            for overwrite in overwrites:
                if type(overwrite) is discord.Member:
                    vc_create_user = overwrite
                    break
            await modmails.save_modmail(channel=before.channel, vc_log=True, save_channel=client.get_channel(config.vccreate_log_channel), vc_create_user=vc_create_user)
            await before.channel.delete()
            
    #suggest/auto-join
    if config.voice_suggest and after.channel and len(after.channel.members) == 1:
        
        if before.channel and before.channel == after.channel:
            return
        if after.channel == vccreate_voice:
            return
        try:
            if after.channel.category_id == vccreate_category.id or after.channel.id == config.event_stage_channel:

                join_channel = after.channel
                logger.info(f"{member.name}にボイス読み上げの提案を行います")

                send_channel = after.channel
            
                embed = discord.Embed(title = "ボイスチャットに接続しました！", description = "聞き専チャットを読み上げる機能を有効にしますか？\nこのメッセージは60秒で削除されます！\n後で`/join`コマンドを使用することでも読み上げを始めます！", color = discord.Color.blue())
                embed.set_author(name = "チャット読み上げ")
                message = await send_channel.send(embed = embed, view = VoiceSpeechButtons(join_channel = join_channel))
                await asyncio.sleep(60)
                try:
                    await message.delete()
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(e)    
        
@client.tree.command(name="help",
                        description="現在実装されているコマンドの使い方を簡単に説明します！")
async def help(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="コマンドヘルプ",
                            description="以下が現在実装されているコマンドになります。",
                            color=0x979C9F)
    embed.add_field(name="「ドクターネーム」", value="ゲーム内のドクターネーム(Dr.xxxx#0000の形のゲーム内ID)を紐づけします\n・**/doctorname set**：ドクターネームを登録/変更します\n・**/doctorname show**：指定した人のドクターネームを表示します\n・**/doctorname delete**：登録したドクターネームを削除します", inline=False)
    embed.add_field(
        name="「サポートリクエスト」", value="チャンネルを使ってサポートオペレーターのリクエストができます。攻略に詰まったら是非使ってください！\n・**/request**：サポートのリクエストを送信します", inline=False)
    embed.add_field(
        name="「Modmail」", value="運営スタッフへの問い合わせが簡単にできます\n・**/modmail**：運営スタッフへの問い合わせを開始します", inline=False)
    embed.add_field(name="「ボイスチャット読み上げ」", value="対応したチャットの読み上げをします\n・**/join**：読み上げを開始します\n・**/leave**：ボイスチャットから切断します", inline=False)
    embed.add_field(name = "「公開求人シミュレーター」", value = "公開求人のタグから獲得できるオペレーターを表示します。ドロップダウンメニューからタグを一つずつ指定してください。")

    logger.info(f"{interaction.user.name}がコマンド/helpを使用しました")

    await interaction.followup.send(embed=embed, ephemeral=True)
    
@client.tree.command(name="add_reminder", description="reminds.jsonにanniRemind、sssRemindを追加します", guild=discord.Object(config.testserverid))
@app_commands.describe(
    game = "ゲーム arknights/endfield (デフォルト: arknights)",
    remind_id = "リマインダーID(anniRemind-202507, sssRemind-202507等)",
    remind_name = "殲滅作戦or保全駐在の名前(例: 殲滅依頼「66号航路」, 協奏保全駐在)",
    remind_type = "anni or sss",
    link = "攻略Wikiのリンク",
    start_time = "開始時間(例: 2023-10-01 16:00:00)",
    end_time = "終了時間(例: 2023-10-15 3:59:59)"
)
async def add_reminder(interaction: discord.Interaction, remind_id: str, remind_name: str, remind_type: Literal["anni", "sss"], link: str, start_time: str, end_time: str, game: str = "arknights"):
    """リマインダーを追加します。"""
    if interaction.user == client.user:
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        startTime = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        endTime = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("日付のフォーマットエラーです。「YYYY-MM-DD HH:MM:SS」")
        await interaction.followup.send("日付のフォーマットが正しくありません。「YYYY-MM-DD HH:MM:SS」の形式で入力してください。")
        return
    
    startTime_timestamp = floor(startTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    endTime_timestamp = floor(endTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    
    new_remind_dict = {
        remind_id: {
            "name": remind_name,
            "description": None,
            "type": remind_type,
            "link": link,
            "startTime": startTime_timestamp,
            "endTime": endTime_timestamp
        }
    }
    
    remind_archive = load_json("reminds.json")
    
    # Check if game section exists
    if game not in remind_archive:
        remind_archive[game] = {}
    
    # Check if remind_id already exists in the game section
    if remind_id in remind_archive[game]:
        logger.error(f"リマインダーID {remind_id} は{game}セクションに既に存在します。")
        await interaction.followup.send(f"リマインダーID `{remind_id}` は{game}セクションに既に存在します。別のIDを使用してください。")
        return
    
    remind_archive[game].update(new_remind_dict)
    save_json("reminds.json", remind_archive)
    
    await interaction.followup.send(f"リマインダー `{remind_id}` を{game}セクションに追加しました！\n名前: {remind_name}\nタイプ: {remind_type}\nリンク: {link}\n開始時間: {startTime.strftime('%Y-%m-%d %H:%M:%S')}\n終了時間: {endTime.strftime('%Y-%m-%d %H:%M:%S')}")
    
@client.tree.command(name="add_event", description="イベントを追加します", guild=discord.Object(config.testserverid))
@app_commands.describe(
    event_id="イベントID（任意、自動生成されます）",
    event_type="イベントの種類",
    name="イベントの名前",
    start_time="開始時間(例: 2023-10-01 16:00:00)",
    end_time="終了時間(例: 2023-10-15 3:59:59)",
    description="イベントの説明（任意）",
    news_url="ニュースURL（任意）",
    wiki_url="WikiのURL（任意）",
    image_url="イベントの画像URL（任意、カンマ区切りで複数可）",
    reward_end_time="報酬交換期限（任意、例: 2023-10-20 3:59:59）",
    version_name="バージョン名（VERSION_CALENDARの場合のみ、例: 初号指令）"
)
@app_commands.choices(event_type=event_handlers.ALL_EVENT_CHOICES)
async def add_event(
    interaction: discord.Interaction,
    event_type: str,
    name: str,
    start_time: str,
    end_time: str,
    event_id: str = None,
    description: str = None,
    news_url: str = None,
    wiki_url: str = None,
    image_url: str = None,
    reward_end_time: str = None,
    version_name: str = None
):
    """イベントを追加します。"""
    if interaction.user == client.user:
        return
    
    game = event_handlers.get_game_by_event_type(event_type)
    
    await interaction.response.defer(ephemeral=True)
    
    # Parse times
    try:
        startTime = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        endTime = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("日付のフォーマットエラーです。「YYYY-MM-DD HH:MM:SS」")
        await interaction.followup.send("日付のフォーマットが正しくありません。「YYYY-MM-DD HH:MM:SS」の形式で入力してください。")
        return
    
    startTime_timestamp = floor(startTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    endTime_timestamp = floor(endTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    
    # Parse reward end time if provided
    rewardEndTime_timestamp = None
    if reward_end_time:
        try:
            rewardEndTime = datetime.datetime.strptime(reward_end_time, "%Y-%m-%d %H:%M:%S")
            rewardEndTime_timestamp = floor(rewardEndTime.astimezone(tz=JSTTime.tz_JST).timestamp())
        except ValueError:
            logger.error("報酬交換期限のフォーマットエラーです。")
            await interaction.followup.send("報酬交換期限のフォーマットが正しくありません。「YYYY-MM-DD HH:MM:SS」の形式で入力してください。")
            return
    
    # Generate event_id if not provided
    if not event_id:
        if event_type == "VERSION_CALENDAR":
            event_id = f"version_calendar_{version_name}" if version_name else f"version_calendar_{startTime.strftime('%Y%m')}"
        else:
            event_id = name.replace(" ", "_").replace("(", "").replace(")", "")
    
    # Build event dictionary based on type
    new_event_dict = {
        "id": event_id,
        "type": event_type,
        "name": name,
        "startTime": startTime_timestamp,
        "endTime": endTime_timestamp
    }
    
    # Add optional fields
    if description:
        new_event_dict["description"] = description
    
    if news_url:
        new_event_dict["news"] = news_url
    
    if wiki_url:
        new_event_dict["link"] = wiki_url
    
    # Handle image_url - can be comma-separated for VERSION_CALENDAR
    if image_url:
        if event_type == "VERSION_CALENDAR":
            # Split by comma and strip whitespace
            images = [url.strip() for url in image_url.split(",")]
            new_event_dict["images"] = images
        else:
            new_event_dict["pic"] = image_url.strip()
    
    # Add version name for VERSION_CALENDAR
    if event_type == "VERSION_CALENDAR":
        if not version_name:
            await interaction.followup.send("VERSION_CALENDARタイプにはversion_nameが必要です。")
            return
        new_event_dict["version"] = version_name
    
    # Add reward end time if provided
    if rewardEndTime_timestamp:
        new_event_dict["rewardEndTime"] = rewardEndTime_timestamp
    
    # Add game-specific fields for Arknights
    if game == "arknights":
        if event_type in ["SIDESTORY", "MINISTORY"]:
            new_event_dict["stageAdd"] = False
        elif event_type in ["ROGUELIKE", "SANDBOX"]:
            new_event_dict["monthlyUpdate"] = []
    
    # Load events.json
    events_archive = load_json("events.json")
    
    # Check if game section exists
    if game not in events_archive:
        events_archive[game] = {}
    
    # Ensure unique event_id
    original_event_id = event_id
    counter = 2
    while event_id in events_archive[game]:
        event_id = f"{original_event_id}-{counter}"
        counter += 1
    new_event_dict["id"] = event_id
    
    # Add event
    events_archive[game][event_id] = new_event_dict
    save_json("events.json", events_archive)
    
    # Build confirmation message
    confirm_msg = f"イベント `{event_id}` を{game}セクションに追加しました！\n"
    confirm_msg += f"名前: {name}\n"
    confirm_msg += f"タイプ: {event_type}\n"
    confirm_msg += f"開始時間: {startTime.strftime('%Y-%m-%d %H:%M:%S')}\n"
    confirm_msg += f"終了時間: {endTime.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if event_type == "VERSION_CALENDAR":
        confirm_msg += f"バージョン: {version_name}\n"
        if image_url:
            confirm_msg += f"画像数: {len(new_event_dict['images'])}枚\n"
    
    if description:
        confirm_msg += f"説明: {description}\n"
    
    if reward_end_time:
        confirm_msg += f"報酬交換期限: {rewardEndTime.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    await interaction.followup.send(confirm_msg)
    
@client.tree.command(name="gather_reed_arts",
                        description="Twitterから必要な情報を収集します", guild=discord.Object(config.testserverid))
async def gather_reed_arts(interaction: discord.Interaction):
    await interaction.response.defer()
    await twitterpost.gather_reed_arts(since=datetime.datetime.now(tz=JSTTime.tz_JST))
    await interaction.followup.send("Twitterからの情報収集を開始しました。完了までしばらくお待ちください。")

@client.tree.command(name="ping",
                        description="botの応答時間を確認します",
                        guild=discord.Object(config.testserverid))
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()

    raw_ping = client.latency
    ping_ms = round(raw_ping * 1000)
    response = await interaction.followup.send(f"WebSocket待ち時間:{ping_ms}ms")
    rap = datetime.datetime.now(datetime.timezone.utc)
    waittime = rap - response.created_at
    waittime_ms = round(waittime.total_seconds() * 1000)
    await response.edit(content=f"WebSocket待機時間:{ping_ms}ms\n送信までの待機時間:{waittime_ms}ms")

@client.tree.command(name="maintenance",
                        description="メンテナンスについて",
                        guild=discord.Object(config.testserverid))
@app_commands.describe(number="0からの参照番号", status="ruined(中止)/end(終了)/change(終了時間変更)", name="告知する名前。デフォルトは「メンテナンス」", new_end="新しい終了時間(例: 2023-10-01 16:00:00)")
async def maintenance(interaction: discord.Interaction, number: int, status: Literal["ruined", "end", "change"], name: str = "メンテナンス", new_end: str = None):
    if interaction.user == client.user:
        return
    
    if status == "ruined":
        await interaction.response.defer()
        await maintenances.maintenance_ruined(number)
        await interaction.followup.send("完了しました")

    elif status == "end":
        await interaction.response.defer()
        await maintenances.maintenance_end(name, number)
        await interaction.followup.send("完了しました")
        
    elif status == "change":
        if new_end is None:
            await interaction.response.send_message("新しい終了時間を指定してください", ephemeral=True)
            return
        try:
            new_end_dt = datetime.datetime.strptime(new_end, "%Y-%m-%d %H:%M:%S")
            new_end_timestamp = floor(new_end_dt.astimezone(tz=JSTTime.tz_JST).timestamp())
        except ValueError:
            logger.error("日付のフォーマットエラーです。「YYYY-MM-DD HH:MM:SS」")
            await interaction.response.send_message("日付のフォーマットが正しくありません。「YYYY-MM-DD HH:MM:SS」の形式で入力してください。", ephemeral=True)
            return
        await interaction.response.defer()
        await maintenances.change_maint_end(number, new_end_timestamp)
        await interaction.followup.send("完了しました")

@client.tree.command(name="add_maintenance", description="メンテナンスを追加します", guild=discord.Object(config.testserverid))
@app_commands.describe(
    start_time="開始時間(例: 2025-08-20 14:00:00)",
    end_time="終了時間(例: 2025-08-20 17:00:00)",
    link="公式サイトのお知らせURL(任意)",
    pic="画像のURL(任意)"
)
async def add_maintenance(
    interaction: discord.Interaction,
    start_time: str,
    end_time: str,
    link: str = None,
    pic: str = None
):
    """メンテナンス情報を追加します。"""
    if interaction.user == client.user:
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        startTime = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        endTime = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("日付のフォーマットエラーです。「YYYY-MM-DD HH:MM:SS」")
        await interaction.followup.send("日付のフォーマットが正しくありません。「YYYY-MM-DD HH:MM:SS」の形式で入力してください。")
        return

    startTime_timestamp = floor(startTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    endTime_timestamp = floor(endTime.astimezone(tz=JSTTime.tz_JST).timestamp())
    
    new_maint_dict = {
        "type": "MAINTENANCE",
        "startTime": startTime_timestamp,
        "endTime": endTime_timestamp,
        "doing": False
    }
    
    if link:
        new_maint_dict["link"] = link

    if pic:
        new_maint_dict["pic"] = pic
        
    maint_list = load_json("maintenances.json")
    if not isinstance(maint_list, list):
        maint_list = []
        
    maint_list.append(new_maint_dict)
    save_json("maintenances.json", maint_list)
    
    await interaction.followup.send(f"メンテナンス情報を追加しました！\n開始: {start_time}\n終了: {end_time}")
        
@client.tree.command(name="nickname", description="ロードに覚えてほしいあなたの呼び方を設定します")
@app_commands.describe(name="AIに覚えてほしいあなたの呼び方(後ろに先輩が付きます)")
async def nickname(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        user_id_str = str(interaction.user.id)
        await chat.update_long_term_memory(user_id_str, 'nickname', name)
        await interaction.followup.send(f"あなたの呼び方を「{name}」として覚えました！\nこれからの会話に活かしていきますね。")
    except Exception as e:
        logger.error(f"Error in /nickname command: {e}")
        await interaction.followup.send("エラーが発生して、名前を覚えられませんでした。ごめんなさい。")
                
@client.tree.command(name="edit_dynamic_config",
                        description="動的configの編集を行います",
                        guild=discord.Object(config.testserverid))
@app_commands.describe(key="編集するキー", value="新しい値")
async def edit_dynamic_config(interaction: discord.Interaction, key: str, value: str):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    try:
        config.dynamic_set(key, value)
        await interaction.followup.send("完了しました")
    except Exception as e:
        logger.error(f"動的configの編集に失敗しました！\n{e}")
        await interaction.followup.send(f"動的configの編集に失敗しました！\n{e}")

@client.tree.command(name="add_recruit",
                     description="公開求人対象のオペレーターを追加します（複数追加可能）",
                        guild=discord.Object(config.testserverid))
@app_commands.describe(operators="追加するオペレーターの名前をカンマ区切りで入力してください", add_time="追加する時間(例: 2023-10-01 12:00:00)")
async def add_recruit(interaction: discord.Interaction, operators: str, add_time: str):
    await interaction.response.defer(ephemeral=True)

    scheduled_tasks = load_json("scheduled_tasks.json")
    operator_list = [op.strip() for op in operators.split(",")]

    try:
        # 時間文字列をdatetimeオブジェクトに変換 (JSTとして解釈)
        naive_dt = datetime.datetime.strptime(add_time, "%Y-%m-%d %H:%M:%S")
        add_time_dt = naive_dt.replace(tzinfo=JSTTime.tz_JST)

        # 現在時刻 (JST)
        now_jst = datetime.datetime.now(JSTTime.tz_JST)

        # 未来の時刻かチェック
        if add_time_dt <= now_jst:
            await interaction.followup.send("過去または現在の時刻は指定できません。", ephemeral=True)
            return

        # 待機秒数を計算
        wait_seconds = (add_time_dt - now_jst).total_seconds()

        # バックグラウンドで実行するタスク
        async def scheduled_task():
            await asyncio.sleep(wait_seconds)
            try:
                config.add_recruit_list(operator_list)
                logger.info(f"予約されたadd_recruitタスクを実行しました。オペレーター: {', '.join(operator_list)}")
                # 完了通知を元のチャンネルに送信
                await interaction.channel.send(
                    f"{interaction.user.mention} 予約されていた公開求人オペレーターの追加が完了しました！\n"
                    f"対象: `{', '.join(operator_list)}`"
                )
            except Exception as e:
                logger.error(f"予約されたadd_recruitタスクの実行中にエラーが発生しました: {e}")
                await interaction.channel.send(
                    f"{interaction.user.mention} 予約されていた公開求人オペレーターの追加処理中にエラーが発生しました。"
                )
            finally:
                # タスク完了後はスケジュールから削除
                for task in scheduled_tasks:
                    if task["task_id"] == f"add_recruit_{add_time_dt.strftime('%Y%m%d%H%M%S')}":
                        scheduled_tasks.remove(task)
                        save_json("scheduled_tasks.json", scheduled_tasks)
                        break

        # タスクを作成
        asyncio.create_task(scheduled_task())
        new_task = {
            "task_id": f"add_recruit_{add_time_dt.strftime('%Y%m%d%H%M%S')}",
            "task_type": "add_recruit",
            "excute_at": add_time_dt.isoformat(),
            "user_id": interaction.user.id,
            "data": {
                "operators": operator_list
            }
        }
        scheduled_tasks.append(new_task)
        save_json("scheduled_tasks.json", scheduled_tasks)
        
        # ユーザーに予約完了を通知
        await interaction.followup.send(
            f"`{add_time_dt.strftime('%Y-%m-%d %H:%M:%S')}` にオペレーター追加を予約しました。",
            ephemeral=True
        )

    except ValueError:
        await interaction.followup.send(
            "時間の形式が正しくありません。`YYYY-MM-DD HH:MM:SS` の形式で入力してください。",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"add_recruitコマンドでエラーが発生: {e}")
        await interaction.followup.send(
            "コマンドの処理中に予期せぬエラーが発生しました。",
            ephemeral=True
        )

@client.tree.command(name="remind",
                        description="リマインドのテストを送ります",
                        guild=discord.Object(config.testserverid))
@app_commands.describe(
    game="ゲーム arknights/endfield (デフォルト: arknights)"
)
async def remind(interaction: discord.Interaction, game: str = "arknights"):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    
    global remindThreadID
    target_channel = await reminder.remind(game)
    remindThreadID = target_channel.id
    
    await interaction.followup.send("完了しました！")

@client.tree.command(name="eventtest",
                        description="イベントリストのテストを行います",
                        guild=discord.Object(config.testserverid))
async def eventtest(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    events = evjson.eventget()
    await interaction.followup.send(events)
    
@client.tree.command(name = "send_voice", description="指定したチャンネルにTTSを送信します", guild=discord.Object(config.testserverid))
async def send_voice(interaction: discord.Interaction, text: str, channelid: str):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    
    channelid = int(normalize("NFKC", channelid))
    await voicechat.send_voice_message(text, channelid)
        
    await interaction.followup.send("完了しました")
    
@client.tree.command(name="eventcounttest",
                        description="イベントカウントのテストを行います",
                        guild=discord.Object(config.testserverid))
async def eventcounttest(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    eventcount = evjson.eventcount()
    await interaction.followup.send(f"- eventnow: {eventcount[0]}\n- eventend: {eventcount[1]}\n- eventvalue: {eventcount[2]}\n- eventtoday: {eventcount[3]}\n- eventendtoday: {eventcount[4]}")       

@client.tree.command(name="config_reload", description="dynamic configのリロードを行います", guild=discord.Object(config.testserverid))
async def config_reload(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    try:
        config.reload()
        await recruit.operators_list_refresh()
        await interaction.followup.send("完了しました")
    except Exception as e:
        logger.error(f"configのリロードに失敗しました！\n{e}")
        await interaction.followup.send(f"configのリロードに失敗しました！\n{e}")

@client.tree.command(name="shutdown", description="botを終了します", guild=discord.Object(config.testserverid))
async def shutdown(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    await interaction.followup.send("botを終了します")
    await client.close()
    quit()

@client.tree.command(name="send_text_message",
                        description="channelIDが空欄の場合、リマインダーチャンネルに投稿します！",
                        guild=discord.Object(config.testserverid))
async def send_text_message(interaction: discord.Interaction, text: str, channelid: str = None):
    if not channelid:
        channel = client.get_channel(remindThreadID)
    else:
        channelid = int(normalize("NFKC", channelid))
        channel = client.get_channel(channelid)
    await channel.send(text)
    await interaction.response.send_message("完了しました")
    
@client.tree.command(name="add_preset", description="プリセットを追加します(現在はスタッフオンリー)")
@app_commands.describe(name="プリセットの名前(必ず.から始めてください)", description="プリセットの説明(.helpで表示)", bodytext="プリセットへの返答内容(本文)")
@discord.app_commands.default_permissions(manage_messages=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def add_preset(interaction: discord.Interaction, name: str, description: str, bodytext: str):
    if interaction.user == client.user:
        return
    if name.startswith(".") is False:
        embed = discord.Embed(title="プリセット名が不正です！", description="プリセット名は必ず「.」から始めてください", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        return
    await interaction.response.defer()
    presets_dict = load_json("presets.json")
    presets_dict[name] = {"description": description, "bodytext": bodytext}
    save_json("presets.json", presets_dict)
    global preset_names
    preset_names = list(presets_dict.keys())
    embed = discord.Embed(title="プリセット追加完了", description=f"プリセット名: {name}\n説明: {description}\n本文: {bodytext}", color=discord.Color.green())
    await interaction.followup.send(embed=embed)

@client.tree.command(name="add_endfield_birthday", description="エンドフィールドの誕生日データを追加します(スタッフ専用)")
@app_commands.describe(date="誕生日(例: 12/25)", characters="キャラクター名(複数の場合はカンマ区切り)")
@discord.app_commands.default_permissions(manage_messages=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def add_endfield_birthday(interaction: discord.Interaction, date: str, characters: str):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    
    formatted_chars = "、".join([c.strip() for c in characters.replace("、", ",").split(",") if c.strip()])
    
    try:
        birthday_json_path = "jsons/endfield_birthday.json"
        
        try:
            with open(os.path.join(dir, birthday_json_path), "r", encoding="utf-8") as f:
                birthday = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            birthday = {}
            
        if date in birthday:
            existing_chars = birthday[date].split("、")
            new_chars = formatted_chars.split("、")
            combined = existing_chars + [c for c in new_chars if c not in existing_chars]
            birthday[date] = "、".join(combined)
        else:
            birthday[date] = formatted_chars
            
        with open(os.path.join(dir, birthday_json_path), "w", encoding="utf-8") as f:
            json.dump(birthday, f, indent=4, ensure_ascii=False)
            
        embed = discord.Embed(title="エンドフィールド誕生日データ追加完了", description=f"**日付**: {date}\n**キャラクター**: {birthday[date]}", color=discord.Color.green())
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"エンドフィールド誕生日データの追加に失敗しました: {e}")
        embed = discord.Embed(title="エラー", description=f"エンドフィールド誕生日データの追加に失敗しました:\n{e}", color=discord.Color.red())
        await interaction.followup.send(embed=embed)

class DoctorNameCommand(app_commands.Group):

    @app_commands.command(name="set",
                            description="ドクターネーム(Dr.****#0000の形のゲーム内ID)を登録/変更します"
                            )
    @discord.app_commands.describe(name="IDの前半の名前の部分(「Dr.」を含まない)",
                                    tag="IDの後半の数字の部分(「#」を含まない)")
    async def doctorname_set(self, interaction: discord.Interaction, name: str,
                                tag: str):
        if interaction.user == client.user:
            return

        num_tag = normalize("NFKC", tag)

        if len(tag) > 6 or len(name) > 16:
            embed = discord.Embed(title="名前が長すぎます！",
                                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=0xf45d5d)
            await interaction.response.send_message(embed=embed)
            return

        if tag.isdecimal() is False or re.match(r"[0-9]{1,6}$", num_tag) is None:
            embed = discord.Embed(title="タグは数字のみを入力してください！",
                                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=0xf45d5d)
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        added = await supportrequest.doctor_add(interaction.user, name, num_tag)
        embed = discord.Embed(title="ドクターネームの登録が完了しました！",
                                description=f"新しく設定された貴方のドクターネームは「{added}」です！",
                                color=0x5cb85c)

        embed.set_author(name=interaction.user.name,
                            icon_url=interaction.user.avatar)
        embed.set_footer(
            text="変更する場合はもう一度「/doctorname set」、登録を削除する場合は「/doctorname delete」をご利用ください")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="show", description="指定された人のドクターネームを表示します")
    @discord.app_commands.describe(
        user="ドクターネームを知りたい人を選択してください(設定していない人も選択肢に表示されます)")
    async def doctorname_show(self, interaction: discord.Interaction,
                                user: discord.Member):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        name_full = await supportrequest.doctor_check(user)
        if name_full is None:
            embed = discord.Embed(title="ドクターネームが見つかりません！",
                                    description=f"{user.name}さんのドクターネームは見つかりませんでした！",
                                    color=0xf45d5d)
            embed.set_author(name=user.name, icon_url=user.avatar)
            await interaction.followup.send(embed=embed)
            return
        else:
            embed = discord.Embed(
                title="ドクターネームが見つかりました！",
                description=f"{user.name}さんのドクターネームは以下になります！\n「{name_full}」",
                color=0x5cb85c)
            embed.set_author(name=user.name, icon_url=user.avatar)
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="delete", description="設定された自分のドクターネームを削除します")
    async def doctorname_delete(self, interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        delete = await supportrequest.doctor_delete(interaction.user)
        if delete == "success":
            embed = discord.Embed(
                title="ドクターネームの登録を削除しました！",
                description="登録しなおす場合は、「/doctorname set」をご利用ください！",
                color=0x5cb85c)
            embed.set_author(name=interaction.user.name,
                                icon_url=interaction.user.avatar)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="ドクターネームの登録を削除できませんでした。",
                description="ドクターネームの登録を削除できませんでした！既に登録が削除されている場合があります！\nもし削除されているか確認したい場合は「/modmail」にてお問い合わせください！",
                color=0xf45d5d)
            embed.set_author(name=interaction.user.name,
                                icon_url=interaction.user.avatar)
            await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="mainttest",
                        description="メンテナンスリストのテストを行います",
                        guild=discord.Object(config.testserverid))
async def mainttest(interaction: discord.Interaction):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    maintenance = await maintenances.maintenance_list()
    await interaction.followup.send(maintenance)

@tasks.loop(time=config.morningtime)
async def morning():
    try:
        logger.info("時間になりました。モーニングルーティンを始めます")
        await reminder.remind("arknights")
        await reminder.remind("endfield")

    except Exception as e:
        logger.exception(f"[morning]にてエラー：{e}")  
        
@tasks.loop(time=config.threadtime)
async def send_remind():
    try:
        logger.info("時間になりました。メンバーにリマインドを送ります。")
        await reminder.remind("arknights", send_to_thread=True)
        await reminder.remind("endfield", send_to_thread=True)
        await supportrequest.delete_old_request()

    except Exception as e:
        logger.exception(f"[send_remind]にてエラー：{e}") 

@tasks.loop(time=config.afternoontime)
async def afternoon():
    try:
        logger.info("時間になりました。アフタヌーンルーティンを始めます")
        await reminder.remind("arknights")
        await reminder.remind("endfield")

    except Exception as e:
        logger.exception(f"[afternoon]にてエラー：{e}") 
        
@tasks.loop(time=config.eveningtime)
async def evening():
    try:
        logger.info("時間になりました。イヴニングルーティンを始めます")
        await reminder.remind("arknights")
        await reminder.remind("endfield")

    except Exception as e:
        logger.exception(f"[evening]にてエラー：{e}") 
        
@tasks.loop(time=config.newdaytime)
async def new_days():
    try:
        logger.info("時間になりました。０時ルーティンを始めます")
        await reminder.remind("arknights")
        await reminder.remind("endfield")

    except Exception as e:
        logger.exception(f"[new_days]にてエラー：{e}") 
