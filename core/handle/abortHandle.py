import json
import asyncio
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

nfc_role = {
"040C02200004005E409A6E3B": "tangseng",
"040C0220000400CEFF8DEF82": "tangseng",
"040C02200004000E5551F02B": "wukong",
"040C02200004006E8248F085": "wukong",
"040C02200004001E1B51F075": "bajie",
"040C02200004001E5993EFEA": "bajie",
"040C0220000400AEB147F079": "shaseng",
"040C0220000400BE3A996EA2": "shaseng",
}
async def schedule_with_interrupt(delay, coro):
    """可中断的延迟调度"""
    try:
        await asyncio.sleep(delay)
        await coro
    except asyncio.CancelledError:
        pass

async def send_stt_message(conn, text):
    """发送 STT 状态消息"""
    await conn.websocket.send(json.dumps({
        "type": "stt",
        "text": text,
        "session_id": conn.session_id}
    ))
    await conn.websocket.send(
        json.dumps({
            "type": "llm",
            "text": "😊",
            "emotion": "happy",
            "session_id": conn.session_id}
        ))
    await send_tts_message(conn, "start")


async def send_tts_message(conn, state, text=None):
    """发送 TTS 状态消息"""
    print("TTS_start!!!!")
    message = {
        "type": "tts",
        "state": state,
        "session_id": conn.session_id
    }
    if text is not None:
        message["text"] = text
    await conn.websocket.send(json.dumps(message))
    if state == "stop":
        conn.clearSpeakStatus()


async def handleAbortMessage(conn, msg_json):
    logger.bind(tag=TAG).info("Abort message received")
    # 设置成打断状态，会自动打断llm、tts任务
    nfc_info = msg_json.get("nfc", None)
    if nfc_info:
        logger.bind(tag=TAG).info(f"nfc_info: {nfc_info}")
        conn.nfc_abort = True
        conn.llm_role = nfc_role.get(nfc_info, "1")
        print("nfc刷卡，打断tts播放")
        await conn.websocket.send(json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id}))
        conn.clearSpeakStatus()
        logger.bind(tag=TAG).info("Abort_NFC message received-end")
        conn.asr_audio.clear()
        conn.reset_vad_states()
        await asyncio.sleep(0.1) # 等待0.1秒，确保tts打断
        conn.nfc_abort = False
        conn.client_have_voice = True
        conn.client_voice_stop = True
        print("???????????")
        await send_stt_message(conn, "NFC刷卡")
        print("************")
        conn.executor.submit(conn.chat, "锄禾日当午")

    else:
        conn.client_abort = True
        # conn.nfc_abort = False
        # 打断屏显任务
        # 打断客户端说话状态
        await conn.websocket.send(json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id}))
        conn.clearSpeakStatus()

        logger.bind(tag=TAG).info("Abort message received-end")
