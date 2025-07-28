import asyncio
import json
import os
import sqlite3
from datetime import datetime, timedelta

import discord
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from extentions import JSTTime, log
from extentions.aclient import client
from extentions.config import config
from mcp_use import MCPClient, MCPAgent


logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")

db_path = os.path.join(dir, "db", "chat_history.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cur = conn.cursor()
load_dotenv()

# 短期的な会話履歴テーブル
cur.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
''')
cur.execute("CREATE INDEX IF NOT EXISTS idx_user_id_timestamp ON chat_history (user_id, timestamp)")

# 長期記憶用テーブル
cur.execute('''
    CREATE TABLE IF NOT EXISTS long_term_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        UNIQUE(user_id, key)
    )
''')
conn.commit()

mcp_config = {
    "mcpServers": {
        "playwright": {
            "command": "C:\\Program Files\\nodejs\\npx.cmd",
            "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated"],
            "url": "https://arknights.wikiru.jp/",
            "selector": "#body",
            "exclude_selectors": [".adsbygoogle"],
            "env": {
                "DISPLAY": ":1"
            }
        }
    }
}

arknights_agent_prompt = """
あなたはアークナイツについて聞かれたら答えるエージェントです。ユーザーからアークナイツの事に聞かれたら、聞かれている内容について簡潔に纏めて正確に教えてください。聞かれた内容に合わせて、以下の通りにWikiのURLを参照し、最後に参照したURLを"参照: [有志Wiki](https://example.com)"という風に追記してください
- キャラクターについて聞かれた時 https://arknights.wikiru.jp/?キャラクター一覧 でキャラクターが存在することを確認し、存在する場合そのページに遷移します。
- イベントについて聞かれた時 https://arknights.wikiru.jp/?イベント一覧 でイベントが存在することを確認し、存在する場合そのページに遷移します。
- 統合戦略について聞かれた時 https://arknights.wikiru.jp/?統合戦略 の「「統合戦略」とは」から該当するイベントを探し、そのページに遷移します。統合戦略はローグライク、統合戦略#1、〇〇ローグという呼び方をされます。次が特別な呼び方の例です(「サーミローグ」→統合戦略#4、「古城」、「ファントムローグ」→統合戦略#2、「ミヅキローグ」→統合戦略#3、「サルカズローグ」→統合戦略#5)
    - 統合戦略において「秘宝」について聞かれている場合、それぞれのイベントページから「秘宝一覧」のリンクに遷移し、該当する秘宝を探します。
    - 統合戦略においてステージについて聞かれている場合、それぞれのイベントページの「ステージ一覧」からステージを探し、該当するステージのリンクに遷移します。
それぞれ該当するものが見つからなかったら、存在しないことを返答します。最初から上記以外のURLにアクセスしないでください。上記以外について聞かれた時は、今は対応していない旨を返答します。
"""

mcp_client = MCPClient(mcp_config)
model = ChatOpenAI(model="gpt-4.1-mini-2025-04-14", temperature=1.0)
agent_model = ChatOpenAI(model="gpt-4.1-mini-2025-04-14", temperature=0.0)
agent = MCPAgent(llm=agent_model, client=mcp_client, max_steps=5, system_prompt=arknights_agent_prompt, auto_initialize=True)


async def add_message_to_db(user_id: str, role: str, content: str):
    #データベースにメッセージを追加し、挿入された行のIDを返す
    timestamp = datetime.now(tz=JSTTime.tz_JST).isoformat()
    cur.execute(
        "INSERT INTO chat_history (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, role, content, timestamp)
    )
    conn.commit()
    return cur.lastrowid

async def get_history_from_db(user_id: str, limit: int = 20):
    #データベースからユーザーのチャット履歴を取得
    cur.execute(
        "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

async def delete_message_from_db(message_id: int):
    #データベースからメッセージを削除
    cur.execute("DELETE FROM chat_history WHERE id = ?", (message_id,))
    conn.commit()
    
async def update_long_term_memory(user_id: str, key: str, value: str):
    """長期記憶を追加または更新する"""
    timestamp = datetime.now(tz=JSTTime.tz_JST).isoformat()
    cur.execute("""
        INSERT INTO long_term_history (user_id, key, value, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET
        value = excluded.value,
        timestamp = excluded.timestamp
    """, (user_id, key, value, timestamp))
    conn.commit()

async def get_long_term_memories(user_id: str) -> dict:
    """ユーザーの長期記憶を辞書として取得する"""
    cur.execute("SELECT key, value FROM long_term_history WHERE user_id = ?", (user_id,))
    rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


async def arknights_agent_with_chat_memory(user: discord.User, question: str):
    user_id_str = str(user.id)
    user_message_id = await add_message_to_db(user_id_str, "user", question)

    try:
        response = await agent.run(question)
        await add_message_to_db(user_id_str, "assistant", response)
        return response
    except Exception as e:
        logger.error(f"Error in direct_chat: {e}")
        await delete_message_from_db(user_message_id)
        return None

async def direct_chat(user: discord.User, message: discord.Message):
    user_id_str = str(user.id)
    
    # ユーザーのメッセージをDBに追加 (エラー時に削除するためIDを保持)
    user_message_id = await add_message_to_db(user_id_str, "user", message.content)

    # --- APIに渡すメッセージリストを作成 ---
    # 1. 長期記憶からシステムプロンプトを動的に生成
    long_term_memories = await get_long_term_memories(user_id_str)
    system_prompt_content = config.dynamic["chat_starting_prompt"] + json.dumps(config.dynamic["chat_persona"], ensure_ascii=False)
    if long_term_memories:
        memory_items = []
        if 'nickname' in long_term_memories:
            memory_items.append(f"- ユーザーの呼び方は「{long_term_memories['nickname']}」です。\n")
        # 他の記憶項目もここに追加可能
        
        if memory_items:
            system_prompt_content += "\n\n【ユーザーに関する記憶】\n" + "\n".join(memory_items)
            system_prompt_content += "\nこの記憶を会話に活かしてください。"

    # 2. 短期記憶（直近の会話履歴）を取得し、システムプロンプトと結合
    # システムプロンプトは動的に生成したもので上書きするため、履歴からは除外
    short_term_history = await get_history_from_db(user_id_str, limit=19)
    history_without_system_prompt = [msg for msg in short_term_history if msg["role"] != "system"]

    messages_for_api = [{"role": "system", "content": system_prompt_content}]
    messages_for_api.extend(history_without_system_prompt)
    
    async with message.channel.typing():
        try:
            
            response = await model.ainvoke(messages_for_api)
            output_text = response.content
            await add_message_to_db(user_id_str, "assistant", output_text)
            await message.channel.send(output_text)
            return output_text
        
        except Exception as e:
            logger.error(f"Error in direct_chat: {e}")
            await message.channel.send("ごめんなさい、エラーが発生したみたいです。少し待ってからもう一度試してみてください。")
            await delete_message_from_db(user_message_id)
            return None