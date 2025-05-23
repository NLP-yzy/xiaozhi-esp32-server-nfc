from config.logger import setup_logging
import requests
import json
import re
from core.providers.llm.base import LLMProviderBase
import os
# official coze sdk for Python [cozepy](https://github.com/coze-dev/coze-py)
from cozepy import COZE_CN_BASE_URL
from cozepy import Coze, TokenAuth, Message, ChatStatus, MessageContentType, ChatEventType  # noqa

TAG = __name__
logger = setup_logging()

class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.personal_access_token = config.get("personal_access_token")
        self.bot_id = config.get("bot_id")
        self.user_id = config.get("user_id")

    def response(self, session_id, dialogue):
        coze_api_token = self.personal_access_token
        coze_api_base = COZE_CN_BASE_URL

        last_msg = next(m for m in reversed(dialogue) if m["role"] == "user")

        coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)

        for event in coze.chat.stream(
            bot_id=self.bot_id,
            user_id=self.user_id,
            additional_messages=[
                Message.build_user_question_text(last_msg["content"]),
            ],
        ):
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                print(event.message.content, end="", flush=True)
                yield event.message.content
