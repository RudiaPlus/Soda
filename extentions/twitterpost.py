from typing import List, Tuple
from discord import Embed, Color
from discord.ext import tasks
from extentions import log, config
from extentions.aclient import client
import time
import datetime
import requests
import re
import os
import feedparser

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger(__name__)
        
async def create_embed(content: str) -> Tuple[List[Embed], List[str]]:
    try:
        twitter_x_pattern = r"https?:\/\/(www\.)?(x|twitter)\.com\/[^/]+\/status\/(\d+)"
        links_twitter_x = re.finditer(twitter_x_pattern, content)
        if not links_twitter_x:
            return [], []
        
        ids = []
        for matched in links_twitter_x:
            link = matched.group()
            index = link.find("/status/")
            id = link[index+8:]
            ids.append(id)
            
        responses = []
        for id in ids:
            response = requests.get(f"https://api.fxtwitter.com/status/{id}")
            if response.status_code == 200:
                tweet_data = response.json()["tweet"]
                
                tweet_url = tweet_data["url"]
                
                author = tweet_data["author"]
                
                if "avatar_url" in author:
                    avatar_url = author["avatar_url"]
                else:
                    avatar_url = None
                
                tweet_text = tweet_data["text"]
                
                created_at = tweet_data["created_timestamp"]
                
                media_urls = []
                video_urls = []
                
                if "media" in tweet_data:
                    
                    for key in tweet_data["media"]:
                        if key != "photos" and key != "videos":
                            continue
                        
                        tweet_medias = tweet_data["media"][key]                        
                        for media in tweet_medias:
                            url = media["url"]
                            if key == "photos":
                                media_urls.append(url)
                            elif key == "videos":
                                video_urls.append(url)
                
                tweet_dict = {"id": id, "url": tweet_url, "author_name": author["name"], "screen_name": author["screen_name"], "author_avatar": avatar_url, "text": tweet_text, "created_at": created_at, "media_urls": media_urls, "video_urls": video_urls}
                responses.append(tweet_dict)
        
        embeds = []
        video_urls = []
        
        for dic in responses:
            timestamp = datetime.datetime.fromtimestamp(dic["created_at"])
            tweet_embed = Embed(color = Color.blue(), description=dic["text"], timestamp = timestamp)
            tweet_embed.set_author(name = f"{dic['author_name']} @{dic['screen_name']}", url = dic["url"], icon_url=dic["author_avatar"])
            embeds.append(tweet_embed)
            
            if dic["media_urls"]:
                for url in dic["media_urls"]:
                    media_embed = Embed(color = Color.blue(), description=f"[ブラウザで開く]({url})")
                    media_embed.set_image(url = url)
                    embeds.append(media_embed)
                    
            if dic["video_urls"]:
                for url in dic["video_urls"]:
                    video_urls.append(url)
        
        return embeds, video_urls

    except Exception as e:
        logger.error(f"[create_embed]にてエラー: {e}")
        return [], []

   
@tasks.loop(minutes=1)
async def ake_tweet_retrieve():
    try:
        logger.debug("ツイートを取得します")
        feed = feedparser.parse(config.rss_endfield_link)
        minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes = 1)
        count = 0
        new_tweet_urls = []
        
        for entry in feed.entries:
            pubdate = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed), datetime.timezone.utc) + datetime.timedelta(hours = 9)
            if pubdate > minutes_ago:
                tweet_url = entry.link
                count += 1
                new_tweet_urls.append(tweet_url)
        
        if new_tweet_urls:    
            logger.info(f"@AKEndfieldJPの最新ツイートを{count}個取得しました: {new_tweet_urls}")
        
            new_tweet_urls = list(reversed(new_tweet_urls))
            
            for url in new_tweet_urls:
                channel = client.get_channel(config.ake_news)
                embeds, video_urls = await create_embed(url)
                message = await channel.send(f"<{url}>", embeds = embeds)
                await message.publish()
                if video_urls:
                    for url in video_urls:
                        await message.reply(content = f"[ブラウザで開く]({url})")
                logger.info(f"新規ツイート({url})をアナウンスしました。")
            
    except Exception as e:
        print(f"【ake_tweet_retrieve】にてエラー: {e}")
        
@tasks.loop(minutes=1)
async def ww_tweet_retrieve():
    try:
        logger.debug("ツイートを取得します")
        feed = feedparser.parse(config.rss_ww_link)
        minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes = 1)

        count = 0
        new_tweet_urls = []
        
        for entry in feed.entries:
            pubdate = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed), datetime.timezone.utc) + datetime.timedelta(hours = 9)
            if pubdate > minutes_ago:
                tweet_url = entry.link
                count += 1
                new_tweet_urls.append(tweet_url)
        
        if new_tweet_urls:    
            logger.info(f"@WW_JP_Officialの最新ツイートを{count}個取得しました: {new_tweet_urls}")
        
            new_tweet_urls = list(reversed(new_tweet_urls))
            
            for url in new_tweet_urls:
                channel = client.get_channel(config.ww_news)
                embeds, video_urls = await create_embed(url)
                message = await channel.send(f"<{url}>", embeds = embeds)
                await message.publish()
                if video_urls:
                    for url in video_urls:
                        await message.reply(content = f"[ブラウザで開く]({url})")
                logger.info(f"新規ツイート({url})をアナウンスしました。")
            
    except Exception as e:
        print(f"【ww_tweet_retrieve】にてエラー: {e}")
        
@tasks.loop(minutes=1)
async def ww_youtube_retrieve():
    try:
        logger.debug("ツイートを取得します")
        feed = feedparser.parse(config.rss_ww_youtube)
        minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes = 1)
        count = 0
        new_video_urls = []
        
        for entry in feed.entries:
            pubdate = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed), datetime.timezone.utc) + datetime.timedelta(hours = 9)
            if pubdate > minutes_ago:
                video_url = entry.link
                count += 1
                new_video_urls.append(video_url)
        
        if new_video_urls:    
            logger.info(f"@WW_JP_Officialの最新YouTubeを{count}個取得しました: {new_video_urls}")
        
            new_video_urls = list(reversed(new_video_urls))
            
            for url in new_video_urls:
                channel = client.get_channel(config.ww_news_youtube)
                message = await channel.send(f"{url}")
                logger.info(f"新規YouTube({url})をアナウンスしました。")
            
    except Exception as e:
        print(f"【ww_youtube_retrieve】にてエラー: {e}")