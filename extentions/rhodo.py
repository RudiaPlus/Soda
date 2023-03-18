import discord
from extentions import (responses, config, evjson, JSTTime, modmails)
import re
import os
import json
from discord import app_commands
from discord.ext import tasks


class Rhodolite(discord.Client):

  def __init__(self, *, intents: discord.Intents):
    super().__init__(intents=intents)
    self.tree = app_commands.CommandTree(self)
    self.activity = discord.Activity(type=discord.ActivityType.watching,
                                     name="DISCOVERED TERRA")


async def send_message(message, user_message):
  try:
    response = await responses.get_response(user_message, reset=False)
    print(f"【rhodo.send_message】返信を取得しました「{response}」")

    if len(response) > 1900:
      await message.channel.send("文字数制限を超えてしまいました！すみませんがもう一度お願いします！")
    else:
      await message.channel.send(response)

  except Exception as e:
    print(f"【rhodo.send_message】エラー：{e}")

  except Exception as e:
    print(f"【rhodo.send_start_prompt】エラー：{e}")


def run_discord_bot():

  TOKEN = config.token
  intents = discord.Intents.default()
  intents.message_content = True
  intents.guilds = True
  intents.members = True
  intents.voice_states = True
  client = Rhodolite(intents=intents)
  dir = os.path.abspath(__file__ + "/../")

  @client.event
  async def on_ready():
    print("【rhodo.run_discord_bot.on_ready】準備を始めます")
    try:
      #await send_start_prompt(client)
      synced = await client.tree.sync()
      await client.tree.sync(guild=config.testserverid)
      print(f"【rhodo.run_discord_bot.on_ready】{len(synced)}個のコマンドを同期しました。")
    except Exception as e:
      print(f"【rhodo.run_discord_bot.on_ready】 エラー：{e}")
    print(f"【rhodo.run_discord_bot.on_ready】{client.user} 、準備完了です！")

  @client.event
  async def setup_hook() -> None:
    morning.start()

  class ModmailButton(discord.ui.View):

    @discord.ui.button(label="開始する",
                       style=discord.ButtonStyle.success,
                       emoji="✅")
    async def button_callback(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
      channel = client.get_channel(config.modchannnel)
      user = interaction.user
      if await modmails.modmail_queue(user) == "Ready":
        embed = discord.Embed(
          title="あしたはこぶね・お問い合わせ",
          description="お問い合わせありがとうございます！\nこのDMにメッセージを送ることで、スタッフとの会話を開始できます",
          color=0x696969)
        embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
        embed_mod = discord.Embed(
          title="Modmailが開始されました！",
          description=
          f"ニックネーム : {user.display_name}\nid : {user.id}\nアカウント作成日 : {user.created_at}",
          color=user.accent_color)
        embed_mod.set_author(name=user.name, icon_url=user.avatar.url)
        await channel.send(embed=embed_mod)
        await user.send(embed=embed)
        await interaction.response.send_message("DMをお送りしました。ご確認ください！",
                                                ephemeral=True)

      elif await modmails.modmail_queue(user) == "False":
        await interaction.response.send_message("DMを既にお送りしております。ご確認ください！",
                                                ephemeral=True)

      else:
        embed = discord.Embed(
          title="あしたはこぶね・お問い合わせ",
          description=
          "お問い合わせありがとうございます！\n現在問い合わせが立て込んでおり、今すぐに会話を開始できない状態となっております。\n順番になり次第こちらから連絡致します。今しばらくお待ちください",
          color=0x696969)
        embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
        embed_mod = discord.Embed(
          title="Modmailの予約が入りました！",
          description=
          f"ニックネーム : {user.display_name}\nid : {user.id}\nアカウント作成日 : {user.created_at}",
          color=user.accent_color)
        embed_mod.set_author(name=user.name, icon_url=user.avatar.url)
        await channel.send(embed=embed_mod)
        await user.send(embed=embed)
        await interaction.response.send_message("DMをお送りしました。ご確認ください！",
                                                ephemeral=True)

  @client.tree.command(name="modmail",
                       description="サーバースタッフと会話を開始することが出来ます！お気軽にご利用ください！")
  async def modmail(interaction: discord.Interaction):
    if interaction.user == client.user:
      return
    embed = discord.Embed(title="あしたはこぶね・お問い合わせ",
                          description="以下のボタンを押すと、スタッフとの会話が開始されます\nよろしいですか？",
                          color=0x696969)
    embed.set_author(
      name="あしたはこぶねスタッフ",
      icon_url=
      "https://cdn.discordapp.com/icons/1018858818345631745/039c77dd10811cb8e193c8e0cd4be453.webp?size=1024"
    )
    await interaction.response.send_message(embed=embed,
                                            ephemeral=True,
                                            view=ModmailButton())

  @client.tree.command(name="rechat",
                       description="for dev only",
                       guild=config.testserverid)
  async def rechat(interaction: discord.Interaction):
    if interaction.user == client.user:
      return
    await interaction.response.defer()
    await responses.get_response("reset", reset=True)
    await interaction.followup.send("完了しました！")

  @client.tree.command(name="eventtest",
                       description="イベントリストのテストを行います",
                       guild=config.testserverid)
  async def eventtest(interaction: discord.Interaction):
    if interaction.user == client.user:
      return
    await interaction.response.defer()
    events = evjson.eventget()
    print(
      f"【rhodo.run_discord_bot.eventtest】イベントのリストを受け取りました。以下になります。\n{events}")
    await interaction.followup.send(events)

  @client.event
  async def on_message(message):

    if message.author == client.user:
      return

    messageuser = client.get_user(modmails.modmail_get_user())

    if messageuser and message.channel.id == config.modchannnel:
      if message.content == "終了":
        await modmails.modmail_finish(messageuser)
      else:
        mail = discord.Embed(title=f"【スタッフ】{message.author.name}からのメッセージ",
                             description=message.content)
        mail.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
        await messageuser.send(embed=mail)

    elif message.author == messageuser:
      channel = client.get_channel(config.modchannnel)
      mail = discord.Embed(title=f"{message.author.name}からのメッセージ",
                           description=message.content)
      mail.set_footer(text="Modmailを終わらせるには「終了」と送信してください")
      await channel.send(embed=mail)

    username = str(message.author)
    user_message = str(message.content)
    channel = str(message.channel)
    channelID = int(message.channel.id)

    print(
      f"【rhodo.run_discord_bot.on_message】{username}が{channel}({channelID})にて「{user_message}」と言ったのを記録しました"
    )

    if channelID == config.chat:
      clean_message = re.sub('<.*?>', '', user_message)
      print("【rhodo.run_discord_bot.on_message】返事をします")
      await send_message(message, clean_message)

    else:
      return

  @tasks.loop(time=config.morningtime)
  async def morning():
    try:
      print("【rhodo.morning】時間になりました。モーニングルーティンを始めます")

      if config.morning == True:
        events = evjson.eventget()
        print(f"【rhodo.morning】イベントのリストを受け取りました。以下になります。\n{events}")
        eventcount = evjson.eventcount()
        channel = client.get_channel(config.announce)

        if eventcount[0] == 0:
          eventnow = "本日は少し休める日ですね！"
        elif eventcount[0] == 1:
          eventnow = f"\n・イベントが進行中です:sparkles: 頑張りましょう！"
        else:
          eventnow = f"\n・本日は{eventcount[0]}個のイベントが進行中です:sparkles: 頑張りましょう！"

        if eventcount[1] == 0:
          eventend = ""
        elif eventcount[1] == 1:
          eventend = f"\n・終了したイベントが在ります！ 報酬の受け取りを忘れずに！:eyes:"
        else:
          eventend = f"\n・{eventcount[1]}個のイベントが終了しています。報酬の受け取りを忘れずに！:eyes:"

        if eventcount[2] == 0:
          eventfuture = ""
        elif eventcount[2] == 1:
          eventfuture = f"\n・開催予定のイベントがあります！ 楽しみですね！:star2:"
        else:
          eventfuture = f"\n・{eventcount[2]}個のイベントがこの先やってきます！準備は出来ていますか？"

        if JSTTime.timeJST("weekday") == "日":
          weekday = "\n・本日は日曜日です！ 殲滅作戦は終わらせましたか？"
        else:
          weekday = ""

        json_name = "jsons/birthday.json"
        with open(os.path.join(dir, json_name), encoding="utf-8") as f:
          birthday = json.load(f)
          today = JSTTime.timeJST("m/d")
          if today in birthday:
            bdayop = f"\n・本日は{birthday[today]}が誕生日です:birthday: おめでとうございます！"
          else:
            bdayop = ""

        await channel.send(
          f"<@&1076155144363851888>\nおはようございます:sunny: ロードです！  {eventnow}{eventend}{eventfuture}{weekday}{bdayop}"
        )

        for i in range(len(events)):
          if events[i]["dif"] == "present":
            if events[i]["type"] == "CRISIS":
              if events[i]["contractAdd"] == False:
                try:
                  link = events[i]["link"]
                  eventpic = events[i]["pic"]
                except Exception:
                  pass

                png_name = "images/contingencycontract.png"
                file = discord.File(os.path.join(dir, png_name),
                                    filename="image.png")
                embed = discord.Embed(title=events[i]["name"],
                                      description=events[i]["time"],
                                      color=0x6d2727,
                                      url=link)
                embed.set_author(name="危機契約",
                                 icon_url="attachment://image.png")
                embed.add_field(name="・常設ステージ",
                                value=events[i]["permStage"],
                                inline=False)
                embed.add_field(name="・本日のデイリーステージ",
                                value=events[i]["todaysDaily"]["stageName"],
                                inline=False)
                embed.add_field(name="・契約追加日",
                                value=events[i]["contractAddTime"],
                                inline=False)
                embed.set_image(url=eventpic)
                await channel.send(files=file, embed=embed)

              else:
                try:
                  link = events[i]["link"]
                  eventpic = events[i]["pic"]
                except Exception:
                  pass

                png_name = "images/contingencycontract.png"
                file = discord.File(os.path.join(dir, png_name),
                                    filename="image.png")
                embed = discord.Embed(title=events[i]["name"],
                                      description=events[i]["time"],
                                      color=0x6d2727,
                                      url=link)
                embed.set_author(name="危機契約",
                                 icon_url="attachment://image.png")
                embed.add_field(name="・常設ステージ",
                                value=events[i]["permStage"],
                                inline=False)
                embed.add_field(name="・本日のデイリーステージ",
                                value=events[i]["todaysDaily"]["stageName"],
                                inline=False)
                embed.add_field(name="・契約が追加されています！",
                                value="危機契約も後半戦です！一緒に頑張りましょう！！",
                                inline=False)
                embed.set_image(url=eventpic)
                await channel.send(file=file, embed=embed)

            elif events[i]["type"] == "SIDESTORY":
              if events[i]["stageAdd"] == "True":
                try:
                  nextStageName = events[i]["nextStageName"]
                  nextAddTime = events[i]["nextAddTime"]
                  link = events[i]["link"]
                  eventpic = events[i]["pic"]
                except Exception:
                  pass

                embed = discord.Embed(title=events[i]["name"],
                                      description=events[i]["time"],
                                      color=0x24ab12,
                                      url=link)
                embed.set_author(name="サイドストーリー")
                embed.add_field(name=f"次のステージ追加 「{nextStageName}」",
                                value=nextAddTime)
                embed.set_image(url=eventpic)
                await channel.send(embed=embed)
              else:
                try:
                  link = events[i]["link"]
                  eventpic = events[i]["pic"]
                except Exception:
                  pass

                embed = discord.Embed(title=events[i]["name"],
                                      description=events[i]["time"],
                                      color=0x368ad9,
                                      url=link)
                embed.set_author(name="サイドストーリー")
                embed.set_image(url=eventpic)
                await channel.send(embed=embed)

            elif events[i]["type"] == "MINISTORY":
              try:
                link = events[i]["link"]
                eventpic = events[i]["pic"]
              except Exception:
                pass

              embed = discord.Embed(title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0xCAC531,
                                    url=link)
              embed.set_author(name="オムニバスストーリー")
              embed.set_image(url=eventpic)
              await channel.send(embed=embed)

            else:
              embed = discord.Embed(title=events[i]["name"],
                                    description=events[i]["time"],
                                    color=0xf29382)
              embed.set_author(name="イベント")
              await channel.send(embed=embed)

          elif events[i]["dif"] == "past":
            rewardEndTime = events[i]["rewardEndTime"]
            embed = discord.Embed(title=events[i]["name"],
                                  description=f"報酬受取期限：{rewardEndTime}",
                                  color=0x454545)
            embed.set_author(name="終了したイベント")
            await channel.send(embed=embed)

          else:
            embed = discord.Embed(title=events[i]["name"],
                                  description=events[i]["time"],
                                  color=0xba80ea)
            embed.set_author(name="開催予定のイベント")
            await channel.send(embed=embed)

      await responses.get_response("reset", reset=True)

    except Exception as e:
      print(e)

  client.run(TOKEN)
