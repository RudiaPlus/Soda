from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from discord.ext import tasks
from extentions import log, config
from extentions.aclient import client
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
        
        wait = WebDriverWait(driver, 20)
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
    new_tweet_url_vx = f"https://vxtwitter.com/{new_tweet_url_splitted}"
    duplicate = await check_duplicate(new_tweet_url_vx)
    if duplicate == False:
        channel = client.get_channel(config.ake_news)
        message = await channel.send(new_tweet_url_vx)
        await message.publish()
        logger.info(f"新規ツイート({new_tweet_url_vx})をアナウンスしました。")
    else:
        logger.info(f"新規ツイート({new_tweet_url_vx})は既にアナウンスされています。投稿を中止しました。")
   
@tasks.loop(minutes=3)
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