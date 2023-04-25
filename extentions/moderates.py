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
            member_punishments = punishments[str(member.id)]["punishments"]
            for index in range(len(member_punishments)):
                if member_punishments[index]["id"] == id:
                    del member_punishments[index]
                    punishments[str(member.id)]["punishments"] = member_punishments
                    await punishment_write(punishments)
                    return True
            return False
        
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

@client.tree.command(name = "warn", description = "指定したメンバーに警告を科します。")
@discord.app_commands.describe(member = "警告するメンバー(どちらか)", member_id = "警告するメンバーの ID(どちらか)", reason = "警告する理由")
@discord.app_commands.default_permissions(kick_members = True)
@discord.app_commands.guild_only()
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
        search_id = str(member_got.id)
        
        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]
            #logger.info(member_punishments)
        
        embed = discord.Embed(title = "⚠️メンバーに「警告」を科しました。",
                              description = f"メンバー「{member_got.display_name}」に「警告」を科しました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰です。\n「警告」が数回重なった場合、より重い処罰が科される場合があります。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "warn", "date": now, "reason": reason, "by": interaction.user.id}
        
        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": member_punishments}
            punishments[search_id] = new
            #logger.info(new)
            await punishment_write(punishments)
        
        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": lists}
            punishments[search_id] = new
            await punishment_write(punishments)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if reason:
            embed = discord.Embed(title = "⚠️あなたはスタッフから「警告」されました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によって「警告」が科されました。「警告」の理由は以下になります\n{reason}\n\nこれは{len(member_punishments)}回目の処罰です。「警告」が数回重なるとサーバーからの追放、Banなどの重い処罰が科されます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。\nこの理由に身に覚えが無い場合、/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(content = member_got.mention, embed=embed)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーへの警告に失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}\n{str(member_got)}/{member_id}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[warn]にてエラー：{e}")

@client.tree.command(name = "kick", description = "指定したメンバーをキックします。")
@discord.app_commands.describe(member = "キックするメンバー(どちらか)", member_id = "キックするメンバーの ID(どちらか)", reason = "キックする理由")
@discord.app_commands.default_permissions(kick_members = True)
@discord.app_commands.guild_only()
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
        search_id = str(member_got.id)
        
        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]
        
        embed = discord.Embed(title = "⚠️メンバーを追放しました",
                              description = f"メンバー「{member_got.display_name}」をサーバーから追放しました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰で、このメンバーはサーバーに入りなおすことが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "kick", "date": now, "reason": reason, "by": interaction.user.id}
        
        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": member_punishments}
            punishments[search_id] = new
            await punishment_write(punishments)
        
        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": lists}
            punishments[search_id] = new
            await punishment_write(punishments)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if reason != "無し":
            embed = discord.Embed(title = "⚠️あなたはサーバーから追放されました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によってサーバーから追放されました。処罰の理由は以下になります\n{reason}\n\nあなたはまたサーバーに入りなおすことが出来ますが、これは{len(member_punishments)}回目の処罰です。回数が重なると、あなたはサーバーに入りなおすことが出来なくなります。\nこの理由に身に覚えが無い場合、あなたは/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(embed=embed)
            
        await interaction.guild.kick(user= member_got, reason = reason)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーの追放に失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}\n{str(member_got)}/{member_id}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[kick]にてエラー：{e}")
        
@client.tree.command(name = "ban", description = "指定したメンバーをBanします。")
@discord.app_commands.describe(member = "Banするメンバー(どちらか)", member_id = "Banするメンバーの ID(どちらか)", reason = "Banする理由")
@discord.app_commands.default_permissions(kick_members = True, ban_members = True)
@discord.app_commands.guild_only()
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
        search_id = str(member_got.id)
        
        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]
        
        embed = discord.Embed(title = "⚠️メンバーをBanしました",
                              description = f"メンバー「{member_got.display_name}」をBanしました。\n理由：{reason}\nこれは{len(member_punishments)+1}回目の処罰で、このメンバーは二度とサーバーに参加することは出来ません。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed = embed)
        
        punishment = {"id": message.id, "type": "ban", "date": now, "reason": reason, "by": interaction.user.id}
        
        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": True, "punishments": member_punishments}
            punishments[search_id] = new
            await punishment_write(punishments)
        
        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": True, "punishments": lists}
            punishments[search_id] = new
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
        embed = discord.Embed(title = "⚠️メンバーのBanに失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\nメッセージを送信出来なかった場合、理由を入力せずにもう一度お願いします。\n出現した例外：{e}\n{member_id}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[ban]にてエラー：{e}")
        
@client.tree.command(name = "unban", description = "指定したメンバーのBanを解除します。")
@discord.app_commands.describe(member = "Banされたメンバー(どちらか)", member_id = "Banされたメンバーの ID(どちらか)", delete = "Banの経歴を削除するかどうか(デフォルトはFalse)")
@discord.app_commands.default_permissions(kick_members = True, ban_members = True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True, ban_members = True)
async def unban(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, delete: bool = False):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title = "メンバーを指定してください！",
                                  description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return
        
        member_got = await client.fetch_user(int(member_id)) if member is None else member
            
        await interaction.guild.unban(user = member_got)
        
        now = str(JSTTime.timeJST("raw"))
        search_id = str(member_got.id)
        
        punishments = await punishment_load()
        if search_id in punishments:
            if punishments[search_id]["banned"] == True:
                punishments[search_id]["banned"] = False
            if delete == True:    
                criminal_record = punishments[search_id]
                member_punishments = criminal_record["punishments"]
                for index in range(len(member_punishments)):
                    if member_punishments[index]["type"] == "ban":
                        del member_punishments[index]
                        
        await punishment_write(punishments)
        
        embed = discord.Embed(title = "✅メンバーのBanを解除しました",
                              description = f"スタッフの判断により、メンバー「{member_got.display_name}」のBanを解除しました。\nこのメンバーはまたサーバーに参加することが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color = member_got.accent_color)
        embed.set_author(name = str(member_got), icon_url = member_got.avatar)
        embed.set_footer(text = f"{now}")
        await interaction.followup.send(embed = embed)
        
        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed = embed)
            
        if delete == True:
            embed = discord.Embed(title = "✅あなたのBanは解除されました",
                                  description = f"{member_got.name}さん、あなたはスタッフの判断によってサーバーからのBanを解除されました。\nBanの経歴も削除されます。\n「あしたはこぶね」をクリックすると、サーバーに入りなおすことができます。")
            embed.set_author(name = "あしたはこぶね", url = config.server_invite_link, icon_url=config.server_icon)
            await member_got.send(embed=embed)
    
    except Exception as e:
        embed = discord.Embed(title = "⚠️メンバーのBan解除に失敗しました！",
                              description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\nメッセージを送信出来なかった場合、無視しても構いません。\n出現した例外：{e}\n{str(member_got)}/{member_id}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[unban]にてエラー：{e}")

@discord.app_commands.default_permissions(administrator = True)   
@discord.app_commands.guild_only()     
class ModerateCommand(discord.app_commands.Group):
    @discord.app_commands.command(name = "show", description = "指定されたメンバーの情報/処罰履歴を確認します。#botmoderate限定")
    @discord.app_commands.describe(member = "メンバー(推奨)", member_id = "ユーザーID(メンバー以外)")
    @discord.app_commands.checks.has_permissions(view_audit_log = True)
    async def show(self, interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None):
        await interaction.response.defer()
        try:
            if member is None and member_id is None:
                embed = discord.Embed(title = "メンバーを指定してください！",
                                    description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
                await interaction.followup.send(embed=embed)
                return
            
            if interaction.channel_id != config.moderatorchannel:
                embed = discord.Embed(title = f"専用チャンネルで使用してください！",
                                        description = f"このコマンドは<#{config.moderatorchannel}>限定のコマンドです。")
                await interaction.followup.send(embed=embed)
                return
            
            if member:
                member_got = member

                #ロール
                roles = []
                for index in member_got.roles:
                    roles.append(index.name)
                    
                role = "\n".join(roles)
                
                embed = discord.Embed(title = f"{member_got.display_name}さんの情報", description=f"{member_got.mention}\nID: {member_got.id}\nアカウント作成日: {member_got.created_at}\n", color = member_got.accent_color)
                embed.set_thumbnail(url = member_got.display_avatar)
                embed.set_author(name = str(member_got), icon_url=member_got.avatar)
                embed.add_field(name = "所持しているロール", value = role, inline = True)
                embed.add_field(name = "最高のロール", value = member_got.top_role, inline = True)
                if member_got.is_timed_out() == True:
                    embed.add_field(name = "タイムアウト状態", value=f"<t:{0}:F>( <t:{0}:R> )まで".format(member_got.timed_out_until.timestamp), inline=False)
            
            else:
                member_got = await client.fetch_user(int(member_id))
                embed = discord.Embed(title = f"{member_got.display_name}さんの情報", description=f"{member_got.mention}\nID: {member_got.id}\nアカウント作成日: {member_got.created_at}\n", color = member_got.accent_color)
                embed.set_thumbnail(url = member_got.display_avatar)
                embed.set_author(name = str(member_got), icon_url=member_got.avatar)
            
            search_id = str(member_got.id)
            embed2 = None
        
            punishments = await punishment_load()
            if search_id in punishments:
                banned = punishments[search_id]["banned"]
                user_puni = punishments[search_id]["punishments"]
                
                if banned == True:
                    embed.add_field(name = "Banされています", value = "このユーザーはサーバーからBanされています", inline = False)
                    
                embed2 = discord.Embed(title = "処罰履歴", description = f"このユーザーは{len(user_puni)}回処罰を受けています")
                
                for index in range(len(user_puni)):
                    id = user_puni[index]["id"]
                    date = user_puni[index]["date"]
                    reason = user_puni[index]["reason"]
                    by = user_puni[index]["by"]
                    embed2.add_field(name = user_puni[index]["type"], value = f"ID: {id}\n時間: {date}\n理由: {reason}\n処罰者: {by}", inline = False)
            
            if embed2:
                embeds = [embed, embed2]
                await interaction.followup.send(embeds = embeds)
            
            else:
                await interaction.followup.send(embed = embed)
            
        
        except Exception as e:
            embed = discord.Embed(title = "⚠️メンバーの情報を取得できませんでした！",
                                description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}\n{str(member_got)}/{member_id}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand.show]にてエラー：{e}")
    
    @discord.app_commands.command(name = "delete", description = "指定された処罰履歴を削除します。#botmoderate限定")
    @discord.app_commands.describe(id = "処罰ID(/moderate showコマンドで表示されます)", member = "メンバー(どちらか)", member_id = "メンバーの ID(どちらか)")
    @discord.app_commands.checks.has_permissions(view_audit_log = True)
    async def delete(self, interaction:  discord.Interaction, id: str,  member:  discord.Member = None, member_id: str = None):
        await interaction.response.defer()
        try:
            if member is None and member_id is None:
                embed = discord.Embed(title = "メンバーを指定してください！",
                                      description = "memberかmember_idのどちらかでメンバーの指定する必要があります！")
                await interaction.followup.send(embed=embed)
                return

            member_got = await client.fetch_user(int(member_id)) if member is None else member
            id = int(id)
            
            result = await punishment_delete(member = member_got, id = id)
            if result == True:
                embed = discord.Embed(title = "処罰履歴の削除",
                                      description = f"{member_got.display_name}さんの処罰履歴#{id}を削除しました。")
                embed.set_author(name = str(member_got), icon_url=member_got.avatar)
                await interaction.followup.send(embed=embed)
            
            else:
                raise ValueError("result False")
            
        except Exception as e:
            embed = discord.Embed(title = "⚠️処罰履歴の削除に失敗しました！",
                                description = f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}\n{str(member_got)}/{member_id}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand.delete]にてエラー：{e}")