import csv
from dataclasses import dataclass
import datetime
import os
import typing as t


@dataclass
class FitnessRecord:
    datetime: str
    name: str
    duration: str
    remark: str = ""

    @staticmethod
    def db_loc():
        return ".data/fitness_record.csv"

    @staticmethod
    def from_dict(d: dict):
        return FitnessRecord(**d)

    def __str__(self) -> str:
        msg = f"{self.datetime}, 运动: {self.name}, 时长: {self.duration}"
        if self.remark:
            msg += f", 备注: {self.remark}"
        return msg


async def add_fitness_record(
    name: str,
    duration: str,
    remark: str = "",
) -> str:
    """
    记录用户的运动记录。

    :param name: The name of the fitness activity, eg 练腿
    :param duration: The duration of the fitness activity, eg 30分钟
    :param remark: Additional remarks for the fitness record, optional.
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = FitnessRecord(now, name, duration, remark)
    if not os.path.isfile(record.db_loc()):
        with open(record.db_loc(), "w") as f:
            writer = csv.DictWriter(f, fieldnames=record.__annotations__.keys())
            writer.writeheader()
    with open(record.db_loc(), "a") as f:
        writer = csv.DictWriter(f, fieldnames=record.__annotations__.keys())
        writer.writerow(record.__dict__)
    return "success"


async def query_fitness_record(days_offset=0) -> str:
    """
    查询用户的运动记录。

    :param days_offset: The number of days to offset from today, eg 0 for today, -1 for yesterday.
    :return: A list of FitnessRecord objects.
    """
    if isinstance(days_offset, str):
        days_offset = int(days_offset)
    if days_offset > 0:
        return "未来的记录无法查询"
    if not os.path.isfile(FitnessRecord.db_loc()):
        return "暂无记录"
    with open(FitnessRecord.db_loc(), "r") as f:
        reader = csv.DictReader(f)
        prefix = (
            datetime.datetime.now() - datetime.timedelta(days=days_offset)
        ).strftime("%Y-%m-%d")
        records = map(FitnessRecord.from_dict, reader)
        records = [record for record in records if record.datetime.startswith(prefix)]
    if not records:
        return "暂无记录"
    return "\n".join(map(str, records))


async def _local_test():
    await add_fitness_record("跑步", "30分钟")
    await add_fitness_record("举重", "1小时", "哑铃")
    print(await query_fitness_record())


if __name__ == "__main__":
    import asyncio

    asyncio.run(_local_test())
