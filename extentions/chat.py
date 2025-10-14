import asyncio
import json
import os
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4

import chromadb
import discord
import dotenv
import torch
from chromadb.config import Settings
from dotenv import load_dotenv
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_chroma import Chroma
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from tavily import AsyncTavilyClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from extentions import JSTTime, log
from extentions.aclient import client
from extentions.config import config

dotenv.load_dotenv()

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

async def get_embedding_model()->HuggingFaceEmbeddings:
    """
    HuggingFaceの事前学習済みのモデルをロードして返す関数
    戻り値:
        HuggingFaceEmbeddingsオブジェクト: 事前学習済みのモデルをラップしたオブジェクト
    """
    return HuggingFaceEmbeddings(
        model_name="sbintuitions/sarashina-embedding-v1-1b"
    )

async def get_akdb_conn():
    akdb_client = chromadb.HttpClient(
        host="localhost",
        port=8000,
        settings = Settings(allow_reset=True, anonymized_telemetry=False)
    )
    return akdb_client

embedding_model = None
db_client = None
model=None
agent_model=None
ak_collection=None
ak_retriever=None
analyze_model=None
search = None
reranker = None

async def init_models():
    global db_client, embedding_model, model, agent_model, ak_collection, ak_retriever, analyze_model, search, reranker
    db_client = await get_akdb_conn()
    model = ChatOpenAI(model="gpt-5-chat-latest")
    analyze_model = ChatOpenAI(model = "gpt-5")
    agent_model = ChatOpenAI(model="gpt-5-mini")
    embedding_model = await get_embedding_model()
    
    ak_collection = Chroma(
        collection_name = "arknights_wiki",
        embedding_function=embedding_model,
        client=db_client
    )
    retriever = ak_collection.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 50, "fetch_k": 100, "lambda_mult": 0.8},
    )
    
    search = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    encoder = HuggingFaceCrossEncoder(model_name = "hotchpotch/japanese-reranker-xsmall-v2")
    reranker = CrossEncoderReranker(model=encoder, top_n=10)
    ak_retriever = ContextualCompressionRetriever(
        base_compressor=reranker,
        base_retriever=retriever
    )

async def similar_document_search(query: str):
    results = await ak_retriever.ainvoke(input=query)
    
    # 結果が空の場合は警告を出して空の結果を返す
    logger.debug(f"Query: {query}, Results: {len(results)} documents found")
    if not results:
        logger.warning("No relevant documents found for the query.")
        return None
    return results


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
    
    if key == "delete_memory":
        longtime_memory = await get_long_term_memories(user_id)
        # "delete_memory"の場合は、指定された内容を削除
        if value in longtime_memory.values():
            # キーを取得して削除
            key_to_delete = next((k for k, v in longtime_memory.items() if v == value), None)
            if key_to_delete:
                cur.execute("DELETE FROM long_term_history WHERE user_id = ? AND key = ?", (user_id, key_to_delete))
                conn.commit()
                return
            
        else:
            logger.warning(f"指定された内容 '{value}' は長期記憶に存在しません。削除できませんでした。")
            return
    
    if key == "store_memory":
        #キーは"memory_[uuid]"の形式で保存
        uuid = uuid4()
        key = f"memory_{uuid}"

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

def get_metadata_dict(meta_item):
    """
    Safely extracts the metadata dictionary from a potentially nested list.
    Handles cases where the item is a dictionary or a list containing a dictionary.
    """
    if isinstance(meta_item, dict):
        return meta_item
    if isinstance(meta_item, list) and meta_item and isinstance(meta_item[0], dict):
        # Handles the case where meta_item is a list like: [{'key': 'value'}]
        return meta_item[0]
    # Return an empty dictionary for other unexpected formats to prevent errors
    return {}

async def analyze_message(user_id_str: str, user_message: str, history: str):

    prompt = f'''
    あなたは、ユーザーとの会話を分析し、後続のシステムが必要とするアクションを判断する、優秀なアシスタントです。
    特に、アークナイツのWikiデータベースとWeb検索を効率的に活用するための検索クエリ生成を得意とします。

    # 指示
    以下の会話履歴とユーザーの最新メッセージを分析し、思考プロセスに従って最適なアクションを判断し、指定されたJSON形式で出力してください。

    # 思考プロセス
    1.  まず、ユーザーの最新メッセージの意図を分析します。これは単純な挨拶や雑談ですか？ それとも特定の情報を求めていますか？
    2.  情報を求めている場合、その内容はアークナイツのWikiにありそうですか？（例：キャラクターの性能、イベント攻略、世界観） それともWeb全体で検索すべき新しい情報や一般的な知識ですか？
    3.  **Wiki検索クエリの生成**:
        -   Wikiに情報がありそうな場合、ベクトル検索で最もヒットしやすいように、具体的で詳細な検索クエリを生成します。
        -   **クエリのヒント**: Wikiには「キャラクター一覧」「統合戦略」といったページが存在し、各ページは「# プロファイル」「## スキル」のような見出しで構成されています。これらの構造を意識し、例えば「統合戦略#2 ファントムと緋き貴石における秘宝「騎士の戒律」の効果と入手方法」のように、具体的なページ名やセクション名を推測して含めると、より精度が向上します。
        -   アークナイツに関しない質問の場合は`null`にしてください。
    4.  **Web検索クエリの生成**:
        -   最新情報（例: 次のイベント、メンテナンス情報）、キャラクターの最新評価、またはアークナイツ以外の一般的な質問の場合に生成します。
        -   このクエリは、後続の検索エージェント（例: travily）が直接理解できるように、**ユーザーの質問を簡潔にまとめた文章形式**にしてください。
        - 例: 「アークナイツのホルハイヤの最新評価と使い方は？」
    5.  **記憶操作の判断**:
        -   ユーザーが「覚えて」「記憶して」のように明示的に指示した場合のみ、`memory_operation`を`"store"`とし、記憶すべき内容を`memory_content`に設定します。
        -   ユーザーが「忘れて」のように明示的に指示した場合のみ、`memory_operation`を`"delete"`とし、忘れるべき内容を`memory_content`に設定します。
    6.  上記以外（単純な挨拶や雑談）の場合は、すべての検索・記憶に関する値を`null`または`false`にしてください。

    # 会話履歴
    {history}

    # ユーザーの最新メッセージ
    {user_message}

    # 出力JSONフォーマット
    {{
        "is_retrieval_needed": boolean, // 情報検索が必要か
        "retrieval_query": "string | null", // Wiki検索用クエリ
        "web_search_query": "string | null",  // Web検索用クエリ (ユーザーの質問の要約)
        "memory_operation": "store | delete | null", // "store" または "delete" のいずれか。nullの場合は記憶操作なし
        "memory_content": "string | null" // 記憶する内容。nullの場合は記憶操作なし
    }}
    
    # 出力例
    // 例1: キャラクターの詳細な情報について
    {{
        "is_retrieval_needed": true,
        "retrieval_query": "アークナイツのキャラクター「ホルハイヤ」の特性、素質、スキル2「焦熱が如き渇望」の詳細、昇進素材と特化素材",
        "web_search_query": "アークナイツのホルハイヤの最新評価と使い方",
        "memory_operation": null,
        "memory_content": null
    }},
    // 例2: 記憶の指示
    {{
        "is_retrieval_needed": false,
        "retrieval_query": null,
        "web_search_query": null,
        "memory_operation": "store",
        "memory_content": "ユーザーの好きなオペレーターはリード"
    }}
    '''

    response = await analyze_model.ainvoke(prompt)
    logger.debug(f"Analyze response: {response.content}")
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        logger.error(f"JSONの解析に失敗しました: {response.content}")
        # デフォルトの応答（検索しないなど）を返す
        return {"is_retrieval_needed": False, "retrieval_query": None, "web_search_query": None}
    
async def handle_memory_operation(analysis_result: dict, user_id_str: str):
    operation = analysis_result.get("memory_operation")
    content = analysis_result.get("memory_content")
    
    if operation is None or content is None:
        return ""
    
    try:
        if operation == "store":
            # 長期記憶に保存
            await update_long_term_memory(user_id_str, "store_memory", content)
            return f"「{content}」を記憶しました。"
        elif operation == "delete":
            # 長期記憶から削除
            await update_long_term_memory(user_id_str, "delete_memory", content)
            return f"「{content}」を忘れました。"
        else:
            logger.warning(f"Unknown memory operation: {operation}")
            return ""
        
    except Exception as e:
        logger.error(f"メモリ操作中にエラーが発生しました: {e}")
        return "メモリ操作中にエラーが発生しました。もう一度試してください。"

async def analyze_information(information: str, question: str):
    prompt = f"""
    あなたは与えられた情報から要点を正確に抽出する専門家です。
    以下の「ユーザーの質問」に答えるために、提供された「参考情報」の中から、必要な部分を判断して抽出してください。
    
    ## ルール
    - 質問に直接関連する情報のみを抽出してください。
    - 情報を追加したり、自分の言葉で解釈したりしないでください。参考情報にある文章を基に、忠実に抜き出してください。
    - 関連する情報が何も見つからない場合は、空の文字列を返してください。
    - 出力は、箇条書きや文章の形式でまとめてください。
    
    ## ユーザーの質問
    {question}
    
    ## 参考情報
    {information}
    """
    try:
        response = await analyze_model.ainvoke(prompt)
        extracted_info = response.content
        logger.debug(f"Extracted information: {extracted_info}")
        return extracted_info
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        return ""

async def information_retrieval(queries: dict):
    if not queries.get("is_retrieval_needed", False):
        logger.debug("情報検索は不要と判断されました。")
        return None
    retrieval_query = queries.get("retrieval_query")
    web_search_query = queries.get("web_search_query")
    
    try:
        results = await similar_document_search(retrieval_query)
        retrieval_result = ""
        
        for doc in results:
            header_parts = []
            if doc.metadata:
                #header1からheader5までをチェック
                for i in range(1, 6):
                    header_key = f"header{i}"
                    if header_key in doc.metadata:
                        header_parts.append(doc.metadata[header_key])
            
            header_str = "見出し：" + " > ".join(header_parts) if header_parts else ""
            retrieval_result += f"{header_str}\n{doc.page_content}\n\n"
            
    except Exception as e:
        logger.error(f"情報検索中にエラーが発生しました: {e}")
        retrieval_result = None
    
    try:
        web_search_result_json = await search.search(web_search_query, include_answer="basic")
        web_search_result = ""
        if isinstance(web_search_result_json, dict):
            llm_answer = web_search_result_json.get("answer", "")
            web_search_result += f"**AIによる要約:**\n{llm_answer}\n\n" if llm_answer else ""
            for item in web_search_result_json.get("results", []):
                if isinstance(item, dict):
                    title = item.get("title", "タイトルなし")
                    content = item.get("content", "本文なし")
                    link = item.get("url", "#")
                    web_search_result += f"**{title}**\n{content}\n[リンク]({link})\n\n"
                else:
                    logger.warning(f"Unexpected item format in web search results: {item}")
        else:
            logger.warning(f"Unexpected web search results format: {web_search_result_json}")
    except Exception as e:
        logger.error(f"Web検索中にエラーが発生しました: {e}")
        web_search_result = None
        
    result = f"""
    # Wikiからの参考情報(アークナイツのみ)
    {retrieval_result if retrieval_result else "関連する情報が見つかりませんでした。"}
    
    # Webからの参考情報(アークナイツ以外も含む。優先度低)
    {web_search_result if web_search_result else "関連する情報が見つかりませんでした。"}
    """
    logger.debug(f"情報検索結果: {result}")
    return result

async def response_generation_from_information(user_id_str: str, question: str, information: str, history: str):
    # --- APIに渡すメッセージリストを作成 ---
    # 1. 長期記憶からシステムプロンプトを動的に生成
    long_term_memories = await get_long_term_memories(user_id_str)
    persona = json.dumps(config.dynamic["chat_persona"], ensure_ascii=False)
    longterm_memory = ""
    if long_term_memories:
        memory_items = []
        for memory in long_term_memories.keys():
        
            if 'nickname' in memory:
                memory_items.append(f"- ユーザーの呼び方は「{long_term_memories['nickname']}」です。\n")
            if "memory" in memory:
                memory_items.append(f"- ユーザーに関する記憶: {long_term_memories[memory]['memory']}\n")
            
            # 他の記憶項目もここに追加可能
            
        if memory_items:
            longterm_memory += "\n".join(memory_items)

    # 2. インフォメーションと長期記憶を結合
    prompt = f"""
    ## キャラクター設定（ペルソナ）
    {persona}
    
    ## 応答ルール
    - ユーザーの質問に対しては、提供された「参考情報」を最大限活用し、誠実かつ簡潔に回答してください。
    - 「参考情報」に答えが無い場合は、回答を「情報が見つかりませんでした」としてください。
    - 常にあなたのキャラクター設定を保った口調で話してください。
    - ユーザーのメッセージは「質問」でない場合もあります。その場合は、ユーザーの意図を汲み取り、適切な応答をしてください。
    
    ## 参考情報
    {information}
    
    ## 会話履歴
    {history}
    
    ## 長期記憶
    {longterm_memory}
    
    ## ユーザーの最新メッセージ
    {question}

    ## 応答例
    - アークナイツのキャラクター「ラップランド」についてですね！調べたところ、こんな情報がありました！......
    - 調べてみたのですが、参考になる情報は見つかりませんでした。
    
    """
    
    
    logger.debug(f"統合したシステムプロンプト: {prompt}")
    
    # 3. システムプロンプトをAPIに渡す
    response = await model.ainvoke(prompt)
    output_text = response.content
    if "ロード:" in output_text:
        output_text = output_text.split("ロード:")[-1].strip()
    if output_text.startswith("「") and output_text.endswith("」"):
        output_text = output_text[1:-1]
    return output_text

async def direct_chat(user: discord.User, message: discord.Message):
    total_start_time = datetime.now()

    user_id_str = str(user.id)
    
    # ユーザーのメッセージをDBに追加 (エラー時に削除するためIDを保持)
    user_message_id = await add_message_to_db(user_id_str, "user", message.content)

    # ユーザーの過去の会話履歴を取得
    history = await get_history_from_db(user_id_str, limit=10)
    history_without_system_prompt = [msg for msg in history if msg["role"] != "system"]
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history_without_system_prompt])
    
    async with message.channel.typing():
        try:
            # 1. メッセージ分析
            analysis_start_time = datetime.now()
            analysis_result = await analyze_message(user_id_str, message.content, history_str)
            analysis_end_time = datetime.now()
            logger.debug(f"メッセージ分析時間: {(analysis_end_time - analysis_start_time).total_seconds():.2f}秒")
            
            if analysis_result.get("memory_operation") in ["store", "delete"]:
                memory_response = await handle_memory_operation(analysis_result, user_id_str)
                logger.debug(f"Memory operation response: {memory_response}")
            
            if not analysis_result.get("is_retrieval_needed", False):
                # 2. (検索なし) 応答生成
                logger.debug("情報検索は不要と判断されました。")
                generation_start_time = datetime.now()
                response_text = await response_generation_from_information(user_id_str, message.content, "", history_str)
                generation_end_time = datetime.now()
                logger.debug(f"応答生成時間 (検索なし): {(generation_end_time - generation_start_time).total_seconds():.2f}秒")

                await add_message_to_db(user_id_str, "assistant", response_text)
                await message.channel.send(response_text)
                total_end_time = datetime.now()
                logger.info(f"総処理時間 (検索なし): {(total_end_time - total_start_time).total_seconds():.2f}秒")
                return response_text
            
            # 2. 情報検索
            retrieval_start_time = datetime.now()
            information_raw = await information_retrieval(analysis_result)
            retrieval_end_time = datetime.now()
            logger.debug(f"情報検索時間: {(retrieval_end_time - retrieval_start_time).total_seconds():.2f}秒")

            # 3. 情報の要約・抽出
            extraction_start_time = datetime.now()
            information = await analyze_information(information_raw, message.content)
            extraction_end_time = datetime.now()
            logger.debug(f"情報抽出時間: {(extraction_end_time - extraction_start_time).total_seconds():.2f}秒")

            # 4. 応答生成
            generation_start_time = datetime.now()
            response_text = await response_generation_from_information(user_id_str, message.content, information, history_str)
            generation_end_time = datetime.now()
            logger.debug(f"応答生成時間 (検索あり): {(generation_end_time - generation_start_time).total_seconds():.2f}秒")

            logger.debug(f"Response text: {response_text}")
            await add_message_to_db(user_id_str, "assistant", response_text)
            await message.channel.send(response_text)
            total_end_time = datetime.now()
            logger.info(f"総処理時間 (検索あり): {(total_end_time - total_start_time).total_seconds():.2f}秒")
            return response_text

        except Exception as e:
            logger.error(f"Error in direct_chat: {e}")
            await message.channel.send("ごめんなさい、エラーが発生したみたいです。少し待ってからもう一度試してみてください。")
            await delete_message_from_db(user_message_id)
            return None