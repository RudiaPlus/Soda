import discord

from extentions import config, log
from extentions.aclient import client

logger = log.setup_logger()

class MultiCreateButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = None)

@client.tree.command(name = "vccreate", guild = discord.Object(config.testserverid))
async def vccreate(interaction: discord.Interaction, channel: str = str(config.voicecreate_channel), edit_message: str = None):
    await interaction.response.defer()
    if channel and not channel.isdecimal():
        await interaction.followup.send(f"channel({channel})の型が不正です！")
    else:
        channel = int(channel)
    if edit_message and not edit_message.isdecimal():
        await interaction.followup.send(f"edit_message({edit_message})の型が不正です！")
    elif edit_message:
        edit_message = int(edit_message)
    
    vccreate_voice = client.get_channel(config.voicecreate_vc)
    channel_get = client.get_channel(channel)

    embed = discord.Embed(color = discord.Color.green(), title = "ボイスチャット作成", description=f"用途に沿った臨時ボイスチャットを作成します！\n{vccreate_voice.jump_url} を押すと**自動的に**ボイスチャットが作成されます！")
    embed.add_field(name = "名前の変え方", value = "作成されたボイスチャットから、「⚙️チャンネルの編集」→「チャンネル名」の欄に好きな名前を入力してください！\nオススメ: 今の状況や来て欲しい人など 例:「危機契約620点挑戦中」、「作業通話 誰でも来て下さい！」", inline = False)
    embed.add_field(name = "最大人数の設定", value = "「⚙️チャンネルの編集」→「ユーザー人数制限」のスライダーを動かすことで、ボイスチャットに接続できる最大人数を設定できます。数人用のゲームで遊ぶときにおススメです！", inline = False)
    embed.add_field(name = "聞き専チャット、読み上げについて", value = "聞き専チャットは作成されたボイスチャットの「💬チャットを開く」ボタンから開けます。\nまた、現在読み上げbotの数が限られているので、読み上げbotを使用することは**推奨されません**。ご協力をお願いします。", inline = False)
    
    if edit_message:
        message = await channel_get.fetch_message(edit_message)
        await message.edit(embed = embed)
        await interaction.followup.send("送信しました！")
    else:
        await channel_get.send(embed = embed)
        await interaction.followup.send("送信しました！")
        
        