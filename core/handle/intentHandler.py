from config.logger import setup_logging
import json
from core.handle.sendAudioHandle import send_stt_message
from core.handle.iotHandle import send_iot_conn
from core.utils.dialogue import Message
from config.functionCallConfig import FunctionCallConfig
import asyncio
from enum import Enum
import re

TAG = __name__
logger = setup_logging()


class Action(Enum):
    NOTFOUND = (0, "没有找到函数")
    NONE = (1, "啥也不干")
    RESPONSE = (2, "直接回复")
    REQLLM = (3, "调用函数后再请求llm生成回复")

    def __init__(self, code, message):
        self.code = code
        self.message = message


class ActionResponse:
    def __init__(self, action: Action, result, response):
        self.action = action  # 动作类型
        self.result = result  # 动作产生的结果
        self.response = response  # 直接回复的内容



def get_functions():
    """获取功能调用配置"""
    return FunctionCallConfig


async def recognize_intent(volume_value, text):
    """
    识别用户输入文本中的意图
    
    参数:
        text (str): 用户输入的文本
        volume_value (int): 当前音量值
        
    返回:
        dict: 包含识别到的意图和相关信息
    """
    # 转换为小写以进行不区分大小写的匹配
    text = text.lower()
    
    # 定义播放音乐相关的关键词
    play_music_keywords = [
        "播放音乐", "放音乐", "听音乐", "开始播放", "放歌", "听歌",
        "播放", "播一首", "来首歌"
    ]
    
    # 定义调节音量相关的关键词
    volume_control_keywords = [
        "调节音量", "音量", "声音", "调大", "调小", "调高", "调低",
        "增大", "减小", "放大", "放小", "大声", "小声"
    ]
    
    # 定义调大音量的关键词
    volume_up_keywords = [
        "大", "增加", "调大", "调高", "放大", "增大", "提高", "加大"
    ]
    
    # 定义调小音量的关键词
    volume_down_keywords = [
        "小", "减小", "调小", "调低", "放小", "降低", "减少", "变小"
    ]
    
    # 首先检查是否包含调节音量意图
    is_volume_intent = False
    matched_volume_keyword = None
    
    for keyword in volume_control_keywords:
        if keyword in text:
            is_volume_intent = True
            matched_volume_keyword = keyword
            break
            
    if is_volume_intent:
        # 已确认是音量调节意图，接下来判断具体的调节方式
        
        # 检测"调到/设为/设置为"等表示设置到特定值的模式
        set_volume_patterns = [
            r"调到(\d+)[%％]?",
            r"设为(\d+)[%％]?", 
            r"设置为(\d+)[%％]?",
            r"设置到(\d+)[%％]?",
            r"调节到(\d+)[%％]?",
            r"提高到(\d+)[%％]?",
            r"降低到(\d+)[%％]?",
            r"音量(\d+)[%％]?"  # 直接说"音量80"这种情况
        ]
        
        # 检测增加/减少特定值的模式
        change_volume_patterns = [
            r"(提高|增加|加大|调高|调大|增大)(\d+)[%％]?",
            r"(降低|减小|减少|调低|调小|减弱)(\d+)[%％]?"
        ]
        
        # 首先检查是否是设置到特定值
        for pattern in set_volume_patterns:
            match = re.search(pattern, text)
            if match:
                volume_value = int(match.group(1))
                volume_action = "set"
                break
        else:
            # 如果不是设置到特定值，检查是否是增加/减少特定值
            for pattern in change_volume_patterns:
                match = re.search(pattern, text)
                if match:
                    change_type = match.group(1)
                    change_value = int(match.group(2))
                    
                    if change_type in ["提高", "增加", "加大", "调高", "调大", "增大"]:
                        volume_action = "change"
                        volume_value += change_value
                    else:
                        volume_action = "change"
                        volume_value -= change_value
                    break
            else:
                # 如果没有找到数字，就是简单的调大/调小
                volume_up = any(word in text for word in volume_up_keywords)
                volume_down = any(word in text for word in volume_down_keywords)
                
                if volume_up and not volume_down:
                    volume_action = "up"
                    volume_value += 20  # 默认调整20
                elif volume_down and not volume_up:
                    volume_action = "down"
                    volume_value -= 20  # 默认调整20
                else:
                    # 无法确定方向
                    volume_action = "unknown"
        
        # 确保音量值在0到100之间
        if volume_value > 100:
            volume_value = 100
        elif volume_value < 0:
            volume_value = 0
        
        return {
            "intent": "volume_control",
            "confidence": 1.0,
            "matched_keyword": matched_volume_keyword,
            "volume_action": volume_action,
            "volume_value": volume_value
        }
    
    # 再检查是否包含播放音乐意图
    for keyword in play_music_keywords:
        if keyword in text:
            return {
                "intent": "play_music",
                "confidence": 1.0,
                "matched_keyword": keyword
            }
    
    # 如果没有匹配到任何意图
    return {
        "intent": "unknown",
        "confidence": 0.0
    }


def handle_llm_function_call(conn, function_call_data):
    try:
        function_name = function_call_data["name"]

        if function_name == "handle_exit_intent":
            # 处理退出意图
            try:
                say_goodbye = json.loads(function_call_data["arguments"]).get("say_goodbye", "再见")
                conn.close_after_chat = True
                logger.bind(tag=TAG).info(f"退出意图已处理:{say_goodbye}")
                return ActionResponse(action=Action.RESPONSE, result="退出意图已处理", response=say_goodbye)
            except Exception as e:
                logger.bind(tag=TAG).error(f"处理退出意图错误: {e}")

        elif function_name == "play_music":
            # 处理音乐播放意图
            try:
                song_name = "random"
                arguments = function_call_data["arguments"]
                if arguments is not None and len(arguments) > 0:
                    args = json.loads(arguments)
                    song_name = args.get("song_name", "random")
                music_intent = f"播放音乐 {song_name}" if song_name != "random" else "随机播放音乐"

                # 执行音乐播放命令
                future = asyncio.run_coroutine_threadsafe(
                    conn.music_handler.handle_music_command(conn, music_intent),
                    conn.loop
                )
                future.result()
                return ActionResponse(action=Action.RESPONSE, result="退出意图已处理", response="还想听什么歌？")
            except Exception as e:
                logger.bind(tag=TAG).error(f"处理音乐意图错误: {e}")
        elif function_name == "volume_control":
            try:
                volume_value = function_call_data["volume_value"]
                # send_iot_conn(conn, "Speaker", "SetVolume", {"volume": default_iot_volume})
            except Exception as e:
                logger.bind(tag=TAG).error(f"处理音量控制意图错误: {e}")
        else:
            return ActionResponse(action=Action.NOTFOUND, result="没有找到对应的函数", response="没有找到对应的函数处理相对于的功能呢，你可以需要添加预设的对应函数处理呢")
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理function call错误: {e}")

    return None


async def handle_user_intent(conn, text):
    """
    Handle user intent before starting chat
    
    Args:
        conn: Connection object
        text: User's text input
    
    Returns:
        bool: True if intent was handled, False if should proceed to chat
    """
    # 检查是否有明确的退出命令
    if await check_direct_exit(conn, text):
        return True

    if conn.use_function_call_mode:
        # 使用支持function calling的聊天方法,不再进行意图分析
        return False

    logger.bind(tag=TAG).info(f"分析用户意图: {text}")

    # 使用LLM进行意图分析
    if conn.llm_intent == "nointent":
        intent_parms = await recognize_intent(conn.device_volume, text)
        logger.bind(tag=TAG).info(f"nointent模式的意图获取: {intent_parms}")
        if intent_parms["intent"] == "unknown":
            return False
        return await process_intent_parms_result(conn, intent_parms, text)
    else:
        intent = await analyze_intent_with_llm(conn, text)
        # 处理各种意图
        if not intent:
            return False
        return await process_intent_result(conn, intent, text)


async def check_direct_exit(conn, text):
    """检查是否有明确的退出命令"""
    cmd_exit = conn.cmd_exit
    for cmd in cmd_exit:
        if cmd in text:
            logger.bind(tag=TAG).info(f"识别到明确的退出命令: {text}")
            await conn.close()
            return True
    return False


async def analyze_intent_with_llm(conn, text):
    """使用LLM分析用户意图"""
    if not hasattr(conn, 'intent') or not conn.intent:
        logger.bind(tag=TAG).warning("意图识别服务未初始化")
        return None

    # 对话历史记录
    dialogue = conn.dialogue
    try:
        intent_result = await conn.intent.detect_intent(dialogue.dialogue, text)
        logger.bind(tag=TAG).info(f"意图识别结果: {intent_result}")

        # 尝试解析JSON结果
        try:
            intent_data = json.loads(intent_result)
            if "intent" in intent_data:
                return intent_data["intent"]
        except json.JSONDecodeError:
            # 如果不是JSON格式，尝试直接获取意图文本
            return intent_result.strip()

    except Exception as e:
        logger.bind(tag=TAG).error(f"意图识别失败: {str(e)}")

    return None


async def process_intent_result(conn, intent, original_text):
    """处理意图识别结果"""
    # 处理退出意图
    if "结束聊天" in intent:
        logger.bind(tag=TAG).info(f"识别到退出意图: {intent}")

        # 如果正在播放音乐，可以关了 TODO

        # 如果是明确的离别意图，发送告别语并关闭连接
        await send_stt_message(conn, original_text)
        conn.executor.submit(conn.chat_and_close, original_text)
        return True

    # 处理播放音乐意图
    if "播放音乐" in intent:
        logger.bind(tag=TAG).info(f"识别到音乐播放意图: {intent}")
        await conn.music_handler.handle_music_command(conn, intent)
        return True

    # 其他意图处理可以在这里扩展

    # 默认返回False，表示继续常规聊天流程
    return False


async def process_intent_parms_result(conn, intent_parms, original_text):
    """处理意图识别结果"""
    # 处理退出意图
    intent = intent_parms["intent"]
    if "结束聊天" in intent:
        logger.bind(tag=TAG).info(f"识别到退出意图: {intent}")

        # 如果正在播放音乐，可以关了 TODO

        # 如果是明确的离别意图，发送告别语并关闭连接
        await send_stt_message(conn, original_text)
        conn.executor.submit(conn.chat_and_close, original_text)
        return True

    # 处理播放音乐意图
    elif "play_music" in intent:
        logger.bind(tag=TAG).info(f"识别到音乐播放意图: {original_text}")
        # await conn.music_handler.handle_music_command(conn, intent)
        # return True
        if await conn.music_handler.handle_music_command(conn, original_text):
            conn.asr_server_receive = True
            conn.asr_audio.clear()
            return True

    elif "volume_control" in intent:
    # 其他意图处理可以在这里扩展
        logger.bind(tag=TAG).info(f"识别到修改音量意图: {original_text}")
        conn.device_volume = intent_parms["volume_value"] # 更新
        await send_iot_conn(conn, "Speaker", "SetVolume", {"volume": intent_parms["volume_value"]})
        return False
    # 默认返回False，表示继续常规聊天流程
    return False