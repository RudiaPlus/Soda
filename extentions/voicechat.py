import asyncio
import atexit
import datetime
import json
import os
import re
import subprocess

import aiohttp
import discord
from discord.errors import ClientException
from discord.ext import tasks

from extentions import log
from extentions.aclient import client, voice_clients_list
from extentions.config import config

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
    with open(os.path.join(dir, voice_status_json_name), "r", encoding="utf-8") as f:
        return json.load(f)

def write_voice_status(d: dict):
    # normalize keys to str to avoid int/str mismatch
    normalized = {str(k): v for k, v in d.items()}
    with open(os.path.join(dir, voice_status_json_name), "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=4)
    return

def split_to_moras(kana: str) -> list[str]:
    # 小書きゃゅょァィゥェォャュョッー等を前の仮名に連結
    small = set("ァィゥェォャュョヮぁぃぅぇぉゃゅょゎッっー")
    moras = []
    for ch in kana:
        if moras and (ch in small or ch == "ー"):
            moras[-1] += ch
        else:
            moras.append(ch)
    return moras

def accent_from_marked_pron(pron: str) -> tuple[str, int|None]:
    # 例: まっけ'んゆう -> ("まっけんゆう", 3)
    if "'" not in pron:
        return pron.replace("'", ""), None
    plain = pron.replace("'", "")
    left, _, right = pron.partition("'")
    moras = split_to_moras(plain)
    # マーク位置のモーラ index を数える
    idx = len(split_to_moras(left))
    # 下がる直前のモーラを 1-indexed で指定
    accent_type = idx
    return plain, accent_type

def guess_accent_type(pron: str) -> int:
    # 超簡易: 平板を既定、長語は中高寄り
    n = len(split_to_moras(pron))
    if n <= 2:
        return 1  # 短語は頭高が無難なことが多い
    if n >= 5:
        return max(2, min(n-1, round(n/2)))
    return 0  # 平板

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
    
async def user_word_exists(surface: str, max_retry: int = 3) -> bool:
    async with aiohttp.ClientSession() as session:
        user_dict = await get_user_dict(session, max_retry)
        for uid in user_dict:
            try:
                if user_dict[uid]["surface"] == surface:
                    return True
            except Exception:
                continue
    return False

# ===== ユーザー辞書操作コマンド =====
@client.tree.command(name="dict_add", description="TTS辞書に単語を追加（存在時は更新）します")
@discord.app_commands.describe(surface="登録する単語の表記", yomi="読み（カタカナ）", accent="アクセント核の位置（0=平板）")
async def dict_add(interaction: discord.Interaction, surface: str, yomi: str, accent: int = 0):
    await interaction.response.defer()
    try:
        # 既存確認 → 既存なら編集、無ければ追加
        exists = await user_word_exists(surface)
        ok = await (edit_user_word(surface, yomi, accent) if exists else add_user_word(surface, yomi, accent))
        if ok:
            action = "更新" if exists else "追加"
            embed = discord.Embed(title=f"ユーザー辞書に{action}しました", description=f"{surface} / {yomi} / accent={accent}", color=discord.Color.green())
        else:
            action = "更新" if exists else "追加"
            embed = discord.Embed(title=f"ユーザー辞書の{action}に失敗しました", description=f"{surface} / {yomi} / accent={accent}", color=discord.Color.red())
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"[dict_add] error: {e}")
        embed = discord.Embed(title="ユーザー辞書の登録に失敗しました", description=str(e), color=discord.Color.red())
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)
        
@client.tree.command(name="dict_delete", description="TTS辞書から単語を削除します")
@discord.app_commands.describe(surface="削除する単語の表記")
async def dict_delete(interaction: discord.Interaction, surface: str):
    await interaction.response.defer()
    try:
        ok = await delete_user_word(surface)
        if ok:
            embed = discord.Embed(title="ユーザー辞書から削除しました", description=surface, color=discord.Color.green())
        else:
            embed = discord.Embed(title="ユーザー辞書の削除に失敗しました", description=surface, color=discord.Color.red())
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"[dict_delete] error: {e}")
        embed = discord.Embed(title="ユーザー辞書の削除に失敗しました", description=str(e), color=discord.Color.red())
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)

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

        # 先にVC接続の有無を確認
        if not user.voice:
            embed = discord.Embed(title="ボイスチャンネルに接続してください", description="ボイスチャンネルに接続してからコマンドを実行してください。", color=discord.Color.red())
            embed.set_author(name="チャット読み上げ")
            await interaction.followup.send(embed=embed)
            return

        join_channel = user.voice.channel if not channel else channel

        # すでに同一のVCに接続中かチェック（いずれかの読み上げクライアント）
        for checking_voice_client in voice_clients_list:
            if any(vc.channel == join_channel for vc in checking_voice_client.voice_clients):
                embed = discord.Embed(title="既にボイスチャンネルに接続しています", description="既にこのボイスチャンネルに接続しています。`/leave`で読み上げを終了します。", color=discord.Color.red())
                embed.set_author(name="チャット読み上げ")
                await interaction.followup.send(embed=embed)
                return

        # 読み上げ対象テキストチャンネルの重複チェック
        # 同じテキストチャンネルを複数クライアントが担当しないようにする
        for _, status in voice_client_status().items():
            if interaction.channel.id in status.get("target_chats", []):
                embed = discord.Embed(
                    title="このテキストチャンネルは既に読み上げ中です",
                    description="`/leave`で一度終了してから、もう一度お試しください。",
                    color=discord.Color.red(),
                )
                embed.set_author(name="チャット読み上げ")
                await interaction.followup.send(embed=embed)
                return

        # 利用可能な読み上げクライアントを探す（どこにも接続していないものを優先）
        available_client = next((vc for vc in voice_clients_list if not vc.voice_clients), None)

        if available_client is None:
            logger.warning("/joinが実行されましたが使用できるボイスクライアントがありませんでした！")
            embed = discord.Embed(title="利用できるbotがありません！", description="現在利用できる読み上げbotがありません！\nしゃべるくん(!sh s)など、他の読み上げbotをご利用ください！", color=discord.Color.red())
            embed.set_author(name="チャット読み上げ")
            await interaction.followup.send(embed=embed)
            return

        # 読み上げ対象は「コマンド実行テキストチャンネル」＋「VCのテキストチャット(同一ID)」
        target_chats = [interaction.channel.id, join_channel.id] if interaction.channel.id != join_channel.id else [interaction.channel.id]

        await available_client.join_voice_channel(join_channel)
        # 記憶しておく（voice_status が消されていても再接続可能にするため）
        try:
            if not hasattr(available_client, "guild_connected_channels"):
                available_client.guild_connected_channels = {}
            available_client.guild_connected_channels[join_channel.guild.id] = join_channel.id
        except Exception:
            pass

        voice_status = voice_client_status()
        voice_status.update({str(available_client.user.id): {"connected_channel": join_channel.id, "target_chats": target_chats}})
        write_voice_status(voice_status)

        target_chat_str = "<#" + ">, <#".join(map(str, target_chats)) + ">"

        embed = discord.Embed(title="ボイスチャンネルに接続しました", description="チャット読み上げを開始します。\n`/leave`で読み上げを終了します。", color=discord.Color.green())
        embed.add_field(name="接続したチャンネル", value=f"<#{join_channel.id}>")
        embed.add_field(name="読み上げ対象のチャンネル", value=target_chat_str)
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)

    except asyncio.TimeoutError as e:
        logger.error(f"[join]にてエラー{e}")
        embed = discord.Embed(title="ボイスチャンネルに接続出来ませんでした", description="もう一度お試しください。このエラーが繰り返す場合、Botが落ちている可能性があります。", color=discord.Color.red())
        embed.set_author(name="チャット読み上げ")
        await interaction.followup.send(embed=embed)

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

    client_voice = voice_clients_list[i]
    # per-voice-client state containers
    client_voice.guild_queues = {}
    client_voice.guild_locks = {}
    client_voice.guild_playing_flags = {}
    client_voice.guild_connected_channels = {}
    
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
                    # also clear in-memory connected channel so we don't auto-reconnect unintentionally
                    try:
                        if before.channel.guild.id in client_voice.guild_connected_channels:
                            del client_voice.guild_connected_channels[before.channel.guild.id]
                    except Exception:
                        pass
    
    async def play_next_in_queue(guild: discord.Guild, client_voice = client_voice, vc: discord.VoiceClient | None = None):
        """
        キューから次のメッセージを取り出して再生する関数。
        一つの音声の再生が終わるたびに after コールバックから呼び出される。
        """
        queue = client_voice.guild_queues.setdefault(guild.id, asyncio.Queue())
        
        if client_voice.guild_playing_flags.get(guild.id, False):
            logger.debug(f"[voice:{client_voice.user.id}] already playing for guild {guild.id}")
            return
        
        lock = client_voice.guild_locks.setdefault(guild.id, asyncio.Lock())
        
        async with lock:
            
            if client_voice.guild_playing_flags.get(guild.id, False):
                logger.debug(f"[voice:{client_voice.user.id}] playing flag set; skip start for guild {guild.id}")
                return
            
            # キューから次のメッセージを取得（空なら到着まで待つ）
            logger.debug(f"[voice:{client_voice.user.id}] waiting for message; qsize={queue.qsize()}")
            message = await queue.get()
            logger.debug(f"[voice:{client_voice.user.id}] dequeued message; remaining qsize={queue.qsize()}")
            client_voice.guild_playing_flags[guild.id] = True
            
            try:
                # ボイスクライアントを特定（このクライアントが当該ギルドで接続しているもの）
                if vc is None:
                    for _vc in client_voice.voice_clients:
                        if _vc.guild.id == guild.id:
                            vc = _vc
                            break
                if vc is None:
                    logger.debug(f"[voice:{client_voice.user.id}] vc not found for guild {guild.id}")
                    client_voice.guild_playing_flags[guild.id] = False
                    return

                # 接続が切れている場合は必要に応じて再接続
                if not vc.is_connected():
                    # 再接続先を決める: 優先はメモリ -> voice_status.json
                    channel_id = client_voice.guild_connected_channels.get(guild.id)
                    if not channel_id:
                        vs = voice_client_status()
                        channel_id = vs.get(str(client_voice.user.id), {}).get("connected_channel")
                    if channel_id:
                        channel = client_voice.get_channel(channel_id)
                        if channel:
                            try:
                                await client_voice.join_voice_channel(channel)
                                client_voice.guild_connected_channels[guild.id] = channel_id
                                logger.info(f"[voice:{client_voice.user.id}] 自動再接続: {channel.name}")
                                # 再取得
                                for _vc in client_voice.voice_clients:
                                    if _vc.guild.id == guild.id:
                                        vc = _vc
                                        break
                            except Exception as reconnect_e:
                                logger.error(f"[voice:{client_voice.user.id}] 再接続に失敗: {reconnect_e}")
                                client_voice.guild_playing_flags[guild.id] = False
                                return
                    else:
                        logger.debug(f"[voice:{client_voice.user.id}] not connected and no reconnect info; skip playback")
                        client_voice.guild_playing_flags[guild.id] = False
                        return
                # キューの現在のサイズに基づいて再生速度を動的に決定
                queue_size = queue.qsize()
                speedScale = 1.0
                if queue_size > 1:  # キューに2つ以上待機している場合
                    # キューが多いほど少し速くする
                    speedScale = 1.0 + queue_size * 0.1 if queue_size < 10 else 2.0
                
                # TTSを生成（この処理が完了するまで次の再生は始まらない）
                logger.debug(f"[voice:{client_voice.user.id}] synthesize start; speedScale={speedScale}")
                source_path = await text_to_speech(message.content, volumeScale=0.5, speedScale=speedScale, split_count=40)
                if source_path is None:
                    logger.debug(f"音声ファイルの生成をスキップしました。メッセージ内容: {message.content[:40]}")
                    client_voice.guild_playing_flags[guild.id] = False
                    asyncio.create_task(play_next_in_queue(guild, client_voice))
                    return
                
                source = discord.FFmpegPCMAudio(
                    executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",
                    source=source_path
                )

                def after_playback(e):
                    client_voice.guild_playing_flags[guild.id] = False
                    asyncio.run_coroutine_threadsafe(
                        play_next_in_queue(guild, client_voice, vc=vc),
                        client_voice.loop
                    )
                
                logger.debug(f"[voice:{client_voice.user.id}] playback start")
                vc.play(
                    source, 
                    after=after_playback
                )

            except Exception as e:
                logger.error(f"Error during playback for guild {guild.id}: {type(e)}:{e}")
                # エラーが発生しても、次のメッセージの再生を試みる
                if "Not connected to voice" in str(e):
                    # 再接続処理を試みる（メモリ > voice_status）
                    try:
                        channel_id = client_voice.guild_connected_channels.get(guild.id)
                        if not channel_id:
                            voice_status = voice_client_status()
                            channel_id = voice_status.get(str(client_voice.user.id), {}).get("connected_channel")
                        if channel_id:
                            channel = client_voice.get_channel(channel_id)
                            if channel:
                                await client_voice.join_voice_channel(channel)
                                client_voice.guild_connected_channels[guild.id] = channel_id
                                logger.info(f"[voice:{client_voice.user.id}] 自動再接続しました: {channel.name}")
                    except Exception as reconnect_e:
                        logger.error(f"[voice:{client_voice.user.id}] 再接続に失敗しました: {reconnect_e}")

                client_voice.guild_playing_flags[guild.id] = False
                asyncio.run_coroutine_threadsafe(
                    play_next_in_queue(guild, client_voice, vc=vc), 
                    client_voice.loop
                )
            finally:
                # キューのタスクが完了したことを通知
                queue.task_done()    
    
    @client_voice.event
    async def on_message(message: discord.Message, client_voice = client_voice):

        if message.author == client_voice.user or message.author.bot is True:
            logger.debug(f"[voice:{client_voice.user.id}] ignore bot/self message in {getattr(message.channel, 'id', 'N/A')}")
            return
        if not message.guild:
            logger.debug(f"[voice:{client_voice.user.id}] ignore DM message")
            return
        # このクライアント自身が当該ギルドで接続しているか判定
        vc = None
        for _vc in client_voice.voice_clients:
            if _vc.guild.id == message.guild.id:
                vc = _vc
                break
        if vc is None:
            return

        channelID = message.channel.id
        parent_id = getattr(message.channel, "parent_id", None)

        target_channels = None
        
        # 自分の担当チャンネルを取得
        my_status = voice_client_status().get(str(client_voice.user.id))
        if my_status:
            target_channels = my_status.get("target_chats", [])

        # 他のクライアントが担当しているチャンネルか確認
        for other_client_id, status in voice_client_status().items():
            if other_client_id != str(client_voice.user.id) and (channelID in status.get("target_chats", []) or (parent_id and parent_id in status.get("target_chats", []))):
                logger.debug(f"[voice:{client_voice.user.id}] channel {channelID} is owned by other client {other_client_id}")
                return

        if target_channels is None:
            logger.error("読み上げクライアントが接続しているのにも関わらず、ボイスステータスが記録されていません！")
            return

        is_target = channelID in target_channels or (parent_id and parent_id in target_channels)
        if not is_target:
            logger.debug(f"[voice:{client_voice.user.id}] channel {channelID} (parent {parent_id}) not in targets {target_channels}")
            return
        
        guild_id = message.guild.id
        if guild_id not in client_voice.guild_queues:
            # 新しいギルドのキューを初期化
            client_voice.guild_queues[guild_id] = asyncio.Queue()
        await client_voice.guild_queues[guild_id].put(message)
        logger.debug(f"[voice:{client_voice.user.id}] enqueued message from channel {channelID} (parent {parent_id}); qsize={client_voice.guild_queues[guild_id].qsize()}")
        # 再生が始まっていない場合やフラグが立っていない場合に起動
        if not client_voice.guild_playing_flags.get(guild_id, False) or not vc.is_playing():
            logger.debug(f"[voice:{client_voice.user.id}] start playback trigger; guild={message.guild.id}")
            await play_next_in_queue(message.guild, client_voice, vc=vc)
                    
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
