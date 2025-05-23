import os
import re
import json
import yaml
import socket
import subprocess


def get_project_dir():
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + '/'


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to Google's DNS servers
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        return "127.0.0.1"


def read_config(config_path):
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    return config


def write_json_file(file_path, data):
    """将数据写入 JSON 文件"""
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def is_punctuation_or_emoji(char):
    """检查字符是否为空格、指定标点或表情符号"""
    # 定义需要去除的中英文标点（包括全角/半角）
    punctuation_set = {
        '，', ',',  # 中文逗号 + 英文逗号
        '。', '.',  # 中文句号 + 英文句号
        '！', '!',  # 中文感叹号 + 英文感叹号
        '-', '－',  # 英文连字符 + 中文全角横线
        '、'  # 中文顿号
    }
    if char.isspace() or char in punctuation_set:
        return True
    # 检查表情符号（保留原有逻辑）
    code_point = ord(char)
    emoji_ranges = [
        (0x1F600, 0x1F64F), (0x1F300, 0x1F5FF),
        (0x1F680, 0x1F6FF), (0x1F900, 0x1F9FF),
        (0x1FA70, 0x1FAFF), (0x2600, 0x26FF),
        (0x2700, 0x27BF)
    ]
    return any(start <= code_point <= end for start, end in emoji_ranges)


def get_string_no_punctuation_or_emoji(s):
    """去除字符串首尾的空格、标点符号和表情符号"""
    chars = list(s)
    # 处理开头的字符
    start = 0
    while start < len(chars) and is_punctuation_or_emoji(chars[start]):
        start += 1
    # 处理结尾的字符
    end = len(chars) - 1
    while end >= start and is_punctuation_or_emoji(chars[end]):
        end -= 1
    return ''.join(chars[start:end + 1])


def remove_punctuation_and_length(text):
    # 全角符号和半角符号的Unicode范围
    full_width_punctuations = '！＂＃＄％＆＇（）＊＋，－。／：；＜＝＞？＠［＼］＾＿｀｛｜｝～'
    half_width_punctuations = '!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'
    space = ' '  # 半角空格
    full_width_space = '　'  # 全角空格

    # 去除全角和半角符号以及空格
    result = ''.join([char for char in text if
                      char not in full_width_punctuations and char not in half_width_punctuations and char not in space and char not in full_width_space])

    if result == "Yeah":
        return 0, ""
    return len(result), result


def check_password(password):
    """
    检查密码是否满足以下条件：
    1. 密码长度大于八位。
    2. 密码包含英文和数字。
    3. 密码不能包含“xiaozhi”字符。

    :param password: 要检查的密码
    :return: 如果密码满足条件，则返回True；否则返回False。
    """
    # 检查密码长度
    if len(password) < 8:
        return False

    # 检查是否包含英文字符和数字
    if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        return False

    # 检查是否包含“xiaozhi”字符
    if "xiaozhi" in password:
        return False

    if "1234" in password:
        return False

    # 如果满足所有条件，则返回True
    return True

def check_ffmpeg_installed():
    ffmpeg_installed = False
    try:
        # 执行ffmpeg -version命令，并捕获输出
        result = subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True  # 如果返回码非零则抛出异常
        )
        # 检查输出中是否包含版本信息（可选）
        output = result.stdout + result.stderr
        if 'ffmpeg version' in output.lower():
            ffmpeg_installed = True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        # 命令执行失败或未找到
        ffmpeg_installed = False
    if not ffmpeg_installed:
        error_msg = "您的电脑还没正确安装ffmpeg\n"
        error_msg += "\n建议您：\n"
        error_msg += "1、按照项目的安装文档，正确进入conda环境\n"
        error_msg += "2、查阅安装文档，如何在conda环境中安装ffmpeg\n"
        raise ValueError(error_msg)
