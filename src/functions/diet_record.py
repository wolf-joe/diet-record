import csv
from dataclasses import dataclass
import datetime
import json
import logging
import typing as t
import os

import aiohttp

if __name__ == "__main__":
    import sys
    import os

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src import config, utils, recorder

logger = logging.getLogger()


@dataclass
class FoodNutrition:
    name: str
    per_unit: str
    energy_kj: float
    protein: float
    fat: float
    carbs: float
    remark: str

    @staticmethod
    def db_loc():
        return ".data/food_db.csv"

    @staticmethod
    def from_dict(d: dict):
        return FoodNutrition(**d)

    def __str__(self) -> str:
        return f"{self.name} ({self.per_unit}): 热量 {self.energy_kj}kj, 蛋白质 {self.protein}g, 脂肪 {self.fat}g, 碳水化合物 {self.carbs}g, 备注 {self.remark}"


async def add_food_to_database(
    name: str,
    per_unit: str,
    energy_kj: float,
    protein: float,
    fat: float,
    carbs: float,
    remark: str,
) -> str:
    """
    Add a food item to the database.

    :param name: The name of the food item.
    :param per_unit: The unit in which the food item is measured, e.g. 100g
    :param energy_kj: The energy content of the food item.
    :param protein: The protein content of the food item.
    :param fat: The fat content of the food item.
    :param carbs: The carbohydrate content of the food item.
    :param remark: Additional information about the food item.
    :return: A success message.
    """
    item = FoodNutrition(name, per_unit, energy_kj, protein, fat, carbs, remark)
    if not os.path.isfile(item.db_loc()):
        with open(item.db_loc(), "w") as f:
            writer = csv.DictWriter(f, fieldnames=item.__annotations__.keys())
            writer.writeheader()
    with open(item.db_loc(), "a") as f:
        writer = csv.DictWriter(f, fieldnames=item.__annotations__.keys())
        writer.writerow(item.__dict__)
    return "success"


@dataclass
class DietRecord:
    food_name: str
    amount: str
    energy_kj: float
    protein: float
    fat: float
    carbs: float
    datetime: str

    @staticmethod
    def db_loc():
        return ".data/diet_record.csv"

    @staticmethod
    def from_dict(d: dict) -> "DietRecord":
        d = dict(d)
        d["energy_kj"] = float(d["energy_kj"])
        d["protein"] = float(d["protein"])
        d["fat"] = float(d["fat"])
        d["carbs"] = float(d["carbs"])
        return DietRecord(**d)

    def __str__(self) -> str:
        return f"{self.datetime}: {self.food_name} ({self.amount}): 热量 {self.energy_kj}kj, 蛋白质 {self.protein}g, 脂肪 {self.fat}g, 碳水化合物 {self.carbs}g"


async def add_diet_record(
    food_name: str,
    amount: str,
    energy_kj: float,
    protein: float,
    fat: float,
    carbs: float,
) -> str:
    """
    记录用户吃过的食物

    :param food_name: The name of the food item.
    :param amount: The amount of the food item consumed, e.g. 100g
    :param energy_kj: The energy content of the food item.
    :param protein: The protein content of the food item.
    :param fat: The fat content of the food item.
    :param carbs: The carbohydrate content of the food item.
    :return: A success message.
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = DietRecord(food_name, amount, energy_kj, protein, fat, carbs, now)
    if not os.path.isfile(record.db_loc()):
        with open(record.db_loc(), "w") as f:
            writer = csv.DictWriter(f, fieldnames=record.__annotations__.keys())
            writer.writeheader()
    with open(record.db_loc(), "a") as f:
        writer = csv.DictWriter(f, fieldnames=record.__annotations__.keys())
        writer.writerow(record.__dict__)
    return "success"


async def _query_diet_record(days_offset: int = 0) -> t.List[DietRecord]:
    now = datetime.datetime.now()
    prefix = (now - datetime.timedelta(days=days_offset)).strftime("%Y-%m-%d")
    records = []
    if os.path.isfile(DietRecord.db_loc()):
        with open(DietRecord.db_loc(), "r") as f:
            reader = csv.DictReader(f)
            records = map(DietRecord.from_dict, reader)
            records = [x for x in records if x.datetime.startswith(prefix)]
    return records


async def query_diet_record(days_offset: int = 0) -> str:
    """
    Query the user's dietary records within a day

    :param days_offset: The number of days to offset from today. 0 means today, -1 means yesterday.
    """
    if isinstance(days_offset, str):
        days_offset = int(days_offset)
    if days_offset > 0:
        return "不支持查询未来的记录"
    records = await _query_diet_record(days_offset)
    if not records:
        return "没有找到记录"
    return "\n".join([str(x) for x in records])


async def query_food_nutrition(name: str) -> str:
    """
    Query the nutrition information of a food item.

    :param name: The name of the food item.
    """
    already_known: t.List[FoodNutrition] = []
    if os.path.isfile(FoodNutrition.db_loc()):
        with open(FoodNutrition.db_loc(), "r") as f:
            reader = csv.DictReader(f)
            already_known = [FoodNutrition.from_dict(row) for row in reader]

    payload = {
        "contents": [],
        "tools": [{"google_search": {}}, {"code_execution": {}}],
    }

    def add_text(text: str):
        payload["contents"].append({"role": "user", "parts": [{"text": text}]})

    prompt = f"你是一个经验丰富的营养师，可以通过已知信息或搜索引擎查询食物的营养信息。我们现在需要查询`{name}`的营养成分信息，"
    prompt += "包括每份的数量（如 每100g）、热量（单位：千焦，注意不是千卡）、蛋白质含量（单位：克）、脂肪含量（单位：克）、碳水化合物含量（单位：克）等。"
    add_text(prompt)
    if already_known:
        lines = [str(x) for x in already_known]
        add_text("已知食物信息：\n" + "\n".join(lines))

    req_str = json.dumps(payload, ensure_ascii=False)
    uuid = utils.get_random_str(10)
    logger.info(f"[{uuid}] search food nutrition in web: {req_str[:500]}")
    recorder.record(f"search food " + uuid, req_str)

    model = "gemini-2.0-flash"
    url = f"{config.app.gemini_host}/v1beta/models/{model}:generateContent?key={config.app.gemini_key}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            text = await response.text()
            hds_str = "\n".join([f"{k}: {v}" for k, v in response.headers.items()])
            recorder.record("search food " + uuid, text, hds_str)
            if response.status != 200:
                raise Exception(
                    f"[{uuid}] Request failed with status {response.status}: {text[:500]}"
                )
            resp_js = json.loads(text)
            parts = resp_js["candidates"][0]["content"]["parts"]
            full_text = "\n".join([part["text"] for part in parts])
            return full_text


async def main():
    global logger
    logger = utils.init_logger()
    # add_food_to_database("apple", "100g", 52, 0.3, 0.2, 14)
    # res = await search_food_nutrition_in_web("生意大利面")
    # res = await search_food_nutrition("意大利面,意大利面酱,水浸金枪鱼罐头")
    res = await query_diet_record()
    print(res)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
