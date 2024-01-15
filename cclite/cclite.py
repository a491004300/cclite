from openai import OpenAI
import plugins
import requests
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from plugins import *
from common.log import logger
from datetime import datetime
import os
import time
import traceback
from .lib import fetch_tv_show_id as fetch_tv_show_id, tvshowinfo as tvinfo, function as fun, search_google as google


def read_file(path):
    with open(path, mode="r", encoding="utf-8") as f:
        return f.read()


@plugins.register(
    name="cclite", desc="A plugin that supports multi-function_call", version="0.1.0", author="cc", desire_priority=66
)
class CCLite(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        logger.info(f"[cclite] current directory: {curdir}")
        logger.info(f"加载配置文件: {config_path}")
        function_path = os.path.join(curdir, "lib", "functions.json")
        if not os.path.exists(config_path):
            logger.info("[RP] 配置文件不存在，将使用config.json.template模板")
            config_path = os.path.join(curdir, "config.json.template")
            logger.info(f"[cclite] config template path: {config_path}")
        try:
            with open(function_path, "r", encoding="utf-8") as f:
                functions = json.load(f)
                self.functions = functions
                logger.info(f"[cclite] functions content: {functions}")

            config = super().load_config()
            if not config:
                if os.path.exists(config_path):
                    # 读取config.json配置文件
                    config = json.loads(read_file(config_path))
            logger.info(f"[cclite] config content: {config}")
            self.openai_api_key = config.get("open_ai_api_key")
            if len(self.openai_api_key) <= 10:
                raise Exception("[cclite] openai_api_key is required")
            self.openai_api_base = config.get("open_ai_api_base") or "https://api.openai.com/v1"
            self.client = OpenAI(api_key=self.openai_api_key, base_url=self.openai_api_base)
            self.alapi_key = config.get("alapi_key", "")
            self.bing_subscription_key = config.get("bing_subscription_key", "")
            self.google_api_key = config.get("google_api_key", "")
            self.google_cx_id = config.get("google_cx_id", "")
            self.getwt_key = config.get("getwt_key", "")
            self.cc_api_base = config.get("cc_api_base") or "https://api.lfei.cc"
            self.functions_openai_model = config.get("functions_openai_model", "gpt-3.5-turbo")
            self.assistant_openai_model = config.get("assistant_openai_model", "gpt-3.5-turbo-16k")
            self.temperature = config.get("temperature", 0.9)
            self.prompt = {
                "bing_google_search": "现在时间是{time}，根据用户要求和返回的搜索结果(包括标题、来源、内容、链接),将各条结果进行汇总分析,适当归类,使其结果符合搜索引擎返回的结果(只要简洁明了呈现分析结果以满足提问的需求即可)。适当加入emoji表情,以增加用户的体验感。不用提供新闻链接",
                "webpilot_search": "现在时间是{time}，根据用户要求和返回的搜索结果(包括标题、来源、内容、链接),将各结果进行汇总分析,对搜索结果适当归类,适当划分段落结构(每段可按需设置段落标题并搭配emoji)，使其结果符合搜索引擎返回的结果(简洁明了呈现分析结果以满足提问的需求即可)。适当加入emoji表情,以增加用户的体验感。",
                "search_bing_news": "现在时间是{time},请根据搜索引擎返回的信息,按照用户的要求,告诉用户'{name}'想要的信息。要求在汇总分析结果的时候,适当加入代表实时数据的emoji表情,以增加用户的体验感。尽量保持返回的信息结构(新闻标题、来源、新闻内容、新闻链接,适当加入合适的emoji)的一致性,以便用户更好地阅读。最后将各条结果根据用户要求进行汇总分析。",
                "get_tv_show_interests": "请分析以下的影视评论,逐条罗列(无序罗列,配合emoji表达感受)并最后提供一句总结,表示推荐度如：'推荐5⭐、3⭐...'",
                "fetch_top_tv_shows": "为以下的电视剧榜单推荐, 适当进行优化排版,使其显得更像一个'热门榜单',并添加合适的emoji。",
                "get_morning_news": "根据返回的早报的内容,优化其排版、分类,同时保留其内容的丰富完整性,根据新闻条目的类型添加不同的符合新闻主题的emoji",
                "fetch_latest_news": "保留返回的新闻内容的排版格式,告知用户当前的时间{time},保留内容的丰富性和完整性,在最后对列出的新闻进行适当总结,使用户更生动地理解新闻内容,确保段落结构清晰,总结内容可以适当添加emoji。链接前后不要添加括号",
                "fetch_financial_news": "保留返回的新闻内容的排版格式,确保段落结构清晰,告知用户当前的时间{time},保留内容的丰富性和完整性,对新闻内容适当归类，在最后对列出的新闻进行适当总结,使用户更生动地理解新闻内容,总结内容适当添加emoji。",
                "fetch_ai_news": "保留返回的新闻内容的排版格式,告知用户当前的时间{time},保留内容的丰富性和完整性,在最后对列出的新闻进行适当总结,使用户更生动地理解新闻内容,确保段落结构清晰,总结内容可适当添加emoji。",
                "fetch_hero_trending": "以下返回的数据是王者荣耀英雄相关的胜率、登场率等数据,近30天的热度值,请排版美观地展示各个不同分段地胜率、禁用率等数据,并对返回的英雄近30天的热度进行趋势分析,根据这些日期对应的数值判断英雄的受欢迎程度、热门程度,数值越大,越热门,可以从<最热门的时间段、热门的趋势、热度上升/下降的走势分析等多个维度>,预测预判未来这个英雄是否值得玩家使用,分析完毕后进行一个受欢迎程度的推荐,分析时请优化排版,方便阅读,适当使用emoji,逻辑清晰,分析时不要把观察到的数据全部罗列出,只需要对数据进行分析即可。不要使用markdown语法",
                "get_weather": "告知用户当前的时间{time}, 根据返回的城市的天气情况,并根据用户的需求(例如气温、是否下雨、未来天气等),精确整理出当前城市的重要天气信息,注意美化排版,确保段落结构清晰,适当使用emoji,使返回的内容像极了生动的天气预报!不要使用markdown语法",
                "fetch_nowplaying_movies": "告知用户当前的时间{time}, 根据返回的正在上映的电影的内容,要优化其排版,确保段落结构清晰,添加适当的动态实时emoji,以增加用户的体验感。",
                "get_hero_ranking": "以下返回的是当前时间{time}的英雄梯度榜,请根据排名根据不同T度等级进行优化排版,适当添加emoji,使其更像一个榜单,以增加用户的体验感。",
                "get_weather_by_city_name": "根据用户查询的当前城市的重要天气信息,美化排版,确保段落结构清晰,适当使用emoji,使返回的内容像极了生动的天气预报!",
                "get_hotlist": "以下是返回的热榜信息,请优化排版,体现热榜的特点,确保段落结构清晰,不要提供链接。",
                "fetch_cls_news": "请保留返回的财联社新闻内容的排版格式,告知用户当前的时间{time},保留内容的丰富性和完整性,分析和总结新闻重点,使用户更生动地理解新闻内容,确保段落结构清晰,总体内容长度控制在500字以内,总结内容适当添加emoji。",
            }
            self.default_prompt = "当前中国北京时间是：{time}，你是一个可以通过联网工具获取各种实时信息、也可以使用联网工具访问指定URL内容的AI助手,请根据联网工具返回的信息按照用户的要求，告诉用户'{name}'想要的信息,要求排版美观，依据联网工具提供的内容进行描述！严禁胡编乱造！如果用户没有指定语言，默认中文。"
            logger.info("[cclite] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[cclite] init failed, config.json not found.")
            else:
                logger.warn("[cclite] init failed." + str(e))
            raise e

    def get_prompt_for_function(self, function_name):
        return self.prompt.get(function_name, self.default_prompt)

    def base_url(self):
        return self.cc_api_base

    # 定义常量来表示不同的会话阶段和查询类型
    STAGE = "current_stage"
    QUERY_TYPE = "query_type"
    QUERY_VALUE = "query_value"

    # 查询类型与提示信息的映射
    query_types = {
        "查天气": "你要查询哪个城市的天气呀？",
        "查新闻": "你想看哪类新闻？财经头条、微博热搜、实时要闻...",
        "查聊天": "你想查谁的聊天记录？或者你想搜索哪个聊天记录关键词？试试吧",
        "查王者": "关于王者荣耀，你可以查看英雄梯度榜/查英雄的数据/热度趋势...",
        # "刷抖音": "你想看什么内容的抖音视频？",
        "看剧": "你想看哪部电视剧或电影？输入电视剧/电影+名字即可，例如电视剧汉武大帝。",
    }

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        # 过滤不需要处理的内容类型
        if context.type not in [
            ContextType.TEXT,
            ContextType.IMAGE,
            ContextType.IMAGE_CREATE,
            ContextType.FILE,
            ContextType.SHARING,
        ]:
            # filter content no need solve
            return

        if context.type == ContextType.TEXT:
            input_messages = self.build_input_messages(context)
            logger.debug(f"Input messages: {input_messages}")

            # 运行会话并获取输出
            result = self.run_conversation(input_messages, e_context)
            called_function_name, conversation_output = result if result else (None, None)
            # 处理对话输出
            if conversation_output:
                # if called_function_name:
                # 处理当我们有一个具体的函数名时的情况
                # 如果函数返回的是视频播放源
                if called_function_name == "fetch_dyvideo_sources" and isinstance(conversation_output, list):
                    reply_type = ReplyType.VIDEO_URL
                    for video_url in conversation_output:
                        # 对于每个视频源，单独发送一个视频消息
                        _set_reply_text(video_url, e_context, level=reply_type)
                # else:
                #  ... 其他基于函数名称的逻辑 ...
                else:
                    # 对于其他类型的回复
                    conversation_output = remove_markdown(conversation_output)
                    reply_type = ReplyType.TEXT
                    _set_reply_text(conversation_output, e_context, level=reply_type)

                logger.debug(f"Conversation output: {conversation_output}")

    def build_input_messages(self, context):
        find_content = context.content
        return [{"role": "user", "content": find_content}]

    def run_conversation(self, input_messages, e_context: EventContext):
        global function_response
        context = e_context["context"]
        called_function_name = None  # 初始化变量
        logger.debug(f"User input: {input_messages}")  # 用户输入
        start_time = time.time()  # 开始计时
        response = self.client.chat.completions.create(
            model=self.functions_openai_model,
            messages=input_messages,
            functions=self.functions,
            function_call="auto",
        )
        logger.debug(f"Initial response: {response}")  # 打印原始的response以及其类型
        message = response.choices[0].message  # 获取模型返回的消息。

        logger.debug(f"message={message}")
        # 检查模型是否希望调用函数
        if message.function_call:
            function_name = message.function_call.name
            called_function_name = function_name  # 更新变量
            logger.debug(f"Function call: {function_name}")  # 打印函数调用

            # 处理各种可能的函数调用，执行函数并获取函数的返回结果
            if function_name == "fetch_latest_news":  # 1.获取最新新闻
                api_url = f"{self.base_url()}/latest_news/"

                try:
                    # 发送GET请求到你的FastAPI服务
                    response = requests.get(api_url)
                    response.raise_for_status()  # 如果响应状态码不是200，将抛出异常
                    function_response = response.json()  # 解析JSON响应体为字典
                    logger.debug(f"Function response: {function_response}")  # 打印函数响应
                    function_response = function_response["results"]  # 返回结果字段中的数据
                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅获取实时要闻成功,正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅获取实时要闻成功,正在整理。🕒耗时{elapsed_time:.2f}秒")

                except requests.RequestException as e:
                    logger.error(f"Request to API failed: {e}")
                    _set_reply_text("获取最新新闻失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "fetch_financial_news":  # 2.获取财经新闻
                api_url = f"{self.base_url()}/financial_news/"

                try:
                    # 发送GET请求到你的FastAPI服务
                    response = requests.get(api_url)
                    response.raise_for_status()  # 如果响应状态码不是200，将抛出异常
                    function_response = response.json()  # 解析JSON响应体为字典
                    logger.debug(f"Function response: {function_response}")  # 打印函数响应
                    function_response = function_response["results"]  # 返回结果字段中的数据
                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅获取实时财经资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅获取实时财经资讯成功，正在整理。🕒耗时{elapsed_time:.2f}秒")

                except requests.RequestException as e:
                    logger.error(f"Request to API failed: {e}")
                    _set_reply_text("获取财经新闻失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "get_weather_by_city_name":  # 3.获取天气
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                logger.debug(f"函数调用返回的原始字符串: {function_args_str}")
                function_args = json.loads(function_args_str)
                logger.debug(f"解析后的函数调用参数: {function_args}")
                city_name = function_args.get("city_name", "北京")  # 默认为北京
                logger.debug(f"查询的城市名参数值: {city_name} (类型: {type(city_name)})")
                adm = function_args.get("adm", None)  #
                user_key = self.getwt_key

                if context.kwargs.get("isgroup"):
                    msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(e_context, "@{name}\n🔜正在获取{city}的天气情况🐳🐳🐳".format(name=nickname, city=city_name))
                else:
                    _send_info(e_context, "🔜正在获取{city}的天气情况🐳🐳🐳".format(city=city_name))

                # 向API端点发送GET请求，获取指定城市的天气情况
                try:
                    response = requests.get(
                        self.base_url() + "/weather/",
                        params={"city_name": city_name, "user_key": user_key, "adm": adm},
                    )
                    response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                    function_response = response.json()
                    function_response = function_response.get("results", "未知错误")
                except Exception as e:
                    logger.error(f"Error fetching weather info: {e}")
                    _set_reply_text("获取天气信息失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
                return called_function_name, function_response

            elif function_name == "request_train_info":  # 4.获取火车票信息
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                departure = function_args.get("departure", None)  # 默认值可以根据需要设置
                arrival = function_args.get("arrival", None)
                num_trains = function_args.get("num_trains", 3)  # 默认返回前3个车次
                date = function_args.get("date", None)  # 默认值为None，使用API的默认日期

                if context.kwargs.get("isgroup"):
                    msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(
                        e_context,
                        "@{name}\n🔍正在查询从{departure}到{arrival}的火车票信息，请稍后...".format(
                            name=nickname, departure=departure, arrival=arrival
                        ),
                    )
                else:
                    _send_info(
                        e_context,
                        "🔍正在查询从{departure}到{arrival}的火车票信息，请稍后...".format(departure=departure, arrival=arrival),
                    )
                # 向端点发送请求，获取指定路线的火车票信息
                try:
                    response = requests.get(
                        self.base_url() + "/train_info/",
                        params={"departure": departure, "arrival": arrival, "num_trains": num_trains, "date": date},
                    )
                    response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                    function_response = response.json()
                    function_response = function_response["results"]
                except Exception as e:
                    logger.error(f"Error fetching train info: {e}")
                    _set_reply_text("获取火车票信息失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
                return function_response

            elif function_name == "fetch_nowplaying_movies":  # 6.获取正在上映的电影
                # 发送信息到用户，告知正在获取数据
                if e_context["context"].kwargs.get("isgroup"):
                    msg = e_context["context"].kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(e_context, f"@{nickname}\n🔜正在获取最新影讯🐳🐳🐳")
                else:
                    _send_info(e_context, "🔜正在获取最新影讯🐳🐳🐳")

                # 构建API请求的URL
                api_url = f"{self.base_url()}/now_playing_movies/"

                # 向FastAPI端点发送GET请求
                try:
                    response = requests.get(api_url)
                    response.raise_for_status()  # 检查请求是否成功

                    # 解析响应数据
                    data = response.json()
                    function_response = data.get("results")
                    status_msg = data.get("status")
                    elapsed_time = data.get("elapsed_time")

                    # 根据响应设置回复文本
                    if status_msg == "失败":
                        _set_reply_text(f"\n❌获取失败: {status_msg}", e_context, level=ReplyType.TEXT)
                    else:
                        _set_reply_text(
                            f"\n✅获取成功，耗时: {elapsed_time:.2f}秒\n{function_response}", e_context, level=ReplyType.TEXT
                        )
                except requests.HTTPError as http_err:
                    # 如果请求出错，则设置失败消息
                    _set_reply_text(f"\n❌HTTP请求错误: {http_err}", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")

            elif function_name == "fetch_top_tv_shows":  # 7.获取豆瓣最热电视剧榜单
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                limit = function_args.get("limit", 10)
                type_ = function_args.get("type", "tv")  # 默认为电视剧
                if context.kwargs.get("isgroup"):
                    msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(e_context, "@{name}\n☑️正在为您查询豆瓣的最热影视剧榜单🐳🐳🐳".format(name=nickname))
                else:
                    _send_info(e_context, "☑️正在为您查询豆瓣的最热影视剧榜单，请稍后...")
                # 调用函数，获取豆瓣最热电视剧榜单
                # 向API端点发送GET请求，获取最热影视剧榜单
                try:
                    response = requests.get(
                        self.base_url() + "/top_tv_shows/",
                        params={
                            "limit": limit,
                            "type": type_,
                        },
                    )
                    response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                    function_response = response.json()
                    function_response = function_response.get("results", "未知错误")
                except Exception as e:
                    logger.error(f"Error fetching top TV shows info: {e}")
                    _set_reply_text("获取最热影视剧榜单失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "fetch_ai_news":  # 7.获取AI新闻
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                max_items = function_args.get("max_items", 6)
                try:
                    response = requests.get(self.base_url() + "/ainews/", params={"max_items": max_items})
                    response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                except Exception as e:
                    logger.error(f"Error fetching AI news: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Traceback:\n{traceback.format_exc()}")
                    _set_reply_text(f"获取AI新闻失败，请稍后再试。错误信息: {e}", e_context, level=ReplyType.TEXT)
                    return  # 终止后续代码执行

                try:
                    function_response = response.json()
                    function_response = function_response.get("results", "未知错误")
                except ValueError as e:  # 捕获JSON解析错误
                    logger.error(f"JSON parsing error: {e}")
                    function_response = "未知错误"

                elapsed_time = time.time() - start_time  # 计算耗时

                try:
                    # 发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅获取AI资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅获取AI资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                except Exception as e:
                    logger.error(f"Error sending response: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Traceback:\n{traceback.format_exc()}")

                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            # elif function_name == "fetch_dyvideo_sources":  # 抖音视频源获取
            #     # 从message里提取函数调用参数
            #     function_args_str = message.function_call.arguments or "{}"
            #     function_args = json.loads(function_args_str)
            #     search_content = function_args.get("search_content", "")
            #     max_videos = function_args.get("max_videos", 1)
            #     try:
            #         response = requests.get(
            #             self.base_url() + "/dyvideo_sources/",
            #             params={"search_content": search_content, "max_videos": max_videos},
            #         )
            #         response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
            #     except Exception as e:
            #         logger.error(f"Error fetching Douyin video sources: {e}")
            #         logger.error(f"Exception type: {type(e).__name__}")
            #         logger.error(f"Traceback:\n{traceback.format_exc()}")
            #         _set_reply_text(f"获取抖音视频源失败，请稍后再试。错误信息: {e}", e_context, level=ReplyType.TEXT)
            #         return  # 终止后续代码执行

            #     try:
            #         function_response = response.json()
            #         function_response = function_response.get("results", "未知错误")
            #         elapsed_time = time.time() - start_time  # 计算耗时
            #         # 仅在成功获取数据后发送信息
            #         if context.kwargs.get("isgroup"):
            #             msg = context.kwargs.get("msg")  # 这是WechatMessage实例
            #             nickname = msg.actual_user_nickname  # 获取nickname
            #             _send_info(e_context, f"@{nickname}\n✅获取dy视频成功。🕒耗时{elapsed_time:.2f}秒")
            #         else:
            #             _send_info(e_context, f"✅获取dy视频成功。🕒耗时{elapsed_time:.2f}秒")
            #     except ValueError as e:  # 捕获JSON解析错误
            #         logger.error(f"JSON parsing error: {e}")
            #         function_response = "未知错误"
            #     logger.debug(f"Function response: {function_response}")  # 打印函数响应
            #     return called_function_name, function_response

            elif function_name == "fetch_cls_news":  # 获取CLS新闻
                try:
                    response = requests.get(self.base_url() + "/clsnews/")
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error fetching CLS news: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Traceback:\n{traceback.format_exc()}")
                    _set_reply_text(f"获取CLS新闻失败,请稍后再试,错误信息为 {e}", e_context, level=ReplyType.TEXT)

                try:
                    # 验证并解析JSON响应
                    function_response = response.json()
                except ValueError as e:  # 捕获JSON解析错误
                    logger.error(f"JSON parsing error: {e}")
                    function_response = "未知错误"
                else:
                    function_response = function_response.get("results", "未知错误")

                elapsed_time = time.time() - start_time  # 计算耗时

                # 发送信息
                try:
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")
                        nickname = msg.actual_user_nickname
                        _send_info(e_context, f"@{nickname}\n✅获取财联社新闻成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅获取财联社新闻成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                except Exception as e:
                    logger.error(f"Error sending response: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Traceback:\n{traceback.format_exc()}")

                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "fetch_hero_trending":  # 8.获取英雄热度趋势
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                hero_name = function_args.get("hero_name", "未指定英雄")
                if context.kwargs.get("isgroup"):
                    msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(
                        e_context, "@{name}\n☑️正在为您进行指定英雄（{hero}）的数据获取，请稍后...".format(name=nickname, hero=hero_name)
                    )
                else:
                    _send_info(e_context, f"☑️正在为进行指定英雄（{hero_name}）的数据获取，请稍后...")

                # 调用函数并获取返回值
                function_response = fun.get_hero_info(hero_name)
                # 转换为 JSON 格式
                # function_response = json.dumps(function_response, ensure_ascii=False)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
                return called_function_name, function_response

            elif function_name == "get_hero_ranking":  # 9.获取英雄梯度榜
                # 构建 API 请求的 URL
                api_url = f"{self.base_url()}/hero_ranking/"

                # 向 FastAPI 端点发送 GET 请求
                try:
                    response = requests.get(api_url)
                    response.raise_for_status()  # 检查请求是否成功
                    # 解析响应数据
                    data = response.json()
                    function_response = data.get("results")
                    # 根据响应设置回复文本
                    if function_response is None or "查询出错" in function_response:
                        _set_reply_text(f"❌获取失败: {function_response}", e_context, level=ReplyType.TEXT)
                    else:
                        _send_info(f"✅获取成功\n{function_response}", e_context, level=ReplyType.TEXT)
                except requests.HTTPError as http_err:
                    # 如果请求出错，则设置失败消息
                    _set_reply_text(f"❌HTTP请求错误: {http_err}", e_context, level=ReplyType.TEXT)
                except Exception as err:
                    # 如果发生其他错误，则设置失败消息
                    _set_reply_text(f"❌请求失败: {err}", e_context, level=ReplyType.TEXT)
                # 记录响应
                logger.debug(f"Function response: {function_response}")

            elif function_name == "get_tv_show_interests":  # 10.获取电视剧或电影的评论
                com_reply = Reply()
                com_reply.type = ReplyType.TEXT
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)  # 使用 json.loads 将字符串转换为字典
                tv_show_name = function_args.get("tv_show_name", "未指定电视剧或电影")
                media_type = function_args.get("media_type", "tv")  # 默认为 'tv'
                count = function_args.get("count", 10)  # 默认10条评论
                order_by = function_args.get("orderBy", "hot")  # 默认按照'hot'排序

                if context.kwargs.get("isgroup"):
                    msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(
                        e_context,
                        "@{name}\n☑️正在为您获取《{show}》的{media_type_text}信息和剧评，请稍后...".format(
                            name=nickname, show=tv_show_name, media_type_text="电影" if media_type == "movie" else "电视剧"
                        ),
                    )
                else:
                    _send_info(
                        e_context,
                        "☑️正在为您获取《{show}》的{media_type_text}信息和剧评，请稍后...".format(
                            show=tv_show_name, media_type_text="电影" if media_type == "movie" else "电视剧"
                        ),
                    )

                # 使用 fetch_tv_show_id 获取电视剧 ID
                tv_show_id, status_msg, elapsed_time = fetch_tv_show_id.fetch_tv_show_id(
                    tv_show_name
                )  # 假设函数返回 ID, 状态信息和耗时
                logger.debug(
                    f"TV show ID: {tv_show_id}, status message: {status_msg}, elapsed time: {elapsed_time:.2f}秒"
                )  # 打印获取的 ID 和状态信息
                # 初始化回复内容
                com_reply.content = ""  # 假设 Reply 是一个您定义的类或数据结构

                # 根据获取的电视剧 ID 设置回复内容
                if tv_show_id is None:
                    # 如果获取 ID 失败，设置失败消息
                    com_reply.content += f"❌获取影视信息失败: {status_msg}"
                else:
                    # 如果获取 ID 成功，设置成功消息和链接
                    com_reply.content += f"✅获取影视信息成功，耗时: {elapsed_time:.2f}秒\n现可访问页面：https://m.douban.com/movie/subject/{tv_show_id}/\n以下为平台及播放跳转链接:"

                    # 调用 fetch_media_details 函数获取影视详细信息
                    media_details = tvinfo.fetch_media_details(tv_show_name, media_type)
                    com_reply.content += (
                        f"\n{media_details}\n-----------------------------\n😈即将为你呈现精彩剧评🔜"  # 将详细信息添加到回复内容中
                    )

                # 发送回复
                _send_info(e_context, com_reply.content)
                # 调用函数
                function_response = tvinfo.get_tv_show_interests(
                    tv_show_name, media_type=media_type, count=count, order_by=order_by
                )  # 注意这里我们直接调用函数，并没有使用shows_map
                function_response = json.dumps({"response": function_response}, ensure_ascii=False)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "get_morning_news":  # 11.获取每日早报
                function_response = fun.get_morning_news(api_key=self.alapi_key)
                elapsed_time = time.time() - start_time  # 计算耗时
                _send_info(e_context, f"✅获取早报成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "get_hotlist":  # 12.获取热榜信息
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)  # 使用 json.loads 将字符串转换为字典
                hotlist_type = function_args.get("type", "未指定类型")
                try:
                    # 直接调用get_hotlist获取数据
                    function_response = fun.get_hotlist(api_key=self.alapi_key, type=hotlist_type)
                    logger.debug(f"Function response: {function_response}")
                except Exception as e:
                    logger.error(f"Error fetching hotlist: {e}")
                    _set_reply_text(f"❌获取热榜信息失败,请稍后再试,错误信息为 {e}", e_context, level=ReplyType.TEXT)

            elif function_name == "bing_google_search":  # 13.搜索功能
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)  # 使用 json.loads 将字符串转换为字典
                search_query = function_args.get("query", "未指定关键词")
                search_count = function_args.get("count", 1)
                if "搜索" in context.content or "必应" in context.content.lower():
                    function_response = fun.search_bing(
                        subscription_key=self.bing_subscription_key, query=search_query, count=int(search_count)
                    )
                    function_response = json.dumps(function_response, ensure_ascii=False)
                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅Bing搜索{search_query}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅Bing搜索{search_query}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    logger.debug(f"Function response: {function_response}")  # 打印函数响应
                elif "谷歌" in context.content or "谷歌搜索" in context.content or "google" in context.content.lower():
                    function_response = google.search_google(
                        search_terms=search_query,
                        iterations=1,
                        count=1,
                        api_key=self.google_api_key,
                        cx_id=self.google_cx_id,
                        model=self.assistant_openai_model,
                        client=self.client,
                    )
                    function_response = json.dumps(function_response, ensure_ascii=False)
                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅Google搜索{search_query}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅Google搜索{search_query}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    logger.debug(f"Function response: {function_response}")  # 打印函数响应
                else:
                    return None

            elif function_name == "webpilot_search":  # 调用WebPilot内容获取函数
                # 从message里提取函数调用参数
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                search_term = function_args.get("search_term", "")  # 默认搜索词为空字符串

                # 向API端点发送POST请求，获取与搜索词相关的内容
                try:
                    response = requests.post(self.base_url() + "/webpilot_search/", json={"search_term": search_term})
                    response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                    function_response = response.json()
                    function_response = function_response.get("results", "未知错误")
                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get("isgroup"):
                        msg = context.kwargs.get("msg")  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅Webpilot搜索{search_term}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅Webpilot搜索{search_term}成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    logger.debug(f"Function response: {function_response}")  # 打印函数响应
                except Exception as e:
                    logger.error(f"Error fetching content: {e}")
                    _set_reply_text(f"获取内容失败，请稍后再试。错误信息 {e}", e_context, level=ReplyType.TEXT)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应

            elif function_name == "search_bing_news":  # 14.搜索新闻
                function_args_str = message.function_call.arguments or "{}"
                function_args = json.loads(function_args_str)
                logger.debug(f"Function arguments: {function_args}")  # 打印函数参数
                search_query = function_args.get("query", "未指定关键词")
                search_count = function_args.get("count", 10)
                function_response = fun.search_bing_news(
                    count=search_count,
                    subscription_key=self.bing_subscription_key,
                    query=search_query,
                )
                function_response = json.dumps(function_response, ensure_ascii=False)
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
            else:
                return

            # 以下为个性化提示词，并交给第二个模型处理二次响应
            prompt_template = self.get_prompt_for_function(function_name)

            msg: ChatMessage = e_context["context"]["msg"]
            current_date = datetime.now().strftime("%Y年%m月%d日%H时%M分")
            if e_context["context"]["isgroup"]:
                prompt = prompt_template.format(
                    time=current_date, bot_name=msg.to_user_nickname, name=msg.actual_user_nickname
                )
            else:
                prompt = prompt_template.format(
                    time=current_date, bot_name=msg.to_user_nickname, name=msg.from_user_nickname
                )
            # 将函数的返回结果发送给第二个模型
            logger.debug("messages: %s", [{"role": "system", "content": prompt}])
            # 打印即将发送给 openai.ChatCompletion 的 messages 参数
            logger.info("Preparing messages for openai.ChatCompletion...")
            messages = [
                {"role": "system", "content": f"{prompt}"},
                *input_messages,
                {"role": "assistant", "content": f"{message}"},
                {"role": "function", "name": f"{function_name}", "content": f"{function_response}"},
            ]
            logger.debug(f"messages: {messages}")

            second_response = self.client.chat.completions.create(
                model=self.assistant_openai_model,
                messages=messages,
                temperature=float(self.temperature),
            )
            # 打印原始的second_response以及其类型
            # second_response_json = json.dumps(second_response, ensure_ascii=False)
            # logger.debug(f"Full second_response: {second_response_json}")
            # logger.debug(f"called_function_name: {called_function_name}")
            # messages.append(second_response["choices"][0]["message"])
            return called_function_name, second_response.choices[0].message.content
        else:
            # 如果模型不希望调用函数，直接打印其响应
            logger.debug(f"未调用函数，原始模型响应: {message.content}")  # 打印模型的响应
            return

    def get_help_text(self, verbose=False, **kwargs):
        # 初始化帮助文本，插件的基础描述
        help_text = "\n🤖 基于微信的多功能聊天机器人，提供新闻、天气、火车票信息、娱乐内容等实用服务。\n"

        # 如果不需要详细说明，则直接返回帮助文本
        if not verbose:
            return help_text

        # 添加详细的使用方法到帮助文本中
        help_text += """
        🗞 实时新闻
        - "实时要闻", "实时新闻": 获取澎湃新闻的实时要闻。
        - "财经头条": 获取第一财经的财经新闻。可指定数量（默认8条）。
        - "AI资讯": 获取AI资讯。可指定数量（默认8条）。
        - "财联社新闻"：获取财联社新闻。可指定数量。

        🌅 每日早报
        - "早报": 获取每日早报信息。

        🔥 热榜信息
        - "热榜": 获取各大平台的热门话题。可指定平台（知乎、微博等）。

        🔍 搜索功能
        - "搜索 xxx": 使用必应、谷歌进行搜索，实现联网。
        - 新增 "Webpilot" 搜索功能，通过"w搜索"一般能准确调用，搜索内容质量较高。
        
        🎮 王者荣耀
        - "xx英雄数据", "xx英雄热度": 获取指定英雄的数据和趋势。
        - "英雄梯度榜": 获取王者荣耀英雄梯度榜。(来自苏苏的荣耀助手)

        📺 娱乐信息
        - "热播电视剧", "热播电影": 获取豆瓣热门电视剧和电影。
        - "热映电影": 获取电影院热映电影信息。
        - "电视剧/电影XXX": 获取指定电视剧或电影的信息、评价。

        ☀ 天气信息
        - "北京的天气怎么样": 获取北京的天气信息。        
        """
        # 🎥 抖音视频
        # - "抖音+内容": 获取与搜索内容相关的抖音视频。
        # 返回帮助文本
        return help_text


def _send_info(e_context: EventContext, content: str):
    reply = Reply(ReplyType.TEXT, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])


def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS


def remove_markdown(text):
    # 替换Markdown的粗体标记
    text = text.replace("**", "")
    # 替换Markdown的标题标记
    text = text.replace("### ", "").replace("## ", "").replace("# ", "")
    return text
