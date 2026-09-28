import json, os, urllib.request, time

# 读取 champion.json 总表
with open("champion.json", encoding="utf-8") as f:
    data = json.load(f)["data"]

version = data["Aatrox"]["version"]  # 自动获取版本号
os.makedirs("champions", exist_ok=True)

print(f"开始下载版本 {version} 的全部英雄详情...")

for champ_id in data.keys():
    save_path = f"champions/{champ_id}.json"
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion/{champ_id}.json"
    try:
        urllib.request.urlretrieve(url, save_path)
        print(f"已下载：{champ_id}")
        time.sleep(0.2)  # 稍微停顿，防止请求过快
    except Exception as e:
        print(f"下载失败 {champ_id}: {e}")

print("全部下载完成！")