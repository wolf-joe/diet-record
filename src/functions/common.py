import json
import os
import sys
import logging

import aiohttp


if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src import config, recorder

logger = logging.getLogger()


async def calc(exp: str) -> str:
    """
    Calculate the expression and return the result. support multiple expressions, separated by comma(,).

    :param exp: The expression to be calculated, e.g. 1+1, 2*3
    :return: The result of the calculation.
    """
    try:
        if "," in exp:
            exps = [e.strip() for e in exp.split(",")]
        else:
            exps = [exp]
        results = []
        for exp in exps:
            result = eval(exp)
            result = round(float(result), 2)
            results.append(f"{exp} = {result}")
        return "\n".join(results)
    except (SyntaxError, NameError, ZeroDivisionError) as e:
        return f"Error: {e}"


async def google_search(query: str) -> str:
    """
    Search for the query on Google and return the search results.

    :param query: The query to search for.
    """

    model = "gemini-2.0-flash"
    url = f"{config.app.gemini_host}/v1beta/models/{model}:generateContent?key={config.app.gemini_key}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"Search for '{query}' on Google"}]},
        ],
        "tools": [{"google_search": {}}],
    }
    req_str = json.dumps(payload, ensure_ascii=False)
    logger.info(f"google search: {req_str}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            text = await response.text()
            recorder.record("google search", text)
            if response.status != 200:
                raise Exception(
                    f"[uuid] Request failed with status {response.status}: {text[:500]}"
                )
            logger.info(f"search food nutrition in web: {text[:500]}")
            resp_js = json.loads(text)
            parts = resp_js["candidates"][0]["content"]["parts"]
            full_text = "\n".join([part["text"] for part in parts])
            return full_text


if __name__ == "__main__":
    import asyncio

    async def _local_test():
        print(await calc("1+1, 2*3"))
        # print(await google_search("apple"))

    asyncio.run(_local_test())
