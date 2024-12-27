import asyncio
import json
import os
import re
import time
import subprocess
import atexit

import discord
import requests

from extentions import config, log
from extentions.aclient import client, voice_clients_list

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "\\..\\")
voice_status_json_name = "jsons\\voice_status.json"

host = "127.0.0.1"
port = "10101"
sleep_time = 0.5

#新しいVCを登録する場合、channels.jsonも忘れずに
#二つ以上の場合、最後がVC_chatが望ましい

def voice_client_status():
    with open(os.path.join(dir, voice_status_json_name), "r", encoding = "utf-8") as f:
        status_dict = json.load(f)
    return status_dict

def write_voice_status(dict):
    with open(os.path.join(dir, voice_status_json_name), "w", encoding = "utf-8") as f:
        json.dump(dict, f, ensure_ascii=False)
    return

async def audio_query(text, speaker, max_retry):
    # 音声合成用のクエリを作成する
    query_payload = {"text": text, "speaker": speaker}
    for query_i in range(max_retry):
        r = requests.post(f"http://{host}:{port}/audio_query", 
                        params=query_payload, timeout=(10.0, 300.0))
        if r.status_code == 200:
            query_data = r.json()
            break
        asyncio.sleep(1)
    else:
        raise ConnectionError("リトライ回数が上限に到達しました。 audio_query : ", "/", text[:40], r.text)
    return query_data

async def synthesis(speaker, query_data, max_retry, intonationScale = 1.0, outputSamplingRate = 44100, outputStereo = False, pauseLength = None, pauseLengthScale = 1.0, pitchScale = 0.0, postPhonemeLength = 0.1, prePhonemeLength = 0.1, speedScale = 1.0, tempoDynamicsScale = 1.0, volumeScale = 1.0):
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
    
    for synth_i in range(max_retry):
        r = requests.post(f"http://{host}:{port}/synthesis", params=synth_payload, 
                          data=json.dumps(query_data), timeout=(10.0, 300.0))
        if r.status_code == 200:
            #音声ファイルを返す
            return r.content
        asyncio.sleep(1)
    else:
        raise ConnectionError("音声エラー：リトライ回数が上限に到達しました。 synthesis : ", r)

async def text_to_speech(texts, speaker=888753760, max_retry=20, intonationScale = 1.0, outputSamplingRate = 44100, outputStereo = False, pauseLength = None, pauseLengthScale = 1.0, pitchScale = 0.0, postPhonemeLength = 0.1, prePhonemeLength = 0.1, speedScale = 1.0, tempoDynamicsScale = 1.0, volumeScale = 1.0):
    if texts is None:
        texts=""
    
    url_pattern = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    texts = re.sub(url_pattern, 'URL省略', texts)
    
    if len(texts) > 40:
        texts = texts[:40] + "以下略"
    
        
    # audio_query
    query_data = await audio_query(texts,speaker,max_retry)
    # synthesis
    voice_data = await synthesis(speaker,query_data,max_retry,intonationScale,outputSamplingRate,outputStereo,pauseLength,pauseLengthScale,pitchScale,postPhonemeLength,prePhonemeLength,speedScale,tempoDynamicsScale,volumeScale)
    filepath = "TTS\\voice.wav"
    with open(os.path.join(dir, filepath), mode = "wb") as f:
        f.write(voice_data)
    return os.path.join(dir, filepath)

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
            embed = discord.Embed(title="利用できるbotがありません！", description= "現在利用できる読み上げbotがありません！\nしゃべるくんなど、他の読み上げbotをご利用ください！",color = discord.Color.red())
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
        voice_status.update({available_client.user.id: {"connected_channel": join_channel.id, "target_chats": target_chats, "queues": 0}})
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

@client.tree.command(name="join", description="利用できる読み上げクライアントを探し、チャット読み上げを開始します")
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
        await connected_client.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="/joinで読み上げを開始します"), status=discord.Status.online)
        
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
    
    @client_voice.event
    async def on_ready(client_voice = client_voice):
        logger.info(f"ボイスモジュール[{client_voice.user}]、準備完了です！")
    
    @client_voice.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState, client_voice = client_voice):
        if before.channel and not after.channel:
            if member.guild.voice_client and len(before.channel.members) < 2:
                if member.guild.voice_client.channel == before.channel:
                    await member.guild.voice_client.disconnect()
                    await client_voice.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="/joinで読み上げを開始します"), status=discord.Status.online)
                    voice_status = voice_client_status()
                    for clientID in voice_status:
                        if clientID == str(client_voice.user.id):
                            del voice_status[clientID]
                            break
                    
                    write_voice_status(voice_status)
    
    @client_voice.event
    async def on_message(message: discord.Message, client_voice = client_voice):

        if message.author == client_voice.user or message.author.bot is True:
            return

        author = message.author
        username = str(author)
        user_message = message.content
        channel = message.channel
        channelID = message.channel.id

        if message.guild:
                            
            if message.guild.voice_client:
                voice_status = voice_client_status()
                try:
                    target_channels = voice_status[str(client_voice.user.id)]["target_chats"]
                    
                except KeyError:
                    logger.error("読み上げクライアントが接続しているのにも関わらず、ボイスステータスが記録されていません！")
                    return
                
                speedScale = 1.0
                    
                if channelID in target_channels:
                    if message.guild.voice_client.is_playing():
                        voice_status[str(client_voice.user.id)]["queues"] += 1
                        write_voice_status(voice_status)
                        if voice_status[str(client_voice.user.id)]["queues"] > 2:
                            speedScale = 1.0 + (voice_status[str(client_voice.user.id)]["queues"] - 1) * 0.1
                    while message.guild.voice_client.is_playing():
                        await asyncio.sleep(0.3)
                    source = discord.FFmpegPCMAudio(executable="C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",source= await text_to_speech(message.content, volumeScale=0.7, speedScale=speedScale))
                    message.guild.voice_client.play(source)
                    voice_status[str(client_voice.user.id)]["queues"] -= 1
                    write_voice_status(voice_status)