import datetime
import json
import logging
import random
import string
import time
import typing as t
import uuid

random.seed(uuid.uuid4().int)

BASE36_ALPHABET = string.digits + string.ascii_lowercase
cst_zone = datetime.timezone(datetime.timedelta(hours=8))  # China Standard Time
ts_begin = datetime.datetime(2024, 6, 1, tzinfo=cst_zone).timestamp()


def get_random_str(length: int, choices=None) -> str:
    """生成随机字符串，内容默认为大小写字母和数字"""
    if choices is None:
        choices = BASE36_ALPHABET

    if length > 6:
        now_str = int_to_base36(int(time.time() - ts_begin))
        tail = "".join(random.choices(choices, k=length - 6))
        return f"{now_str:0>6}{tail}"

    return "".join(random.choices(choices, k=length))


def int_to_base36(num: int):
    # Encode the integer to base36
    if num == 0:
        return BASE36_ALPHABET[0]

    encoded = []
    while num > 0:
        num, rem = divmod(num, len(BASE36_ALPHABET))
        encoded.append(BASE36_ALPHABET[rem])

    # The encoded list is in reverse order
    encoded.reverse()
    return "".join(encoded)


def init_logger(name="") -> logging.Logger:
    """初始化日志记录器， 只应该在主程序/本地测试中调用"""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger(name=name)


def extract_json(text: str) -> t.Any:
    """
    Extract the JavaScript code from the text.

    :param text: The text from which the JavaScript code is to be extracted.
    :return: The JavaScript code.
    """
    # 去掉开头的部分
    if "```json" in text:
        text = text.split("```json")[1]
    elif "```" in text:
        text = text.split("```")[1]

    # 去掉结尾的部分
    if "```" in text:
        text = text.split("```")[0]

    # 去掉每行末尾的 //
    text = "\n".join([line.split("//")[0] for line in text.split("\n")])

    try:
        js = json.loads(text)
        return js
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {text}") from e
