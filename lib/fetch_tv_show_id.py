from lxml import etree
import requests
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def fetch_html(url):
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text, "成功"
    except requests.RequestException as e:
        return None, str(e)

def extract_tv_show_id(html_content, tv_show_name):
    tree = etree.HTML(html_content)
    modules = tree.xpath('//li[span[@class="search-results-modules-name"][contains(text(), "电影") or contains(text(), "电视剧")]]')

    if not modules:
        return None, "未找到匹配的电影或电视剧模块"

    for module in modules:
        subject_links = module.xpath('.//li//a/@href')
        subject_titles = module.xpath('.//li//span[@class="subject-title"]/text()')

        if not subject_titles:
            continue

        for idx, title in enumerate(subject_titles):
            if title == tv_show_name:
                return subject_links[idx].split('/')[-2], "成功"
    return None, "未找到匹配的电视剧"


def fetch_tv_show_id(tv_show_name):
    start_time = time.time()  # 记录开始时间
    search_url = f"https://m.douban.com/search/?query={tv_show_name}"
    html_content, html_status_msg = fetch_html(search_url)

    if not html_content:
        elapsed_time = time.time() - start_time  # 计算耗时
        return None, html_status_msg, elapsed_time

    tv_show_id, extract_status_msg = extract_tv_show_id(html_content, tv_show_name)
    elapsed_time = time.time() - start_time  # 计算耗时

    return tv_show_id, extract_status_msg, elapsed_time

# 下面的代码可以用于测试或独立运行
"""
# 从用户那里获取电视剧名
tv_show_name = input("请输入你想查找的电视剧名: ")

# 获取电视剧ID，状态信息和耗时
tv_show_id, status_msg, elapsed_time = fetch_tv_show_id(tv_show_name)

# 打印结果或生成API URL
if tv_show_id:
    print(f"找到的电视剧ID为：{tv_show_id}")
    api_url = f"https://m.douban.com/movie/subject/{tv_show_id}/"
    print(f"相应的API地址为：{api_url}")
    print(f"获取成功，耗时: {elapsed_time:.2f}秒")
else:
    print(f"未找到对应的电视剧, 状态信息：{status_msg}, 耗时: {elapsed_time:.2f}秒")
"""