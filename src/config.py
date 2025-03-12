import typing as t
from dataclasses import dataclass
import os
from string import Template

import dotenv


@dataclass
class _config:
    bot_token: str
    gemini_key: str
    admin_chat_id: int
    dashscope_api_key: str
    gemini_host: str = "https://generativelanguage.googleapis.com"
    litellm_host: str = "http://127.0.0.1:4000"

    def fix_type(self):
        if isinstance(self.admin_chat_id, str):
            self.admin_chat_id = int(self.admin_chat_id)


_values: dict = {}

# Load values from environment variables and .env files
for f in ["~/.config/.env", "/config/.env", ".env", os.environ.get("ENV_FILE", "")]:
    if "~" in f:
        f = os.path.expanduser(f)
    if f and os.path.isfile(f):
        _values.update(dotenv.dotenv_values(f))

# 处理变量
_keys = _values.keys()
_values.update(os.environ)
for k in _keys:
    if "$" in _values[k]:
        t = Template(_values[k])
        try:
            _values[k] = t.substitute(_values)
        except KeyError as e:
            raise KeyError(f"var in {repr(_values[k])} not found: {e}")

_values = {k: v for k, v in _values.items() if k in _config.__dataclass_fields__}
app = _config(**_values)
app.fix_type()


with open(".data/daily_diet_kcal", "r") as f:
    daily_diet_kcal = int(f.read())  # 每日热量摄入限额
    daily_diet_kj = daily_diet_kcal * 4.184  # 每日热量摄入限额

if __name__ == "__main__":
    print(app)
