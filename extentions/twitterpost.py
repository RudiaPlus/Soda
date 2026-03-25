import asyncio
import datetime
import re
from typing import List, Optional, Tuple, Union

import aiohttp
from discord import Color, Embed
from discord.ext import tasks
from tweety import Twitter
from tweety.types import (
    HOME_TIMELINE_TYPE_FOLLOWING,
    ConversationThread,
    SelfThread,
    Tweet,
)

from extentions import log
from extentions.aclient import client
from extentions.config import config

# Logger and constants
logger = log.setup_logger()
APP: Optional[Twitter] = None

FXTWITTER_ENDPOINT = "https://api.fxtwitter.com/status/{id}"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate, br",
}

TARGET_USERNAME = "AKEndfieldJP"


def date_comparator(
    date1: Union[datetime.datetime, str],
    date2: Union[datetime.datetime, str],
    fmt: str = "%Y-%m-%d %H:%M:%S%z",
) -> int:
    """Compare two datetimes (aware) or formatted strings.

    Returns 1 if date1 > date2, -1 if date1 < date2, 0 if equal.
    """
    d1 = datetime.datetime.strptime(date1, fmt) if isinstance(date1, str) else date1
    d2 = datetime.datetime.strptime(date2, fmt) if isinstance(date2, str) else date2
    return (d1 > d2) - (d1 < d2)


async def _expand_tweets(items) -> List[Tweet]:
    """Flatten threads/conversations into a simple Tweet list."""
    result: List[Tweet] = []
    for item in items:
        if isinstance(item, (SelfThread, ConversationThread)):
            result.extend(await _expand_tweets(item.tweets))
        elif isinstance(item, Tweet):
            result.append(item)
    return result


async def _channel_for_username(username: str):
    if username == TARGET_USERNAME:
        return client.get_channel(config.ake_news)
    return None


async def _filter_new_tweets(tweets: List[Tweet], username: str) -> Optional[List[Tweet]]:
    """Filter tweets posted after the last bot message in target channel."""
    channel = await _channel_for_username(username)
    if channel is None:
        return None

    # Determine last published time by the bot in the channel.
    try:
        last_message = await channel.fetch_message(channel.last_message_id)
    except Exception as e:
        logger.warning(f"最後のメッセージ取得に失敗しました: {e} / 履歴から探索します")
        last_message = None
        async for message in channel.history(limit=20):
            if message.author.id == client.user.id:
                last_message = message
                break
        if last_message is None:
            # Fallback to now-1day to avoid flooding on first run.
            last_published_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        else:
            last_published_time = last_message.created_at
    else:
        last_published_time = last_message.created_at

    expanded = await _expand_tweets(tweets)
    own_new = [
        t
        for t in expanded
        if t.author.screen_name == username and t.created_on and date_comparator(t.created_on, last_published_time) == 1
    ]
    if not own_new:
        return None
    return sorted(own_new, key=lambda t: t.created_on)


async def setup_app():
    """Authenticate Tweety client and verify timeline access."""
    async def authenticate(account_name: str, account_token: str) -> Twitter:
        twitter = Twitter(account_name)
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                await twitter.load_auth_token(account_token)
                logger.info(f"Twitter認証に成功: {account_name}")
                tl = await twitter.get_home_timeline(timeline_type=HOME_TIMELINE_TYPE_FOLLOWING)
                if not tl:
                    raise ValueError("Home timeline is empty")
                logger.debug(f"ホームTL取得成功 / 先頭ツイート: {tl.tweets[0].text[:30]}...")
                return twitter
            except Exception as e:
                logger.error(f"Twitter認証に失敗 ({account_name}): {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(4 ** attempt)
                else:
                    raise

    global APP
    try:
        APP = await authenticate(config.twitter_account_name, config.twitter_account_token)
    except Exception as e:
        logger.error(f"Twitterクライアントの初期化に失敗しました。Twitter関連機能はスキップされます: {e}")
        APP = None


async def gather_reed_arts(since: datetime.datetime):
    """Search and post recent Reed-related arts since given date (JST)."""
    # Keywords intentionally broad to collect fan arts; limit by media and retweets.
    query = (
        '("苇芦" OR "Reed" OR "loughshinny" OR "爱因威" OR "拉芙希妮" OR '
        '"ラフシニー" OR "エブラナ" OR "Eblana" OR "リード" OR "死者" OR '
        '"ネクラス" OR "Necrass") min_retweets:3 '
        '(アークナイツ OR 明日方舟 OR Arknights) (filter:images OR filter:videos)'
    )
    since_str = (since - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    query += f" since:{since_str}"

    try:
        assert APP is not None, "Twitterクライアント未初期化"
        search_results = await APP.search(keyword=query)
        tweets: List[Tweet] = getattr(search_results, "results", []) or []
        channel = client.get_channel(1393533104391589952)  # Reed Arts channel ID
        for t in tweets:
            await channel.send(t.url.replace("x.com", "fxtwitter.com"))
    except Exception as e:
        logger.error(f"Reed Arts 検索に失敗: {e}")


async def _notify(tweets: List[Tweet], username: str):
    latest = await _filter_new_tweets(tweets, username)
    if not latest:
        return

    channel = await _channel_for_username(username)
    if channel is None:
        return

    for t in latest:
        url = t.url
        embeds, video_urls = await create_embed(url)
        msg = await channel.send(f"<{url}>", embeds=embeds)
        try:
            await msg.publish()
        except Exception:
            # Non-news channels can't publish; ignore.
            pass
        for v in video_urls:
            await msg.reply(content=f"[ブラウザで開く]({v})")
        logger.info(f"新規ツイートをアナウンス: {url}")


async def _fetch_list_tweets(api: Twitter):
    try:
        notifications = await api.get_list_tweets(list_id=config.notify_list_id)
        if not notifications:
            return None
        return notifications.tweets
    except Exception as e:
        logger.error(f"通知リストの取得に失敗: {e}")
        return None


@tasks.loop(minutes=5)
async def ake_tweet_retrieve():
    global APP
    if APP is None:
        logger.debug("Twitterクライアント未接続")
        return
    try:
        tweets = await _fetch_list_tweets(APP)
        if not tweets:
            logger.debug("新着ツイートなし / 取得失敗")
            return
        await _notify(tweets, TARGET_USERNAME)
    except Exception as e:
        logger.error(f"ake_tweet_retrieveにてエラー: {e}")


async def get_response(url: str, as_json: bool = False):
    """HTTP GET with robust content-encoding handling.

    Forces manual decompression to work around servers replying with zstd
    (or other encodings) that aiohttp doesn't decode by default.
    """
    async with aiohttp.ClientSession(
        timeout=HTTP_TIMEOUT,
        headers=HTTP_HEADERS,
        auto_decompress=False,
    ) as session:
        async with session.get(url) as r:
            raw = await r.read()
            encoding = (r.headers.get("Content-Encoding") or "").lower()

            try:
                if encoding == "zstd":
                    import zstandard as zstd  # type: ignore
                    raw = zstd.ZstdDecompressor().decompress(raw)
                elif encoding in ("br",):
                    import brotli  # type: ignore
                    raw = brotli.decompress(raw)
                elif encoding in ("gzip",):
                    import gzip
                    raw = gzip.decompress(raw)
                elif encoding in ("deflate",):
                    import zlib
                    raw = zlib.decompress(raw)
            except Exception:
                pass

            if not as_json:
                charset = r.charset or "utf-8"
                try:
                    text = raw.decode(charset, errors="replace")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")
                return r, text

            import json
            try:
                return r, json.loads(raw)
            except Exception:
                return r, {}


async def create_embed(content: str) -> Tuple[List[Embed], List[str]]:
    """Create Tweet embeds and collect video URLs from an x.com/twitter.com link."""
    pattern = r"https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/(\d+)"
    ids = [m.group(1) for m in re.finditer(pattern, content)]
    if not ids:
        return [], []

    items = []
    for tid in ids:
        resp, payload = await get_response(FXTWITTER_ENDPOINT.format(id=tid), as_json=True)
        if resp.status != 200:
            continue
        data = payload.get("tweet", {})
        author = data.get("author", {})
        media_urls: List[str] = []
        video_urls: List[str] = []
        for kind, medias in (data.get("media") or {}).items():
            if kind not in ("photos", "videos"):
                continue
            for m in medias:
                url = m.get("url")
                if not url:
                    continue
                if kind == "photos":
                    media_urls.append(url)
                else:
                    video_urls.append(url)

        items.append(
            {
                "url": data.get("url"),
                "author_name": author.get("name"),
                "screen_name": author.get("screen_name"),
                "author_avatar": author.get("avatar_url"),
                "text": data.get("text", ""),
                "created_at": data.get("created_timestamp", 0),
                "media_urls": media_urls,
                "video_urls": video_urls,
                "replying_to": data.get("replying_to"),
            }
        )

    embeds: List[Embed] = []
    videos: List[str] = []
    for d in items:
        ts = datetime.datetime.fromtimestamp(d["created_at"]) if d["created_at"] else None
        base = Embed(color=Color.blue(), description=d["text"], timestamp=ts)
        if d.get("replying_to"):
            base.set_author(
                name=f"{d['author_name']} @{d['screen_name']} の @{d['replying_to']} へのリプライ",
                url=d["url"],
                icon_url=d.get("author_avatar"),
            )
        else:
            base.set_author(
                name=f"{d['author_name']} @{d['screen_name']}",
                url=d["url"],
                icon_url=d.get("author_avatar"),
            )
        embeds.append(base)

        for u in d["media_urls"]:
            e = Embed(color=Color.blue(), description=f"[ブラウザで開く]({u})")
            e.set_image(url=u)
            embeds.append(e)
        for v in d["video_urls"]:
            videos.append(v)

    return embeds, videos
