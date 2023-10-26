from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from discord.ext import tasks
from extentions import log, config
from extentions.aclient import client
import os


dir = os.path.abspath(__file__ + "/../")
logger = log.setup_logger(__name__)
test = config.test

if config.web == True:
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
    
@tasks.loop(seconds=60)
async def ake_tweet_retrieve():
    try:
        driver.refresh()
        new_tweet = wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "]')))
        
        try:
            pinned = new_tweet.find_element(By.XPATH, ".//div//div[@class='pinned']")
            new_tweet=wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@class="timeline-item "][2]')))
        except:
            pass
        
        new_tweet_url = new_tweet.find_element(By.XPATH, ".//a").get_attribute("href")
        
        if new_tweet_url != last_tweet_url:
            logger.info(f"@AKEndfieldJPの最新ツイートをnitterにて取得しました: {new_tweet_url}")
            target = new_tweet_url.find(".net/")
            target_end = new_tweet_url.find("#m")
            new_tweet_url_splitted = new_tweet_url[target+5:target_end]
            new_tweet_url_vx = f"https://vxtwitter.com/{new_tweet_url_splitted}"
            channel = client.get_channel(config.ake_news)
            await channel.send(new_tweet_url_vx)
            
    except Exception as e:
        print(f"error: {e}")