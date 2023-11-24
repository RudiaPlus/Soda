from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from typing import List, Tuple
from discord import Embed, Color
from discord.ext import tasks
from extentions import log, config
from extentions.aclient import client
import datetime
import requests
import re
import os
import json

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger(__name__)
test = config.test
last_tweet_url = ""
web = True # Switch of web

if web == True:
    try:
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome()
        driver.get("https://nitter.net/AKEndfieldJP")
        
        wait = WebDriverWait(driver, 9)
        last_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "]')))
        
        try:
            pinned = last_tweet.find_element(By.XPATH, ".//div//div[@class='pinned']")
            last_tweet=wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "][2]')))
        except:
            pass
        
        last_tweet_url = last_tweet.find_element(By.XPATH, ".//a").get_attribute('href')
        logger.info(f"@AKEndfieldJPの最後のツイートをnitterにて取得しました: {last_tweet_url}")
        
    except Exception as e:
        web=False
        logger.error(f"nitterにてエラー: {e}")
        
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
                        if key != "external" and key != "photos" and key != "videos":
                            continue
                        tweet_medias = tweet_data["media"][key]
                        for media in tweet_medias:
                            url = media["url"]
                            if key == "photos":
                                media_urls.append(url)
                            elif key == "videos" or key == "external":
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
            
        
async def check_duplicate(url: str) -> bool:
    json_name = "jsons/tweeted.json"
    with open(os.path.join(dir, json_name), "r", encoding = "UTF-8") as f:
        tweeted_list = json.load(f)
    if url in tweeted_list:
        duplicate = True
    else:
        duplicate = False
        tweeted_list.append(url)
        if len(tweeted_list) > 10:
            tweeted_list.pop(0)
        with open(os.path.join(dir, json_name), "w", encoding = "UTF-8") as f:
            json.dump(tweeted_list, f, indent=4, ensure_ascii=False)
    return duplicate

async def publish_tweet_from_nitter_url(url: str) -> None:
    target = url.find(".net/")
    target_end = url.find("#m")
    new_tweet_url_splitted = url[target+5:target_end]
    new_tweet_url_twitter = f"https://twitter.com/{new_tweet_url_splitted}"
    duplicate = await check_duplicate(new_tweet_url_twitter)
    if duplicate == False:
        channel = client.get_channel(config.ake_news)
        embeds, video_urls = await create_embed(new_tweet_url_twitter)
        message = await channel.send(f"<{new_tweet_url_twitter}>", embeds = embeds)
        await message.publish()
        if video_urls:
            for url in video_urls:
                await message.reply(content = f"[ブラウザで開く]({url})")
        logger.info(f"新規ツイート({new_tweet_url_twitter})をアナウンスしました。")
    else:
        logger.info(f"新規ツイート({new_tweet_url_twitter})は既にアナウンスされています。投稿を中止しました。")
   
@tasks.loop(minutes=7)
async def ake_tweet_retrieve():
    global last_tweet_url
    try:
        logger.debug("ツイートを取得します")
        new_tweet_urls = []
        driver.refresh()
        new_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "]')))
        
        new_tweet_url = new_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
        
        try:
            pinned = new_tweet.find_element(By.XPATH, ".//div//div[@class='pinned']")
            new_tweet=wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "][2]')))
            new_tweet_url = new_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
        except:
            pass
        
        if new_tweet_url != last_tweet_url:
            current_tweet_url = new_tweet_url
            count = 1
            while current_tweet_url != last_tweet_url and count < 10:
                count += 1
                new_tweet_urls.append(current_tweet_url)
                if pinned:
                    current_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, f'//div[@class="timeline-item "][{count+1}]')))
                else:
                    current_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, f'//div[@class="timeline-item "][{count}]')))
                
                current_tweet_url = current_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
            
            last_tweet_url = new_tweet_urls[0]
            
            logger.info(f"@AKEndfieldJPの最新ツイートを{count-1}個nitterにて取得しました: {new_tweet_urls}")
            
            new_tweet_urls = list(reversed(new_tweet_urls))
            
            for url in new_tweet_urls:
                await publish_tweet_from_nitter_url(url)

            
    except Exception as e:
        print(f"error: {e}")