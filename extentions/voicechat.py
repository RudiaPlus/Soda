import asyncio
import json
import os
import re
import datetime
import subprocess
import atexit
import aiohttp

import discord
from discord.ext import tasks

from extentions import log
from extentions.aclient import client, voice_clients_list
from extentions.config import config

from discord.errors import ClientException

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "\\..\\")
jsons_dir = os.path.join(dir, "jsons")
voice_status_json_name = "jsons\\voice_status.json"

host = "127.0.0.1"
port = "10101"
sleep_time = 0.5

voicechat = False

#新しいVCを登録する場合、channels.jsonも忘れずに
#二つ以上の場合、最後がVC_chatが望ましい

def voice_client_status():
    with open(os.path.join(dir, voice_status_json_name), "r", encoding = "utf-8") as f:
        status_dict = json.load(f)
    return status_dict

def write_voice_status(dict):
    with open(os.path.join(dir, voice_status_json_name), "w", encoding = "utf-8") as f:
        json.dump(dict, f, ensure_ascii=False, indent=4)
    return

async def get_user_dict(session: aiohttp.ClientSession, max_retry: int = 3):
    """
    VOICEVOX互換APIのユーザー辞書を取得します。

    Args:
        session (aiohttp.ClientSession): aiohttpのセッション。
        max_retry (int): 失敗時の最大リトライ回数。

    Returns:
        dict: ユーザー辞書の内容。
    """
    url = f"http://{host}:{port}/user_dict"
    for i in range(max_retry):
        try:
            async with session.get(url, timeout=10.0) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"ユーザー辞書の取得に失敗しました。ステータス: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"ユーザー辞書の取得処理がタイムアウトしました。リトライします... ({i + 1}/{max_retry})")
        except aiohttp.ClientError as e:
            logger.error(f"クライアントエラーが発生しました: {e}。リトライします... ({i + 1}/{max_retry})")
        
        if i < max_retry - 1:
            await asyncio.sleep(1)

    logger.error("リトライ回数の上限に到達したため、ユーザー辞書の取得に失敗しました。")
    return {}

async def add_user_word(
    surface: str,
    pronunciation: str,
    accent_type: int,
    max_retry: int = 3,
):
    """
    VOICEVOX互換APIのユーザー辞書に単語を登録します。

    Args:
        session (aiohttp.ClientSession): aiohttpのセッション。
        surface (str): 登録する単語の表記。
        pronunciation (str): 単語の読み方（カタカナ）。
        accent_type (int): アクセント核の位置（0は平板型）。
        max_retry (int): 失敗時の最大リトライ回数。

    Returns:
        bool: 登録に成功した場合はTrue、失敗した場合はFalse。
    """
    params = {
        "surface": surface,
        "pronunciation": pronunciation,
        "accent_type": accent_type,
    }
    url = f"http://{host}:{port}/user_dict_word"
    async with aiohttp.ClientSession() as session:
        for i in range(max_retry):
            try:
                # /user_dict_word エンドポイントにPOSTリクエストを送信
                async with session.post(url, params=params, timeout=10.0) as resp:
                    # 成功（ステータスコード 200 OK または 204 No Content）
                    if resp.status in [200, 204]:
                        logger.info(f"ユーザー辞書に単語を追加しました: {surface}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(
                            f"単語の追加に失敗しました。ステータス: {resp.status}, "
                            f"レスポンス: {error_text}"
                        )
            except asyncio.TimeoutError:
                logger.warning(f"単語の追加処理がタイムアウトしました。リトライします... ({i + 1}/{max_retry})")
            except aiohttp.ClientError as e:
                logger.error(f"クライアントエラーが発生しました: {e}。リトライします... ({i + 1}/{max_retry})")
            
            if i < max_retry - 1:
                await asyncio.sleep(1)

        logger.error(f"リトライ回数の上限に到達したため、単語 '{surface}' の追加に失敗しました。")
        return False
    
async def edit_user_word(
    surface: str,
    pronunciation: str,
    accent_type: int,
    max_retry: int = 3,
):
    params = {
        "surface": surface,
        "pronunciation": pronunciation,
        "accent_type": accent_type,
    }
    async with aiohttp.ClientSession() as session:
        #単語のUUIDを取得
        user_dict = await get_user_dict(session, max_retry)
        uuid = None
        for uid in user_dict:
            if user_dict[uid]["surface"] == surface:
                uuid = uid
                break
        else:
            logger.error(f"単語 '{surface}' がユーザー辞書に存在しません。編集できません。")
            return False
        
        # /user_dict_word エンドポイントにPUTリクエストを送信
        url = f"http://{host}:{port}/user_dict_word/{uuid}"
        for i in range(max_retry):
            try:
                async with session.put(url, params=params, timeout=10.0) as resp:
                    if resp.status in [200, 204]:
                        logger.info(f"ユーザー辞書の単語を編集しました: {surface}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(
                            f"単語の編集に失敗しました。ステータス: {resp.status}, "
                            f"レスポンス: {error_text}"
                        )
            except asyncio.TimeoutError:
                logger.warning(f"単語の編集処理がタイムアウトしました。リトライします... ({i + 1}/{max_retry})")
            except aiohttp.ClientError as e:
                logger.error(f"クライアントエラーが発生しました: {e}。リトライします... ({i + 1}/{max_retry})")
            
            if i < max_retry - 1:
                await asyncio.sleep(1)

        logger.error(f"リトライ回数の上限に到達したため、単語 '{surface}' の編集に失敗しました。")
        return False
    
async def delete_user_word(surface: str, max_retry: int = 3):
    async with aiohttp.ClientSession() as session:
        # 単語のUUIDを取得
        user_dict = await get_user_dict(session, max_retry)
        uuid = None
        for uid in user_dict:
            if user_dict[uid]["surface"] == surface:
                uuid = uid
                break
        else:
            logger.error(f"単語 '{surface}' がユーザー辞書に存在しません。削除できません。")
            return False

        url = f"http://{host}:{port}/user_dict_word/{uuid}"
        for i in range(max_retry):
            try:
                # /user_dict_word エンドポイントにDELETEリクエストを送信
                async with session.delete(url, timeout=10.0) as resp:
                    if resp.status == 204:  # No Content
                        logger.info(f"ユーザー辞書から単語を削除しました: {surface}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(
                            f"単語の削除に失敗しました。ステータス: {resp.status}, "
                            f"レスポンス: {error_text}"
                        )
            except asyncio.TimeoutError:
                logger.warning(f"単語の削除処理がタイムアウトしました。リトライします... ({i + 1}/{max_retry})")
            except aiohttp.ClientError as e:
                logger.error(f"クライアントエラーが発生しました: {e}。リトライします... ({i + 1}/{max_retry})")
            
            if i < max_retry - 1:
                await asyncio.sleep(1)
        logger.error(f"リトライ回数の上限に到達したため、単語 '{surface}' の削除に失敗しました。")
        return False
    
async def audio_query(session: aiohttp.ClientSession, text: str, speaker: int, max_retry: int):
    # 音声合成用のクエリを作成する
    query_payload = {"text": text, "speaker": speaker}
    for _ in range(max_retry):
        try:
            async with session.post(f"http://{host}:{port}/audio_query", params=query_payload, timeout=300.0) as resp:
                if resp.status == 200:
                    return await resp.json()
        except asyncio.TimeoutError:
            logger.warning("audio_query timed out.")
        await asyncio.sleep(1)
    else:
        raise ConnectionError(f"リトライ回数が上限に到達しました。 audio_query : / {text[:40]}")

async def synthesis(session: aiohttp.ClientSession, speaker: int, query_data: dict, max_retry: int, intonationScale = 1.0, outputSamplingRate = 44100, outputStereo = False, pauseLength = None, pauseLengthScale = 1.0, pitchScale = 0.0, postPhonemeLength = 0.1, prePhonemeLength = 0.1, speedScale = 1.0, tempoDynamicsScale = 1.0, volumeScale = 1.0):
    synth_payload = {"speaker": speaker}
    
    query_data["intonationScale"] = intonationScale
    query_data["outputSamplingRate"] = outputSamplingRate
    query_data["outputStereo"] = outputStereo
    query_data["pauseLength"] = pauseLength
    query_data["pauseLengthScale"] = pauseLengthScale
    query_data["pitchScale"] = pitchScale
    query_data["postPhonemeLength"] = postPhonemeLength
    query_data["prePhonemeLength"] = prePhonemeLength
    query_data["speedScale"] = speedScale
    query_data["tempoDynamicsScale"] = tempoDynamicsScale
    query_data["volumeScale"] = volumeScale
    
    for _ in range(max_retry):
        try:
            async with session.post(f"http://{host}:{port}/synthesis", params=synth_payload, json=query_data, timeout=300.0) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.error(f"音声合成に失敗しました。ステータスコード: {resp.status}, メッセージ: {await resp.json()}")
        except asyncio.TimeoutError:
            logger.warning("synthesis timed out.")
        await asyncio.sleep(1)
    else:
        raise ConnectionError("音声エラー：リトライ回数が上限に到達しました。 synthesis")

async def text_to_speech(texts, speaker=config.aivis_speaker_ids["ノーマル"], max_retry=20, intonationScale = 1.0, outputSamplingRate = 44100, outputStereo = False, pauseLength = None, pauseLengthScale = 1.0, pitchScale = 0.0, postPhonemeLength = 0.1, prePhonemeLength = 0.1, speedScale = 1.0, tempoDynamicsScale = 1.0, volumeScale = 1.0, split_count = 0, is_ogg = False):
    if texts is None:
        texts=""
    
    url_pattern = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    texts = re.sub(url_pattern, 'URL省略', texts)

    # メンション・タグ・絵文字など <...> で囲まれたもの全てを削除
    tag_pattern = r"<[^>]+>"
    texts = re.sub(tag_pattern, '', texts)

    #<>,~,@,|,*,#などの特殊文字を削除
    non_text_pattern = r"[<>~@[\]|*#]"
    texts = re.sub(non_text_pattern, '', texts)

    if len(texts) > split_count and split_count > 0:
        texts = texts[:40] + "以下略"
        
    if len(texts) == 0 or not texts.strip():
        return None
    
    async with aiohttp.ClientSession() as session:
        # audio_query
        query_data = await audio_query(session, texts,speaker,max_retry)
        # synthesis
        voice_data = await synthesis(session, speaker,query_data,max_retry,intonationScale,outputSamplingRate,outputStereo,pauseLength,pauseLengthScale,pitchScale,postPhonemeLength,prePhonemeLength,speedScale,tempoDynamicsScale,volumeScale)
    
    filepath = "TTS\\voice.wav"
    ogg_filepath = "TTS\\voice.ogg"
    with open(os.path.join(dir, filepath), mode = "wb") as f:
        f.write(voice_data)
    
    #ogg変換
    if is_ogg:
        command = [
            "ffmpeg",
            "-y",
            "-i", os.path.join(dir, filepath),
            os.path.join(dir, ogg_filepath)
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()
        if process.returncode != 0:
            logger.error(f"ffmpeg failed with exit code {process.returncode}")
            return None
        return os.path.join(dir, ogg_filepath)
    return os.path.join(dir, filepath)

async def send_voice_message(text: str, channelid: int):

    file = await text_to_speech(text, speaker= config.aivis_speaker_ids["通常"], volumeScale=0.5, is_ogg=True)
    if file is None or not os.path.exists(file):
        logger.error("音声ファイルの生成に失敗しました。")
        return
    
    async with aiohttp.ClientSession() as session:
        #アップロードurlの取得
        headers = {
            "authorization": f"Bot {config.token}",
            "content-type": "application/json"
        }
        data = {
            "files": [
                {
                    "filename": "voice.ogg",
                    "file_size": os.path.getsize(file),
                    "id": "2"
                }
            ]
        }
        async with session.post(f"https://discord.com/api/v9/channels/{channelid}/attachments", headers=headers, json=data) as resp:
            if resp.status != 200:
                logger.error(f"アップロードurlの取得に失敗しました: {resp.status}")
                return
            upload_url = (await resp.json())["attachments"][0]["upload_url"]
            upload_filename = (await resp.json())["attachments"][0]["upload_filename"]
            
        #ファイルのアップロード
        with open(file, "rb") as f:
            data = f.read()
        headers = {
            "authorization": f"Bot {config.token}",
            "content-type": "audio/ogg"
        }
        async with session.put(upload_url, headers=headers, data=data) as resp:
            if resp.status != 200:
                logger.error(f"ボイスのアップロードに失敗しました: {resp.status}")
                return
        
        #ボイスメッセージの送信
        headers = {
            "authorization": f"Bot {config.token}",
            "content-type": "application/json"
        }
        data = {
            "flags": 8192,
            "attachments": [
                {
                    "id": "0",
                    "filename": "voice-message.ogg",
                    "uploaded_filename": upload_filename,
                    "duration_secs": os.path.getsize(file) / 10000,
                    "waveform": config.default_waveform_base64
                }
            ]
        }
        
        async with session.post(f"https://discord.com/api/v9/channels/{channelid}/messages", headers=headers, json = data) as resp:
            if resp.status != 200:
                logger.error(f"メッセージの送信に失敗しました: {resp.status}")
                return
            return resp.status

if config.voicechat is True:
    
    voicechat = True
    
    #ボイスエンジン起動
    try:
        voice_engine = subprocess.Popen([r"C:\\Program Files\\AivisSpeech-Engine\\Windows-x64\\run.exe", "--host=0.0.0.0", "--use_gpu"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        
    except Exception as e:
        logger.error(f"ボイスエンジンの起動に失敗しました！: {e}")
        voicechat = False

    atexit.register(voice_engine.terminate)
    
async def join_voice(interaction: discord.Interaction, channel: discord.VoiceChannel = None):
    await interaction.response.defer()
    try:
        user = interaction.user
        available_client = None
        connected = False
        for i in range(config.voice_clients):
            checking_voice_client: discord.Client = voice_clients_list[i]
            available = True
            for connected_voice_client in checking_voice_client.voice_clients:
                if connected_voice_client.channel.guild == interaction.guild:
                    available = False
                if connected_voice_client.channel == interaction.user.voice.channel:
                    connected = True
                    break
            
            if available is True:
                available_client = checking_voice_client
                break
            
        if connected is True:
            embed = discord.Embed(title="既にボイスチャンネルに接続しています", description= "既にボイスチャンネルに接続しています。`/leave`で読み上げを終了します。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            return
        
        if available_client is None:
            logger.warning("/joinが実行されましたが使用できるボイスクライアントがありませんでした！")
            embed = discord.Embed(title="利用できるbotがありません！", description= "現在利用できる読み上げbotがありません！\nしゃべるくん(!sh s)など、他の読み上げbotをご利用ください！",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            return
        
        if not user.voice:
            embed = discord.Embed(title="ボイスチャンネルに接続してください", description= "ボイスチャンネルに接続してからコマンドを実行してください。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            return
                
        join_channel = user.voice.channel if not channel else channel
        target_chats = [interaction.channel.id, join_channel.id] if interaction.channel != join_channel else [interaction.channel.id]
        
        await available_client.join_voice_channel(join_channel)
        
        voice_status = voice_client_status()
        voice_status.update({available_client.user.id: {"connected_channel": join_channel.id, "target_chats": target_chats}})
        write_voice_status(voice_status)
        
        target_chat_str = "<#" + ">, <#".join(map(str,target_chats)) + ">"
        
        embed = discord.Embed(title="ボイスチャンネルに接続しました", description= "チャット読み上げを開始します。\n`/leave`で読み上げを終了します。", color = discord.Color.green())
        embed.add_field(name = "接続したチャンネル", value = f"<#{join_channel.id}>")
        embed.add_field(name = "読み上げ対象のチャンネル", value = target_chat_str)
        embed.set_author(name = "チャット読み上げ")
        await interaction.followup.send(embed = embed)
        
    except asyncio.TimeoutError as e:
        logger.error(f"[join]にてエラー{e}")
        embed = discord.Embed(title="ボイスチャンネルに接続出来ませんでした", description= "もう一度お試しください。このエラーが繰り返す場合、Botが落ちている可能性があります。",color = discord.Color.red())
        embed.set_author(name = "チャット読み上げ")
        await interaction.followup.send(embed = embed)

@client.tree.command(name="join", description="【まずこちらを使ってください】利用できる読み上げクライアントを探し、チャット読み上げを開始します")
@discord.app_commands.describe(channel="参加するチャンネル(任意)")
async def join(interaction:  discord.Interaction, channel:  discord.VoiceChannel = None):
    await join_voice(interaction, channel)
        
@client.tree.command(name="leave", description="チャット読み上げ中の場合、それを終了します")
async def leave(interaction:  discord.Interaction):
    await interaction.response.defer()
    try:
        
        if not interaction.user.voice:
            embed = discord.Embed(title="ボイスチャンネルに接続していません", description= "ボイスチャンネルに接続し、`/join`で読み上げを開始します。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            return
        
        connected_client = None
        for i in range(config.voice_clients):
            checking_voice_client: discord.Client = voice_clients_list[i]
            connected = False
            for connected_voice_client in checking_voice_client.voice_clients:
                if connected_voice_client.channel == interaction.user.voice.channel:
                    connected = True
                    break
            
            if connected is True:
                connected_client = connected_voice_client
                break
            
        if connected_client is None:  
                
            embed = discord.Embed(title="こちらで紐づけられた読み上げbotは接続していないようです。", description= "`/join`で読み上げを開始します。\nまた、ロードbot以外の読み上げ機能を利用している場合、そちらの切断コマンドをお試しください。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            return
            
        await connected_client.disconnect()
        await connected_client.client.change_presence(activity=discord.CustomActivity(name="/joinで読み上げを開始します"), status=discord.Status.online)
        
        voice_status = voice_client_status()
        for clientID in voice_status:
            if clientID == str(connected_client.client.user.id):
                del voice_status[clientID]
                break
        
        write_voice_status(voice_status)
        
        embed = discord.Embed(title="読み上げを終了しました", description= "`/join`で読み上げを再開します。",color = discord.Color.green())
        embed.set_author(name = "チャット読み上げ")
        await interaction.followup.send(embed = embed)
    
    except Exception as e:
        logger.error(f"[leave]にてエラー{e}")
        embed = discord.Embed(title="ボイスチャンネルを退出出来ませんでした", description= "もう一度お試しください。このエラーが繰り返す場合、Botが落ちている可能性があります。",color = discord.Color.red())
        embed.set_author(name = "チャット読み上げ")
        await interaction.followup.send(embed = embed)
        
for i in range(config.voice_clients):

    guild_queues = {}
    guild_locks = {}
    guild_playing_flags = {}
    client_voice = voice_clients_list[i]
    
    @client_voice.event
    async def on_ready(client_voice = client_voice):
        logger.info(f"ボイスモジュール[{client_voice.user}]、準備完了です！")
    
    @client_voice.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState, client_voice = client_voice):
        if before.channel and not after.channel:
            if member.guild.voice_client and len(before.channel.members) < 2:
                if member.guild.voice_client.channel == before.channel:
                    await member.guild.voice_client.disconnect()
                    await client_voice.change_presence(activity=discord.CustomActivity(name="/joinで読み上げを開始します"), status=discord.Status.online)
                    voice_status = voice_client_status()
                    for clientID in voice_status:
                        if clientID == str(client_voice.user.id):
                            del voice_status[clientID]
                            break
                    
                    write_voice_status(voice_status)
    
    async def play_next_in_queue(guild: discord.Guild, client_voice = client_voice):
        """
        キューから次のメッセージを取り出して再生する関数。
        一つの音声の再生が終わるたびに after コールバックから呼び出される。
        """
        queue = guild_queues.get(guild.id)
        if not queue or queue.empty():
            guild_playing_flags[guild.id] = False
            return
        
        if guild_playing_flags.get(guild.id, False):
            return
        
        lock = guild_locks.setdefault(guild.id, asyncio.Lock())
        
        async with lock:
            
            if guild_playing_flags.get(guild.id, False):
                return
            
            # キューから次のメッセージを取得
            message = await queue.get()
            guild_playing_flags[guild.id] = True
            
            try:
                # キューの現在のサイズに基づいて再生速度を動的に決定
                queue_size = queue.qsize()
                speedScale = 1.0
                if queue_size > 1:  # キューに2つ以上待機している場合
                    # キューが多いほど少し速くする
                    speedScale = 1.0 + queue_size * 0.1 if queue_size < 10 else 2.0
                
                # TTSを生成（この処理が完了するまで次の再生は始まらない）
                source_path = await text_to_speech(message.content, volumeScale=0.5, speedScale=speedScale, split_count=40)
                if source_path is None:
                    logger.debug(f"音声ファイルの生成をスキップしました。メッセージ内容: {message.content[:40]}")
                    guild_playing_flags[guild.id] = False
                    asyncio.create_task(play_next_in_queue(guild, client_voice))
                    return
                
                source = discord.FFmpegPCMAudio(
                    executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",
                    source=source_path
                )

                # afterコールバックで、再生終了後に再度この関数を呼び出すように設定
                # コールバックは別スレッドで実行されるため、asyncio.run_coroutine_threadsafe を使うのが安全
                def after_playback(e):
                    guild_playing_flags[guild.id] = False
                    asyncio.run_coroutine_threadsafe(
                        play_next_in_queue(guild, client_voice),
                        client_voice.loop
                    )
                
                guild.voice_client.play(
                    source, 
                    after=after_playback
                )

            except Exception as e:
                logger.error(f"Error during playback for guild {guild.id}: {type(e)}:{e}")
                # エラーが発生しても、次のメッセージの再生を試みる
                if "Not connected to voice" in str(e):
                    # 再接続処理
                    try:
                        voice_status = voice_client_status()
                        channel_id = voice_status.get(str(client_voice.user.id), {}).get("connected_channel")
                        if channel_id:
                            channel = client_voice.get_channel(channel_id)
                            if channel:
                                await channel.connect(reconnect=True)
                                logger.info(f"再接続しました: {channel}")
                    except Exception as reconnect_e:
                        logger.error(f"再接続に失敗しました: {reconnect_e}")

                guild_playing_flags[guild.id] = False
                asyncio.run_coroutine_threadsafe(
                    play_next_in_queue(guild, client_voice), 
                    client_voice.loop
                )
            finally:
                # キューのタスクが完了したことを通知
                queue.task_done()    
    
    @client_voice.event
    async def on_message(message: discord.Message, client_voice = client_voice):

        if message.author == client_voice.user or message.author.bot is True:
            return
        if not message.guild or not message.guild.voice_client:
            return

        author = message.author
        username = str(author)  # noqa: F841
        user_message = message.content  # noqa: F841
        channel = message.channel  # noqa: F841
        channelID = message.channel.id
 
        voice_status = voice_client_status()
        try:
            target_channels = voice_status[str(client_voice.user.id)]["target_chats"]
            
        except KeyError:
            logger.error("読み上げクライアントが接続しているのにも関わらず、ボイスステータスが記録されていません！")
            return
        
        if channelID not in target_channels:
            return
        
        guild_id = message.guild.id
        if guild_id not in guild_queues:
            # 新しいギルドのキューを初期化
            guild_queues[guild_id] = asyncio.Queue()
        await guild_queues[guild_id].put(message)
        if not message.guild.voice_client.is_playing():
            await play_next_in_queue(message.guild, client_voice)
                    
    @tasks.loop(time = datetime.time(hour = 4, minute = 50, tzinfo = config.JST))
    async def before_reboot(client_voice = client_voice):
        try:
            #再起動前に接続しているVCに告知する
            voice_status = voice_client_status()
            await client_voice.change_presence(activity=discord.CustomActivity(name="まもなく再起動を行います。朝の5時以降にまたご利用ください。"), status=discord.Status.idle)
            connected_channel_id = None
            for clientID in voice_status:
                if clientID == str(client_voice.user.id):
                    
                    connected_channel_id = voice_status[clientID]["connected_channel"]
                    logger.info(f"再起動のため、読み上げを終了します。チャンネルID: {connected_channel_id}")
                    break
                
            if connected_channel_id is None:
                return
            
            voice_channel = client_voice.get_channel(connected_channel_id)
            while voice_channel.guild.voice_client.is_playing():
                await asyncio.sleep(0.3)
            source = discord.FFmpegPCMAudio(executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",source= await text_to_speech("再起動の為、まもなく読み上げを終了します。朝5時以降にもう一度入れなおして下さい", volumeScale=0.7))
            voice_channel.guild.voice_client.play(source)
            await asyncio.sleep(30)
            await voice_channel.guild.voice_client.disconnect()
            for clientID in voice_status:
                if clientID == str(client_voice.user.id):
                    del voice_status[clientID]
                    break
            write_voice_status(voice_status)
            
        except Exception as e:
            logger.exception(e) 