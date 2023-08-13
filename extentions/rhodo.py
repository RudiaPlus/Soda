import discord
from extentions import (moderates, reminder, responses, config, voicechat,
                        evjson, JSTTime, modmails, log, maintenances, requests)
from extentions.aclient import client
import re
import asyncio
import datetime
import unicodedata
import os
import json
from discord import app_commands
from discord.ext import tasks

logger = log.setup_logger(__name__)


async def send_message(message, user_message):
    try:
        response = await responses.get_response(user_message, reset=False)
        logger.info(f"返信を取得しました「{response}」")

        if len(response) > 1900:
            await message.channel.send("文字数制限を超えてしまいました！すみませんがもう一度お願いします！")
        else:
            await message.channel.send(response)

    except Exception as e:
        logger.exception(f"[send_message]にてエラー：{e}")


def run_discord_bot():

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
            await client.tree.sync(guild=config.testserverid)
            
            logger.info(f"{len(synced)}個のコマンドを同期しました。")
            
            #ボタン登録
            client.add_view(requests.RequestComplete())
            client.add_view(modmails.ModmailButton())
            client.add_view(modmails.ModmailFinish())
            client.add_view(modmails.ModmailControl())
            
        except Exception as e:
            logger.exception(f"[on_ready]にて エラー：{e}")
            
        logger.info(f"{client.user} 、準備完了です！")

    @client.event
    async def setup_hook() -> None:
        morning.start()
        maintenances.maintenance_timer.start()   
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
            guild = client.get_guild(config.main_server)
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

        if channelID == config.chat:
            clean_message = re.sub('<.*?>', '', user_message)
            logger.info("返事をします")
            await send_message(message, clean_message)
            
        else:
            return
        
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

        await interaction.followup.send(embed=embed, ephemeral=True)

    @client.tree.command(name="ping",
                         description="botの応答時間を確認します",
                         guild=config.testserverid)
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
                         guild=config.testserverid)
    async def rechat(interaction: discord.Interaction):
        if interaction.user == client.user:
            return

        await interaction.response.defer()
        await responses.get_response("reset", reset=True)
        await interaction.followup.send("完了しました！")

    @client.tree.command(name="set_remind",
                         description="リマインドを作り直します",
                         guild=config.testserverid)
    @app_commands.describe(version="リマインドの時間 morning/afternoon/evening")
    async def set_remind(interaction: discord.Interaction, version: str):
        await interaction.response.defer()
        channel = client.get_channel(config.announce)
        await channel.send("リマインダーを作り直します")
        await reminder.remind(version)
        await interaction.followup("完了しました")

    @client.tree.command(name="maintenance",
                         description="メンテナンスについて",
                         guild=config.testserverid)
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
                         guild=config.testserverid)
    @app_commands.describe(version="リマインドの時間 morning/afternoon/evening")
    async def remind(interaction: discord.Interaction, version: str):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        await reminder.remind(version)
        await interaction.followup.send("完了しました！")

    @client.tree.command(name="eventtest",
                         description="イベントリストのテストを行います",
                         guild=config.testserverid)
    async def eventtest(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await interaction.response.defer()
        events = evjson.eventget()
        await interaction.followup.send(events)

    @client.tree.command(name="send",
                         description="dev only",
                         guild=config.testserverid)
    async def send(interaction: discord.Interaction, channelid: int, text: str):
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
                         guild=config.testserverid)
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

    TOKEN = config.token
    client.run(TOKEN)
