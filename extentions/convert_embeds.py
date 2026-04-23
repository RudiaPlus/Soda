import os
import json

def convert_item_to_components(item):
    components = []
    
    def process_item(item_data):
        if "image" in item_data:
            url = item_data["image"].get("url")
            placeholder = item_data["image"].get("_placeholder_filename")
            if url:
                clean_url = url.split("?")[0] if url.startswith("http") else url
                components.append({"type": 10, "content": clean_url})
            elif placeholder:
                components.append({"type": 10, "_placeholder_filename": placeholder})

        text_content = ""
        if "title" in item_data:
            text_content += f"# {item_data['title']}\n\n"
        if "description" in item_data:
            text_content += f"{item_data['description']}\n\n"
        if "fields" in item_data:
            for field in item_data["fields"]:
                name = field.get("name", "")
                val = field.get("value", "")
                val = val.replace(">>> ", "> ")
                text_content += f"**{name}**\n{val}\n\n"
        if "footer" in item_data and item_data["footer"]:
            footer_text = item_data["footer"]
            if isinstance(footer_text, dict):
                footer_text = footer_text.get("text", "")
            if footer_text:
                text_content += f"-# {footer_text}\n"

        text_content = text_content.strip()
        if text_content:
            for i in range(0, len(text_content), 2000):
                components.append({"type": 10, "content": text_content[i:i+2000]})

    title = ""
    if "embeds" in item:
        if "content" in item:
            components.append({"type": 10, "content": item["content"]})
        for emb in item["embeds"]:
            if "title" in emb and not title:
                title = emb["title"]
            process_item(emb)
    else:
        if "title" in item and not title:
            title = item["title"]
        process_item(item)
        
    res = {
        "flags": 32768,
        "components": components
    }
    if title:
        res["_original_title"] = title
    return res

if __name__ == "__main__":
    src_dir = "c:/Users/Rudia/OneDrive/ドキュメント/Soda/extentions/embeds"
    dst_dir = "c:/Users/Rudia/OneDrive/ドキュメント/Soda/extentions/components"
    os.makedirs(dst_dir, exist_ok=True)
    
    for filename in os.listdir(src_dir):
        if filename.endswith(".json"):
            src_path = os.path.join(src_dir, filename)
            dst_path = os.path.join(dst_dir, filename)
            
            with open(src_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                
            if isinstance(old_data, list):
                new_data = [convert_item_to_components(i) for i in old_data]
            else:
                new_data = convert_item_to_components(old_data)
            
            with open(dst_path, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            print(f"Converted {filename}")
