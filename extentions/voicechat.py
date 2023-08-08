import discord
import json
import asyncio
from extentions import log, config, JSTTime
from extentions.aclient import client
import os

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "\\..\\")
voice_name = "voiceroid\\VOICEROID2"
channel_json_path = "jsons\\channels.json"

print(os.path.join(dir, voice_name))

with open(os.path.join(dir, channel_json_path), encoding="UTF-8") as f:
    channels = json.load(f)

channel_register = {
    "ak1_vc": ["ak1_vc", "ak1_vc_chat"],
    "ak2_vc": ["ak2_vc", "ak2_vc_chat"],
    "spoiler_vc": ["spoiler_vc", "spoiler_vc_chat"],
    "general1_vc": ["general1_vc", "general1_vc_chat"],
    "general2_vc": ["general2_vc", "general2_vc_chat"],
}

def speak(text: str):
     
    """with pyvcroid2.VcRoid2(install_path = os.path.join(dir, voice_name)) as voice:
        # Load language library
        lang_list = voice.listLanguages()
        if "standard" in lang_list:
            voice.loadLanguage("standard")
        elif 0 < len(lang_list):
            voice.loadLanguage(lang_list[0])
        else:
            raise Exception("No language library")

        # Load Voice
        voice_list = voice.listVoices()
        if 0 < len(voice_list):
            voice.loadVoice(voice_list[0])
        else:
            raise Exception("No voice library")
        
        # Set parameters
        voice.param.volume = 1.00
        voice.param.speed = 1.2
        voice.param.pitch = 1.1
        voice.param.emphasis = 0.95
        voice.param.pauseMiddle = 80
        voice.param.pauseLong = 100
        voice.param.pauseSentence = 100
        voice.param.masterVolume = 1.123
        
        filepath = "voiceroid\\"
        filename = "voice.wav"
        file = filepath + filename
        speech, tts_events = voice.textToSpeech(text)
    
        with open(file, mode = "wb") as f:
            f.write(speech)
        return f"{filepath}voice.wav"""

async def channels_write(dic):
    with open(os.path.join(dir, channel_json_path), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"channels.jsonに新しく書き込みを行いました")

async def get_target_channels(vc_channel) -> list:
    for index in channels:
        if channels[index]["id"] == vc_channel.id:
            target_chat = channel_register[index]
            id_ = "id"
            target_chat_id = [channels[d][id_] for d in target_chat]
            return(target_chat_id)

"""       
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
        await interaction.followup.send(embed = embed)"""