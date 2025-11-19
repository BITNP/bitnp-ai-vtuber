# This file is modified on the basis of official "api.py"

"""
Modified Functional API for GPT-SoVITS v1

提供以下API函数：
    - 注册说话人: define_speaker(name: str, gpt_weights_path: str, sovits_weights_path: str, ref_wav_path: str, prompt_text: str, prompt_language: str)
    - 合成音频:   get_tts_wav(text: str, text_language: str = "zh", spk: str = None, ...)

使用示例见 "backend/_examples/tts_test.py"
"""

import os,re
import sys

now_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(now_dir)
sys.path.append("%s/GPT_SoVITS" % (now_dir))

import signal
from text.LangSegmenter import LangSegmenter
from time import time as ttime
import torch
import librosa
import soundfile as sf
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
from transformers import AutoModelForMaskedLM, AutoTokenizer
import numpy as np
from feature_extractor import cnhubert
from io import BytesIO
from module.models import SynthesizerTrn
from AR.models.t2s_lightning_module import Text2SemanticLightningModule
from text import cleaned_text_to_sequence
from text.cleaner import clean_text
from module.mel_processing import spectrogram_torch
from tools.my_utils import load_audio
import config as global_config
import logging
import subprocess

# --------------------------------
# 0. 辅助函数
# --------------------------------
def is_empty(*items):  # 任意一项不为空返回False
    for item in items:
        if item is not None and item != "":
            return False
    return True

def is_full(*items):  # 任意一项为空返回False
    for item in items:
        if item is None or item == "":
            return False
    return True

def read_clean_buffer(audio_bytes):
    audio_chunk = audio_bytes.getvalue()
    audio_bytes.truncate(0)
    audio_bytes.seek(0)

    return audio_bytes, audio_chunk

def cut_text(text, punc):
    punc_list = [p for p in punc if p in {",", ".", ";", "?", "!", "、", "，", "。", "？", "！", "；", "：", "…"}]
    if len(punc_list) > 0:
        punds = r"[" + "".join(punc_list) + r"]"
        text = text.strip("\n")
        items = re.split(f"({punds})", text)
        mergeitems = ["".join(group) for group in zip(items[::2], items[1::2])]
        # 在句子不存在符号或句尾无符号的时候保证文本完整
        if len(items)%2 == 1:
            mergeitems.append(items[-1])
        text = "\n".join(mergeitems)

    while "\n\n" in text:
        text = text.replace("\n\n", "\n")

    return text

def only_punc(text):
    return not any(t.isalnum() or t.isalpha() for t in text)

class DictToAttrRecursive(dict):
    def __init__(self, input_dict):
        super().__init__(input_dict)
        for key, value in input_dict.items():
            if isinstance(value, dict):
                value = DictToAttrRecursive(value)
            self[key] = value
            setattr(self, key, value)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"Attribute {item} not found")

    def __setattr__(self, key, value):
        if isinstance(value, dict):
            value = DictToAttrRecursive(value)
        super(DictToAttrRecursive, self).__setitem__(key, value)
        super().__setattr__(key, value)

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError:
            raise AttributeError(f"Attribute {item} not found")

# --------------------------------
# 1. 数据结构
# --------------------------------
class Gpt:
    def __init__(self, max_sec, t2s_model):
        self.max_sec = max_sec
        self.t2s_model = t2s_model

class Sovits:
    def __init__(self, vq_model, hps):
        self.vq_model = vq_model
        self.hps = hps

class Speaker:
    def __init__(self, name: str, gpt: Gpt, sovits: Sovits, phones = None, bert = None, prompt = None, ref_wav_path = None, prompt_text = None, prompt_language = None):
        self.name = name
        self.sovits = sovits
        self.gpt = gpt
        self.phones = phones
        self.bert = bert
        self.prompt = prompt
        self.ref_wav_path = ref_wav_path
        self.prompt_text = prompt_text
        self.prompt_language = prompt_language

speaker_list: dict[str, Speaker] = {} # global: 所有说话人

# --------------------------------
# 2. 模型参数加载
# --------------------------------
def get_sovits_weights(sovits_path):
    dict_s2 = torch.load(sovits_path, map_location="cpu", weights_only=False)
    hps = dict_s2["config"]
    hps = DictToAttrRecursive(hps)
    hps.model.semantic_frame_rate = "25hz"
    if dict_s2['weight']['enc_p.text_embedding.weight'].shape[0] == 322:
        hps.model.version = "v1"
    else:
        hps.model.version = "v2"
    logger.info(f"模型版本: {hps.model.version}")
    model_params_dict = vars(hps.model)
    vq_model = SynthesizerTrn(
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        **model_params_dict
    )
    if ("pretrained" not in sovits_path):
        del vq_model.enc_q
    if is_half == True:
        vq_model = vq_model.half().to(device)
    else:
        vq_model = vq_model.to(device)
    vq_model.eval()
    vq_model.load_state_dict(dict_s2["weight"], strict=False)

    sovits = Sovits(vq_model, hps)
    return sovits

global hz
hz = 50
def get_gpt_weights(gpt_path):
    dict_s1 = torch.load(gpt_path, map_location="cpu")
    config = dict_s1["config"]
    max_sec = config["data"]["max_sec"]
    t2s_model = Text2SemanticLightningModule(config, "****", is_train=False)
    t2s_model.load_state_dict(dict_s1["weight"])
    if is_half == True:
        t2s_model = t2s_model.half()
    t2s_model = t2s_model.to(device)
    t2s_model.eval()
    total = sum([param.nelement() for param in t2s_model.parameters()])
    logger.info("Number of parameter: %.2fM" % (total / 1e6))

    gpt = Gpt(max_sec, t2s_model)
    return gpt

# --------------------------------
# 3. 文本特征计算 (bert)
# --------------------------------
def get_bert_feature(text, word2ph):
    with torch.no_grad():
        inputs = tokenizer(text, return_tensors="pt")
        for i in inputs:
            inputs[i] = inputs[i].to(device)  #####输入是long不用管精度问题，精度随bert_model
        res = bert_model(**inputs, output_hidden_states=True)
        res = torch.cat(res["hidden_states"][-3:-2], -1)[0].cpu()[1:-1]
    assert len(word2ph) == len(text)
    phone_level_feature = []
    for i in range(len(word2ph)):
        repeat_feature = res[i].repeat(word2ph[i], 1)
        phone_level_feature.append(repeat_feature)
    phone_level_feature = torch.cat(phone_level_feature, dim=0)
    # if(is_half==True):phone_level_feature=phone_level_feature.half()
    return phone_level_feature.T

def clean_text_inf(text, language, version):
    phones, word2ph, norm_text = clean_text(text, language, version)
    phones = cleaned_text_to_sequence(phones, version)
    return phones, word2ph, norm_text

def get_bert_inf(phones, word2ph, norm_text, language):
    language=language.replace("all_","")
    if language == "zh":
        bert = get_bert_feature(norm_text, word2ph).to(device)#.to(dtype)
    else:
        bert = torch.zeros(
            (1024, len(phones)),
            dtype=torch.float16 if is_half == True else torch.float32,
        ).to(device)

    return bert

def get_phones_and_bert(text, language, version, final=False):
    text = re.sub(r' {2,}', ' ', text)
    textlist = []
    langlist = []
    if language == "all_zh":
        for tmp in LangSegmenter.getTexts(text,"zh"):
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    elif language == "all_yue":
        for tmp in LangSegmenter.getTexts(text,"zh"):
            if tmp["lang"] == "zh":
                tmp["lang"] = "yue"
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    elif language == "all_ja":
        for tmp in LangSegmenter.getTexts(text,"ja"):
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    elif language == "all_ko":
        for tmp in LangSegmenter.getTexts(text,"ko"):
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    elif language == "en":
        langlist.append("en")
        textlist.append(text)
    elif language == "auto":
        for tmp in LangSegmenter.getTexts(text):
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    elif language == "auto_yue":
        for tmp in LangSegmenter.getTexts(text):
            if tmp["lang"] == "zh":
                tmp["lang"] = "yue"
            langlist.append(tmp["lang"])
            textlist.append(tmp["text"])
    else:
        for tmp in LangSegmenter.getTexts(text):
            if langlist:
                if (tmp["lang"] == "en" and langlist[-1] == "en") or (tmp["lang"] != "en" and langlist[-1] != "en"):
                    textlist[-1] += tmp["text"]
                    continue
            if tmp["lang"] == "en":
                langlist.append(tmp["lang"])
            else:
                # 因无法区别中日韩文汉字,以用户输入为准
                langlist.append(language)
            textlist.append(tmp["text"])
    phones_list = []
    bert_list = []
    norm_text_list = []
    for i in range(len(textlist)):
        lang = langlist[i]
        phones, word2ph, norm_text = clean_text_inf(textlist[i], lang, version)
        bert = get_bert_inf(phones, word2ph, norm_text, lang)
        phones_list.append(phones)
        norm_text_list.append(norm_text)
        bert_list.append(bert)
    bert = torch.cat(bert_list, dim=1)
    phones = sum(phones_list, [])
    norm_text = "".join(norm_text_list)

    if not final and len(phones) < 6:
        return get_phones_and_bert("." + text, language, version, final=True)

    return phones, bert.to(torch.float16 if is_half == True else torch.float32), norm_text

# --------------------------------
# 4. 频谱计算与音频打包
# --------------------------------
def get_spepc(hps, filename):
    audio,_ = librosa.load(filename, sr=int(hps.data.sampling_rate))
    audio = torch.FloatTensor(audio)
    maxx=audio.abs().max()
    if(maxx>1):
        audio/=min(2,maxx)
    audio_norm = audio
    audio_norm = audio_norm.unsqueeze(0)
    spec = spectrogram_torch(audio_norm, hps.data.filter_length, hps.data.sampling_rate, hps.data.hop_length,
                             hps.data.win_length, center=False)
    return spec

def pack_audio(audio_bytes, data, rate):
    if media_type == "ogg":
        audio_bytes = pack_ogg(audio_bytes, data, rate)
    elif media_type == "aac":
        audio_bytes = pack_aac(audio_bytes, data, rate)
    else:
        # wav无法流式, 先暂存raw
        audio_bytes = pack_raw(audio_bytes, data, rate)

    return audio_bytes


def pack_ogg(audio_bytes, data, rate):
    # Author: AkagawaTsurunaki
    # Issue:
    #   Stack overflow probabilistically occurs
    #   when the function `sf_writef_short` of `libsndfile_64bit.dll` is called
    #   using the Python library `soundfile`
    # Note:
    #   This is an issue related to `libsndfile`, not this project itself.
    #   It happens when you generate a large audio tensor (about 499804 frames in my PC)
    #   and try to convert it to an ogg file.
    # Related:
    #   https://github.com/RVC-Boss/GPT-SoVITS/issues/1199
    #   https://github.com/libsndfile/libsndfile/issues/1023
    #   https://github.com/bastibe/python-soundfile/issues/396
    # Suggestion:
    #   Or split the whole audio data into smaller audio segment to avoid stack overflow?

    def handle_pack_ogg():
        with sf.SoundFile(audio_bytes, mode='w', samplerate=rate, channels=1, format='ogg') as audio_file:
            audio_file.write(data)

    import threading
    # See: https://docs.python.org/3/library/threading.html
    # The stack size of this thread is at least 32768
    # If stack overflow error still occurs, just modify the `stack_size`.
    # stack_size = n * 4096, where n should be a positive integer.
    # Here we chose n = 4096.
    stack_size = 4096 * 4096
    try:
        threading.stack_size(stack_size)
        pack_ogg_thread = threading.Thread(target=handle_pack_ogg)
        pack_ogg_thread.start()
        pack_ogg_thread.join()
    except RuntimeError as e:
        # If changing the thread stack size is unsupported, a RuntimeError is raised.
        print("RuntimeError: {}".format(e))
        print("Changing the thread stack size is unsupported.")
    except ValueError as e:
        # If the specified stack size is invalid, a ValueError is raised and the stack size is unmodified.
        print("ValueError: {}".format(e))
        print("The specified stack size is invalid.")

    return audio_bytes


def pack_raw(audio_bytes, data, rate):
    audio_bytes.write(data.tobytes())

    return audio_bytes


def pack_wav(audio_bytes, rate):
    if is_int32:
        data = np.frombuffer(audio_bytes.getvalue(),dtype=np.int32)
        wav_bytes = BytesIO()
        sf.write(wav_bytes, data, rate, format='WAV', subtype='PCM_32')
    else:
        data = np.frombuffer(audio_bytes.getvalue(),dtype=np.int16)
        wav_bytes = BytesIO()
        sf.write(wav_bytes, data, rate, format='WAV')
    return wav_bytes


def pack_aac(audio_bytes, data, rate):
    if is_int32:
        pcm = 's32le'
        bit_rate = '256k'
    else:
        pcm = 's16le'
        bit_rate = '128k'
    process = subprocess.Popen([
        'ffmpeg',
        '-f', pcm,  # 输入16位有符号小端整数PCM
        '-ar', str(rate),  # 设置采样率
        '-ac', '1',  # 单声道
        '-i', 'pipe:0',  # 从管道读取输入
        '-c:a', 'aac',  # 音频编码器为AAC
        '-b:a', bit_rate,  # 比特率
        '-vn',  # 不包含视频
        '-f', 'adts',  # 输出AAC数据流格式
        'pipe:1'  # 将输出写入管道
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = process.communicate(input=data.tobytes())
    audio_bytes.write(out)

    return audio_bytes

# --------------------------------
# 5. 说话人定义 API
# --------------------------------
def define_speaker(name: str, gpt_weights_path: str, sovits_weights_path: str, ref_wav_path: str, prompt_text: str, prompt_language: str):
    """
    注册一个说话人 / 更新一个已注册的说话人
    会在注册的同时计算参考音频和参考文本的特征，并进行缓存，以加速后续合成。
    
    Args:
        name (str): 说话人名称
        gpt_weights_path (str): GPT 模型权重路径
        sovits_weights_path (str): SoVITS 模型权重路径
        ref_wav_path (str): 参考音频路径
        prompt_text (str): 提示文本
        prompt_language (str): 提示文本语言
    """
    speaker = Speaker(name = name, gpt=get_gpt_weights(gpt_weights_path), sovits=get_sovits_weights(sovits_weights_path),
                      ref_wav_path=ref_wav_path, prompt_text=prompt_text, prompt_language=prompt_language)
    
    infer_sovits = speaker.sovits
    vq_model = infer_sovits.vq_model
    hps = infer_sovits.hps

    zero_wav = np.zeros(int(hps.data.sampling_rate * 0.3), dtype=np.float16 if is_half == True else np.float32)

    # compute reference audio features (prompt, phones, bert)
    # # compute prompt
    with torch.no_grad():
        wav16k, sr = librosa.load(ref_wav_path, sr=16000)
        wav16k = torch.from_numpy(wav16k)
        zero_wav_torch = torch.from_numpy(zero_wav)
        if (is_half == True):
            wav16k = wav16k.half().to(device)
            zero_wav_torch = zero_wav_torch.half().to(device)
        else:
            wav16k = wav16k.to(device)
            zero_wav_torch = zero_wav_torch.to(device)
        wav16k = torch.cat([wav16k, zero_wav_torch])
        ssl_content = ssl_model.model(wav16k.unsqueeze(0))["last_hidden_state"].transpose(1, 2)  # .float()
        codes = vq_model.extract_latent(ssl_content)
        prompt_semantic = codes[0, 0]
        prompt = prompt_semantic.unsqueeze(0).to(device)
        speaker.prompt = prompt

    version = vq_model.version
    os.environ['version'] = version
    prompt_language = dict_language[prompt_language.lower()]

    # # compute  phones and bert
    phones1, bert1, norm_text1 = get_phones_and_bert(prompt_text, prompt_language, version)
    speaker.phones = phones1
    speaker.bert = bert1

    speaker_list[name] = speaker
    return speaker

# --------------------------------
# 6. 音频合成 API
# --------------------------------
splits = {"，", "。", "？", "！", ",", ".", "?", "!", "~", ":", "：", "—", "…", }
def get_tts_wav(text: str, text_language: str = "zh", spk: str = None, ref_wav_path: str = None, prompt_text: str = None, prompt_language: str = None, top_k: int = 15, top_p: float = 0.6, temperature: float = 0.6, speed: float = 1, inp_refs: list = None):
    """
    合成音频

    Args:
        text (str): 待合成的文本
        text_language (str, optional): 文本语言代号，默认值为 "zh"
        spk (str, optional): 说话人名称，默认值为 None
        ref_wav_path (str, optional):    [若指定了spk, 则无需指定此参数] 参考音频路径，默认值为 None
        prompt_text (str, optional):     [若指定了spk, 则无需指定此参数] 提示文本，默认值为 None
        prompt_language (str, optional): [若指定了spk, 则无需指定此参数] 提示文本语言，默认值为 None
        top_k (int, optional): 采样时的 top_k 选择，默认值为 15
        top_p (float, optional): 采样时的 top_p 选择，默认值为 0.6
        temperature (float, optional): 采样时的温度参数，默认值为 0.6
        speed (float, optional): 合成音频的速度，默认值为 1
        inp_refs (list, optional, deprecated): 输入的参考音频列表，默认值为 None
    """
    # print(ref_wav_path, prompt_text, prompt_language, text, text_language)

    infer_sovits = speaker_list[spk].sovits
    vq_model = infer_sovits.vq_model
    hps = infer_sovits.hps

    infer_gpt = speaker_list[spk].gpt
    t2s_model = infer_gpt.t2s_model
    max_sec = infer_gpt.max_sec

    # Use speaker's "ref_wav_path", "prompt_text", "prompt_language" as default, so that front end does not need to pass these params.
    speaker = speaker_list[spk]
    ref_wav_path = ref_wav_path or speaker.ref_wav_path
    prompt_text = prompt_text or speaker.prompt_text
    prompt_language = prompt_language or speaker.prompt_language

    t0 = ttime()
    prompt_text = prompt_text.strip("\n")
    if (prompt_text[-1] not in splits): prompt_text += "。" if prompt_language != "en" else "."
    prompt_language, text = prompt_language, text.strip("\n")
    dtype = torch.float16 if is_half == True else torch.float32
    zero_wav = np.zeros(int(hps.data.sampling_rate * 0.3), dtype=np.float16 if is_half == True else np.float32)
    with torch.no_grad():
        # important! 这里加载了reference audio，但只在首次调用时计算！

        if speaker_list[spk].prompt is None:
            wav16k, sr = librosa.load(ref_wav_path, sr=16000)
            wav16k = torch.from_numpy(wav16k)
            zero_wav_torch = torch.from_numpy(zero_wav)
            if (is_half == True):
                wav16k = wav16k.half().to(device)
                zero_wav_torch = zero_wav_torch.half().to(device)
            else:
                wav16k = wav16k.to(device)
                zero_wav_torch = zero_wav_torch.to(device)
            wav16k = torch.cat([wav16k, zero_wav_torch])
            ssl_content = ssl_model.model(wav16k.unsqueeze(0))["last_hidden_state"].transpose(1, 2)  # .float()
            codes = vq_model.extract_latent(ssl_content)
            prompt_semantic = codes[0, 0]
            prompt = prompt_semantic.unsqueeze(0).to(device) # important!
            speaker_list[spk].prompt = prompt

        prompt = speaker_list[spk].prompt

        refers=[]
        if(inp_refs):
            for path in inp_refs:
                try:
                    refer = get_spepc(hps, path).to(dtype).to(device)
                    refers.append(refer)
                except Exception as e:
                    logger.error(e)
        if(len(refers)==0):
            refers = [get_spepc(hps, ref_wav_path).to(dtype).to(device)]

    t1 = ttime()

    version = vq_model.version
    os.environ['version'] = version
    prompt_language = dict_language[prompt_language.lower()]
    text_language = dict_language[text_language.lower()]

    if (speaker_list[spk].phones is None or speaker_list[spk].bert is None):
        phones1, bert1, norm_text1 = get_phones_and_bert(prompt_text, prompt_language, version)
        speaker_list[spk].phones = phones1
        speaker_list[spk].bert = bert1

    # phones1, bert1, norm_text1 = get_phones_and_bert(prompt_text, prompt_language, version)
    phones1 = speaker_list[spk].phones
    bert1 = speaker_list[spk].bert

    texts = text.split("\n")
    audio_bytes = BytesIO()

    for text in texts:
        # 简单防止纯符号引发参考音频泄露
        if only_punc(text):
            continue

        audio_opt = []
        if (text[-1] not in splits): text += "。" if text_language != "en" else "."
        phones2, bert2, norm_text2 = get_phones_and_bert(text, text_language, version)
        bert = torch.cat([bert1, bert2], 1)

        all_phoneme_ids = torch.LongTensor(phones1 + phones2).to(device).unsqueeze(0)
        bert = bert.to(device).unsqueeze(0)
        all_phoneme_len = torch.tensor([all_phoneme_ids.shape[-1]]).to(device)
        t2 = ttime()
        with torch.no_grad():
            pred_semantic, idx = t2s_model.model.infer_panel( # important! 语义预测
                all_phoneme_ids,
                all_phoneme_len,
                prompt,
                bert,
                # prompt_phone_len=ph_offset,
                top_k = top_k,
                top_p = top_p,
                temperature = temperature,
                early_stop_num=hz * max_sec)
            pred_semantic = pred_semantic[:, -idx:].unsqueeze(0)
        t3 = ttime()
        audio = \
            vq_model.decode(pred_semantic, torch.LongTensor(phones2).to(device).unsqueeze(0), # important! 音频解码
                            refers,speed=speed).detach().cpu().numpy()[
                0, 0]  ###试试重建不带上prompt部分
        max_audio=np.abs(audio).max()
        if max_audio>1:
            audio/=max_audio
        audio_opt.append(audio)
        audio_opt.append(zero_wav)
        t4 = ttime()
        if is_int32:
            audio_bytes = pack_audio(audio_bytes,(np.concatenate(audio_opt, 0) * 2147483647).astype(np.int32),hps.data.sampling_rate)
        else:
            audio_bytes = pack_audio(audio_bytes,(np.concatenate(audio_opt, 0) * 32768).astype(np.int16),hps.data.sampling_rate)

        logger.info("%.3f\t%.3f\t%.3f\t%.3f" % (t1 - t0, t2 - t1, t3 - t2, t4 - t3))

        if stream_mode == "normal":
            audio_bytes, audio_chunk = read_clean_buffer(audio_bytes)
            yield audio_chunk
    
    if not stream_mode == "normal": 
        if media_type == "wav":
            audio_bytes = pack_wav(audio_bytes,hps.data.sampling_rate)
        yield audio_bytes.getvalue()

# --------------------------------
# 初始化部分
# --------------------------------
dict_language = {
    "中文": "all_zh",
    "粤语": "all_yue",
    "英文": "en",
    "日文": "all_ja",
    "韩文": "all_ko",
    "中英混合": "zh",
    "粤英混合": "yue",
    "日英混合": "ja",
    "韩英混合": "ko",
    "多语种混合": "auto",    #多语种启动切分识别语种
    "多语种混合(粤语)": "auto_yue",
    "all_zh": "all_zh",
    "all_yue": "all_yue",
    "en": "en",
    "all_ja": "all_ja",
    "all_ko": "all_ko",
    "zh": "zh",
    "yue": "yue",
    "ja": "ja",
    "ko": "ko",
    "auto": "auto",
    "auto_yue": "auto_yue",
}

# logger
logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
logger = logging.getLogger('uvicorn')

# 获取配置
g_config = global_config.Config()

cnhubert_base_path = g_config.cnhubert_path
bert_path = g_config.bert_path
device = g_config.infer_device
# gpt_path = g_config.gpt_path
# sovits_path = g_config.sovits_path
is_half = g_config.is_half
default_cut_punc = ""
media_type = "wav" # using wav
stream_mode = "non-stream" # disable stream mode (to get wav output, not ogg)
is_int32 = False # using int16

# 初始化模型
cnhubert.cnhubert_base_path = cnhubert_base_path
tokenizer = AutoTokenizer.from_pretrained(bert_path)
bert_model = AutoModelForMaskedLM.from_pretrained(bert_path)
ssl_model = cnhubert.get_model()

if is_half:
    bert_model = bert_model.half().to(device)
    ssl_model = ssl_model.half().to(device)
else:
    bert_model = bert_model.to(device)
    ssl_model = ssl_model.to(device)

if __name__ == "__main__":
    define_speaker(
        name="paimeng",
        gpt_weights_path="GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        sovits_weights_path="GPT_SoVITS/pretrained_models/s2G488k.pth",
        ref_wav_path="ref_audio/paimeng.wav",
        prompt_text="蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。",
        prompt_language="zh")

    # for further examples, see "backend/_examples/tts_test.py"
