import discord
from extentions import (moderates, reminder, responses, config, voicechat,
                        evjson, JSTTime, modmails, log, maintenances, requests, recruit, twitterpost)
from extentions.aclient import client
import re
import asyncio
import datetime
import unicodedata
import os
import json
from math import floor
from discord import app_commands
from discord.ext import tasks

logger = log.setup_logger(__name__)

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
            client.add_view(requests.RequestComplete())
            client.add_view(modmails.ModmailButton())
            client.add_view(modmails.ModmailFinish())
            client.add_view(modmails.ModmailControl())
            client.add_view(ToolButtons())
            
            #ルーティン
            maintenances.maintenance_timer.start()
            
            if twitterpost.web == True:
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
                    logger.warn(f"前回のリマインダー投稿から1日以上({passed_second}秒)が経過していました。リマインダーを投稿します。")
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

        if message.author == client.user:
            return

        author = message.author
        username = str(author)
        user_message = message.content
        channel = message.channel
        channelID = message.channel.id

        if message.guild:
            
            if channelID == remindThreadID:
                
                greet_pattern = ".*(お(は(よ|ー|～)|早)|こんにち(は|わ)|こんばん(は|わ)).*"
                result = re.match(greet_pattern, message.content)
                if result:
                    logger.info(f"{author.name}さんが挨拶しました！")
                    await message.add_reaction("🌟")

            if channel.category_id == config.feedback_category and channel.name.startswith("mail"):

                idx = channel.name.find("-") + 1
                userID = int(channel.name[idx:])
                user = await client.fetch_user(userID)

                mail = discord.Embed(
                    title=f"【スタッフ】{author.display_name}からのメッセージ", description=user_message, color=0x979C9F)
                mail.set_author(name=author.display_name,
                                icon_url=author.avatar)
                await user.send(embed=mail)
                
            if message.guild.voice_client:
                target_channels = await voicechat.get_target_channels(message.guild.voice_client.channel)
                if channelID in target_channels:
                    while message.guild.voice_client.is_playing():
                        await asyncio.sleep(0.1)
                    source = discord.FFmpegPCMAudio(executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",source=voicechat.text_to_speech(message.content))
                    message.guild.voice_client.play(source)
                    
        else:
            guild = client.get_guild(config.main_server) if config.test == False else client.get_guild(config.testserverid)
            logger.info(f"{username}に「{user_message}」と言われました。")
            mod_channel = await modmails.fetch_mod_channel(guild=guild, user=author)
            if mod_channel is not None:
                mail = discord.Embed(title=f"{message.author.name}さんからのメッセージ",
                                     description=message.content, color=message.author.accent_color)
                mail.set_author(name=str(message.author),
                                icon_url=message.author.avatar)
                await mod_channel.send(embed=mail)

            else:
                mail = discord.Embed(
                    title="お問い合わせの場合は、/modmailをご利用ください！",
                    description="DMありがとうございます！\nスタッフと個別で会話をしたい場合は、コマンド/modmailをご利用ください！\n私とお話ししたい場合は、<#1072158278634713108>までどうぞ！",
                    color=0x979C9F)
                mail.set_author(name="あしたはこぶねスタッフ",
                                icon_url=config.server_icon)
                await message.author.send(embed=mail)
    
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
            
            embed = discord.Embed(title="ボイスチャンネルに接続しました", description= f"チャット読み上げを開始します。\n`/leave`で読み上げを終了します。", color = discord.Color.green())
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

    class ToolButtons(discord.ui.View):
        def __init__(self):
            super().__init__(timeout = None)
        
        @discord.ui.button(label = "公開求人ツール", custom_id = "recruitbutton", style = discord.ButtonStyle.primary, emoji = "📄")
        async def recruitbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True)
            
            selected_tags = []
            view = recruit.TagSelectView(selected_tags=selected_tags, all = True)
            
            embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
            logger.info(f"{interaction.user.name}がrecruitbuttonを使用しました")
            await interaction.followup.send(embed = embed, view = view, ephemeral=True)            
    
    @client.tree.command(name="tool_form", description = "ツールのチャットを送信します", guild = discord.Object(config.testserverid))
    async def tool_form(interaction: discord.Interaction, channelid: int = 1142491583757951036):
        await interaction.response.defer(ephemeral = True)
        
        channel = await client.fetch_channel(channelid)
        embed = discord.Embed(title = "コミュニティツール", description = "下のボタンから私の便利ツールをご利用できます！", color = discord.Color.red())
        embed.add_field(name = "公開求人ツール", value = "公開求人のタグから獲得できるオペレーターを表示します。\nタイムアウトが設定されているので、リセットする時はボタンを押し直してください！")
        embed.set_author(name = "ロード", icon_url=client.user.avatar)
        await channel.send(embed = embed, view = ToolButtons())
        
        await interaction.followup.send("完了しました！")
    
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
    async def eventtest(interaction: discord.Interaction):
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
            channelid = int(unicodedata.normalize("NFKC", channelid))
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

            num_tag = unicodedata.normalize("NFKC", tag)

            if len(tag) > 6 or len(name) > 16:
                embed = discord.Embed(title="名前が長すぎます！",
                                      description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                      color=0xf45d5d)
                await interaction.response.send_message(embed=embed)
                return

            if tag.isdecimal() == False or re.match(r"[0-9]{1,6}$", num_tag) is None:
                embed = discord.Embed(title="タグは数字のみを入力してください！",
                                      description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                      color=0xf45d5d)
                await interaction.response.send_message(embed=embed)
                return

            await interaction.response.defer()
            added = await requests.doctor_add(interaction.user, name, num_tag)
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
            name_full = await requests.doctor_check(user)
            if name_full is None:
                embed = discord.Embed(title=f"ドクターネームが見つかりません！",
                                      description=f"{user.name}さんのドクターネームは見つかりませんでした！",
                                      color=0xf45d5d)
                embed.set_author(name=user.name, icon_url=user.avatar)
                await interaction.followup.send(embed=embed)
                return
            else:
                embed = discord.Embed(
                    title=f"ドクターネームが見つかりました！",
                    description=f"{user.name}さんのドクターネームは以下になります！\n「{name_full}」",
                    color=0x5cb85c)
                embed.set_author(name=user.name, icon_url=user.avatar)
                await interaction.followup.send(embed=embed)

        @app_commands.command(name="delete", description="設定された自分のドクターネームを削除します")
        async def doctorname_delete(self, interaction: discord.Interaction):
            if interaction.user == client.user:
                return
            await interaction.response.defer()
            delete = await requests.doctor_delete(interaction.user)
            if delete == "success":
                embed = discord.Embed(
                    title=f"ドクターネームの登録を削除しました！",
                    description=f"登録しなおす場合は、「/doctorname set」をご利用ください！",
                    color=0x5cb85c)
                embed.set_author(name=interaction.user.name,
                                 icon_url=interaction.user.avatar)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title=f"ドクターネームの登録を削除できませんでした。",
                    description=f"ドクターネームの登録を削除できませんでした！既に登録が削除されている場合があります！\nもし削除されているか確認したい場合は「/modmail」にてお問い合わせください！",
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
            await responses.get_response("reset", reset=True)

        except Exception as e:
            logger.exception(f"[send_remind]にてエラー：{e}") 
    
    @tasks.loop(time=config.afternoontime)
    async def afternoon():
        try:
            logger.info("時間になりました。アフタヌーンルーティンを始めます")
            await reminder.remind("afternoon")
            await responses.get_response("reset", reset=True)

        except Exception as e:
            logger.exception(f"[afternoon]にてエラー：{e}") 
            
    @tasks.loop(time=config.eveningtime)
    async def evening():
        try:
            logger.info("時間になりました。イヴニングルーティンを始めます")
            await reminder.remind("evening")
            await responses.get_response("reset", reset=True)

        except Exception as e:
            logger.exception(f"[evening]にてエラー：{e}") 
            
    @tasks.loop(time=config.newdaytime)
    async def new_days():
        try:
            logger.info("時間になりました。０時ルーティンを始めます")
            await reminder.remind("evening")
            await responses.get_response("reset", reset=True)

        except Exception as e:
            logger.exception(f"[new_days]にてエラー：{e}") 

    if test == True:

        logger.warn("テストモードで実行しています！")
        TOKEN = config.test_client
    
    else:
        TOKEN = config.token
    
    client.run(TOKEN)
