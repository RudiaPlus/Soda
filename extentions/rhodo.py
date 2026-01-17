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
        await recruit.operators_list_refresh()
        
        #リマインダー(スレッド)の確認
        try:
            global remindThreadID
            channel = client.get_channel(config.remind)
            remindThreadID = await reminder.reminder_message("thread")
            last_remind_id = await reminder.reminder_message("last_remind")
            remind_thread = channel.get_thread(remindThreadID)
            last_remind = await remind_thread.fetch_message(last_remind_id)
            now_utc = datetime.datetime.utcnow()
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
            now_utc_timestamp = now_utc.timestamp()
            tz_JST = JSTTime.tz_JST
            now_JST = now_utc.astimezone(tz_JST)

            passed_second = floor(now_utc_timestamp - last_remind.created_at.timestamp())               
            logger.info(f"前回のリマインダーは{last_remind.created_at.astimezone(tz_JST)}({passed_second}秒前)に投稿されています")

            if passed_second > 86400:
                logger.warning(f"前回のリマインダー投稿から1日以上({passed_second}秒)が経過していました。リマインダーを投稿します。")
                await reminder.remind("thread")
            
        except Exception as e:
            logger.error(f"リマインダースレッドの確認に失敗しました！\n{e}")
        
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

@client.event
async def on_message(message: discord.Message):

    if message.author == client.user or message.author.bot is True:
        return

    author = message.author
    username = str(author)
    user_message = message.content
    channel = message.channel
    channelID = message.channel.id
    
    #preset
    if user_message.startswith("."):
        if user_message == ".help":
            presets_dict = load_json("presets.json")
            preset_describe = "\n- **.help**：この一覧を表示します"
            for preset in presets_dict:
                preset_describe += f"\n- **{preset}**：{presets_dict[preset]["description"]}"
                
            embed = discord.Embed(title = "プリセット一覧", description = f"## 以下が現在利用できるプリセットです！\n{preset_describe}", color = discord.Color.green())
            embed.set_footer(text = "プリセットを利用する場合は、.(ドット)から始まるプリセット名をメッセージに送信するだけでOKです！")
            await message.reply(embed = embed)
            return
        if user_message in preset_names:
            presets_dict = load_json("presets.json")
            await message.reply(presets_dict[user_message]["bodytext"])
            return

    if message.guild:
        
        if channelID == remindThreadID:
            
            greet_pattern = ".*(お(は(よ|ー|～)|早)|こんにち(は|わ)|こんばん(は|わ))|ohayo.*"
            result = re.match(greet_pattern, message.content)
            if result:
                logger.info(f"{author.name}さんが挨拶しました！")
                await message.add_reaction("🌟")
                
        if channelID == config.screenshot_recruit_channel or channelID == config.screenshot_recruit_channel_test:
            if not message.attachments:
                return
            for attachment in message.attachments:
                if "image" not in attachment.content_type:
                    return
                tags_image = io.BytesIO(rq.get(attachment.url).content)
                await recruit.recruit_from_screenshot(image_path=tags_image, message = message)

        if channel.category_id == config.feedback_category and channel.name.startswith("mail"):

            idx = channel.name.find("-") + 1
            userID = int(channel.name[idx:])
            user = await client.fetch_user(userID)

            mail = discord.Embed(
                title=f"【スタッフ】{author.display_name}からのメッセージ", description=user_message, color=0x979C9F)
            mail.set_author(name=author.display_name,
                            icon_url=author.avatar)
            
            embeds = [mail]
            videos = []
            
            for attachment in message.attachments:
                if "image" in attachment.content_type:
                    embed = discord.Embed(color = discord.Color.yellow())
                    embed.set_image(url = attachment.url)
                    embeds.append(embed)
                
                if "video" in attachment.content_type:
                    videos.append(attachment.url)
            
            await user.send(embeds=embeds)
            for video in videos:
                await user.send(content = f"[ブラウザで開く]({video})")

            await message.add_reaction("✅")
            logger.info(f"Modmailに投稿されたメッセージ(id: {message.id})を正常に転送しました")
                
    else:
        guild = client.get_guild(config.main_server) if config.test is False else client.get_guild(config.testserverid)
        logger.info(f"{username}に「{user_message}」と言われました。")
        mod_channel = await modmails.fetch_mod_channel(guild=guild, user=author)
        if mod_channel is not None:
                
            mail = discord.Embed(title=f"{author.display_name}さんからのメッセージ",
                                    description=message.content, color=message.author.accent_color)
            mail.set_author(name=str(message.author),
                            icon_url=message.author.avatar)
            embeds = [mail]
            videos = []
            
            for attachment in message.attachments:
                if "image" in attachment.content_type:
                    embed = discord.Embed(color = discord.Color.yellow())
                    embed.set_image(url = attachment.url)
                    embeds.append(embed)
                
                if "video" in attachment.content_type:
                    videos.append(attachment.url)
            
            await mod_channel.send(embeds=embeds)
            for video in videos:
                await mod_channel.send(content = f"[ブラウザで開く]({video})")
                
            await message.add_reaction("✅")
            logger.info(f"Modmailへ投稿されたメッセージ(id: {message.id})を正常に転送しました")

        else:
            response = await chat.direct_chat(author, message)
            if response:
                logger.info(f"{username}さんのメッセージ{user_message}に対して、{response}と返答しました")
            
def load_json(file_name: str) -> dict:
    with open(os.path.join(dir, f"jsons\\{file_name}"), "r", encoding="utf-8") as f:
        return json.load(f)
    
def save_json(file_name: str, data: dict):
    with open(os.path.join(dir, f"jsons\\{file_name}"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
     
async def load_reactions(reaction: discord.Reaction):
    with open(os.path.join(dir, "jsons/reactions.json"), "r", encoding="utf-8") as f:
        reactions = json.load(f)
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
        
        reactions[reaction.message.id] = {"count": reaction_count, "created_at": created_at, "posted": 0}
        
    with open(os.path.join(dir, "jsons/reactions.json"), "w", encoding="utf-8") as f:
        json.dump(reactions, f, indent=2, ensure_ascii=False)
        
    return reaction_count, posted

async def posted_reaction_message(search_message: int, posted_message: int):
    with open(os.path.join(dir, "jsons/reactions.json"), "r", encoding="utf-8") as f:
        reactions = json.load(f)
    search_id = str(search_message)
    if search_id in reactions:
        reactions[search_id]["posted"] = posted_message
    with open(os.path.join(dir, "jsons/reactions.json"), "w", encoding="utf-8") as f:
        json.dump(reactions, f, indent=2, ensure_ascii=False)
        
@client.event
async def on_raw_reaction_add(reaction_payload: discord.RawReactionActionEvent):
    
    if reaction_payload.emoji.name != "I_agree":
        return
    
    reaction_user = reaction_payload.user_id
    message_channel = client.get_channel(reaction_payload.channel_id)
    message = await message_channel.fetch_message(reaction_payload.message_id)

    if not message.guild:
        return
    if message.author.bot is True:
        return
    found = False
    for reaction in message.reactions:
        if type(reaction.emoji) is str:
            continue
        emoji_name = reaction.emoji.name
        if emoji_name == "I_agree":
            found = True
            break
    if found is False:
        return
    
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
        
        if type(message_channel) is discord.Thread:
            is_private = True
        else:
            default_overwrites = message_channel.overwrites_for(message_guild.default_role)
            if default_overwrites.read_messages is False:
                is_private = True
        if is_private is True:
            logger.info("プライベートチャンネルのため、聖堂入りを中止しました。")
            return
        if message_author.get_role(config.cathedral_NG_role):
            logger.info("聖堂NGのロールを持っているため、聖堂入りを中止しました")
            return
        channel = client.get_channel(config.cathedral)
        
        embeds = []
        embed = discord.Embed(description=message_content, timestamp=message_created_at_JST, color = discord.Color.yellow())
        embed.set_author(name = message_author.display_name, icon_url=message_author.display_avatar, url = message_jump_url)
        embed.set_footer(text = f"ID: {message_id}")
        if message_attachments and "image" in message_attachments[0].content_type:
            embed.set_image(url = message_attachments[0].url)
        embeds.append(embed)
        videos = []
        if message_attachments:
            
            for number in range(len(message_attachments)):
                if "image" in message_attachments[number].content_type and number != 0:
                    embed = discord.Embed(color = discord.Color.yellow())
                    embed.set_image(url = message_attachments[number].url)
                    embeds.append(embed)
                
                if "video" in message_attachments[number].content_type:
                    videos.append(message_attachments[number].url)

        logger.info(f"メッセージ({message_id})が{reaction_user}の手で聖堂へ刻まれました")                        
        posted_message = await channel.send(content = f"{message_author.mention} さんのメッセージが <:I_agree:1183255845497229442> を{reaction.count}個獲得しました！\nメッセージへのリンク: {message_jump_url}", embeds = embeds)
        for video_url in videos:
            await posted_message.reply(content = f"[ブラウザで開く]({video_url})")
        await posted_reaction_message(message_id, posted_message.id)
    
    if posted != 0:
        channel = client.get_channel(config.cathedral)
        edit_message = await channel.fetch_message(posted)
        message_author = message.author
        message_jump_url = message.jump_url
        await edit_message.edit(content = f"{message_author.mention} さんのメッセージが <:I_agree:1183255845497229442> を{reaction.count}個獲得しました！\nメッセージへのリンク: {message_jump_url}")

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
                
        await voicechat.join_voice(interaction = interaction)
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
    
@client.tree.command(name="add_reminder", description="remindarchive.jsonにanniRemind、sssRemindを追加します", guild=discord.Object(config.testserverid))
@app_commands.describe(
    remind_id = "リマインダーID(anniRemind-202507, sssRemind-202507等)",
    remind_name = "殲滅作戦or保全駐在の名前(例: 殲滅依頼「66号航路」, 協奏保全駐在)",
    remind_type = "anni or sss",
    link = "攻略Wikiのリンク",
    start_time = "開始時間(例: 2023-10-01 16:00:00)",
    end_time = "終了時間(例: 2023-10-15 3:59:59)"
)
async def add_reminder(interaction: discord.Interaction, remind_id: str, remind_name: str, remind_type: Literal["anni", "sss"], link: str, start_time: str, end_time: str):
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
    if remind_id in remind_archive:
        logger.error(f"リマインダーID {remind_id} は既に存在します。")
        await interaction.followup.send(f"リマインダーID `{remind_id}` は既に存在します。別のIDを使用してください。")
        return
    remind_archive.update(new_remind_dict)
    save_json("reminds.json", remind_archive)
    
    await interaction.followup.send(f"リマインダー `{remind_id}` が追加されました！\n名前: {remind_name}\nタイプ: {remind_type}\nリンク: {link}\n開始時間: {startTime.strftime('%Y-%m-%d %H:%M:%S')}\n終了時間: {endTime.strftime('%Y-%m-%d %H:%M:%S')}")
    
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

@client.tree.command(name="add_event", description="イベントを追加します", guild=discord.Object(config.testserverid))
@app_commands.describe(name="イベントの名前", 
                       event_type="イベントの種類(例: SIDESTORY, MINISTORY, EVENT, MAIN, MULTIPLAY, BOSS_RUSH",
                       start_time="イベントの開始時間(例: 2023-10-01 16:00:00)", 
                       end_time="イベントの終了時間(例: 2023-10-15 3:59:59)", 
                       stage_add="ステージ追加があるかどうか(T/F)",
                       news_url="ニュースURL",
                       wiki_url="WikiのURL",
                       image_url="イベントの画像URL",
                       reward_end_time="報酬交換期限(入力無の場合、終了時間から7日後の午前3時59分59秒になります)",
                       event_id="イベントID(入力無の場合、イベント名を小文字にしてスペースをアンダースコアに置き換えたものになります)")
async def add_event(interaction: discord.Interaction, name: str, event_type: Literal["SIDESTORY", "MINISTORY", "EVENT", "MAIN", "MULTIPLAY", "BOSS_RUSH"], start_time: str, end_time: str, stage_add: str, news_url: str, wiki_url: str, image_url: str, reward_end_time: str = None, event_id: str = None):

    """新しいイベント情報をevents.jsonに追加します。"""
    await interaction.response.defer()

    try:
        # タイムゾーン設定 (日本時間)
        jst = JSTTime.tz_JST
        time_format = "%Y-%m-%d %H:%M:%S"

        # 時間文字列をパースしてUnixタイムスタンプに変換
        dt_start = datetime.datetime.strptime(start_time, time_format)
        localized_dt_start = dt_start.replace(tzinfo=jst)
        start_timestamp = int(localized_dt_start.timestamp())

        dt_end = datetime.datetime.strptime(end_time, time_format)
        localized_dt_end = dt_end.replace(tzinfo=jst)
        end_timestamp = int(localized_dt_end.timestamp())

        # 報酬交換期限の処理
        if reward_end_time:
            dt_reward_end = datetime.datetime.strptime(reward_end_time, time_format)
            localized_dt_reward_end = dt_reward_end.replace(tzinfo=jst)
            reward_end_timestamp = int(localized_dt_reward_end.timestamp())
        else:
            # 指定がない場合は終了時間の7日後の3:59:59
            reward_dt = localized_dt_end.replace(hour=3, minute=59, second=59) + datetime.timedelta(days=7)
            reward_end_timestamp = int(reward_dt.timestamp())
            
        event_id = name.lower().replace(" ", "_") if event_id is None else event_id

        # 新しいイベントデータを作成
        new_event = {
            "id": event_id,
            "type": event_type,
            "stageAdd": True if stage_add.lower() == "t" else False,
            "name": name,
            "news": news_url,
            "link": wiki_url,
            "pic": image_url,
            "startTime": start_timestamp,
            "endTime": end_timestamp,
            "rewardEndTime": reward_end_timestamp
        }

        # JSONファイルを読み込む
        events_data = load_json("events.json")

        # データを追加
        events_data[event_id] = new_event

        save_json("events.json", events_data)

        # 成功メッセージをEmbedで表示
        embed = discord.Embed(title="イベント追加成功", color=discord.Color.green())
        embed.description = f"イベント「{name}」をeventarchive.jsonに追加しました。確認後、events.jsonに反映してください。"
        embed.add_field(name="ID", value=event_id, inline=False)
        embed.add_field(name="開始日時", value=f"<t:{start_timestamp}:F>", inline=True)
        embed.add_field(name="終了日時", value=f"<t:{end_timestamp}:F>", inline=True)
        embed.add_field(name="報酬交換期限", value=f"<t:{reward_end_timestamp}:F>", inline=True)
        embed.set_image(url=image_url)

        await interaction.followup.send(embed=embed)

    except ValueError:
        await interaction.followup.send(f"エラー: 時間のフォーマットが正しくありません。`{time_format}`の形式で入力してください。")
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}")

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
@app_commands.describe(version="リマインドの時間 morning/afternoon/evening/thread")
async def remind(interaction: discord.Interaction, version: str):
    if interaction.user == client.user:
        return
    await interaction.response.defer()
    if not version == "thread":

        await reminder.remind(version)
        
    else:
        
        global remindThreadID
        thread = await reminder.remind(version)
        remindThreadID = thread.id
        
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
                        description="channelIDが空欄の場合、リマインダースレッドに投稿します！",
                        guild=discord.Object(config.testserverid))
async def send_text_message(interaction: discord.Interaction, text: str, channelid: str = None):
    if not channelid:
        guild = client.get_guild(guildID)
        channel = guild.get_thread(remindThreadID)
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
        await reminder.remind("morning")

    except Exception as e:
        logger.exception(f"[morning]にてエラー：{e}")  
        
@tasks.loop(time=config.threadtime)
async def send_remind():
    try:
        global remindThreadID
        logger.info("時間になりました。メンバーにリマインドを送ります。")
        thread = await reminder.remind("thread")
        remindThreadID = thread.id
        await supportrequest.delete_old_request()

    except Exception as e:
        logger.exception(f"[send_remind]にてエラー：{e}") 

@tasks.loop(time=config.afternoontime)
async def afternoon():
    try:
        logger.info("時間になりました。アフタヌーンルーティンを始めます")
        await reminder.remind("afternoon")

    except Exception as e:
        logger.exception(f"[afternoon]にてエラー：{e}") 
        
@tasks.loop(time=config.eveningtime)
async def evening():
    try:
        logger.info("時間になりました。イヴニングルーティンを始めます")
        await reminder.remind("evening")

    except Exception as e:
        logger.exception(f"[evening]にてエラー：{e}") 
        
@tasks.loop(time=config.newdaytime)
async def new_days():
    try:
        logger.info("時間になりました。０時ルーティンを始めます")
        await reminder.remind("evening")

    except Exception as e:
        logger.exception(f"[new_days]にてエラー：{e}") 
