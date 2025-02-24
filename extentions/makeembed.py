import discord
from unicodedata import normalize
import json
import os
from extentions.aclient import client
from extentions import config, log

logger = log.setup_logger()
dir = os.path.abspath(os.path.dirname(__file__))
embeds_dir = os.path.join(dir, "embeds")

def load_embed_json(file_name: str) -> dict:
    with open(os.path.join(embeds_dir, file_name), "r", encoding="utf-8") as f:
        return json.load(f)

def write_embed_json(file_name: str, data: dict) -> None:
    with open(os.path.join(embeds_dir, file_name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
async def send_embed_to_channel(channel: discord.TextChannel, file_name: str, edit_id: int = None) -> None:
    embeds = []
    for embed in load_embed_json(file_name):
        embeds.append(discord.Embed.from_dict(embed))
    if not edit_id:
        await channel.send(embeds=embeds)
    else:
        message = await channel.fetch_message(edit_id)
        await message.edit(embeds=embeds)
    
@client.tree.command(name="send_embed", description="filenameから埋め込みを送信します" ,guild=discord.Object(config.testserverid))
@discord.app_commands.describe(filename = "ファイル名", channel_id = "送信するチャンネルID", edit_id = "編集するメッセージID")
async def send_embed(interaction: discord.Interaction, filename: str, channel_id: str = None, edit_id: str = None) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        channel_id = normalize("NFKC", channel_id) if channel_id else None
        edit_id = normalize("NFKC", edit_id) if edit_id else None
    except TypeError:
        await interaction.followup.send("不正な値が渡されました")
        return
    if not os.path.exists(os.path.join(embeds_dir, filename)):
        await interaction.followup.send("ファイルが存在しません")
        return
    
    if channel_id:
        channel = client.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send("チャンネルが見つかりません")
            return
        await send_embed_to_channel(channel, filename, edit_id=edit_id)
        
    else:
        await send_embed_to_channel(interaction.channel, filename, edit_id=edit_id)