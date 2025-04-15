import datetime
import os
from html import escape

import discord

from extentions import JSTTime, log
from extentions.aclient import client
from extentions.config import static

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")
modmail_html_path = "htmls/modmail.html"

class ModmailButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="開始する", custom_id = "modmailbutton", style=discord.ButtonStyle.success, emoji="✅")
    async def modmailbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        await interaction.response.send_message("お問い合わせを開始します", ephemeral=True, delete_after=1.0)
        
        result = await create_modmail(user = interaction.user)
        
        embed = discord.Embed(title="あしたはこぶね・お問い合わせ", description="お問い合わせありがとうございます！\nこのDMにメッセージを送ることで、スタッフとの会話を開始できます\nお問い合わせを終了する場合は、下の「終了」ボタンを押してください。", color=discord.Color.green())
        embed.set_author(name="あしたはこぶねスタッフ", icon_url=static.server_icon)
        
        if result == "created":
            await interaction.user.send(embed=embed, view=ModmailFinish())
                
        if result == "duplicated":
            await interaction.user.send("DMを既にお送りしております。ご確認ください！", ephemeral=True)    
            
               

class ModmailFinish(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "終了", custom_id = "modmailfinish", emoji = "🔒")
    async def modmailfinish(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild = client.get_guild(static.main_server) if static.test is False else client.get_guild(static.testserverid)
        
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
                
            embed = discord.Embed(title = "お問い合わせ/個別連絡が終了しました", description = "お問い合わせ/個別連絡が終了しました。ありがとうございました！\nなお、スタッフの判断によって再開され、スタッフからの連絡が来る場合があります。", color=discord.Color.yellow())
            embed.set_author(name="あしたはこぶねスタッフ", icon_url=static.server_icon)
            embed_mod = discord.Embed(title = "ModMailが終了しました", description = f"ModMailは{interaction.user.mention}によって終了しました。", color = discord.Color.yellow())
            
            if target == "member":
                await interaction.response.send_message(embed = embed)
                await mod_channel.send(embed = embed_mod)
                
            else:
                await user.send(embed = embed)
                await interaction.response.send_message(embed = embed_mod)

            if static.test is False:
            
                Administrator = guild.get_role(static.administrator_role)
                Moderator = guild.get_role(static.Moderator_role)
                

                closed_overwrite = {
                    guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True, manage_channels = True),
                    guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
                    Administrator: discord.PermissionOverwrite(read_messages = True, send_messages = True),
                    Moderator: discord.PermissionOverwrite(read_messages = True, send_messages = False)
                }
                
            else:
                closed_overwrite = {}
                
            await mod_channel.edit(name = f"closed-{userID}", overwrites = closed_overwrite)
            
            embed_control = discord.Embed(description = "スタッフのコントロールはこちら")
            await mod_channel.send(embed = embed_control, view = ModmailControl())
        
        else:
            await interaction.response.send_message(content = "お問い合わせは既に終了しています。", ephemeral = True)
        
        
        
class ModmailControl(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "再開", custom_id = "modmailresume", emoji = "🔓")
    async def modmailresume(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild = client.get_guild(static.main_server)
        Administrator = guild.get_role(static.administrator_role)
        Moderator = interaction.guild.get_role(static.Moderator_role)
        
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
            
            embed = discord.Embed(title = "お問い合わせが再開されました", description = f"{user.display_name}さんのお問い合わせが再開されました。スタッフからの返信が来る場合があります。", color=discord.Color.green())
            embed.set_author(name="あしたはこぶねスタッフ", icon_url=static.server_icon)
            await user.send(embed = embed)
            
            embed_mod = discord.Embed(description = "ModMailが再開されました", color=discord.Color.green())
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
            await save_modmail(channel = interaction.channel, save_channel=client.get_channel(static.modmail_save_channel), delete_user = interaction.user)
            await interaction.channel.delete()
            
        else:
            await interaction.response.send_message(content = "ModMailは現在終了していません。", ephemeral = True)
        

async def fetch_mod_channel(guild: discord.Guild, user: discord.User) -> discord.TextChannel:
    channels = guild.channels
    mod_channel = discord.utils.get(channels, name = f"mail-{user.id}")
    return(mod_channel)

async def create_modmail(user: discord.User):

    guild = client.get_guild(static.main_server) if static.test is False else client.get_guild(static.testserverid)
    mod_channel = await fetch_mod_channel(guild=guild, user=user)
    
    if mod_channel is None:
    
        categoty = discord.utils.get(guild.categories, name = "────フィードバック────")
        
        if static.test is False:
            Administrator = guild.get_role(static.administrator_role)
            Moderator = guild.get_role(static.Moderator_role)
        
            role_overwrite = {
                    guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True, manage_channels = True),
                    guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
                    Administrator: discord.PermissionOverwrite(read_messages = True, send_messages = True),
                    Moderator: discord.PermissionOverwrite(read_messages = True, send_messages = True)
            }
        else:
            role_overwrite = {}
            
        mod_channel = await guild.create_text_channel(f"mail-{user.id}", category = categoty, overwrites = role_overwrite, reason = f"ModMailが開始されました:{user.id}")
        announce_channel = client.get_channel(static.moderatorchannel)
        
        embed_mod = discord.Embed(title="ModMailが開始されました！", color=user.accent_color)
        embed_mod.set_author(name=str(user), icon_url=user.avatar.url)
        embed_mod.set_thumbnail(url = user.avatar.url)
        embed_mod.add_field(name = "ニックネーム", value = user.display_name)
        embed_mod.add_field(name = "id", value = user.id)
        embed_mod.add_field(name = "アカウント作成日", value = user.created_at)
        
        await mod_channel.send(embed=embed_mod, view = ModmailFinish())
        await announce_channel.send(embed = embed_mod)
        
        return("created")
        
    else:
        return("duplicated")
        
async def save_modmail(channel: discord.TextChannel, delete_user: discord.User = None, vc_log: bool = False, save_channel: discord.TextChannel = None, vc_create_user = None):
    
    if vc_log is False:
        idx = channel.name.find("-") + 1
        userID = int(channel.name[idx:])
        user = await client.fetch_user(userID)
    else:
        user = vc_create_user
    channel_name = channel.name
    channel_id = channel.id
    
    if not save_channel:
        save_channel = client.get_channel(static.modmail_save_channel)
    
    users = {}
    html_header = f"<!DOCTYPE html>\n<html lang='ja'>\n<head>\n<meta charset='utf-8'>\n<meta name='viewport' content='width=device-width, initial-scale=1.0'>\n<title>{channel_id}</title>\n<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css'>\n</head>\n<body class='bg-gray-700 text-gray-300'>\n<h1 class='text-2xl font-bold text-center my-4'>\n{channel_name} (チャンネルID: {channel_id})\n</h1>\n<div class='container mx-auto px-4'>\n"
    html_body = ""
    html_hooter = "</div>\n</body>\n</html>\n"
    
    log_count = 0
    
    async for message in channel.history(oldest_first = True):
        if vc_log is True and message.author == client.user:
            continue
        log_count += 1
        
        author = f"{str(message.author)} (スタッフ)" if vc_log is False else str(message.author)
        author_avatar = message.author.display_avatar.url
        content_unescape = message.embeds[0].description if message.embeds else message.content
        content_unescape = "" if content_unescape is None else content_unescape
        content = escape(content_unescape)
        content_br = content.replace("\n", "</p>\n<p class='text-base'>")
        timestamp = message.created_at + datetime.timedelta(hours=9)
        
        date_format = "%Y-%m-%d %H:%M:%S"
        image = ""
        
        if message.author != client.user:
            
            for attachment in message.attachments:
                if "image" in attachment.content_type:
                    image += f"<img src='{attachment.url}' alt='{attachment.url}' class='w-96 rounded-lg'>\n"
            
            if author in users:
                
                users[author] += 1
                
            else:
                users[author] = 1 
                
        else:
            for number in range(1, len(message.embeds)):
                image += f"<img src='{message.embeds[number].image.url}' alt='{message.embeds[number].image.url}' class='w-96 rounded-lg'>\n"
                
            if message.embeds[0].author.name is not None:
                author = f"{message.embeds[0].author.name} (メンバー)"
                author_avatar = message.embeds[0].author.icon_url
                
                if author in users:
                
                    users[author] += 1
                
                else:
                    users[author] = 1 
            else:
                author = f"{str(message.author)} (bot)"
        
        html_tag = f"<div class='flex items-start my-2'>\n<img src='{author_avatar}' alt='{author}' class='w-12 h-12 rounded-full mr-2'>\n<div class='flex flex-col'>\n<p class='text-lg font-semibold'>{author}</p>\n<p class='text-sm text-gray-400'>{timestamp.strftime(date_format)}</p>\n<p class='text-base'>{content_br}</p>\n{image}</div>\n</div>\n"
        
        html_body += html_tag
        
    if log_count == 0:
        return
    
    html = html_header + html_body + html_hooter
        
    with open(os.path.join(dir, modmail_html_path), mode = "w", encoding="utf-8") as f:
        f.write(html)
    
    messages_json = discord.File(fp = os.path.join(dir, modmail_html_path), filename = f"Modmail-{channel_id}.html") if vc_log is False else discord.File(fp = os.path.join(dir, modmail_html_path), filename = f"VCLog-{channel_id}.html")
    
    speakers = ""
    
    for index in users:
        speakers += f"{users[index]} - {index}\n"
    
    embed = discord.Embed(color = discord.Color.green())
    embed.set_author(name = str(user), icon_url = user.avatar)
    embed.add_field(name = "ユーザー", value = f"{user.mention} - {str(user)}")
    embed.add_field(name = "終了日時", value = JSTTime.timeJST("full"))
    embed.add_field(name = "発言者", value = speakers, inline = False)
    if vc_log is False:
        embed.add_field(name = "削除者", value = delete_user.mention)
    else:
        embed.add_field(name = "チャンネル名", value = channel_name)
    
    await save_channel.send(embed = embed, file = messages_json)
        
    

@client.tree.command(name = "modmail", description = "サーバーに関するご意見やお問い合わせを開始します。")
async def modmail(interaction:  discord.Interaction):
    await interaction.response.defer()
    
    embed = discord.Embed(title="あしたはこぶね・お問い合わせ",
                          description="以下のボタンを押すと、スタッフとの会話が開始されます\nよろしいですか？",
                          color=discord.Color.blue())
    embed.set_author(name="あしたはこぶねスタッフ", icon_url=static.server_icon)
    await interaction.followup.send(embed=embed, ephemeral=True, view=ModmailButton())
    
"""@client.tree.command(name = "modmail_form", description = "send modmail form", guild=config.testserverid)
async def modmail_form(interaction: discord.Interaction):
    await interaction.response.defer()
    channel = client.get_channel(1108227854245830706)
    
    embed = discord.Embed(title = "あしたはこぶね・お問い合わせ",
                          description = "サーバーに関するご意見やご要望、その他のお問い合わせは下のボタンを押すと開始できます！",
                          color = discord.Color.blue())
    embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
    await channel.send(embed = embed, view = ModmailButton())"""
    