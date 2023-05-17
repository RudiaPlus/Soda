import discord
from discord.ext import tasks
import json
import time
import os
from extentions import log, config, JSTTime
from extentions.aclient import client
from typing import List

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")
modmail_json_path = "jsons/modmail.txt"

class ModmailButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="開始する", custom_id = "modmailbutton", style=discord.ButtonStyle.success, emoji="✅")
    async def modmailbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        result = await create_modmail(user = interaction.user)
        
        embed = discord.Embed(title="あしたはこぶね・お問い合わせ", description="お問い合わせありがとうございます！\nこのDMにメッセージを送ることで、スタッフとの会話を開始できます\nお問い合わせを終了する場合は、下の「終了」ボタンを押してください。", color=0x696969)
        embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
        
        if result == "created":
            if interaction.message.guild:
                await interaction.user.send(embed=embed, view=ModmailFinish())
                await interaction.response.send_message("DMをお送りしました。ご確認ください！", ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=ModmailFinish())
                
        if result == "duplicated":
            await interaction.response.send_message("DMを既にお送りしております。ご確認ください！", ephemeral=True)    
            
               

class ModmailFinish(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "終了", custom_id = "modmailfinish", emoji = "🔒")
    async def modmailfinish(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild = client.get_guild(config.main_server)
        
        if not interaction.guild:
            
            target = "member"
            mod_channel = await fetch_mod_channel(guild=guild, user=interaction.user)
            user = interaction.user
            userID = user.id
            
        else:
            
            target = "mod"
            mod_channel = interaction.channel
            idx = mod_channel.name.find("-") + 1
            userID = int(mod_channel.name[idx:])
            user = await client.fetch_user(userID)
        
        if mod_channel is None:
            await interaction.response.send_message(content = "既に終了しています！")
            return
            
        if mod_channel.name == f"mail-{userID}":
                
            embed = discord.Embed(title = "お問い合わせが終了しました", description = "お問い合わせ頂き、ありがとうございました！\nなお、スタッフの判断によってお問い合わせが再開され、スタッフからの返信が来る場合があります。", color=0x696969)
            embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
            embed_mod = discord.Embed(title = "ModMailが終了しました", description = f"ModMailは{interaction.user.mention}によって終了しました。")
            
            if target == "member":
                await interaction.response.send_message(embed = embed)
                await mod_channel.send(embed = embed_mod)
                
            else:
                await user.send(embed = embed)
                await interaction.response.send_message(embed = embed_mod)
            
            Administrator = guild.get_role(config.administrator_role)
            Moderator = guild.get_role(config.Moderator_role)
            
            closed_overwrite = {
                guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True, manage_channels = True),
                guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
                Administrator: discord.PermissionOverwrite(read_messages = True, send_messages = True),
                Moderator: discord.PermissionOverwrite(read_messages = True, send_messages = False)
            }
            
            await mod_channel.edit(name = f"closed-{interaction.user.id}", overwrites = closed_overwrite)
            
            embed_control = discord.Embed(description = "スタッフのコントロールはこちら")
            await mod_channel.send(embed = embed_control, view = ModmailControl())
        
        else:
            await interaction.response.send_message(content = "お問い合わせは既に終了しています。", ephemeral = True)
        
        
        
class ModmailControl(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "再開", custom_id = "modmailresume", emoji = "🔓")
    async def modmailresume(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild = client.get_guild(config.main_server)
        Administrator = guild.get_role(config.administrator_role)
        Moderator = interaction.guild.get_role(config.Moderator_role)
        
        reopen_overwrite = {
                guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True, manage_channels = True),
                guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
                Administrator: discord.PermissionOverwrite(read_messages = True, send_messages = True),
                Moderator: discord.PermissionOverwrite(read_messages = True, send_messages = True)
        }
        
        mod_channel = interaction.channel
        idx = mod_channel.name.find("-") + 1
        userID = int(mod_channel.name[idx:])
        user = await client.fetch_user(userID)
        
        if mod_channel.name == f"closed-{userID}":
        
            await mod_channel.edit(name = f"mail-{userID}", overwrites = reopen_overwrite)
            
            embed = discord.Embed(title = "お問い合わせが再開されました", description = f"{user.name}さんのお問い合わせが再開されました。スタッフからの返信が来る場合があります。", color=0x696969)
            embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
            await user.send(embed = embed)
            
            embed_mod = discord.Embed(description = "ModMailが再開されました", color=0x696969)
            await interaction.response.send_message(embed = embed_mod)
            
        else:
            await interaction.response.send_message(content = "ModMailは現在終了していません。", ephemeral = True)
            
    @discord.ui.button(label = "削除", custom_id = "modmaildelete", emoji = "🚫")
    async def modmaildelete(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        mod_channel = interaction.channel
        idx = mod_channel.name.find("-") + 1
        userID = int(mod_channel.name[idx:])
        
        if mod_channel.name == f"closed-{userID}":
            
            embed = discord.Embed(description = "このチャンネルは数秒後に削除されます。")
            await interaction.response.send_message(embed = embed)
            await save_modmail(channel = interaction.channel, delete_user = interaction.user)
            await interaction.channel.delete()
            
        else:
            await interaction.response.send_message(content = "ModMailは現在終了していません。", ephemeral = True)
        

async def fetch_mod_channel(guild: discord.Guild, user: discord.User) -> discord.TextChannel:
    channels = guild.channels
    mod_channel = discord.utils.get(channels, name = f"mail-{user.id}")
    return(mod_channel)

async def create_modmail(user: discord.User):

    guild = client.get_guild(config.main_server)
    mod_channel = await fetch_mod_channel(guild=guild, user=user)
    
    if mod_channel is None:
    
        categoty = discord.utils.get(guild.categories, name = "────フィードバック────")
        Administrator = guild.get_role(config.administrator_role)
        Moderator = guild.get_role(config.Moderator_role)
        
        role_overwrite = {
                guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True, manage_channels = True),
                guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
                Administrator: discord.PermissionOverwrite(read_messages = True, send_messages = True),
                Moderator: discord.PermissionOverwrite(read_messages = True, send_messages = True)
        }
        mod_channel = await guild.create_text_channel(f"mail-{user.id}", category = categoty, overwrites = role_overwrite, reason = f"ModMailが開始されました:{user.id}")
        
        embed_mod = discord.Embed(title="Modmailが開始されました！", description=f"ニックネーム : {user.display_name}\nid : {user.id}\nアカウント作成日 : {user.created_at}", color=user.accent_color)
        embed_mod.set_author(name=user.name, icon_url=user.avatar.url)
        
        await mod_channel.send(embed=embed_mod, view = ModmailFinish())
        
        return("created")
        
    else:
        return("duplicated")
        
async def save_modmail(channel: discord.TextChannel, delete_user: discord.User):
    
    idx = channel.name.find("-") + 1
    userID = int(channel.name[idx:])
    user = await client.fetch_user(userID)
    
    messages = []
    users = {}
    
    async for message in channel.history(oldest_first = True):
        author = str(message.author)
        content = message.content
        
        if message.author != client.user:
            
            if author in users:
                
                users[author] += 1
                
            else:
                users[author] = 1 
                
        else:
            content = message.embeds[0].description
            if message.embeds[0].author.name is not None:
                author = message.embeds[0].author.name
                
                if author in users:
                
                    users[author] += 1
                
                else:
                    users[author] = 1 
        
        user_message = {author: content}
        messages.append(user_message)
        
    with open(os.path.join(dir, modmail_json_path), mode = "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    
    with open(os.path.join(dir, modmail_json_path), mode = "r", encoding="utf-8") as f:
        messages_json = discord.File(fp = f, filename = "messages.txt")
    
    speakers = ""
    
    for index in users:
        speakers += f"{users[index]} - {index}\n"
    
    embed = discord.Embed(color = discord.Color.green())
    embed.set_author(name = str(user), icon_url = user.avatar)
    embed.add_field(name = "ユーザー", value = f"{user.mention} - {str(user)}")
    embed.add_field(name = "終了日時", value = JSTTime.timeJST("full"))
    embed.add_field(name = "発言者", value = speakers, inline = False)
    embed.add_field(name = "削除者", value = delete_user.mention)
    
    save_channel = client.get_channel(config.modmail_save_channel)
    await save_channel.send(embed = embed, file = messages_json)
        
    

@client.tree.command(name = "modmail", description = "サーバーに関するご意見やお問い合わせを開始します。")
async def modmail(interaction:  discord.Interaction):
    await interaction.response.defer()
    
    embed = discord.Embed(title="あしたはこぶね・お問い合わせ",
                          description="以下のボタンを押すと、スタッフとの会話が開始されます\nよろしいですか？",
                          color=0x696969)
    embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
    await interaction.followup.send(embed=embed, ephemeral=True, view=ModmailButton())