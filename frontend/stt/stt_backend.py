"""
STT Backend - 语音识别后端服务

支持:
- Silero VAD 语音活动检测
- FunASR 语音识别
- 标点恢复
- WebSocket 实时推送识别结果
"""
import asyncio
import json
import time
import numpy as np
import torch
import sounddevice as sd
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room
from threading import Thread, Lock

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

SAMPLE_RATE = 16000
CHUNK_DURATION = 1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
FRAME_DURATION = 0.5
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION)

vad_buffer = np.zeros(CHUNK_SIZE, dtype=np.float32)
speech_buffer = np.array([], dtype=np.float32)
recording = False
speech_ends = False
enable_dictation = False
buffer_lock = Lock()

vad_model = None
stt_model = None
punc_model = None

STT_BACKEND_PORT = 9236
connected_clients = set()

QUESTION_KEYWORDS = [
    "吗", "呢", "啊", "?", "？", "怎么", "为什么", "什么", "哪", "谁", "多少", "几",
    "是不是", "有没有", "可不可以", "能不能", "会不会", "能不能"
]


def init_models():
    """初始化模型"""
    global vad_model, stt_model, punc_model
    
    print("正在加载模型...")
    
    from funasr import AutoModel
    from silero_vad import load_silero_vad, get_speech_timestamps
    
    vad_model = load_silero_vad()
    stt_model = AutoModel(
        model="paraformer-zh",
        disable_log=True,
        disable_update=True
    )
    punc_model = AutoModel(
        model="ct-punc-c",
        disable_log=True,
        disable_update=True
    )
    
    print("模型加载完成")


def vad_callback(indata, frames, time, status):
    """麦克风音频回调函数"""
    global vad_model, vad_buffer, recording, speech_buffer, speech_ends, buffer_lock
    
    if not enable_dictation:
        with buffer_lock:
            vad_buffer = np.zeros(CHUNK_SIZE, dtype=np.float32)
            speech_buffer = np.array([], dtype=np.float32)
            recording = False
        return
    
    if status.input_overflow:
        print("⚠️ 输入溢出！")
    
    audio_frame = indata[:, 0].copy()
    
    with buffer_lock:
        vad_buffer = np.roll(vad_buffer, -frames)
        vad_buffer[-frames:] = audio_frame
        
        if recording:
            speech_buffer = np.concatenate([speech_buffer, audio_frame])
    
    from silero_vad import get_speech_timestamps
    vad_buffer_tensor = torch.from_numpy(vad_buffer).to(torch.float32)
    speech_timestamps = get_speech_timestamps(
        vad_buffer_tensor,
        vad_model,
        sampling_rate=SAMPLE_RATE,
        return_seconds=True
    )
    
    global prev_recording
    try:
        prev_recording
    except NameError:
        prev_recording = False
    
    if not prev_recording and len(speech_timestamps) > 0:
        with buffer_lock:
            speech_buffer = audio_frame.copy()
        recording = True
        print(f"🔊 语音开始")
    
    elif prev_recording and len(speech_timestamps) == 0:
        recording = False
        speech_ends = True
        print(f"🔇 语音结束")


def is_question(text: str) -> bool:
    """检测文本是否包含问题"""
    if not text:
        return False
    
    text = text.strip()
    
    for keyword in QUESTION_KEYWORDS:
        if keyword in text:
            return True
    
    if text.endswith('?') or text.endswith('？'):
        return True
    
    return False


def process_speech():
    """处理识别到的语音"""
    global speech_ends, vad_model, stt_model, punc_model, ws_clients
    
    while True:
        if speech_ends:
            speech_ends = False
            
            with buffer_lock:
                current_speech = speech_buffer.copy()
                speech_buffer = np.array([], dtype=np.float32)
            
            if len(current_speech) > 0:
                try:
                    result = stt_model.generate(
                        input=current_speech,
                        audio_fs=SAMPLE_RATE,
                        batch_size_s=1
                    )
                    
                    text = result[0]['text'] if result else ""
                    
                    if text:
                        result = punc_model.generate(
                            input=result,
                            batch_size_s=1,
                            task='punc'
                        )
                        text = result[0]['text']
                    
                    if text:
                        question_detected = is_question(text)
                        
                        event_data = {
                            "type": "asr_result",
                            "text": text,
                            "is_speech": True,
                            "is_question": question_detected,
                            "timestamp": time.time()
                        }
                        
                        if question_detected:
                            event_data["question"] = text
                            event_data["type"] = "question_detected"
                        
                        broadcast_to_ws(event_data)
                        print(f"识别结果: {text} {'[问题]' if question_detected else ''}")
                
                except Exception as e:
                    print(f"识别出错: {e}")
        
        time.sleep(0.1)


def broadcast_to_ws(data: dict):
    """广播消息到所有 WebSocket 客户端"""
    socketio.emit('stt_result', data)


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    connected_clients.add(request.sid)
    print(f"客户端连接: {request.sid}, 当前连接数: {len(connected_clients)}")


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    connected_clients.discard(request.sid)
    print(f"客户端断开: {request.sid}, 当前连接数: {len(connected_clients)}")


@socketio.on('enable_dictation')
def handle_enable_dictation(data):
    """设置是否启用语音识别"""
    global enable_dictation
    enable_dictation = data.get('enabled', False)
    print(f"设置 enable_dictation 为: {enable_dictation}")


@app.route('/put_dictation', methods=['POST'])
def put_dictation():
    """接收语音识别结果（备用接口）"""
    global global_dictation
    data = request.get_json()
    if 'dictation' not in data:
        return jsonify({"error": "Missing 'dictation'"}), 400
    
    text = data['dictation']
    question_detected = is_question(text)
    
    event_data = {
        "type": "asr_result",
        "text": text,
        "is_speech": True,
        "is_question": question_detected,
        "timestamp": time.time()
    }
    
    if question_detected:
        event_data["question"] = text
        event_data["type"] = "question_detected"
    
    socketio.emit('stt_result', event_data)
    
    return jsonify({"message": "success"}), 200


@app.route('/get_dictation', methods=['GET'])
def get_dictation():
    return jsonify({"dictation": "", "time": -1}), 200


@app.route('/message', methods=['POST'])
def set_message():
    """设置 enableDictation 状态"""
    global enable_dictation
    data = request.get_json()
    if 'enableDictation' in data:
        enable_dictation = bool(data['enableDictation'])
        print(f"设置 enableDictation 为: {enable_dictation}")
    return jsonify({"message": "success"}), 200


@app.route('/get_message', methods=['GET'])
def get_message():
    return jsonify({"enableDictation": enable_dictation}), 200


def start_audio_capture():
    """启动音频捕获"""
    import sounddevice as sd
    
    print(f"使用采样率: {SAMPLE_RATE}, 设备帧大小: {FRAME_SIZE}")
    
    with sd.InputStream(
        device=None,
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SIZE,
        channels=1,
        dtype='float32',
        callback=vad_callback
    ):
        print("音频捕获已启动")
        while True:
            time.sleep(1)


if __name__ == '__main__':
    init_models()
    
    process_thread = Thread(target=process_speech, daemon=True)
    process_thread.start()
    
    audio_thread = Thread(target=start_audio_capture, daemon=True)
    audio_thread.start()
    
    print(f"STT Backend 启动在端口 {STT_BACKEND_PORT}")
    socketio.run(app, port=STT_BACKEND_PORT, debug=False)