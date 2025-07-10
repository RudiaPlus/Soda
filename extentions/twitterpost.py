import asyncio
import atexit
import datetime
import html
import json as js
import os
import re
import time
from typing import List, Tuple

import aiohttp
import aiosqlite
import feedparser
from discord import Color, Embed
from discord.ext import tasks
from tweety import Twitter
from tweety.types import Tweet, HOME_TIMELINE_TYPE_FOLLOWING, SelfThread, ConversationThread

from extentions import JSTTime, log
from extentions.aclient import client
from extentions.config import config

from typing import Optional, Union, Optional

dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger()
test = config.test
last_tweet_url = ""
web = config.selenium # Switch of web
agent = 'Chromium";v="130","Google Chrome";v="130","Not?A_Brand";v="99'
headers = {'User-Agent': agent}
twitterurl = "https://twstalker.com/AKEndfieldJP"
feedurl = "https://nitter.poast.org/AKEndfieldJP/rss"
feedurl_alter = "https://nitter.privacydev.net/AKEndfieldJP/rss"
twstalker = "https://twstalker.com/AKEndfieldJP"
timeout = aiohttp.ClientTimeout(total=10)

app :Optional[Twitter] = None

def date_comparator(date1: Union[datetime.datetime, str], date2: Union[datetime.datetime, str], FORMAT: str = '%Y-%m-%d %H:%M:%S%z') -> int:
    date1, date2 = [datetime.datetime.strptime(date, FORMAT) if isinstance(date, str) else date for date in (date1, date2)]
    return (date1 > date2) - (date1 < date2)

async def tweet_expand(tweets, expanded_tweets=None) -> List[Tweet]:
    """
    Expand tweets to include threads and conversations.
    """
    if expanded_tweets is None:
        expanded_tweets = []
    for tweet in tweets:
        if isinstance(tweet, (SelfThread, ConversationThread)):
            await tweet_expand(tweet.tweets, expanded_tweets)
        elif isinstance(tweet, Tweet):
            expanded_tweets.append(tweet)
    return expanded_tweets

async def get_tweets(tweets: List[Tweet], username: str) -> Optional[list[Tweet]]:
    if username == "AKEndfieldJP":
        channel = client.get_channel(config.ake_news)
    
    try:
        last_message = await channel.fetch_message(channel.last_message_id)
    except Exception as e:
        logger.warning(f"キャッシュからの最後のメッセージ取得に失敗しました: {e}")
        async for message in channel.history(limit=10):
            if message.author.id == client.user.id:
                last_message = message
                break
    last_published_time = last_message.created_at
    
    expanded_tweets = await tweet_expand(tweets)
    tweets = [tweet for tweet in expanded_tweets if tweet.author.screen_name == username and date_comparator(tweet.created_on, last_published_time) == 1]
    
    if tweets != []:
        return sorted(tweets, key=lambda x: x.created_on)
    else:
        return None
    
async def setup_app():
    async def authenticate_account(account_name, account_token):
        app = Twitter(account_name)
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                await app.load_auth_token(account_token)
                logger.info(f"Authenticated {account_name} successfully.")
                tl = await app.get_home_timeline(timeline_type=HOME_TIMELINE_TYPE_FOLLOWING)
                if not tl:
                    logger.error(f"Failed to retrieve home timeline for {account_name}.")
                    raise ValueError("Home timeline is empty.")
                else:
                    logger.info(f"Successfully retrieved home timeline for {account_name}.")
                    logger.debug(f"Last tweets of timeline: {tl.tweets[0].text[:30]}...")
                return app
            except Exception as e:
                logger.error(f"Authentication failed for {account_name}: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(4 ** attempt)
                else:
                    logger.error(f"Failed to authenticate {account_name} after {max_attempts} attempts.")
                    raise
    
    global app
    app = await authenticate_account(config.twitter_account_name, config.twitter_account_token)

async def notification(tweets, username: str):
    latest_tweets = await get_tweets(tweets, username)
    if latest_tweets is None:
        return
    
    for tweet in latest_tweets:
        logger.info(f"New tweet from {username}: {tweet.text[:30]}...")
        url = tweet.url
        embeds, video_urls = await create_embed(url)
        if username == "AKEndfieldJP":
            channel = client.get_channel(config.ake_news)
        message = await channel.send(f"<{url}>", embeds=embeds)
        await message.publish()
        if video_urls:
            for url in video_urls:
                await message.reply(content = f"[ブラウザで開く]({url})")
        logger.info(f"新規ツイート({url})をアナウンスしました。")
        
async def tweets_updater(app: Twitter):
    try:
        tweet_notifications = await app.get_list_tweets(list_id=config.notify_list_id)
        if not tweet_notifications:
            return
        tweets = tweet_notifications.tweets
        logger.debug(f"notified tweets found: {len(tweets)}")
        return tweets
    except Exception as e:
        logger.error(f"Failed to get tweet notifications: {e}")
        return

@tasks.loop(minutes = 5)
async def ake_tweet_retrieve(): 
    global app
    if app is None:
        logger.debug("Twitterへの接続がありません")
        return
    
    try:
        tweets = await tweets_updater(app)
        if tweets is None:
            logger.debug("No new tweets found or failed to retrieve tweets.")
            return
        
        await notification(tweets, "AKEndfieldJP")
        
    except Exception as e:
        logger.error(f"Error in ake_tweet_retrieve: {e}")
        
async def get_response(url, json: bool = False):
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as r:
            if json is False:
                r_text = await r.text()
                return r, r_text
            else:
                r_json =  await r.json()
                return r, r_json
        
async def create_embed(content: str) -> Tuple[List[Embed], List[str]]:
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
        response, tweet_json = await get_response(f"https://api.fxtwitter.com/status/{id}", json = True)
        if response.status == 200:
            tweet_data = tweet_json["tweet"]
            
            tweet_url = tweet_data["url"]
            
            author = tweet_data["author"]
            
            if "avatar_url" in author:
                avatar_url = author["avatar_url"]
            else:
                avatar_url = None
            
            tweet_text = tweet_data["text"]
            
            created_at = tweet_data["created_timestamp"]
            
            replying_to = tweet_data["replying_to"]
            
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
            
            tweet_dict = {"id": id, "url": tweet_url, "author_name": author["name"], "screen_name": author["screen_name"], "author_avatar": avatar_url, "text": tweet_text, "created_at": created_at, "media_urls": media_urls, "video_urls": video_urls, "replying_to": replying_to}
            responses.append(tweet_dict)
    
    embeds = []
    video_urls = []
    
    for dic in responses:
        timestamp = datetime.datetime.fromtimestamp(dic["created_at"])
        tweet_embed = Embed(color = Color.blue(), description=dic["text"], timestamp = timestamp)
        if replying_to:
            tweet_embed.set_author(name = f"{dic['author_name']} @{dic['screen_name']} の @{dic['replying_to']} へのリプライ", url = dic["url"], icon_url=dic["author_avatar"])
        else:
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

    """except Exception as e:
        logger.error(f"[create_embed]にてエラー: {e}")
        return [], []"""
            
        
"""async def check_duplicate(url: str) -> bool:
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
    if not url:
        return
    target = url.find(".com/")
    new_tweet_url_splitted = url[target+5:]
    new_tweet_url_twitter = f"https://x.com/{new_tweet_url_splitted}"
    duplicate = await check_duplicate(new_tweet_url_twitter)
    if duplicate is False:
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
        response, json = await get_response(twitterurl)
        if response.status != 200:
            logger.error(f"ツイートにアクセスできませんでした。ステータスコード: {response.status}")
            return
        time_before_refresh = JSTTime.timeJST("raw")
        new_tweet_urls = []
        driver.refresh()
        new_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, '(//div[@class="user-text3"])[1]/span')))
        
        new_tweet_url = new_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
        
        if new_tweet_url != last_tweet_url:
            current_tweet_url = new_tweet_url
            count = 1
            while current_tweet_url != last_tweet_url and count < 10:
                count += 1
                new_tweet_urls.append(current_tweet_url)
                print(current_tweet_url)
                current_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, f'(//div[@class="user-text3"])[{count}]/span')))
                
                current_tweet_url = current_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
            
            last_tweet_url = new_tweet_urls[0]
            
            logger.info(f"@AKEndfieldJPの最新ツイートを{count-1}個twstalkerにて取得しました: {new_tweet_urls}")
            
            new_tweet_urls = list(reversed(new_tweet_urls))
            
            for url in new_tweet_urls:
                await publish_tweet_from_nitter_url(url)
        
        time_after_retrieve = JSTTime.timeJST("raw")
        time_passed = time_after_retrieve - time_before_refresh
        logger.debug(f"ツイート取得完了 経過時間: {time_passed.total_seconds()}")

            
    except Exception as e:
        print(f"error: {e}")"""
        
"""@tasks.loop(minutes = 5)
async def ake_feed_retrieve():
    channel = client.get_channel(config.ake_news)
    last_message = await channel.fetch_message(channel.last_message_id)
    last_published_time = last_message.created_at
    response, text = await get_response(feedurl)
    if response.status != 200:
        logger.error(f"ツイートにアクセスできませんでした。ステータスコード: {response.status}")
        return
        
    driver = await asyncio.to_thread(webdriver.Chrome, options = options)
    try:
        driver.set_page_load_timeout(15)
        await asyncio.to_thread(driver.get, feedurl)
        await asyncio.sleep(15)
        source = driver.page_source
        soup = BeautifulSoup(source, "html.parser")
        pre_soup = soup.find("pre")
        pre_content = pre_soup.text
        
    except Exception:
        try:
            driver.set_page_load_timeout(15)
            await asyncio.to_thread(driver.get, feedurl_alter)
            await asyncio.sleep(5)
            source = driver.page_source
            soup = BeautifulSoup(source, "html.parser")
            pre_soup = soup.find("pre")
            pre_content = pre_soup.text
            
        except Exception as e:
            logger.warning(f"フィードにアクセスできませんでした: {type(e)}")
            return
    
    finally:
        await asyncio.to_thread(driver.quit)
    
    decoded_xml = html.unescape(pre_content)
    
    try:
        feed = await asyncio.wait_for(asyncio.to_thread(feedparser.parse, decoded_xml), timeout=10)
    except asyncio.TimeoutError:
        logger.warning("feedparser.parseがタイムアウトしました。")
        return

    new_tweets = []
    for entry in feed["entries"]:
        post_time = entry['published_parsed']
        post_datetime = datetime.datetime(*post_time[:6], tzinfo = datetime.timezone.utc)
        if post_datetime > last_published_time:
            url = entry["link"]
            target = url.find(".org/") if ".org" in url else url.find(".net/")
            #利用するサイトのドメインから決める
            target_end = url.find("#m")
            new_tweet_url_splitted = url[target+5:target_end]
            new_tweet_url_twitter = f"https://x.com/{new_tweet_url_splitted}"
            new_tweets.append(new_tweet_url_twitter)
    new_tweets.reverse()
    for entry in new_tweets:
        embeds, video_urls = await create_embed(entry)
        message = await channel.send(f"<{entry}>", embeds = embeds)
        await message.publish()
        if video_urls:
            for url in video_urls:
                await message.reply(content = f"[ブラウザで開く]({url})")
        logger.info(f"新規ツイート({new_tweet_url_twitter})をアナウンスしました。")"""