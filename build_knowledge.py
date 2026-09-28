import json, os

os.makedirs("docs", exist_ok=True)
count = 0

for filename in os.listdir("champions"):
    if not filename.endswith(".json"):
        continue
    path = os.path.join("champions", filename)
    with open(path, encoding="utf-8") as f:
        try:
            champ_data = json.load(f)["data"]
            champ_id = list(champ_data.keys())[0]  # 获取英雄 ID
            champ = champ_data[champ_id]
        except Exception:
            continue

    # 拼接成 Markdown 格式的文本
    md = f"# {champ['name']}（{champ['title']}）\n\n"
    md += f"## 背景故事\n{champ.get('lore', '暂无')}\n\n"
    md += f"## 基础属性\n生命值: {champ['stats']['hp']}\n攻击力: {champ['stats']['attackdamage']}\n护甲: {champ['stats']['armor']}\n\n"
    md += f"## 被动技能：{champ['passive']['name']}\n{champ['passive']['description']}\n\n"
    for spell in champ["spells"]:
        md += f"## {spell['name']}\n{spell['description']}\n\n"

    # 写入 docs 文件夹
    with open(f"docs/{champ_id}.md", "w", encoding="utf-8") as f:
        f.write(md)
    count += 1

print(f"成功转换 {count} 个英雄的 Markdown 文件！")