from config.logger import setup_logging
import openai
import requests
import json
import time
from core.providers.llm.base import LLMProviderBase

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if 'base_url' in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")
        if "你" in self.api_key:
            logger.bind(tag=TAG).error("你还没配置LLM的密钥，请在配置文件中配置密钥，否则无法正常工作")
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def response(self, session_id, dialogue, llm_role):
        try:
            logger.bind(tag=TAG).info(f"LLMProvider: response llm_role: {llm_role}")
            device_id = 11

            message = dialogue[-1]["content"]
            if message == "锄禾日当午":
                llm_role = {
                    "tangseng": "唐僧",
                    "wukong": "孙悟空",
                    "bajie": "猪八戒",
                    "shaseng": "沙僧",}.get(llm_role, "error")
                if llm_role == "error":
                    time.sleep(0.3)
                    yield("您好, 该卡片没有认证过。")
                    return

            elif llm_role != "1":
                llm_role = "观音菩萨"
                
            logger.bind(tag=TAG).info(f"LLMProvider: final response llm_role: {llm_role}")
            # Make API request
                # Use a thread to handle the streaming response
            response = requests.post(
                f"http://localhost:15001/chat",
                json={
                "device": device_id,
                "role": llm_role,
                "query": message,
                "stream": True  # We want streaming response
            },
                stream=True
            )

            for chunk in response.iter_content(chunk_size=8192):
                yield(json.loads(chunk.decode('utf-8'))["message"])
            


        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")

