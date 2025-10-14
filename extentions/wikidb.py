import asyncio
import json
import os
import time

import requests
from bs4 import BeautifulSoup
from langchain.docstore.document import Document
from langchain.text_splitter import MarkdownHeaderTextSplitter, MarkdownTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from chromadb.config import Settings

update_switch = False

path = os.path.abspath(__file__ + "/../")
json_dir = os.path.join(path, "jsons\\wikidb")
db_dir = os.path.join(path, "db\\arknights_wiki_vectorstore")

PROCESSED_FILE = os.path.join(json_dir, "processed_pages.json")
UPDATE_FILE = os.path.join(json_dir, "update_pages.json")
if os.path.exists(PROCESSED_FILE):
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        processed_titles = set(json.load(f))
else:
    processed_titles = set()
    
if os.path.exists(UPDATE_FILE):
    with open(UPDATE_FILE, "r", encoding="utf-8") as f:
        update_set = set(json.load(f))
else:
    update_set = set()

base = "https://arknights.wikiru.jp/?"
res = requests.get(base + "cmd=list")
soup = BeautifulSoup(res.text, "html.parser")
page_names = [a.text for a in soup.find_all('a') if a.text]

print(f"WIKI_LEN: {len(page_names)}")

header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "header1"), ("##", "header2"), ("###", "header3"), ("####", "header4"), ("#####", "header5"), ("######", "header6")])
text_splitter = MarkdownTextSplitter(chunk_size = 1000, chunk_overlap = 100)


def get_embedding_model()->HuggingFaceEmbeddings:
    """
    HuggingFaceの事前学習済みのモデルをロードして返す関数
    戻り値:
        HuggingFaceEmbeddingsオブジェクト: 事前学習済みのモデルをラップしたオブジェクト
    """
    return HuggingFaceEmbeddings(
        model_name="sbintuitions/sarashina-embedding-v1-1b"
    )

def get_db_conn()->chromadb.HttpClient:
    """
    ChromaDBデータベースへの接続を確立して返す関数
    戻り値:
        Chromadb.HttpClientオブジェクト: ChromaDBデータベースへの接続を表現するオブジェクト
    """
    client = chromadb.HttpClient(
        host="localhost",
        port=8000,
        settings=Settings(allow_reset=True, anonymized_telemetry=False),
        )
    return client

embeddings = get_embedding_model()
db_store = Chroma(collection_name="arknights_wiki", embedding_function=embeddings, host="localhost")

all_ids = db_store.get(include=[])["ids"]

print(f"CURRENT_DB_LEN: {len(all_ids)}")

def fetch_update_links():
    update_links = set()

    # キャラクター一覧ページ
    chara_url = "https://arknights.wikiru.jp/?キャラクター一覧"
    r = requests.get(chara_url)
    soup = BeautifulSoup(r.text, "html.parser")
    main_content = soup.find(id="body") 
    for table in main_content.find_all("table", class_="style_table"):
        for a in table.find_all("a", href=True):
            # title属性があればそれをnameとする
            name = a.get("title") if a.get("title") else a.text
            if not name:
                continue
            name = name.strip()
            update_links.add(name)

    # 統合戦略ページ（最初のテーブルのみ）
    strat_url = "https://arknights.wikiru.jp/?統合戦略"
    r = requests.get(strat_url)
    soup = BeautifulSoup(r.text, "html.parser")
    main_content = soup.find(id="body") 
    table = main_content.find("table", class_="style_table")
    if table:
        for a in table.find_all("a", href=True):
            name = a.get("title") if a.get("title") else a.text
            if not name:
                continue
            name = name.strip()
            update_links.add(name)

    return update_links

def html_table_to_markdown(table_tag):
    """
    HTMLの<table>タグを解析し、rowspanとcolspanを考慮してMarkdownテーブルに変換します。

    Args:
        table_tag: BeautifulSoupで解析された<table>タグオブジェクト。

    Returns:
        Markdown形式のテーブル文字列。
    """
    grid = [] # テーブル全体を表現する2次元リスト（グリッド）

    # 1. HTMLテーブルを解析し、中間的なグリッド表現を構築する
    for y, tr in enumerate(table_tag.find_all("tr")):
        # 現在の行yに対応するリストがなければ追加する
        if y >= len(grid):
            grid.append([])

        x = 0 # 現在の列（x座標）
        for cell in tr.find_all(["th", "td"]):
            # === rowspanによって既に埋められているセルをスキップする ===
            # このループがrowspanを正しく扱うための鍵です。
            while True:
                # 行の長さを超える場合、Noneで埋めて拡張
                if x >= len(grid[y]):
                    grid[y].extend([None] * (x - len(grid[y]) + 1))
                
                # grid[y][x]がNone（空き）なら、そこが挿入位置
                if grid[y][x] is None:
                    break
                # 埋まっていれば次の列へ
                x += 1

            # rowspanとcolspanを取得
            try:
                rowspan = int(cell.get('rowspan', 1))
            except (ValueError, TypeError):
                rowspan = 1
            try:
                colspan = int(cell.get('colspan', 1))
            except (ValueError, TypeError):
                colspan = 1

            # セルのテキストを準備（thタグは太字に）
            text = cell.get_text(strip=True).replace('|', '&#124;') # パイプ文字をエスケープ
            if cell.name == "th":
                text = f"**{text}**"

            # === rowspanとcolspanで指定された領域をグリッドに書き込む ===
            for r_offset in range(rowspan):
                for c_offset in range(colspan):
                    current_y = y + r_offset
                    current_x = x + c_offset

                    # 必要に応じてグリッドを拡張
                    if current_y >= len(grid):
                        grid.extend([[] for _ in range(current_y - len(grid) + 1)])
                    if current_x >= len(grid[current_y]):
                        grid[current_y].extend([None] * (current_x - len(grid[current_y]) + 1))

                    # 左上のセルにテキストを、それ以外は空文字列を配置
                    # Markdownでは結合されたセルは空のセルとして表現される
                    value_to_set = text if r_offset == 0 and c_offset == 0 else ""
                    grid[current_y][current_x] = value_to_set
            
            # 次のセルのためにx座標を更新
            x += colspan

    # 2. 構築したグリッドをMarkdown文字列に変換する
    if not grid:
        return ""

    # 全ての行が同じ列数になるように空文字列で埋める
    max_columns = max(len(r) for r in grid) if grid else 0
    for row in grid:
        # grid作成時にNoneが残っている場合も空文字列に変換
        for i, cell in enumerate(row):
            if cell is None:
                row[i] = ""
        row.extend([""] * (max_columns - len(row)))

    # Markdownの各行を生成
    markdown_rows = []
    # ヘッダー行
    header = "| " + " | ".join(grid[0]) + " |"
    markdown_rows.append(header)
    # 区切り行
    separator = "| " + " | ".join(["---"] * max_columns) + " |"
    markdown_rows.append(separator)
    # ボディ行
    for row in grid[1:]:
        markdown_rows.append("| " + " | ".join(row) + " |")

    return "\n".join(markdown_rows).strip()
if update_switch is True:
    update_set.update(fetch_update_links())
update_set = {name for name in update_set if all(x not in name for x in ["コメント", "雛型", "SandBox"])}

for name in page_names:
    
    print("SCRAPING: "+name)
    
    title = name.split('/')[-1]
    page_url = "https://arknights.wikiru.jp/?" + name.replace(" ", "+")
    
    if title in processed_titles and name not in update_set:
        print(f"SKIP (not in update_set): {name}")
        continue
    
    if "コメント" in name or "雛型/" in name or "SandBox" in name or "PukiWiki" in name or "イベントxx" in name or "テーブル/" in name or "リンク集" in name or "人気100" in name or "今日100" in name:
        print(f"SKIP: {name}")
        continue
    
    #scrape
    url = f"{base}{name.replace(' ', '+')}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"COULDN'T EXTRACT: {name}")
        continue
    soup = BeautifulSoup(r.text, "lxml")
    main_content = soup.find(id="body")  
    
    if main_content is None:
        print(f"COULDN'T EXTRACT: {name}")
        continue
    
    time.sleep(1)

                  
    # 直下にある class="contents" を持つdivをすべて削除
    for element in main_content.select(":scope > div.contents"):
        element.decompose()
    # 直下にある class="navi" を持つdivをすべて削除
    for element in main_content.select(":scope > ul.navi"):
        element.decompose()
        
    #img
    for img in main_content.find_all("img"):
        alt_text = img.get("alt")
        if alt_text:
            img.replace_with(f"img[{alt_text}]")
        else:
            img.decompose()
    
    # <br>タグを改行に変換
    for br in main_content.find_all("br"):
        br.insert_before("\n")
    
    #table
    for table in main_content.find_all("table", class_="style_table"):
        markdown_table = html_table_to_markdown(table)
        table.insert_before(soup.new_string("\n" + markdown_table + "\n"))
        table.decompose()
        
    #見出し
    for i in range(1,7):
        for tag in main_content.find_all(f"h{i}"):
            heading_text = tag.get_text(strip=True)
            markdown_heading = "\n" + ("#"*i) + " " + heading_text + "\n"
            tag.insert_before(soup.new_string(markdown_heading))
            tag.decompose()
            
    # すべてのpcomment要素を取得
    pcomment_elements = main_content.find_all(class_="pcomment")

    # 最後の1つだけを対象にする
    if pcomment_elements:
        pcomment_element = pcomment_elements[-1]  # 最後のpcomment
        print(f"[DEBUG] Found {len(pcomment_elements)} pcomment elements, processing the last one.")

        # pcomment要素以降の兄弟要素をすべて削除
        for tag in list(pcomment_element.find_all_next()):
            tag.decompose()

        # pcomment要素自身も削除
        pcomment_element.decompose()


    page_text = main_content.get_text()
    
    if "Error message : 以下のいずれかの原因で更新を拒否されました" in page_text:
        print(f"ERROR: {name}")
        continue
    
    lines = page_text.splitlines()
    if len(lines) == 0:
        print(f"NO LINES: {name}")
        continue
    
    if len(lines) <= 2:
        print(f"WARN: TOO FEW LINES: {name}")
    
    category_path = lines[0].strip()
    category_path = lines[1].strip() if "最終更新" in category_path else category_path
    if category_path == "### Runtime error":
        print(f"RUNTIME ERROR: {name}")
        continue
    category_parts = [part.strip() for part in category_path.split(" > ")]
    if len(category_parts) >= 2:
        category = category_parts[0] + "/" + category_parts[1]  # "アイテム一覧/消耗品"
    elif len(category_parts) == 1:
        category = category_parts[0]
    else:
        category = "unknown"
        
    content_body = "\n".join(lines[1:])
    
    print(category)

    metadata = {
        "category": category,
        "breadcrumb": category_path,
        "title": name,
        "source_url": url
    }
    
    if not content_body:
        print(f"EMPTY CONTENT_BODY: {name}")
        continue
    
    #chunking
    header_splits = header_splitter.split_text(content_body)
    documents = text_splitter.split_documents(header_splits)
    for document in documents:
        document.metadata.update(metadata)
    
    if not documents:
        print(f"NO DOCUMENTS: {name}")
        continue

    try:
        doc_ids = [f"{name}_{i}" for i in range(len(documents))]
        target_ids = [id for id in all_ids if id.startswith(f"{name}_")]
        if target_ids:
            db_store.delete(target_ids)
        db_store.add_documents(documents=documents, ids=doc_ids)
        print(f"SUCCESS STORED: {name}")
        processed_titles.add(title)
        progress = page_names.index(name) + 1
        print(f"PROGRESS: {progress}/{len(page_names)}")
        if name in update_set:
            update_set.remove(name)
        with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_titles), f, ensure_ascii=False, indent=2)
        with open(UPDATE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(update_set), f, ensure_ascii=False, indent=2)
        
        time.sleep(2)
        
    except Exception as e:
        print(f"FAILED STORE: {name} {e}")
        update_set.add(name)
        with open(UPDATE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(update_set), f, ensure_ascii=False, indent=2)
        
    
    