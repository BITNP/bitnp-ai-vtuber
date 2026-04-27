import sys
import os
import pathlib
import xml.etree.ElementTree as ET
import json
from os import PathLike

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.cosyvoice import CosyVoiceTTS
from tokens import get_token
from tqdm import tqdm


api_key = get_token('dashscope')
voice = "cosyvoice-v3.5-flash-myvoice-237e5f49cf7240df9f3ebb6dcb4ef7a2"

tts = CosyVoiceTTS(api_key=api_key, voice=voice)


async def generate_audio_with_timestamp(text: str):
    audio, timestamp_data = await tts.synthesize(text, word_timestamp_enabled=True)

    return audio, timestamp_data

def split_sentences(text: str):
    sentences = []
    current_sentence = ""
    for char in text:
        current_sentence += char
        if char in ["。", "？", "！"]:
            sentences.append(current_sentence)
            current_sentence = ""
    if current_sentence:
        sentences.append(current_sentence)
    return sentences

def generate_command_json(elements_info, audio_timestamp_map, output_dir):
    """生成command.json文件"""
    commands = []
    current_audio_counter = 1
    
    for element_info in elements_info:
        if element_info["type"] == "ppt":
            commands.append({
                "type": "ppt",
                "page": element_info["page"]
            })
            
            for sentence in element_info["sentences"]:
                if sentence.strip():
                    audio_path = os.path.join("audio", f"{current_audio_counter}.wav")
                    command = {
                        "type": "say",
                        "audio": audio_path,
                        "text": sentence
                    }
                    if current_audio_counter in audio_timestamp_map:
                        command["timestamps"] = audio_timestamp_map[current_audio_counter]
                    commands.append(command)
                    current_audio_counter += 1
        
        elif element_info["type"] == "interaction":
            for sentence in element_info["sentences"]:
                if sentence.strip():
                    audio_path = os.path.join("audio", f"{current_audio_counter}.wav")
                    command = {
                        "type": "say",
                        "audio": audio_path,
                        "text": sentence
                    }
                    if current_audio_counter in audio_timestamp_map:
                        command["timestamps"] = audio_timestamp_map[current_audio_counter]
                    commands.append(command)
                    current_audio_counter += 1

            commands.append({
                "type": "interaction_start",
                "duration": int(element_info["interval"]) if element_info["interval"] else 0,
                "prompt": element_info["prompt"]
            })

    command_json_path = os.path.join(output_dir, "command.json")
    with open(command_json_path, "w", encoding="utf-8") as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)

async def main(path_to_script: PathLike, output_dir: PathLike):
    tree = ET.parse(path_to_script)
    root = tree.getroot()
    
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # 检查进度文件
    progress_file = os.path.join(output_dir, "progress.json")
    completed_audio = 0
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            try:
                progress = json.load(f)
                completed_audio = progress.get("completed_audio", 0)
                print(f"检测到进度文件，已完成 {completed_audio} 个音频")
            except json.JSONDecodeError:
                print("进度文件格式错误，重新开始")
    
    # 收集所有需要的信息
    elements_info = []
    audio_counter = 1
    audio_tasks = []
    
    for element in root:
        if element.tag == "ppt":
            page = element.get("page")
            content = element.text.strip() if element.text else ""
            sentences = split_sentences(content)
            
            elements_info.append({
                "type": "ppt",
                "page": page,
                "sentences": sentences
            })
            
            for sentence in sentences:
                if sentence.strip():
                    audio_tasks.append((audio_counter, sentence))
                    audio_counter += 1
        
        elif element.tag == "interaction":
            interval = element.get("interval")
            prompt_elem = element.find("prompt")
            prompt = prompt_elem.text.strip() if prompt_elem is not None and prompt_elem.text else ""
            
            opening_elem = element.find("opening")
            opening = opening_elem.text.strip() if opening_elem is not None and opening_elem.text else ""
            sentences = split_sentences(opening)
            
            elements_info.append({
                "type": "interaction",
                "interval": interval,
                "prompt": prompt,
                "sentences": sentences
            })
            
            for sentence in sentences:
                if sentence.strip():
                    audio_tasks.append((audio_counter, sentence))
                    audio_counter += 1
    
    # 过滤已完成的音频任务
    remaining_tasks = []
    for task in audio_tasks:
        if task[0] > completed_audio:
            remaining_tasks.append(task)
    
    # 生成音频和时间戳
    print(f"开始生成音频，共 {len(remaining_tasks)} 个音频任务")
    audio_timestamp_map = {}
    
    # 先加载已生成的时间戳
    if completed_audio > 0:
        for i in range(1, completed_audio + 1):
            audio_path = os.path.join(output_dir, "audio", f"{i}.wav")
            if os.path.exists(audio_path):
                # 这里简化处理，实际应该保存时间戳到文件
                # 暂时假设已生成的音频都有时间戳
                pass
    
    for audio_counter, text in tqdm(remaining_tasks, desc="生成音频", unit="句"):
        audio, timestamp_data = await generate_audio_with_timestamp(text)

        audio_path = os.path.join(output_dir, "audio", f"{audio_counter}.wav")
        with open(audio_path, "wb") as f:
            f.write(audio)
        audio_timestamp_map[audio_counter] = timestamp_data
        
        # 更新进度文件
        progress = {"completed_audio": audio_counter}
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        
        # 每生成一段音频后更新command.json
        generate_command_json(elements_info, audio_timestamp_map, output_dir)
        print(f"command.json 已更新，当前完成 {audio_counter} 个音频")
    
    print(f"音频生成完成，共 {len(audio_tasks)} 个音频任务")
    
    # 完成所有任务后删除进度文件
    if os.path.exists(progress_file):
        os.remove(progress_file)
        print("进度文件已删除")

if __name__ == "__main__":
    import asyncio
    
    curr_path = pathlib.Path(__file__).parent
    input_path = curr_path / "example/script.xml"
    output_path = curr_path / "output"
    
    asyncio.run(main(input_path, output_path))