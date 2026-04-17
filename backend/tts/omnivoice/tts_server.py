"""
OmniVoice TTS HTTP Server
在 omnivoice 虚拟环境中运行此服务：
    cd backend/tts/omnivoice
    source .venv/bin/activate
    python tts_server.py

用法:
    POST /synthesize
    Body: {"text": "要合成的文本", "ref_audio": "参考音频路径", "ref_text": "参考文本"}
    返回: WAV 音频数据
"""
import asyncio
import argparse
import base64
import os
import sys

from aiohttp import web

curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, curr_dir)

from omnivoice_wrapper import OmniVoiceTTS

tts: OmniVoiceTTS = None


async def synthesize_handler(request):
    """处理合成请求"""
    try:
        data = await request.json()
        text = data.get("text", "")
        
        if not text:
            return web.json_response({"error": "text is required"}, status=400)
        
        ref_audio = data.get("ref_audio")
        ref_text = data.get("ref_text")
        
        if ref_audio:
            tts.ref_audio = ref_audio
        if ref_text:
            tts.ref_text = ref_text
        
        audio_data = await tts.synthesize(text)
        
        if not audio_data:
            return web.json_response({"error": "synthesis failed"}, status=500)
        
        return web.Response(
            body=audio_data,
            content_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
        
    except Exception as e:
        print(f"合成错误: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def health_handler(request):
    """健康检查"""
    return web.json_response({
        "status": "ok", 
        "initialized": tts._is_initialized if tts else False,
        "model_path": tts.model_path if tts else None
    })


async def init_tts(model_path: str, device: str, dtype: str, ref_audio: str = None, ref_text: str = None):
    """初始化 TTS"""
    global tts
    tts = OmniVoiceTTS(
        model_path=model_path,
        device=device,
        dtype=dtype,
        ref_audio=ref_audio,
        ref_text=ref_text
    )
    await tts._ensure_initialized()


def main():
    parser = argparse.ArgumentParser(description="OmniVoice TTS HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=9237, help="server port")
    parser.add_argument("--model-path", default=None, help="model path")
    parser.add_argument("--device", default="cpu", help="device (auto/cuda:0/cpu)")
    parser.add_argument("--dtype", default="float16", help="dtype (float16/float32)")
    parser.add_argument("--ref-audio", default=None, help="reference audio path")
    parser.add_argument("--ref-text", default=None, help="reference audio text")
    args = parser.parse_args()
    
    model_path = args.model_path or os.path.join(curr_dir, "models", "OmniVoice")
    
    print(f"[OmniVoice Server] 启动中...")
    print(f"[OmniVoice Server] Model: {model_path}")
    print(f"[OmniVoice Server] Device: {args.device}")
    print(f"[OmniVoice Server] Port: {args.port}")
    
    asyncio.run(init_tts(model_path, args.device, args.dtype, args.ref_audio, args.ref_text))
    
    app = web.Application()
    app.router.add_post("/synthesize", synthesize_handler)
    app.router.add_get("/health", health_handler)
    
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()