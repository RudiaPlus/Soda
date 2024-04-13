import discord
import json
import asyncio
from extentions import log, config, JSTTime
from extentions.aclient import client
import os
import requests
import time
import re

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "\\..\\")
channel_json_path = "jsons\\channels.json"

host = "127.0.0.1"
port = "50021"
sleep_time = 0.5

with open(os.path.join(dir, channel_json_path), encoding="UTF-8") as f:
    channels = json.load(f)

#新しいVCを登録する場合、channels.jsonも忘れずに
#二つ以上の場合、最後がVC_chatが望ましい
channel_register = {
    "ak1_vc": ["ak1_vc", "ak1_vc_chat"],
    "ak2_vc": ["ak2_vc", "ak2_vc_chat"],
    "spoiler_vc": ["spoiler_vc", "spoiler_vc_chat"],
    "general1_vc": ["general1_vc", "general1_vc_chat"],
    "general2_vc": ["general2_vc", "general2_vc_chat"],
    "moderator_vc": ["moderator_vc"]
}

def audio_query(text, speaker, max_retry):
    # 音声合成用のクエリを作成する
    query_payload = {"text": text, "speaker": speaker}
    for query_i in range(max_retry):
        r = requests.post(f"http://{host}:{port}/audio_query", 
                        params=query_payload, timeout=(10.0, 300.0))
        if r.status_code == 200:
            query_data = r.json()
            break
        time.sleep(1)
    else:
        raise ConnectionError("リトライ回数が上限に到達しました。 audio_query : ", "/", text[:30], r.text)
    return query_data
def synthesis(speaker, query_data,max_retry):
    synth_payload = {"speaker": speaker}
    for synth_i in range(max_retry):
        r = requests.post(f"http://{host}:{port}/synthesis", params=synth_payload, 
                          data=json.dumps(query_data), timeout=(10.0, 300.0))
        if r.status_code == 200:
            #音声ファイルを返す
            return r.content
        time.sleep(1)
    else:
        raise ConnectionError("音声エラー：リトライ回数が上限に到達しました。 synthesis : ", r)

def text_to_speech(texts, speaker=8, max_retry=20):
    if texts==False:
        texts=""
    texts=re.split("(?<=！|。|？)",texts)
    for i, text in enumerate(texts):
        # audio_query
        query_data = audio_query(text,speaker,max_retry)
        # synthesis
        voice_data=synthesis(speaker,query_data,max_retry)
        filepath = "TTS\\voice.wav"
        with open(os.path.join(dir, filepath), mode = "wb") as f:
            f.write(voice_data)
        return os.path.join(dir, filepath)
        

async def channels_write(dic):
    with open(os.path.join(dir, channel_json_path), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"channels.jsonに新しく書き込みを行いました")

async def get_target_channels(vc_channel) -> list:
    for index in channels:
        if channels[index]["id"] == vc_channel.id:
            try:
                target_chat = channel_register[index]
            except KeyError:
                logger.warn(f"{index}は登録されていません。")
                return
            id_ = "id"
            target_chat_id = [channels[d][id_] for d in target_chat]
            return(target_chat_id)

if config.voicechat == True:     
    @client.tree.command(name="join", description="チャット読み上げを開始します")
    @discord.app_commands.describe(channel="参加するチャンネル(任意)")
    async def join(interaction:  discord.Interaction, channel:  discord.VoiceChannel = None):
        await interaction.response.defer()
        try:
            user = interaction.user
            if not interaction.guild.voice_client:
                if user.voice or channel:
                    
                    join_channel = user.voice.channel if not channel else channel
                    
                    for index in channels.values():
                        
                        if index["id"] == join_channel.id and index["type"] == "vc":
                            
                            await join_channel.connect(timeout = 5, self_deaf = True)
                            
                            target_chat_id = await get_target_channels(join_channel)
                            
                            target_chat_str = "<#" + ">, <#".join(map(str,target_chat_id)) + ">"
                            
                            embed = discord.Embed(title="ボイスチャンネルに接続しました", description= f"チャット読み上げを開始します。\n`/leave`で読み上げを終了します。", color = discord.Color.green())
                            embed.add_field(name = "接続したチャンネル", value = f"<#{join_channel.id}>")
                            embed.add_field(name = "読み上げ対象のチャンネル", value = target_chat_str)
                            embed.set_author(name = "チャット読み上げ")
                            await interaction.followup.send(embed = embed)
                            
                            return    
                            
                    embed = discord.Embed(title="このボイスチャンネルは登録されていません", description= "別のボイスチャンネルに参加してください。",color = discord.Color.red())
                    embed.set_author(name = "チャット読み上げ")
                    await interaction.followup.send(embed = embed)
                            
                    
                else:
                    
                    embed = discord.Embed(title="ボイスチャンネルに接続してください", description= "ボイスチャンネルに接続するか、チャンネルを指定してください。",color = discord.Color.red())
                    embed.set_author(name = "チャット読み上げ")
                    await interaction.followup.send(embed = embed)
            else:
                
                embed = discord.Embed(title="既にチャット読み上げ中です", description= "`/leave`でチャット読み上げを中止します。",color = discord.Color.red())
                embed.set_author(name = "チャット読み上げ")
                await interaction.followup.send(embed = embed)
        
        except asyncio.TimeoutError as e:
            logger.error(f"[join]にてエラー{e}")
            embed = discord.Embed(title="ボイスチャンネルに接続出来ませんでした", description= "もう一度お試しください。このエラーが繰り返す場合、Botが落ちている可能性があります。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)
            
    @client.tree.command(name="leave", description="チャット読み上げを終了します")
    async def leave(interaction:  discord.Interaction):
        await interaction.response.defer()
        try:
            if interaction.guild.voice_client:
                
                await interaction.guild.voice_client.disconnect()
                embed = discord.Embed(title="読み上げを終了しました", description= "`/join`で読み上げを再開します。",color = discord.Color.green())
                embed.set_author(name = "チャット読み上げ")
                await interaction.followup.send(embed = embed)
                
            else:
                
                embed = discord.Embed(title="ボイスチャンネルに接続していません", description= "`/join`で読み上げを開始します。",color = discord.Color.red())
                embed.set_author(name = "チャット読み上げ")
                await interaction.followup.send(embed = embed)
        
        except Exception as e:
            logger.error(f"[leave]にてエラー{e}")
            embed = discord.Embed(title="ボイスチャンネルを退出出来ませんでした", description= "もう一度お試しください。このエラーが繰り返す場合、Botが落ちている可能性があります。",color = discord.Color.red())
            embed.set_author(name = "チャット読み上げ")
            await interaction.followup.send(embed = embed)