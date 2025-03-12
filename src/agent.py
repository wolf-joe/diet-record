import base64
from collections import defaultdict
from dataclasses import dataclass
import json
import logging
import time
import aiohttp
import os
import typing as t
import sys


if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.functions import diet_record
from src import registry, config, utils, recorder, memory

logger = logging.getLogger()
litellm_api = f"{config.app.litellm_host}/v1/chat/completions"


class TokenUsage:
    def __init__(self):
        self.usage = defaultdict(int)

    def add(self, usage: dict):
        for k, v in usage.items():
            if isinstance(v, int):
                self.usage[k] += v

    def get(self):
        return dict(self.usage)


async def explain_jpg(jpg_data: bytes, token_usage: TokenUsage) -> str:
    jpg_base64 = base64.b64encode(jpg_data).decode()
    system_prompt = """你是一名经验丰富的营养师。
- 如果用户发送的图片是营养成分表，请给出营养成分表的详细信息，包含：
  - 每份的单位，如 100ml
  - 每份的热量，如 200kj
  - 每份的蛋白质含量，如 10g
  - 每份的脂肪含量，如 10g
  - 每份的碳水化合物含量，如 20g

- 如果用户发送的图片是具体的食物，请给出食物的具体名称和大致分量，如：全麦面包100g + 纯牛奶200ml
- 如果用户发送的图片是运动记录，请给出运动名称和时长，如：慢跑30分钟
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "解释这张图片",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + jpg_base64},
                },
            ],
        },
    ]
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "解释这张图片",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{jpg_base64}",
                    },
                },
            ],
        },
    ]
    model = "grok-2-vision-1212"
    model = "doubao-1.5-vision-pro-32k"
    model = "openrouter/qwen/qwen2.5-vl-72b-instruct"
    model = "gemini/gemini-2.0-flash"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "no-log": True,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(litellm_api, json=payload) as response:
            text = await response.text()
            hds_str = "\n".join([f"{k}: {v}" for k, v in response.headers.items()])
            recorder.record("image2text resp", text, hds_str)
            if response.status != 200:
                msg = f"image2text failed {response.status}: {text[:500]}"
                raise Exception(msg)

            logger.info(f"image2text resp: {text[:500]}")
            resp_js = json.loads(text)
            token_usage.add(resp_js["usage"])
            message: dict = resp_js["choices"][0]["message"]
            messages.append(message)
            return message.get("content", "")


@dataclass
class Hooks:
    pre_func_call: t.Optional[t.Callable] = None
    post_llm_resp: t.Optional[t.Callable] = None


DEFAULT_HOOKS = Hooks()


async def run_agent(
    user_text: str = "", jpg_data: bytes = b"", hooks: Hooks = DEFAULT_HOOKS
) -> None:
    model = "grok-2-1212"  # 使用tools不积极
    model = "gemini/gemini-2.0-flash"  # 使用tools不积极+幻觉
    model = "gemini/gemini-2.0-pro-exp-02-05"  # 使用tools不积极+服务不稳定
    model = "gemini/gemini-1.5-pro"  # 消极使用tools

    model = (
        "openrouter/anthropic/claude-3.7-sonnet"  # 表现不错，tools一次用一个，很费token
    )
    model = "openrouter/openai/gpt-4o-2024-11-20"  # 使用tools不积极，但提示后可用，支持批量tools
    model = "deepseek-chat"  # 表现不错，tools支持批量调用
    model = "qwen-plus-latest"  # 表现不错
    model = "qwen-max-latest"  # 表现不错
    model = "hunyuan-turbos-latest"  # 表现极差
    model = "doubao-1.5-pro-32k"  # 成功实现图片+文本输入；tools一次用一个；多轮表现稳定

    messages = []

    def add_msg(role: str, content: str):
        messages.append({"role": role, "content": content})

    # 初始化上下文
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = f"当前时间是{now}。你是一个经验丰富的营养师，你会基于我提供的工具完成用户的需求：管理食物、记录饮食和热量、查询食物的营养成分等。如果用户的输入不完整，你可以向用户询问更多信息。"
    today_diet = await diet_record._query_diet_record(0)
    today_energy_kj = sum([x.energy_kj for x in today_diet])
    today_energy_kcal = today_energy_kj / 4.184
    system_prompt += f"\n用户的每日热量摄入限额是{config.daily_diet_kcal}千卡({config.daily_diet_kj}kj)。今日已摄入{today_energy_kcal:.1f}千卡({today_energy_kj:.1f}kj)。"
    add_msg("system", system_prompt)
    # todo 长期记忆

    token_usage = TokenUsage()
    # 解释图片
    if jpg_data:
        jpg_text = await explain_jpg(jpg_data, token_usage)
        logger.info(f"explain {len(jpg_data)} bytes of image to: {jpg_text}")
        memory.add_short_memory("user", "（图片内容）")
        memory.add_short_memory("assistant", jpg_text)
        if hooks.post_llm_resp:
            await hooks.post_llm_resp(jpg_text, short_memory=True)

    if not user_text:
        return
    messages.extend(memory.get_short_memory())
    add_msg("user", user_text)
    final_resp = "<没有回答>"
    for _ in range(20):
        payload = {
            "model": model,
            "messages": messages,
            "tools": registry.tool_openai_fmt,
            "max_tokens": 2048,
            "no-log": True,
        }
        uuid = utils.get_random_str(10)
        req_str = json.dumps(payload, ensure_ascii=False)
        recorder.record("llm req " + uuid, req_str)
        logger.info(f"[{uuid}] call llm")
        async with aiohttp.ClientSession() as session:
            async with session.post(litellm_api, json=payload) as response:
                resp_text = await response.text()
                hds_str = "\n".join([f"{k}: {v}" for k, v in response.headers.items()])
                recorder.record("llm resp" + uuid, resp_text, hds_str)

                if response.status != 200:
                    if (
                        "The tool call is not supported" in resp_text
                        or "Function call is not supported for this model" in resp_text
                    ):
                        logger.warning(f"[{uuid}] llm not support tool call, retry")
                        time.sleep(1)
                        continue
                    raise Exception(
                        f"[{uuid}] llm failed {response.status}: {resp_text[:500]}"
                    )
                logger.info(f"[{uuid}] llm resp: {resp_text[:500]}")
                resp_js = json.loads(resp_text)
                token_usage.add(resp_js["usage"])
                message: dict = resp_js["choices"][0]["message"]
                messages.append(message)
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                if not tool_calls:  # llm没有输出工具调用
                    final_resp = content if content else final_resp
                    break
                if content:  # llm输出了文字
                    logger.info(f"model response: {content}")
                    if hooks.post_llm_resp:
                        await hooks.post_llm_resp(content, short_memory=False)
                for tool_call in tool_calls:
                    _id = tool_call["id"]
                    tool_name = tool_call["function"]["name"]
                    args_str = tool_call["function"]["arguments"]
                    logger.info(f"tool call: {_id} {tool_name} {args_str}")
                    if hooks.pre_func_call:
                        await hooks.pre_func_call(_id, tool_name, args_str)
                    args = json.loads(tool_call["function"]["arguments"])
                    tool_res = await registry.func_map[tool_name](**args)

                    logger.info(f"tool response: {tool_res}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": _id,
                            "content": tool_res,
                        }
                    )

    logger.info(f"token usage: {token_usage.get()}")
    memory.add_short_memory("user", user_text)
    memory.add_short_memory("assistant", final_resp)
    if hooks.post_llm_resp:
        await hooks.post_llm_resp(final_resp, short_memory=True)


async def _local_test():
    with open(".data/蒙牛牛奶营养成分表.jpg", "rb") as f:
        nutrition_facts = f.read()
    with open(".data/意面.jpg", "rb") as f:
        pasta = f.read()

    await run_agent("你是谁")
    await run_agent(
        # "今天长沙天气怎么样"
        # "我吃了200g香蕉",
        jpg_data=nutrition_facts,
        # jpg_data=pasta,
    )
    await run_agent("加入这种食物，蒙牛牛奶，每份200ml")
    import readline

    while True:
        text = input("输入：")
        if not text:
            break
        await run_agent(text)


if __name__ == "__main__":
    import asyncio

    logger = utils.init_logger()

    asyncio.run(_local_test())
