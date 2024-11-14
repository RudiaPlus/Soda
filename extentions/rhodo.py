import asyncio
import datetime
import io
import json
import os
import re
from math import floor
from unicodedata import normalize

import discord
import requests as rq
from discord import app_commands
from discord.ext import tasks

from extentions import (
    JSTTime,
    communitytool,
    config,
    evjson,
    log,
    maintenances,
    moderates,
    modmails,
    multiplayertool,  # noqa: F401
    recruit,
    reminder,
    responses,
    supportrequest,
    twitterpost,
    voicechat,
)
from extentions.aclient import client

logger = log.setup_logger()

#global変数
remindThreadID = 0
guildID = config.main_server

def run_discord_bot():

    test = config.test
    dir = os.path.abspath(__file__ + "/../")

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
            
            #ボタン登録
            client.add_view(supportrequest.RequestComplete())
            client.add_view(modmails.ModmailButton())
            client.add_view(modmails.ModmailFinish())
            client.add_view(modmails.ModmailControl())
            client.add_view(communitytool.ToolButtons())
            client.add_view(multiplayertool.AKMultiJoinButton())
            
            #ルーティン
            maintenances.maintenance_timer.start()
            
            if twitterpost.web is True:
                url = twitterpost.last_tweet_url
                await twitterpost.publish_tweet_from_nitter_url(url)
                twitterpost.ake_tweet_retrieve.start()
            
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

                passed_second = floor(now_utc_timestamp - last_remind.created_at.timestamp())               
                logger.info(f"前回のリマインダーは{last_remind.created_at.astimezone(tz_JST)}({passed_second}秒前)に投稿されています")

                if passed_second > 86400:
                    logger.warning(f"前回のリマインダー投稿から1日以上({passed_second}秒)が経過していました。リマインダーを投稿します。")
                    await reminder.remind("thread")
                
            except Exception as e:
                logger.error(f"リマインダースレッドの確認に失敗しました！\n{e}")
            
        except Exception as e:
            logger.exception(f"[on_ready]にて エラー：{e}")
            
        logger.info(f"{client.user} 、準備完了です！")

    @client.event
    async def setup_hook() -> None:
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

        if message.guild:
                        
            
            if channelID == remindThreadID:
                
                greet_pattern = ".*(お(は(よ|ー|～)|早)|こんにち(は|わ)|こんばん(は|わ))|ohayo.*"
                result = re.match(greet_pattern, message.content)
                if result:
                    logger.info(f"{author.name}さんが挨拶しました！")
                    await message.add_reaction("🌟")
                    
            if channelID == config.screenshot_recruit_channel:
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
                
            if message.guild.voice_client:
                target_channels = await voicechat.get_target_channels(message.guild.voice_client.channel)
                if channelID in target_channels:
                    while message.guild.voice_client.is_playing():
                        await asyncio.sleep(0.1)
                    source = discord.FFmpegPCMAudio(executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",source=voicechat.text_to_speech(message.content))
                    message.guild.voice_client.play(source)
                    
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
                mail = discord.Embed(
                    title="お問い合わせの場合は、/modmailをご利用ください！",
                    description="DMありがとうございます！\nスタッフと個別で会話をしたい場合は、コマンド/modmailをご利用ください！",
                    color=0x979C9F)
                mail.set_author(name="あしたはこぶねスタッフ",
                                icon_url=config.server_icon)
                await message.author.send(embed=mail)
                
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
                if message_channel.is_private() is True:
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
        def __init__(self, join_channel, target_chat_id):
            super().__init__(timeout = 60)
            self.vc_channels = voicechat.channels
            self.join_channel = join_channel
            self.target_chat_id = target_chat_id
            
        @discord.ui.button(label = "はい", style = discord.ButtonStyle.success, emoji = "✅")
        async def speechstart(self, interaction: discord.Interaction, button: discord.ui.Button):
                    
            await self.join_channel.connect(timeout = 5, self_deaf = True)
            
            target_chat_str = "<#" + ">, <#".join(map(str,self.target_chat_id)) + ">"
            
            embed = discord.Embed(title="ボイスチャンネルに接続しました", description= "チャット読み上げを開始します。\n`/leave`で読み上げを終了します。", color = discord.Color.green())
            embed.add_field(name = "接続したチャンネル", value = f"<#{self.join_channel.id}>")
            embed.add_field(name = "読み上げ対象のチャンネル", value = target_chat_str)
            embed.set_author(name = "チャット読み上げ")
            await interaction.message.edit(embed = embed, view = None)
    
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
            
        #suggest
        vc_channels = voicechat.channels
        
        if config.voice_suggest and after.channel and len(after.channel.members) == 1 and not before.channel and not member.guild.voice_client:
            
            join_channel = after.channel
            logger.info(f"{member.name}にボイス読み上げの提案を行います")
            
            target_chat_id = await voicechat.get_target_channels(join_channel)
            if not target_chat_id:
                return        
            if len(target_chat_id) > 1:
            
                for index in vc_channels.values():
                    
                    if index["id"] == join_channel.id and index["type"] == "vc":
                        
                        
                            send_channel = client.get_channel(target_chat_id[-1])
                        
                            embed = discord.Embed(title = "ボイスチャットに接続しました！", description = "聞き専チャットを読み上げる機能を有効にしますか？\nこのメッセージは60秒で削除されます！\n後で`/join`コマンドを使用することでも読み上げを始めます！", color = discord.Color.blue())
                            embed.set_author(name = "チャット読み上げ")
                            message = await send_channel.send(embed = embed, view = VoiceSpeechButtons(join_channel = join_channel, target_chat_id=target_chat_id))
                            asyncio.sleep(60)
                            await message.delete()
                            
        #vccreate
        vccreate_voice = client.get_channel(config.voicecreate_vc)
        
        if after.channel == vccreate_voice:
            vccreate_category = discord.utils.get(after.channel.guild.categories, name = "────VC/個別────")
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
            embed = discord.Embed(title = "ボイスチャット作成成功", description = f"ボイスチャットの作成に成功しました！\n名前の変更、最大人数の設定などは{vccreate_channel.jump_url}をご覧ください！\n**使用されていない「しゃべるくん」以外の読み上げbotの使用はご遠慮ください。**")
            embed.set_footer(text = "VCルールとマナーを厳守してください。このVC内容はログが取られています。")
            await created_vc.send(content = member.mention, embed = embed)
            
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

    @client.tree.command(name="rechat",
                         description="for dev only",
                         guild=discord.Object(config.testserverid))
    async def rechat(interaction: discord.Interaction):
        if interaction.user == client.user:
            return

        await interaction.response.defer()
        await responses.get_response("reset", reset=True)
        await interaction.followup.send("完了しました！")

    @client.tree.command(name="maintenance",
                         description="メンテナンスについて",
                         guild=discord.Object(config.testserverid))
    @app_commands.describe(number="0からの参照番号", status="ruined(中止)/end(終了)", name="告知する名前。デフォルトは「メンテナンス」")
    async def maintenance(interaction: discord.Interaction,
                          number: int,
                          status: str,
                          name: str = "メンテナンス"):
        if status == "ruined":
            await interaction.response.defer()
            await maintenances.maintenance_ruined(number)
            await interaction.followup.send("完了しました")

        if status == "end":
            await interaction.response.defer()
            await maintenances.maintenance_end(name, number)
            await interaction.followup.send("完了しました")

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
        
    @client.tree.command(name="eventcounttest",
                         description="イベントカウントのテストを行います",
                         guild=discord.Object(config.testserverid))
    async def eventcounttest(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        eventcount = evjson.eventcount()
        await interaction.followup.send(f"- eventnow: {eventcount[0]}\n- eventend: {eventcount[1]}\n- eventvalue: {eventcount[2]}\n- eventtoday: {eventcount[3]}\n- eventendtoday: {eventcount[4]}")       

    @client.tree.command(name="send",
                         description="channelIDが空欄の場合、リマインダースレッドに投稿します！",
                         guild=discord.Object(config.testserverid))
    async def send(interaction: discord.Interaction, text: str, channelid: str = None):
        if not channelid:
            guild = client.get_guild(guildID)
            channel = guild.get_thread(remindThreadID)
        else:
            channelid = int(normalize("NFKC", channelid))
            channel = client.get_channel(channelid)
        await channel.send(text)
        await interaction.response.send_message("完了しました")

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
            await responses.get_response("reset", reset=True)

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

    if test is True:

        logger.warning("テストモードで実行しています！")
        TOKEN = config.test_client
    
    else:
        TOKEN = config.token
    
    client.run(TOKEN)
