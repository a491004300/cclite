import json
import requests
import random
from datetime import datetime
import os
from plugins.cclite.lib import fetch_tv_show_id  # 引入函数
# from fetch_tv_show_id import fetch_tv_show_id

def get_tv_show_interests(tv_show_name, media_type='tv', count=10, order_by='hot'):
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
        "Accept": "application/json"
    }

    rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    tv_show_id, _, _ = fetch_tv_show_id.fetch_tv_show_id(tv_show_name)  # 使用函数来获取 ID
    # tv_show_id, _, _ = fetch_tv_show_id(tv_show_name)  # 使用函数来获取 ID


    if tv_show_id:  # 检查是否获取到 ID
        base_url = f"https://m.douban.com/rexxar/api/v2/{media_type}/"  # 根据 media_type 设置 base_url
        start = random.randint(0, 5) * 10
        url = f"{base_url}{tv_show_id}/interests?count=30&order_by={order_by}&start={start}"
        HEADERS["Referer"] = f"https://m.douban.com/{media_type}/subject/{tv_show_id}/?refer=home"

        max_retries = 3  # 最大重试次数
        retry_count = 0  # 当前重试次数
        while retry_count < max_retries:
            try:
                response = requests.get(url, headers=HEADERS, timeout=5)  # 设置超时时间为5秒
                response.raise_for_status()
                interests = response.json().get('interests', [])
                selected_interests = random.sample(interests, min(len(interests), count))

                formatted_comments = []
                for idx, interest in enumerate(selected_interests):
                    rank = rank_emojis[idx] if idx < 10 else str(idx + 1)
                    comment_text = interest['comment']
                    formatted_comment = f"{rank} {comment_text}"
                    formatted_comments.append(formatted_comment)

                return formatted_comments
            except requests.RequestException as e:
                retry_count += 1
        
        return ["❌ 最大重试次数已达到，获取评论失败."]  # 最大重试次数后返回空列表
    
    
def fetch_media_details(tv_show_name, media_type='tv'):
    # 获取media的ID
    media_id, _, _ = fetch_tv_show_id.fetch_tv_show_id(tv_show_name)
    
    if not media_id:
        return "❌ 电影或电视剧ID获取失败."

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
        "Accept": "application/json",
        "Referer": f"https://m.douban.com/{media_type}/subject/{media_id}/?refer=home"
    }

    url = f"https://m.douban.com/rexxar/api/v2/{media_type}/{media_id}"
    
    max_retries = 3  # 最大重试次数
    retry_count = 0  # 当前重试次数

    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            response.raise_for_status()
            details = response.json()
            title = details.get("title", "")
            rating_value = details.get("rating", {}).get("value", "")
            pubdate = details.get("pubdate", [""])[0]

            result = f"📺{title}，⭐豆瓣评分{rating_value}，📅上映日期为:{pubdate}\n"
            for vendor in details.get("vendors", []):
                platform_name = vendor.get("title", "")
                play_url = vendor.get("url", "")
                result += f"{platform_name}:▶️{play_url}\n"

            return result.strip()

        except requests.RequestException as e:
            retry_count += 1

    return f"❌ 获取{media_type}详情失败，重试次数已达最大值."

# # Example usage
# tv_show_name = input("请输入你想查找的电视剧或电影名: ")
# media_type = input("请输入媒体类型（tv 或 movie）: ")

# details = fetch_media_details(tv_show_name, media_type)
# print(details)


# # 用户输入剧名和数量
# tv_show_name = input("请输入你想查找的电视剧或电影名: ")
# media_type = input("请输入媒体类型（tv 或 movie）: ")
# count = int(input("请输入你想查看的评论数量: "))

# # 获取评论
# formatted_comments = get_tv_show_interests(tv_show_name, media_type, count, 'hot')

# # 打印结果
# for formatted_comment in formatted_comments:
#     print(formatted_comment)
#     print("------")

