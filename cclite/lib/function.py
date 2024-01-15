import json
import time
import urllib.parse
import urllib.request
import requests
import random

from typing import Any
from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import urlencode


__author__ = 'cc'
__date__ = '2023.6.21'

#获取王者荣耀英雄的数据
def get_hero_info(hero_name):
    base_url = "https://api.91m.top/hero/v1/app.php"
    params = {
        'type': 'getHeroInfo',
        'heroName': hero_name,
        'openId': 'be0d19e71ca435024ccaa2796d59cb37'
    }
    
    headers = {
        'Content-Type': "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(base_url, params=params, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            hero_info = response_data.get('data', {}).get('heroInfo', {})

            title_parts = hero_info.get('title', '未知标题').split()
            gradient = title_parts[-1] if title_parts else '未知梯度'
            label = hero_info.get('label', '未知标签').split("，")
            hotness_rank = label[0] if len(label) > 0 else '未知热度'
            ban_rank = label[1] if len(label) > 1 else '未知禁用'
            ranks = ["所有段位", "1350巅峰赛", "顶端排位", "顶端巅峰赛"]
            rank_data = {
                "🚫 Ban Rate （禁用率）": hero_info.get('banRate', ['N/A']*4),
                "🎭 Pick Rate （出场率）": hero_info.get('pickRate', ['N/A']*4),
                "🛑 BP Rate （禁选率）": hero_info.get('bpRate', ['N/A']*4),
                "🏆 Win Rate （胜率）": hero_info.get('winRate', ['N/A']*4)
            }
            
            formatted_data = f"{hero_name}当前的英雄梯度是✨ {gradient}\n🔥{hotness_rank}，🔕{ban_rank}\n"
            for key, values in rank_data.items():
                formatted_data += f"\n{key}:\n"
                for rank, value in zip(ranks, values):
                    formatted_data += f"{rank}: {value}%\n"

            return formatted_data.strip()
        else:
            return {"error": f"API responded with status code {response.status_code}"}
    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

#必应搜索引擎
def search_bing(subscription_key, query, count=10):
    """
    This function makes a call to the Bing Web Search API with a query and returns relevant web search.
    Documentation: https://docs.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
    """
    # Construct a request
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    mkt = 'zh-CN'
    params = {'q': query, 'mkt': mkt, 'count': count}
    headers = {'Ocp-Apim-Subscription-Key': subscription_key}

    # Call the API
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        # Parse the response
        data = response.json()

        refined_data = []

        # Extract the required news data
        news_data = data.get('news', {}).get('value', [])
        if news_data:
            for news_item in news_data:
                provider_name = news_item['provider'][0]['name'] if news_item.get('provider') else "未知"
                refined_data.append({
                    '📰标题': news_item.get('name', ""),
                    '📝新闻内容': news_item.get('description', ""),
                    '🌐来源': provider_name,
                    # '🔗新闻链接': news_item.get('url', "")
                })
        else:  # If 'news' data is not present, fetch from 'webPages'
            web_pages_data = data.get('webPages', {}).get('value', [])
            for page_item in web_pages_data:
                refined_data.append({
                    '📰标题': page_item.get('name', ""),
                    '📝描述': page_item.get('snippet', ""),
                    # '🔗链接': page_item.get('url', "displayUrl")
                })
        return refined_data
    except Exception as ex:
        raise ex

#获取早报新闻
def get_morning_news(api_key):
    """获取每日早报、新闻的实现代码"""
    url = "https://v2.alapi.cn/api/zaobao"
    payload = f"token={api_key}&format=json"
    headers = {'Content-Type': "application/x-www-form-urlencoded"}

    try:
        response = requests.request("POST", url, data=payload, headers=headers)
        morning_news_info = response.json()
        if morning_news_info['code'] == 200:  # 验证请求是否成功
            return json.dumps(morning_news_info, ensure_ascii=False)
        else:
            raise ValueError
    except Exception:
        error_msgs = [
            "对不起，我们目前无法获取早报新闻信息",
            "糟糕，早报新闻信息现在不可用",
            "抱歉，获取早报新闻信息遇到了问题",
            "哎呀，早报新闻信息似乎不在服务范围内",
        ]
        return random.choice(error_msgs)  # 随机选择一个错误消息返回

#获取热榜信息
def get_hotlist(api_key, type):
    """获取热榜信息的实现代码，但不返回链接信息"""
    type_mapping = {
        "知乎": "zhihu",
        "微博": "weibo",
        "微信": "weixin",
        "百度": "baidu",
        "头条": "toutiao",
        "163": "163",
        "36氪": "36k",
        "历史上的今天": "hitory",
        "少数派": "sspai",
        "CSDN": "csdn",
        "掘金": "juejin",
        "哔哩哔哩": "bilibili",
        "抖音": "douyin",
        "吾爱破解": "52pojie",
        "V2EX": "v2ex",
        "Hostloc": "hostloc",
    }

    # 如果用户直接提供的是英文名，则直接使用
    try:
        if type.lower() in type_mapping.values():
            api_type = type.lower()
        else:
            api_type = type_mapping.get(type, None)
            if api_type is None:
                raise ValueError(f"未知的类型: {type}")

        url = "https://v2.alapi.cn/api/tophub"
        payload = {"token": api_key, "type": api_type}
        headers = {'Content-Type': "application/x-www-form-urlencoded"}

        response = requests.request("POST", url, data=payload, headers=headers)
        hotlist_info = response.json()
        if hotlist_info['code'] == 200:  # 验证请求是否成功
            return hotlist_info  # 返回整个热榜数据
        else:
            raise ValueError
    except Exception:
        error_msgs = [
            "对不起，我们目前无法获取实时热榜信息",
            "糟糕，实时热榜信息现在不可用",
            "抱歉，获取实时热榜信息遇到了问题",
            "哎呀，实时热榜信息似乎不在服务范围内",
        ]
        return random.choice(error_msgs)  # 随机选择一个错误消息返回

def search_bing_news(count, subscription_key, query):
    # Set your endpoint
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"

    # Set other parameters
    mkt = 'zh-CN'

    # Construct the request
    headers = {'Ocp-Apim-Subscription-Key': subscription_key}
    params = {'mkt': mkt, 'q': query, 'count': count}

    try:
        # Send the request
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()  # 如果发生网络错误，此句会抛出异常
        # Get and return the response data
        data = response.json()
        return data
    except Exception:
        error_msgs = [
            "对不起，我们无法获取新闻",
            "糟糕，获取新闻现在不可用",
            "抱歉，新闻搜索遇到了问题",
            "哎呀，获取新闻似乎出了些问题"
        ]
        return {"error": random.choice(error_msgs)}  # 随机选择一个错误消息返回
