import asyncio
import websockets
from config.logger import setup_logging
from core.connection import ConnectionHandler
from core.handle.musicHandler import MusicHandler
from core.utils.util import get_local_ip
from core.utils.db import MySQLPool
from core.utils import asr, vad, llm, tts, intent
from core.providers.db.nfc import NFCDao

TAG = __name__


class WebSocketServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self._vad, self._asr, self._llm, self._tts, self._music, self.intent = self._create_processing_instances()
        self.active_connections = set()  # 添加全局连接记录

    def _create_processing_instances(self):
        """创建处理模块实例"""
        return (
            vad.create_instance(
                self.config["selected_module"]["VAD"],
                self.config["VAD"][self.config["selected_module"]["VAD"]]
            ),
            asr.create_instance(
                self.config["selected_module"]["ASR"]
                if not 'type' in self.config["ASR"][self.config["selected_module"]["ASR"]]
                else
                self.config["ASR"][self.config["selected_module"]["ASR"]]["type"],
                self.config["ASR"][self.config["selected_module"]["ASR"]],
                self.config["delete_audio"]
            ),
            llm.create_instance(
                self.config["selected_module"]["LLM"]
                if not 'type' in self.config["LLM"][self.config["selected_module"]["LLM"]]
                else
                self.config["LLM"][self.config["selected_module"]["LLM"]]['type'],
                self.config["LLM"][self.config["selected_module"]["LLM"]],
            ),
            tts.create_instance(
                self.config["selected_module"]["TTS"]
                if not 'type' in self.config["TTS"][self.config["selected_module"]["TTS"]]
                else
                self.config["TTS"][self.config["selected_module"]["TTS"]]["type"],
                self.config["TTS"][self.config["selected_module"]["TTS"]],
                self.config["delete_audio"]
            ),
            MusicHandler(self.config),
            intent.create_instance(
                self.config["selected_module"]["Intent"]
                if not 'type' in self.config["Intent"][self.config["selected_module"]["Intent"]]
                else
                self.config["Intent"][self.config["selected_module"]["Intent"]]["type"],
                self.config["Intent"][self.config["selected_module"]["Intent"]]
            ),
        )
    
    async def initialize(self):
        """初始化服务器，包括数据库连接池"""
        # 初始化数据库连接池
        await MySQLPool.initialize(self.config['database'])
    async def start(self):
        await self.initialize()

        server_config = self.config["server"]
        host = server_config["ip"]
        port = server_config["port"]

        self.logger.bind(tag=TAG).info("Server is running at ws://{}:{}", get_local_ip(), port)
        self.logger.bind(tag=TAG).info("=======上面的地址是websocket协议地址，请勿用浏览器访问=======")
        async with websockets.serve(
                self._handle_connection,
                host,
                port
        ):
            try:
                await asyncio.Future()
            finally:
                # 确保在服务关闭时关闭数据库连接池
                await MySQLPool.close()

    async def _handle_connection(self, websocket):
        """处理新连接，每次创建独立的ConnectionHandler"""
        # 创建ConnectionHandler时传入当前server实例
        db_pool = await MySQLPool.get_pool()
        NFC_pool = NFCDao(db_pool)
        handler = ConnectionHandler(self.config, self._vad, self._asr, self._llm, self._tts, self._music, self.intent, NFC_pool)
        self.active_connections.add(handler)
        try:
            await handler.handle_connection(websocket)
        finally:
            self.active_connections.discard(handler)
