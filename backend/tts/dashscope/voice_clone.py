import requests
import base64
import pathlib
import dashscope  # DashScope Python SDK 版本需要不低于1.23.9

# ======= 常量配置 =======
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-realtime-2026-01-15"  # 声音复刻、语音合成要使用相同的模型
DEFAULT_AUDIO_MIME_TYPE = "audio/mpeg"

def query_voice_list(api_key: str, page_size: int = 10, page_index: int = 0):
    """
    查询当前账号下的音色列表
    """
    dashscope.api_key = api_key
    url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"

    payload = {
        "model": "qwen-voice-enrollment", # 不要修改该值
        "input": {
            "action": "list",
            "page_size": page_size,
            "page_index": page_index
        }
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    print("HTTP 状态码:", response.status_code)

    if response.status_code == 200:
        data = response.json()
        voice_list = data["output"]["voice_list"]

        print("查询到的音色列表：")
        for item in voice_list:
            print(f"- 音色: {item['voice']}  创建时间: {item['gmt_create']}  模型: {item['target_model']}")
    else:
        print("请求失败:", response.text)

def create_voice(api_key: str, file_path: str,
                 preferred_name: str,
                 target_model: str = DEFAULT_TARGET_MODEL,
                 audio_mime_type: str = DEFAULT_AUDIO_MIME_TYPE) -> str:
    """
    创建音色，并返回 voice id
    """
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    dashscope.api_key = api_key

    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    base64_str = base64.b64encode(file_path_obj.read_bytes()).decode()
    data_uri = f"data:{audio_mime_type};base64,{base64_str}"

    # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
    url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
    payload = {
        "model": "qwen-voice-enrollment", # 不要修改该值
        "input": {
            "action": "create",
            "target_model": target_model,
            "preferred_name": preferred_name,
            "audio": {"data": data_uri}
        }
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"创建 voice 失败: {resp.status_code}, {resp.text}")

    try:
        voice_id = resp.json()["output"]["voice"]
        print(f"创建 voice 成功: {voice_id}")
        return voice_id
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"解析 voice 响应失败: {e}")
