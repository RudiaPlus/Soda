import asyncio
import time

import requests
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter

from sentence_transformers import SentenceTransformer

base = "https://arknights.wikiru.jp/?"
res = requests.get(base + "cmd=list")
soup = BeautifulSoup(res.text, "html.parser")
page_names = [a.text for a in soup.find_all('a') if a.text]
print(f"LEN: {len(page_names)}")

model = SentenceTransformer("sbintuitions/sarashina-embedding-v1-1b")

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
            text = cell.get_text(strip=True).replace('|', '\|') # パイプ文字をエスケープ
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

for name in page_names:
    
    print("SCRAPING: "+name)
    #scrape
    url = f"{base}{name.replace(' ', '+')}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"COULDN'T EXTRACT: {name}")
        continue
    soup = BeautifulSoup(r.text, "html.parser")
    main_content = soup.find(id="body")  
    
    if main_content is None:
        print(f"COULDN'T EXTRACT: {name}")
        continue
    
    #class="contents", class="navi"内を除外
    for element in main_content.find_all(["div", "ul"]):
        try:
            classes = element.get("class", [])
            if "contents" in classes or "navi" in classes:
                element.decompose()
        except AttributeError:
            pass
    
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
    
    page_text = main_content.get_text().strip()
    lines = page_text.splitlines()
    if len(lines) == 0:
        print(f"COULDN'T EXTRACT: {name}")
        continue
    category_path = lines[0].strip()
    if category_path == "### Runtime error":
        print(f"COULDN'T EXTRACT: {name}")
        continue
    category_parts = [part.strip() for part in category_path.split(" > ")]
    if len(category_parts) >= 3:
        category = category_parts[0] + "/" + category_parts[1]  # "アイテム一覧/消耗品"
    elif len(category_parts) == 1:
        category = category_parts[0]
    else:
        category = "unknown"
        
    content_body = "\n".join(lines[1:]).strip()
    print(category)
    print(content_body)
    
    time.sleep(1)

    title = name.split('/')[-1]
    
    #process
    