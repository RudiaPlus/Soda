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
puni_json_path = "jsons/punishments.json"
    
async def punishment_delete(member, id):
    punishments = await punishment_load()
    try:
        if str(member.id) in punishments:
            member_punishments = punishments[member.id]["punishments"]
            for index in range(len(member_punishments)):
                if member_punishments[index]["id"] == id:
                    del member_punishments[index]
                    break
        
    except Exception as e:
        logger.error(f"[punishment_delete]にてエラー：{e}")

async def punishment_write(dic):
    with open(os.path.join(dir, puni_json_path), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"punishments.jsonに新しく書き込みを行いました")


async def punishment_load():
    with open(os.path.join(dir, puni_json_path), encoding="UTF-8") as f:
        punishments = json.load(f)
    return (punishments)


async def reason_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    reasons = ["迷惑なスパム行為", "サーバールールの違反", "差別/侮辱的な発言", "ハラスメント行為", 
               "ヘイト行為", "暴力的な発言/脅迫行為", "児童への性的加害を含んだコンテンツの共有", 
               "不適切な場所での性的なコンテンツの共有", "他者の権利を侵害するコンテンツの共有", 
               "虚偽の情報/誤解を招く情報の共有", "無許可の不適切な宣伝行為", "違法行為の助長または実行"]
    return [
        discord.app_commands.Choice(name=reason, value = reason)
        for reason in reasons if current.lower() in reason.lower()
    ]

@client.tree.command(name = "warn", description = "指定したメンバーに警告を科します。", guild = config.testserverid)
@discord.app_commands.describe(member = "警告するメンバー(どちらか)", member_id = "警告するメンバーの ID(どちらか)", reason = "警告する理由")
@discord.app_commands.default_permissions(kick_members = True)
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.autocomplete(reason = reason_autocomplete)
async def warn(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title = "メンバーを指定してください！",
                                  description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return
        
        if not reason:
            reason = "無し"
        
        member_got = client.get_user(int(member_id)) if member is None else member
        
        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        
        punishments = await punishment_load()
        if str(member_got.id) in punishments:
            criminal_record = punishments[member_got.id]
            member_punishments = criminal_record["punishments"]
        
        embed = discord.Embed(title = "⚠️メンバーに「警告」を科しました。",
                              description = f"メンバー「{member_got.display_name}」に「警告」を科しました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰です。\n「警告」が数回重なった場合、より重い処罰が科される場合があります。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "warn", "date": now, "reason": reason}
        
        if str(member_got.id) in punishments:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": member_punishments.append(punishment)}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        else:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": punishment}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if reason:
            embed = discord.Embed(title = "⚠️あなたはスタッフから「警告」されました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によって「警告」が科されました。「警告」の理由は以下になります\n{reason}\n\nこれは{len(member_punishments)+1}回目の処罰です。「警告」が数回重なるとサーバーからの追放、Banなどの重い処罰が科されます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。\nこの理由に身に覚えが無い場合、/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(content = member_got.mention, embed=embed)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーへの警告に失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[warn]にてエラー：{e}")

@client.tree.command(name = "kick", description = "指定したメンバーをキックします。", guild = config.testserverid)
@discord.app_commands.describe(member = "キックするメンバー(どちらか)", member_id = "キックするメンバーの ID(どちらか)", reason = "キックする理由")
@discord.app_commands.default_permissions(kick_members = True)
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.autocomplete(reason = reason_autocomplete)
async def kick(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title = "メンバーを指定してください！",
                                  description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return
        
        if not reason:
            reason = "無し"
        
        member_got = client.get_user(int(member_id)) if member is None else member
        
        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        
        punishments = await punishment_load()
        if str(member_got.id) in punishments:
            criminal_record = punishments[member_got.id]
            member_punishments = criminal_record["punishments"]
        
        embed = discord.Embed(title = "⚠️メンバーを追放しました",
                              description = f"メンバー「{member_got.display_name}」をサーバーから追放しました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰で、このメンバーはサーバーに入りなおすことが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "kick", "date": now, "reason": reason}
        
        if str(member_got.id) in punishments:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": member_punishments.append(punishment)}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        else:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": punishment}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if reason != "無し":
            embed = discord.Embed(title = "⚠️あなたはサーバーから追放されました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によってサーバーから追放されました。処罰の理由は以下になります\n{reason}\n\nあなたはまたサーバーに入りなおすことが出来ますが、これは{len(member_punishments)+1}回目の処罰です。回数が重なると、あなたはサーバーに入りなおすことが出来なくなります。\nこの理由に身に覚えが無い場合、あなたは/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(embed=embed)
            
        await interaction.guild.kick(user= member_got, reason = reason)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーの追放に失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[kick]にてエラー：{e}")
        
@client.tree.command(name = "ban", description = "指定したメンバーをBanします。", guild = config.testserverid)
@discord.app_commands.describe(member = "Banするメンバー(どちらか)", member_id = "Banするメンバーの ID(どちらか)", reason = "Banする理由")
@discord.app_commands.default_permissions(kick_members = True, ban_members = True)
@discord.app_commands.checks.has_permissions(kick_members=True, ban_members = True)
@discord.app_commands.autocomplete(reason = reason_autocomplete)
async def ban(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title = "メンバーを指定してください！",
                                  description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return
        
        if not reason:
            reason = "無し"
        
        member_got = await client.fetch_user(int(member_id)) if member is None else member
        
        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        
        punishments = await punishment_load()
        if str(member_got.id) in punishments:
            criminal_record = punishments[member_got.id]
            member_punishments = criminal_record["punishments"]
        
        embed = discord.Embed(title = "⚠️メンバーをBanしました",
                              description = f"メンバー「{member_got.display_name}」をBanしました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰で、このメンバーは二度とサーバーに参加することは出来ません。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "ban", "date": now, "reason": reason}
        
        if str(member_got.id) in punishments:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": True, "punishments": member_punishments.append(punishment)}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        else:
            new = {"userName": str(member_got), "userID": member_got.id, "banned": True, "punishments": punishment}
            punishments[member_got.id] = new
            await punishment_write(punishments)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if reason != "無し":
            embed = discord.Embed(title = "⚠️あなたはサーバーからBanされました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によってサーバーからBanされました。処罰の理由は以下になります\n{reason}\n\nあなたはもう二度とサーバーに入りなおす事が出来ませんが、この処罰に身に覚えが無い場合、/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(embed=embed)
            
        await interaction.guild.ban(user = member_got, reason = reason)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーのキックに失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[kick]にてエラー：{e}")
    