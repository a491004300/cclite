import asyncio
import concurrent
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from common.log import logger

# from pyppeteer import launch

"""谷歌独立搜索函数，通过访问相关URL并提交给GPT整理获得更详细的信息"""

__all__ = ["search_google"]
__author__ = "chazzjimel/跃迁"
__date__ = "2023.6.21"


async def get_url_with_pyppeteer(url):
    logger.debug("正在启动浏览器...")
    browser = await launch()
    logger.debug("正在打开新页面...")
    page = await browser.newPage()
    logger.debug(f"正在访问URL: {url}")
    await page.goto(url)
    logger.debug("正在获取页面内容...")
    content = await page.content()
    logger.debug("正在关闭浏览器...")
    await browser.close()
    return content


def get_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=2)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        logger.warning("无法访问该URL: %s, error: %s", url, str(e))

        try:
            # 使用 asyncio.run 启动协程
            logger.debug("使用pyppeteer重新尝试访问URL...")
            html = asyncio.run(get_url_with_pyppeteer(url))
            soup = BeautifulSoup(html, "html.parser")
            paragraphs = soup.find_all("p")
            paragraphs_text = [p.get_text() for p in paragraphs]
            return paragraphs_text
        except Exception as e:
            logger.warning("在使用 pyppeteer 解析URL时出现问题: %s, error: %s", url, str(e))
            return None

    try:
        soup = BeautifulSoup(response.content, "html.parser")
        paragraphs = soup.find_all("p")
        paragraphs_text = [p.get_text() for p in paragraphs]
        return paragraphs_text

    except Exception as e:
        logger.warning("在解析URL时出现问题: %s, error: %s", url, str(e))
        return None


def build_search_url(
    searchTerms, count=None, startIndex=None, language=None, cx=None, hq=None, dateRestrict=None, key=None
):
    params = {
        "q": searchTerms,
        "num": count,
        "start": startIndex,
        "lr": language,
        "cx": cx,
        "sort": "date",
        "filter": 1,
        "hq": hq,
        "dateRestrict": dateRestrict,
        "key": key,
        "alt": "json",
    }

    params = {k: v for k, v in params.items() if v is not None}

    encoded_params = urlencode(params)

    base_url = "https://www.googleapis.com/customsearch/v1?"
    search_url = base_url + encoded_params

    return search_url


def get_summary(item, model, client, search_terms):
    logger.debug("正在获取链接内容：%s", item["link"])
    link_content = get_url(item["link"])
    if not link_content:
        logger.warning("无法获取链接内容：%s", item["link"])
        return None
    logger.debug("link_content: %s", link_content)
    # 获取链接内容字符数量
    link_content_str = " ".join(link_content)
    content_length = len(link_content_str)
    logger.debug("content_length: %s", content_length)

    # 如果内容少于200个字符，则pass
    if content_length < 200:
        logger.warning("链接内容低于200个字符：%s", item["link"])
        return None
    # 如果内容大于15000个字符，则截取中间部分
    elif content_length > 5000:
        logger.warning("链接内容高于15000个字符，进行裁断：%s", item["link"])
        start = (content_length - 5000) // 2
        end = start + 5000
        link_content = link_content[start:end]

    logger.debug("正在提取摘要：%s", link_content)
    summary = process_content(str(link_content), model, client, search_terms=search_terms)
    return summary


def search_google(model, client, search_terms, count, api_key, cx_id, iterations):
    all_summaries = []
    MAX_RETRIES = 3  # 最大重试次数

    for i in range(iterations):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                startIndex = i * count + 1
                search_url = build_search_url(search_terms, count=10, cx=cx_id, key=api_key, startIndex=startIndex)
                logger.debug("正在进行第 %d 次搜索，URL：%s", i + 1, search_url)
                response = requests.get(search_url, timeout=3)
                model = model
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    logger.debug(f"search_google items:{items}")

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        future_to_item = {
                            executor.submit(get_summary, item, model, client, search_terms): item for item in items
                        }
                        for future in as_completed(future_to_item):
                            try:
                                summary = future.result(timeout=5)  # 设置超时时间
                                if summary is not None:
                                    all_summaries.append("【搜索结果内容摘要】：\n" + summary)
                            except concurrent.futures.TimeoutError:
                                logger.error("处理摘要任务超时")
                            except Exception as e:
                                logger.error("在提取摘要过程中出现错误：%s", str(e))
                    break
                else:
                    logger.error(f"Request failed with status code {response.status_code}")

                # time.sleep(1)  # Delay to prevent rate limiting

            except Exception as e:
                retries += 1
                logger.error("在执行搜索过程中出现错误：%s", str(e))
        else:  # 当达到最大重试次数后的处理
            logger.error("Max retries reached. Moving to next iteration.")

    # 判断 all_summaries 是否为空
    if not all_summaries:
        return ["实时联网暂未获取到有效信息内容，请更换关键词或再次重试······"]

    return all_summaries


def process_content(content, model, client, search_terms=None):
    current_date = datetime.now().strftime("%Y年%m月%d日")
    summary = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"""当前中国北京日期：{current_date}，请判断并提取内容中与"{search_terms}"有关的详细内容，必须保留细节，准确的时间线以及富有逻辑的排版！如果与时间、前因后果、上下文等有关内容不能忽略，不可以胡编乱造！""",
            },
            {"role": "assistant", "content": content},
        ],
        temperature=0.8,
    )
    return summary.choices[0].message.content
