import discord
from unicodedata import normalize
import json
import os
from extentions.aclient import client
from extentions import log
from extentions.config import config
from extentions.JSTTime import timeJST
from copy import deepcopy
from typing import Any, Dict, List

logger = log.setup_logger()
dir = os.path.abspath(os.path.dirname(__file__))
embeds_dir = os.path.join(dir, "embeds")
images_dir = os.path.join(dir, "images")
THREAD_MAP = {
    "important_points": {
        "title": "⚠️ 注意事項(要点) ⚠️",
        "file": "important_points.json",
    },
    "rules": {
        "title": "📝 サーバールールについて 📝",
        "file": "rules.json",
    },
}

def load_embed_json(file_name: str) -> dict:
    with open(os.path.join(embeds_dir, file_name), "r", encoding="utf-8") as f:
        return json.load(f)

def write_embed_json(file_name: str, data: dict) -> None:
    with open(os.path.join(embeds_dir, file_name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
def _is_image_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""

async def _upload_image_and_get_url(filename: str) -> str:
    asset_channel = client.get_channel(config.asset_channel)
    if not asset_channel:
        raise ValueError("Asset channel not found in config.")
    path = os.path.join(images_dir, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"image not found: {filename}")
    msg = await asset_channel.send(file=discord.File(path))
    url = msg.attachments[0].url if msg.attachments else ""
    if not url:
        raise RuntimeError(f"failed to upload image: {filename}")
    return url

async def _ensure_images_in_json(file_name: str, upload_target: discord.abc.Messageable) -> None:
    # Load JSON, scan for image placeholders, upload and rewrite JSON with url dicts
    path = os.path.join(embeds_dir, file_name)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = False

    def handle_embed_dict(ed: Dict[str, Any]) -> None:
        nonlocal updated
        if "image" in ed and _is_image_placeholder(ed["image"]):
            updated = True
            ed["image"] = {"url": None, "_placeholder_filename": ed["image"]}

    # Normalize structure and mark placeholders first
    if isinstance(data, list):
        for item in data:
            # Item can be an embed dict, or a message dict with embeds list
            if isinstance(item, dict) and "embeds" in item and isinstance(item["embeds"], list):
                for emb in item["embeds"]:
                    if isinstance(emb, dict):
                        handle_embed_dict(emb)
            elif isinstance(item, dict):
                handle_embed_dict(item)

    # Upload and fill urls where needed
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "embeds" in item and isinstance(item["embeds"], list):
                for emb in item["embeds"]:
                    if isinstance(emb, dict) and isinstance(emb.get("image"), dict):
                        if emb["image"].get("url") is None and emb["image"].get("_placeholder_filename"):
                            url = await _upload_image_and_get_url(emb["image"]["_placeholder_filename"])
                            emb["image"] = {"url": url}
                            updated = True
            elif isinstance(item, dict) and isinstance(item.get("image"), dict):
                if item["image"].get("url") is None and item["image"].get("_placeholder_filename"):
                    url = await _upload_image_and_get_url(item["image"]["_placeholder_filename"])
                    item["image"] = {"url": url}
                    updated = True

    if updated:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

def _inject_footer_date(embed_dict: Dict[str, Any]) -> Dict[str, Any]:
    ed = deepcopy(embed_dict)
    footer = ed.get("footer")
    if isinstance(footer, str):
        today = timeJST("raw").strftime("%Y-%m-%d")
        ed["footer"] = {"text": f"最終更新: {today}"}
    return ed

def _find_thread_entry_by_title(title: str) -> Dict[str, str] | None:
    for entry in THREAD_MAP.values():
        if entry.get("title") == title:
            return entry
    return None

def _chunk_embeds(embeds: List[discord.Embed], chunk_size: int = 10) -> List[List[discord.Embed]]:
    return [embeds[i:i + chunk_size] for i in range(0, len(embeds), chunk_size)]

async def _clear_thread_messages(thread: discord.Thread) -> None:
    try:
        async for msg in thread.history(limit=None):
            try:
                await msg.delete()
            except Exception:
                continue
    except Exception:
        logger.exception("failed to clear thread messages")

async def _send_embeds_from_json(target: discord.abc.Messageable, file_name: str) -> None:
    embeds: List[discord.Embed] = []
    for item in load_embed_json(file_name):
        if isinstance(item, dict) and "embeds" in item and isinstance(item["embeds"], list):
            for emb in item["embeds"]:
                if isinstance(emb, dict):
                    embeds.append(discord.Embed.from_dict(_inject_footer_date(emb)))
        elif isinstance(item, dict):
            embeds.append(discord.Embed.from_dict(_inject_footer_date(item)))
    for chunk in _chunk_embeds(embeds):
        await target.send(embeds=chunk)
        
async def send_embed_to_channel(channel: discord.TextChannel, file_name: str, edit_id: int = None) -> None:
    embeds = []
    for embed in load_embed_json(file_name):
        embeds.append(discord.Embed.from_dict(_inject_footer_date(embed)))
    if not edit_id:
        await channel.send(embeds=embeds)
    else:
        message = await channel.fetch_message(edit_id)
        await message.edit(embeds=embeds)
        
@client.tree.command(name="send_welcome_embed", description="embedsフォルダから「はじめに」チャンネルの内容を送信します" ,guild=discord.Object(config.testserverid))
@discord.app_commands.describe(channel_id = "送信するチャンネルID", edit_id = "編集するメッセージID", recreate_thread = "スレッドを再作成します(T/F)")
async def send_welcome_embed(interaction: discord.Interaction, channel_id: str = None, edit_id: str = None, recreate_thread: str = "F") -> None:
    await interaction.response.defer(ephemeral=True)
    channel_id = channel_id.strip() if channel_id else "1428531139605430393"
    try:
        channel_id = normalize("NFKC", channel_id) if channel_id else None
        edit_id = normalize("NFKC", edit_id) if edit_id else None
    except TypeError:
        await interaction.followup.send("不正な値が渡されました")
        return
    
    if channel_id:
        channel = client.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send("チャンネルが見つかりません")
            return
        
    else:
        channel = interaction.channel
    
    # Build and send welcome embeds, creating threads for specific titles
    try:
        main_file = "welcome_embeds.json"
        await _ensure_images_in_json(main_file, channel)

        main_data = load_embed_json(main_file)

        for item in main_data:
            sent_message: discord.Message | None = None

            if isinstance(item, dict) and "embeds" in item and isinstance(item["embeds"], list):
                embeds_objs: List[discord.Embed] = []
                for emb in item["embeds"]:
                    if isinstance(emb, dict):
                        embeds_objs.append(discord.Embed.from_dict(_inject_footer_date(emb)))
                sent_message = await channel.send(content=item.get("content", ""), embeds=embeds_objs)
            elif isinstance(item, dict):
                emb = discord.Embed.from_dict(_inject_footer_date(item))
                sent_message = await channel.send(embed=emb)
            else:
                continue

            # Thread creation for specific titles
            try:
                title = None
                if isinstance(item, dict) and isinstance(item.get("title"), str):
                    title = item["title"].strip()
                entry = _find_thread_entry_by_title(title) if title else None
                if entry:
                    thread_file = entry.get("file")
                    if thread_file and sent_message is not None:
                        thread = await sent_message.create_thread(name=f"さらに詳しく - {title}", auto_archive_duration=10080)
                        # Try to delete the auto thread-create message, if any
                        try:
                            thread_create_message = await channel.fetch_message(channel.last_message_id)
                            if thread_create_message.id != sent_message.id:
                                await thread_create_message.delete()
                        except Exception:
                            pass

                        await _ensure_images_in_json(thread_file, thread)
                        thread_embeds_data = load_embed_json(thread_file)
                        thread_embeds: List[discord.Embed] = [
                            discord.Embed.from_dict(_inject_footer_date(e)) for e in thread_embeds_data if isinstance(e, dict)
                        ]
                        if thread_embeds:
                            await thread.send(embeds=thread_embeds)
                        
            except Exception as e:
                logger.error(e)
                continue

        await interaction.followup.send("送信が完了しました")
    except Exception as e:
        logger.error(e)
        await interaction.followup.send("送信に失敗しました")

@client.tree.command(name="update_welcome_thread", description="thread_mapから該当スレッドを再展開します", guild=discord.Object(config.testserverid))
@discord.app_commands.describe(thread_key="thread_mapの名前", thread_channel_id="対象スレッドID")
async def update_welcome_thread(interaction: discord.Interaction, thread_key: str, thread_channel_id: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        thread_key = normalize("NFKC", thread_key)
        thread_channel_id = normalize("NFKC", thread_channel_id)
    except TypeError:
        await interaction.followup.send("不正な値が渡されました")
        return

    entry = THREAD_MAP.get(thread_key)
    if not entry:
        keys = ", ".join(THREAD_MAP.keys())
        await interaction.followup.send(f"thread_mapが見つかりません: {thread_key}\n利用可能: {keys}")
        return

    thread = client.get_channel(int(thread_channel_id))
    if not thread or not isinstance(thread, discord.Thread):
        await interaction.followup.send("スレッドが見つかりません")
        return

    try:
        if thread.archived:
            await thread.edit(archived=False)
    except Exception:
        pass

    try:
        await _clear_thread_messages(thread)
        thread_file = entry.get("file")
        await _ensure_images_in_json(thread_file, thread)
        await _send_embeds_from_json(thread, thread_file)
        await interaction.followup.send("スレッドを更新しました")
    except Exception as e:
        logger.error(e)
        await interaction.followup.send("更新に失敗しました")

@client.tree.command(name="send_embed", description="filenameから埋め込みを送信します" ,guild=discord.Object(config.testserverid))
@discord.app_commands.describe(filename = "ファイル名", channel_id = "送信するチャンネルID", edit_id = "編集するメッセージID")
async def send_embed(interaction: discord.Interaction, filename: str, channel_id: str = None, edit_id: str = None) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        channel_id = normalize("NFKC", channel_id) if channel_id else None
        edit_id = normalize("NFKC", edit_id) if edit_id else None
    except TypeError:
        await interaction.followup.send("不正な値が渡されました")
        return
    if not os.path.exists(os.path.join(embeds_dir, filename)):
        await interaction.followup.send("ファイルが存在しません")
        return
    
    if channel_id:
        channel = client.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send("チャンネルが見つかりません")
            return
        await send_embed_to_channel(channel, filename, edit_id=edit_id)
        
    else:
        await send_embed_to_channel(interaction.channel, filename, edit_id=edit_id)
