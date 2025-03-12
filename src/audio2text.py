import logging
import os

import dashscope
from dashscope.api_entities.dashscope_response import MultiModalConversationResponse

from src import config

logger = logging.getLogger()

dashscope.api_key = config.app.dashscope_api_key


def qwen_asr(filepath: str) -> str:
    """Use qwen's ASR to convert audio to text"""
    abs_path = os.path.abspath(filepath)
    messages = [
        {
            "role": "user",
            "content": [{"audio": f"file://{abs_path}"}],
        }
    ]
    response = dashscope.MultiModalConversation.call(
        model="qwen-audio-asr", messages=messages
    )
    assert isinstance(response, MultiModalConversationResponse)
    logger.info(f"qwen-audio-asr response: {response}")
    if response.status_code != 200:
        raise Exception(f"Failed to call qwen-audio-asr: {response}")
    return response.output["choices"][0]["message"]["content"][0]["text"]
