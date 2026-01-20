import asyncio
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, List, Optional, TypedDict, Dict
from uuid import uuid4

import chromadb
import discord
from chromadb.config import Settings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_chroma import Chroma
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from tavily import AsyncTavilyClient

from extentions import JSTTime, log
from extentions.config import config

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")

db_path = os.path.join(dir, "db", "chat_history.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 短期的な会話履歴テーブル
cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
""")
cur.execute(
    "CREATE INDEX IF NOT EXISTS idx_user_id_timestamp ON chat_history (user_id, timestamp)"
)

# 長期記憶用テーブル
cur.execute("""
    CREATE TABLE IF NOT EXISTS long_term_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        UNIQUE(user_id, key)
    )
""")
conn.commit()

mcp_config = {
    "mcpServers": {
        "playwright": {
            "command": "C:\\Program Files\\nodejs\\npx.cmd",
            "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated"],
            "url": "https://arknights.wikiru.jp/",
            "selector": "#body",
            "exclude_selectors": [".adsbygoogle"],
            "env": {"DISPLAY": ":1"},
        }
    }
}


async def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    HuggingFaceの事前学習済みのモデルをロードして返す関数
    戻り値:
        HuggingFaceEmbeddingsオブジェクト: 事前学習済みのモデルをラップしたオブジェクト
    """
    return HuggingFaceEmbeddings(model_name="sbintuitions/sarashina-embedding-v1-1b")


async def get_akdb_conn():
    akdb_client = chromadb.HttpClient(
        host="localhost",
        port=8000,
        settings=Settings(allow_reset=True, anonymized_telemetry=False),
    )
    return akdb_client


embedding_model = None
db_client = None
model = None
agent_model = None
ak_collection = None
ak_retriever = None
analyze_model = None
search = None
reranker = None
app = None


# === 初期化 ===
async def init_models():
    global \
        db_client, \
        embedding_model, \
        model, \
        agent_model, \
        ak_collection, \
        ak_retriever, \
        analyze_model, \
        search, \
        reranker, \
        app
    db_client = await get_akdb_conn()
    model = ChatOpenAI(model="gpt-5-chat-latest")
    analyze_model = ChatOpenAI(model="gpt-5")
    agent_model = ChatOpenAI(model="gpt-5-mini")
    embedding_model = await get_embedding_model()

    ak_collection = Chroma(
        collection_name="arknights_wiki",
        embedding_function=embedding_model,
        client=db_client,
    )
    retriever = ak_collection.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 50, "fetch_k": 100, "lambda_mult": 0.8},
    )

    search = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    encoder = HuggingFaceCrossEncoder(
        model_name="hotchpotch/japanese-reranker-xsmall-v2"
    )
    reranker = CrossEncoderReranker(model=encoder, top_n=10)
    ak_retriever = ContextualCompressionRetriever(
        base_compressor=reranker, base_retriever=retriever
    )
    app = setup_chat_graph()


class ChatState(TypedDict, total=False):
    user_id: str
    message: str
    history_str: str  # 直近履歴（あなたのDBから取得済みの文字列）
    analysis: Dict[str, Any]  # analyze_message のJSON結果
    memory_note: Optional[str]  # memory 操作の応答文（UI表示用に保持）
    wiki_text: Optional[str]  # wiki由来の原文連結
    web_text: Optional[str]  # web由来の原文連結
    merged_info: str  # wiki / web を見出し付きで合成
    extracted: str  # 抽出済みの要点（回答に使う最小文）
    response_text: str  # 最終回答


# === ヘルパー関数群 ===


async def similar_document_search(query: str):
    results = await ak_retriever.ainvoke(input=query)

    # 結果が空の場合は警告を出して空の結果を返す
    logger.debug(f"Query: {query}, Results: {len(results)} documents found")
    if not results:
        logger.warning("No relevant documents found for the query.")
        return None
    return results


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


# === DB操作関数群 ===


async def add_message_to_db(user_id: str, role: str, content: str):
    # データベースにメッセージを追加し、挿入された行のIDを返す
    timestamp = datetime.now(tz=JSTTime.tz_JST).isoformat()
    cur.execute(
        "INSERT INTO chat_history (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, role, content, timestamp),
    )
    conn.commit()
    return cur.lastrowid


async def get_history_from_db(user_id: str, limit: int = 20):
    # データベースからユーザーのチャット履歴を取得
    cur.execute(
        "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


async def delete_message_from_db(message_id: int):
    # データベースからメッセージを削除
    cur.execute("DELETE FROM chat_history WHERE id = ?", (message_id,))
    conn.commit()


# === 長期記憶操作関数群 ===


async def update_long_term_memory(user_id: str, key: str, value: str):
    """長期記憶を追加または更新する"""
    timestamp = datetime.now(tz=JSTTime.tz_JST).isoformat()

    if key == "delete_memory":
        longtime_memory = await get_long_term_memories(user_id)
        # "delete_memory"の場合は、指定された内容を削除
        if value in longtime_memory.values():
            # キーを取得して削除
            key_to_delete = next(
                (k for k, v in longtime_memory.items() if v == value), None
            )
            if key_to_delete:
                cur.execute(
                    "DELETE FROM long_term_history WHERE user_id = ? AND key = ?",
                    (user_id, key_to_delete),
                )
                conn.commit()
                return

        else:
            logger.warning(
                f"指定された内容 '{value}' は長期記憶に存在しません。削除できませんでした。"
            )
            return

    if key == "store_memory":
        # キーは"memory_[uuid]"の形式で保存
        uuid = uuid4()
        key = f"memory_{uuid}"

    cur.execute(
        """
        INSERT INTO long_term_history (user_id, key, value, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET
        value = excluded.value,
        timestamp = excluded.timestamp
    """,
        (user_id, key, value, timestamp),
    )
    conn.commit()


async def get_long_term_memories(user_id: str) -> dict:
    """ユーザーの長期記憶を辞書として取得する"""
    cur.execute(
        "SELECT key, value FROM long_term_history WHERE user_id = ?", (user_id,)
    )
    rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


# === Graphノード関数 ===


async def analyze_message(state: ChatState) -> ChatState:
    user_id_str = state["user_id"]
    user_message = state["message"]
    history = state["history_str"]

    prompt = f"""
    あなたは、ユーザーとの会話を分析し、後続のシステムが必要とするアクションを判断する、優秀なアシスタントです。
    特に、アークナイツのWikiデータベースとWeb検索を効率的に活用するための検索クエリ生成を得意とします。

    # 指示
    以下の会話履歴とユーザーの最新メッセージを分析し、思考プロセスに従って最適なアクションを判断し、指定されたJSON形式で出力してください。

    # 思考プロセス
    1.  まず、ユーザーの最新メッセージの意図を分析します。これは単純な挨拶や雑談ですか？ それとも特定の情報を求めていますか？
    2.  情報を求めている場合、その内容はアークナイツのWikiにありそうですか？（例：キャラクターの性能、イベント攻略、世界観） それともWeb全体で検索すべき新しい情報や一般的な知識ですか？
    3.  **Wiki検索クエリの生成**:
        -   Wikiに情報がありそうな場合、ベクトル検索で最もヒットしやすいように、具体的で詳細な検索クエリを生成します。
        -   例えば、「アークナイツのキャラクター「ホルハイヤ」の特性、素質、スキル2の詳細、昇進素材と特化素材」のように、特定のキャラクターや要素に焦点を当てたクエリを作成します。
        -   キャラクターの評価や使い方などを調べるとき、「ゲームにおいて」という見出しに求める情報があります。
        -   確実でない情報を推測でクエリに含むことは避けてください。質問に誠実に答えられるように生成します。
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
    """

    response = await analyze_model.ainvoke(prompt)
    logger.debug(f"Analyze response: {response.content}")
    try:
        analysis = json.loads(response.content)
    except json.JSONDecodeError:
        logger.error(f"JSONの解析に失敗しました: {response.content}")
        # デフォルトの応答（検索しないなど）を返す
        analysis = {
            "is_retrieval_needed": False,
            "retrieval_query": None,
            "web_search_query": None,
        }

    state["analysis"] = analysis
    return state


async def handle_memory_operation(state: ChatState) -> ChatState:
    analysis_result = state["analysis"]
    user_id_str = state["user_id"]
    operation = analysis_result.get("memory_operation")
    content = analysis_result.get("memory_content")

    if operation is None or content is None:
        return state

    try:
        if operation == "store":
            # 長期記憶に保存
            await update_long_term_memory(user_id_str, "store_memory", content)
            state["memory_note"] = f"「{content}」を記憶しました。"
        elif operation == "delete":
            # 長期記憶から削除
            await update_long_term_memory(user_id_str, "delete_memory", content)
            state["memory_note"] = f"「{content}」を忘れました。"
        else:
            logger.warning(f"Unknown memory operation: {operation}")
            return state
        return state
    except Exception as e:
        logger.error(f"メモリ操作中にエラーが発生しました: {e}")
        state["memory_note"] = (
            "メモリ操作中にエラーが発生しました。もう一度試してください。"
        )
        return state


async def wiki_retrieve(state: ChatState):
    analysis_result = state["analysis"]
    if not analysis_result.get("retrieval_query"):
        return {"wiki_text": None}
    try:
        docs = await similar_document_search(analysis_result["retrieval_query"])
        buf = []
        if docs:
            for doc in docs:
                headers = []
                if doc.metadata:
                    # header1からheader5までをチェック
                    for i in range(1, 6):
                        header_key = f"header{i}"
                        if header_key in doc.metadata:
                            headers.append(doc.metadata[header_key])
                h = f"見出し：{' > '.join(headers)}" if headers else ""
                buf.append(f"{h}\n{doc.page_content}")
        wiki_text = "\n\n".join(buf) if buf else None
    except Exception as e:
        logger.error(f"Wiki情報の取得中にエラーが発生しました: {e}")
        wiki_text = None
    return {"wiki_text": wiki_text}


async def web_retrieve(state: ChatState):
    analysis_result = state["analysis"]
    query = analysis_result.get("web_search_query")
    if not query:
        return {"web_text": None}
    try:
        res = await search.search(query, include_answer="basic")
        txt = []
        if isinstance(res, dict):
            llm_answer = res.get("answer", "")
            if llm_answer:
                txt.append(f"**AIによる要約:**\n{llm_answer}\n")
            for item in res.get("results", []):
                if isinstance(item, dict):
                    title = item.get("title", "タイトルなし")
                    content = item.get("content", "本文なし")
                    link = item.get("url", "#")
                    txt.append(f"**{title}**\n{content}\n[リンク]({link})\n")
                else:
                    logger.warning(
                        f"Unexpected item format in web search results: {item}"
                    )
        web_text = "\n\n".join(txt) if txt else None
    except Exception as e:
        logger.error(f"Web情報の取得中にエラーが発生しました: {e}")
        web_text = None
    return {"web_text": web_text}


async def merge_refs(state: ChatState) -> ChatState:
    wiki = state["wiki_text"]
    web = state["web_text"]
    merged = []
    merged.append(
        "# Wikiからの参考情報\n"
        + (wiki if wiki else "関連する情報が見つかりませんでした。")
    )
    merged.append(
        "# Webからの参考情報\n"
        + (web if web else "関連する情報が見つかりませんでした。")
    )
    state["merged_info"] = "\n\n".join(merged)
    return state


async def extract_relevant(state: ChatState) -> ChatState:
    info = state.get("merged_info", "")
    question = state["message"]
    extracted = await analyze_information(info, question)
    state["extracted"] = extracted or ""
    return state


async def response_generation_from_information(state: ChatState) -> ChatState:
    user_id_str = state["user_id"]
    question = state["message"]
    history = state["history_str"]
    information = state.get("extracted", "")

    # --- APIに渡すメッセージリストを作成 ---
    # 1. 長期記憶からシステムプロンプトを動的に生成
    long_term_memories = await get_long_term_memories(user_id_str)
    persona = json.dumps(config.dynamic["chat_persona"], ensure_ascii=False)
    longterm_memory = ""
    if long_term_memories:
        memory_items = []
        for memory in long_term_memories.keys():
            if "nickname" in memory:
                memory_items.append(
                    f"- ユーザーの呼び方は「{long_term_memories['nickname']}」です。\n"
                )
            if "memory" in memory:
                memory_items.append(
                    f"- ユーザーに関する記憶: {long_term_memories[memory]['memory']}\n"
                )

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

    state["response_text"] = output_text
    return state


def setup_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("analyze", analyze_message)
    graph.add_node("memory_op", handle_memory_operation)
    graph.add_node("wiki_retrieve", wiki_retrieve)
    graph.add_node("web_search", web_retrieve)
    graph.add_node("merge_refs", merge_refs)
    graph.add_node("extract_relevant", extract_relevant)
    graph.add_node("generate", response_generation_from_information)

    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "memory_op")

    def need_retrieval(state: ChatState) -> str:
        a = state.get("analysis", {})
        return "search" if a.get("is_retrieval_needed") else "nosrch"

    graph.add_conditional_edges(
        "memory_op",
        need_retrieval,
        {
            "search": "wiki_or_web",
            "nosrch": "generate",
        },
    )
    # wiki と web を“並列”に走らせるためのハブ
    graph.add_node("wiki_or_web", lambda s: s)  # ダミー分岐ノード
    graph.add_edge("wiki_or_web", "wiki_retrieve")
    graph.add_edge("wiki_or_web", "web_search")

    # 並列の合流 → 抽出 → 生成
    graph.add_edge("wiki_retrieve", "merge_refs")
    graph.add_edge("web_search", "merge_refs")
    graph.add_edge("merge_refs", "extract_relevant")
    graph.add_edge("extract_relevant", "generate")
    graph.add_edge("generate", END)

    # コンパイル（async）
    app = graph.compile()
    return app


async def run_graph(user_id_str: str, message_content: str):
    # Ensure the app is initialized
    global app
    if app is None:
        await init_models()
    hist = await get_history_from_db(user_id_str, limit=10)
    hist = [msg for msg in hist if msg["role"] != "system"]
    hist_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in hist])

    state: ChatState = {
        "user_id": user_id_str,
        "message": message_content,
        "history_str": hist_str,
    }

    final_state = await app.ainvoke(state)
    return final_state.get("response_text")


async def direct_chat(user: discord.User, message: discord.Message):
    user_id_str = str(user.id)
    msg_id = await add_message_to_db(user_id_str, "user", message.content)
    try:
        async with message.channel.typing():
            response_text = await run_graph(user_id_str, message.content)
        await add_message_to_db(user_id_str, "assistant", response_text)
        await message.channel.send(response_text)
        return response_text
    except Exception as e:
        logger.error(f"Graph error: {e}", exc_info=True)
        await delete_message_from_db(msg_id)
        await message.channel.send(
            "ごめんなさい！今はうまく返答できないんです。後でもう一度お話ししましょう！"
        )
        return None
