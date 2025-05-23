import time
import wave
import sys
import io
from abc import ABC, abstractmethod
from config.logger import setup_logging
from typing import Optional, Tuple, List
import uuid
import opuslib_next
from core.providers.asr.base import ASRProviderBase
from websockets.sync.client import connect
import opuslib
import os
import time
import ssl
import json
from multiprocessing import Process, Manager
from queue import Queue


TAG = __name__
logger = setup_logging()

host='127.0.0.1'
port=10095
chunk_size_str="5, 10, 5"
chunk_size_list = [int(x) for x in chunk_size_str.split(",")]
chunk_interval=10
hotword=''
# audio_in='../audio/asr_example.wav'
audio_fs=16000
send_without_sleep=True
thread_num=1
words_max_print=10000
output_dir=None
use_itn=1
mode='offline'
# 全局变量

voices = Queue()
offline_msg_done=False

if output_dir is not None:
    # if os.path.exists(args.output_dir):
    #     os.remove(args.output_dir)
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

def record_from_scp(pcm_data):
    global voices, websocket, offline_msg_done_event

    is_finished = False
    ssl_context = ssl.SSLContext()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    # url = f"wss://{host}:{port}"
    # with connect(f"wss://{host}:{port}",ssl_context=ssl_context) as websocket:
    with connect(f"ws://{host}:{port}",ssl_context=None) as websocket:
        # 只处理 hotwords 信息
        fst_dict = {}
        hotword_msg = ""
        if hotword.strip() != "":
            f_scp = open(hotword)
            hot_lines = f_scp.readlines()
            for line in hot_lines:
                words = line.strip().split(" ")
                if len(words) < 2:
                    print("Please check the format of hotwords")
                    continue
                try:
                    fst_dict[" ".join(words[:-1])] = int(words[-1])
                except ValueError:
                    print("Please check the format of hotwords")
            hotword_msg = json.dumps(fst_dict)
            print(hotword_msg)

        sample_rate = audio_fs
        wav_format = "pcm"
        use_itn = True  # 假设 ITN（反标准化）总是启用

        
            # 发送初始消息
        message = json.dumps({
            "mode": "offline",  # 设置为 offline 模式
            "chunk_size": len(pcm_data),  # PCM 数据的大小，或设置为一个合适的值
            "audio_fs": sample_rate,
            "wav_name": "demo", 
            "wav_format": wav_format, 
            "is_speaking": True, 
            "hotwords": hotword_msg, 
            "itn": use_itn
        })
        
        websocket.send(message)

        # 发送音频数据（二进制数据）
        websocket.send(pcm_data)

        # 发送结束标志（文本数据）
        websocket.send(json.dumps({"is_speaking": False}))

        # 接收 ASR 结果
        try:
            result = websocket.recv()
            result = json.loads(result)
            text = result.get("text", "")
        except Exception as e:
            print("Exception:", e)
            # 如果捕获到异常，也可以选择返回最后的 text
            text = "None"

        return text
    
async def message(id):
    global websocket, voices, offline_msg_done, offline_msg_done_event
    text_print = ""
    last_text = ""  # 用来保存最后一个 text


    try:
        # 只接收一次消息
        meg = await websocket.recv()  # 这里只接收一次
        meg = json.loads(meg)
        wav_name = meg.get("wav_name", "demo")
        text = meg["text"]
        timestamp = ""
        offline_msg_done = meg.get("is_final", False)
        if "timestamp" in meg:
            timestamp = meg["timestamp"]

        last_text = text  # 每次接收到新消息时，更新 last_text
        offline_msg_done_event.set()

        # 打印信息（仅打印一次）
        if meg.get("mode") == "offline":
            if timestamp != "":
                text_print += "{} timestamp: {}".format(text, timestamp)
            else:
                text_print += "{}".format(text)

            # 打印离线结果
            print("\rpid" + str(id) + ": " + wav_name + ": " + text_print)
            offline_msg_done_event.set()
            print(f"time:{time.time():.3f}")
            offline_msg_done = True  # 标记消息处理完成

    except Exception as e:
        print("Exception:", e)
        # 如果捕获到异常，也可以选择返回最后的 text

    return last_text

# 捕获标准输出
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        self.model_dir = config.get("model_dir")
        self.output_dir = config.get("output_dir")  # 修正配置键名
        self.delete_audio_file = delete_audio_file

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)


    def save_audio_to_file(self, opus_data: List[bytes], session_id: str) -> str:
        """将Opus音频数据解码并保存为WAV文件"""
        file_name = f"asr_{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.output_dir, file_name)

        decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, 单声道
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus解码错误: {e}", exc_info=True)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes = 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(pcm_data))

        return file_path
    def save_audio_to_pcm(self, opus_data: List[bytes], session_id: str) -> str:
        """将Opus音频数据解码并保存为WAV文件"""
        file_name = f"asr_{session_id}_{uuid.uuid4()}.wav"
        # file_path = os.path.join(self.output_dir, file_name)

        decoder = opuslib.Decoder(16000, 1)  # 16kHz, 单声道
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
                pcm_data.append(pcm_frame)
            except opuslib.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus解码错误: {e}", exc_info=True)

        

        return pcm_data

    async def speech_to_text(self, opus_data: List[bytes], session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """语音转文本主处理逻辑"""
        file_path = None
        try:
            # 保存音频文件
            start_time = time.time()
            pcm_data = self.save_audio_to_pcm(opus_data, session_id)
            # 语音识别
            text = str(record_from_scp(pcm_data))
            logger.bind(tag=TAG).info(f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}")
            return text, file_path

        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)
            return "", None