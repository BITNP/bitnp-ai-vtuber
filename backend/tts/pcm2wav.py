import struct

def pcm2wav(pcm_data: bytes, 
               sample_rate: int = 24000, 
               channels: int = 1, 
               bits_per_sample: int = 16) -> bytes:
    """
    将PCM数据转换为WAV格式
    
    Args:
        pcm_data: 原始PCM数据
        sample_rate: 采样率
        channels: 声道数
        bits_per_sample: 位深度
        
    Returns:
        bytes: WAV格式音频数据
    """
    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    
    # 创建WAV文件头
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                     # 文件标识
        36 + data_size,              # 文件总长度减去8字节
        b'WAVE',                     # 格式标识
        b'fmt ',                     # 子块标识
        16,                          # 子块大小
        1,                           # 音频格式（1表示PCM）
        channels,                    # 声道数
        sample_rate,                 # 采样率
        byte_rate,                   # 字节率
        block_align,                 # 块对齐
        bits_per_sample,             # 位深度
        b'data',                     # 数据标识
        data_size                    # 数据长度
    )
    
    return header + pcm_data
