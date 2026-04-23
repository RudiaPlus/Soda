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
components_dir = os.path.join(dir, "components")
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

def load_components_json(file_name: str) -> Any:
    with open(os.path.join(components_dir, file_name), "r", encoding="utf-8") as f:
        return json.load(f)

def write_components_json(file_name: str, data: Any) -> None:
    with open(os.path.join(components_dir, file_name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

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
    path = os.path.join(components_dir, file_name)
    data = load_components_json(file_name)

    updated = False

    async def process_comps(comps: list):
        nonlocal updated
        for comp in comps:
            if "_placeholder_filename" in comp:
                url = await _upload_image_and_get_url(comp["_placeholder_filename"])
                comp["content"] = url
                del comp["_placeholder_filename"]
                updated = True

    if isinstance(data, list):
        for item in data:
            if "components" in item:
                await process_comps(item["components"])
    elif isinstance(data, dict):
        if "components" in data:
            await process_comps(data["components"])

    if updated:
        write_components_json(file_name, data)

def _inject_footer_date(component_dict: Dict[str, Any]) -> Dict[str, Any]:
    today = timeJST("raw").strftime("%Y-%m-%d")
    ed = deepcopy(component_dict)
    if "components" in ed:
        for c in ed["components"]:
            if c.get("type") == 10 and isinstance(c.get("content"), str):
                c["content"] = c["content"].replace("footer_placeholder", f"最終更新: {today}")
    return ed

def _find_thread_entry_by_title(title: str) -> Dict[str, str] | None:
    for entry in THREAD_MAP.values():
        if entry.get("title") == title:
            return entry
    return None

async def _clear_thread_messages(thread: discord.Thread) -> None:
    try:
        async for msg in thread.history(limit=None):
            try:
                await msg.delete()
            except Exception:
                continue
    except Exception:
        logger.exception("failed to clear thread messages")

async def send_v2_component_payload(channel: discord.abc.Messageable, payload: dict, edit_id: int = None) -> discord.Message:
    final_payload = {
        "flags": payload.get("flags", 32768),
        "components": payload.get("components", []),
    }
    # send via raw http request
    if not edit_id:
        # discord.abc.Messageable does not have id sometimes? channel.id works for TextChannel/Thread
        route = discord.http.Route("POST", "/channels/{channel_id}/messages", channel_id=channel.id)
        result = await client.http.request(route, json=final_payload)
        return discord.Message(state=client._connection, channel=channel, data=result)
    else:
        route = discord.http.Route("PATCH", "/channels/{channel_id}/messages/{message_id}", channel_id=channel.id, message_id=edit_id)
        result = await client.http.request(route, json=final_payload)
        return discord.Message(state=client._connection, channel=channel, data=result)

async def _send_components_from_json(target: discord.abc.Messageable, file_name: str) -> None:
    data = load_components_json(file_name)
    if isinstance(data, list):
        for item in data:
            injected = _inject_footer_date(item)
            await send_v2_component_payload(target, injected)
    elif isinstance(data, dict):
        injected = _inject_footer_date(data)
        await send_v2_component_payload(target, injected)

@client.tree.command(name="send_welcome_embed", description="componentsフォルダから「はじめに」チャンネルの内容を送信します" ,guild=discord.Object(config.testserverid))
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
    
    try:
        main_file = "welcome_embeds.json"
        await _ensure_images_in_json(main_file, channel)

        main_data = load_components_json(main_file)
        if not isinstance(main_data, list):
            main_data = [main_data]

        for item in main_data:
            injected = _inject_footer_date(item)
            sent_message = await send_v2_component_payload(channel, injected)

            # Thread creation for specific titles
            try:
                title = item.get("_original_title")
                if not title:
                    continue
                title = title.strip()
                entry = _find_thread_entry_by_title(title)
                if entry:
                    thread_file = entry.get("file")
                    if thread_file and sent_message is not None:
                        thread = await sent_message.create_thread(name=f"さらに詳しく - {title}", auto_archive_duration=10080)
                        try:
                            thread_create_message = await channel.fetch_message(channel.last_message_id)
                            if thread_create_message.id != sent_message.id:
                                await thread_create_message.delete()
                        except Exception:
                            pass

                        await _ensure_images_in_json(thread_file, thread)
                        await _send_components_from_json(thread, thread_file)
                        
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
    if not thread or not getattr(thread, "history", None):
        await interaction.followup.send("スレッドが見つかりません")
        return

    try:
        if getattr(thread, "archived", False):
            await thread.edit(archived=False)
    except Exception:
        pass

    try:
        await _clear_thread_messages(thread)
        thread_file = entry.get("file")
        await _ensure_images_in_json(thread_file, thread)
        await _send_components_from_json(thread, thread_file)
        await interaction.followup.send("スレッドを更新しました")
    except Exception as e:
        logger.error(e)
        await interaction.followup.send("更新に失敗しました")

@client.tree.command(name="send_embed", description="filenameからコンポーネントを構築して送信します" ,guild=discord.Object(config.testserverid))
@discord.app_commands.describe(filename = "ファイル名", channel_id = "送信するチャンネルID", edit_id = "編集するメッセージID")
async def send_embed(interaction: discord.Interaction, filename: str, channel_id: str = None, edit_id: str = None) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        channel_id = normalize("NFKC", channel_id) if channel_id else None
        edit_id = normalize("NFKC", edit_id) if edit_id else None
    except TypeError:
        await interaction.followup.send("不正な値が渡されました")
        return
    if not os.path.exists(os.path.join(components_dir, filename)):
        await interaction.followup.send("ファイルが存在しません")
        return
    
    target_channel = interaction.channel
    if channel_id:
        tc = client.get_channel(int(channel_id))
        if not tc:
            await interaction.followup.send("チャンネルが見つかりません")
            return
        target_channel = tc

    try:
        data = load_components_json(filename)
        if isinstance(data, list):
            # fallback for lists in send_embed: just send the first element or all
            # send_embed in past was sending all embeds in one message. For components V2, we might send them sequentially if it's a list.
            if edit_id:
                # edit only handles the first item payload then limits
                injected = _inject_footer_date(data[0])
                await send_v2_component_payload(target_channel, injected, int(edit_id))
            else:
                for item in data:
                    injected = _inject_footer_date(item)
                    await send_v2_component_payload(target_channel, injected)
        else:
            injected = _inject_footer_date(data)
            await send_v2_component_payload(target_channel, injected, int(edit_id) if edit_id else None)
        await interaction.followup.send("送信が完了しました")
    except Exception as e:
        logger.error(e)
        await interaction.followup.send("送信に失敗しました")
