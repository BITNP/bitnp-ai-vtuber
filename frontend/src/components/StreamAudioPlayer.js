export default class StreamAudioPlayer {
  constructor() {
    this.audioContext = null;
    this.sourceNode = null;
    this.scriptProcessor = null;
    this.isPlaying = false;
    this.audioBuffer = null;
    this.bufferPosition = 0;
    this.expectedSampleRate = 24000; // 常见TTS采样率
    this.numChannels = 1; // 默认单声道
    this.isStreaming = false;
    this.mediaIdCounter = 0;
    this.mediaMap = new Map();
    this.isContextSuspended = false;

    // 音量计算相关属性
    this.volume = 0; // 当前音量 (0-1)
    // this.volumeUpdateInterval = 30; // 音量更新间隔(ms)
    this.lastVolumeUpdateTime = 0;
    
  }

  /**
   * 初始化音频上下文
   */
  async init() {
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // 创建分析器节点
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 256; // 小一点的fftSize提高性能
      this.analyserNode.smoothingTimeConstant = 0.5; // 平滑处理
      this.analyserDataArray = new Float32Array(this.analyserNode.fftSize);
      
      if (this.audioContext.state === 'suspended') {
        console.log('Audio context is suspended, user interaction required to resume');
        this.isContextSuspended = true;
      }
      
      console.log('Audio context initialized, sample rate:', this.audioContext.sampleRate);
      return true;
    } catch (error) {
      console.error('Failed to initialize audio context:', error);
      return false;
    }
  }

  /**
   * 开始播放流
   */
  startStream() {
    if (!this.audioContext) {
      console.error('Audio context not initialized. Call init() first.');
      return;
    }

    if (this.isStreaming) {
      console.warn('Stream is already playing');
      return;
    }

    this.isStreaming = true;
    this.isPlaying = true;
    
    // 如果音频上下文被挂起，尝试恢复
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().then(() => {
        console.log('Audio context resumed');
        this.isContextSuspended = false;
        this.setupAudioProcessing();
      });
    } else {
      this.setupAudioProcessing();
    }
  }

  /**
   * 设置音频处理
   */
  setupAudioProcessing() {
    // 创建 ScriptProcessorNode
    this.scriptProcessor = this.audioContext.createScriptProcessor(4096, 0, 1);
    
    // 连接节点: scriptProcessor -> analyser -> destination
    this.scriptProcessor.connect(this.analyserNode);
    this.analyserNode.connect(this.audioContext.destination);
    
    this.scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
      if (!this.isPlaying) return;
      
      const outputBuffer = audioProcessingEvent.outputBuffer;
      const outputData = outputBuffer.getChannelData(0);
      const samplesNeeded = outputBuffer.length;
      
      // 输出数据处理
      if (!this.audioBuffer) {
        outputData.fill(0);
        // this.updateVolume(0, Date.now());
        return;
      }
      
      if (this.bufferPosition >= this.audioBuffer.length) {
        outputData.fill(0);
        // this.updateVolume(0, Date.now());
        return;
      }
      
      const samplesAvailable = this.audioBuffer.length - this.bufferPosition;
      const samplesToCopy = Math.min(samplesNeeded, samplesAvailable);
      
      // 复制数据
      for (let i = 0; i < samplesToCopy; i++) {
        outputData[i] = this.audioBuffer[this.bufferPosition + i];
      }
      
      // 剩余部分填0
      for (let i = samplesToCopy; i < samplesNeeded; i++) {
        outputData[i] = 0;
      }
      
      this.bufferPosition += samplesToCopy;
      
      // 更新音量
      const self = this;
      const volumeLoop = () => {
        self.updateVolumeFromData(outputData, Date.now());
        requestAnimationFrame(volumeLoop);
      }
      volumeLoop();
    };
  }

  /**
   * 从音频数据计算音量
   */
  updateVolumeFromData(audioData, currentTime) {
    // // 按间隔更新音量
    // if (currentTime - this.lastVolumeUpdateTime < this.volumeUpdateInterval) {
    //   return;
    // }
    
    this.lastVolumeUpdateTime = currentTime;
    
    // 计算RMS音量
    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    
    const rms = Math.sqrt(sum / audioData.length);
    
    // 计算峰值
    let peak = 0;
    for (let i = 0; i < audioData.length; i++) {
      const absValue = Math.abs(audioData[i]);
      if (absValue > peak) {
        peak = absValue;
      }
    }
    
    // 使用RMS和峰值的综合值
    const rawVolume = Math.max(rms, peak * 0.7) * 10;

    // 平滑处理
    const smoothingFactor = 0.5;
    this.volume = smoothingFactor * rawVolume + (1 - smoothingFactor) * this.volume;
  }

  /**
   * 添加 base64 编码的 WAV 音频数据
   */
  async addWavData(base64WavData) {
    if (!this.isStreaming) {
      console.warn('Stream not started. Call startStream() first.');
      return -1;
    }

    try {
      const mediaId = ++this.mediaIdCounter;
      
      // 解码 base64
      let binaryString;
      if (base64WavData.startsWith('data:audio/wav;base64,')) {
        // 如果包含data URL前缀，移除它
        const base64Data = base64WavData.split(',')[1];
        binaryString = atob(base64Data);
      } else {
        binaryString = atob(base64WavData);
      }
      
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      // 解析WAV并获取音频数据
      const audioData = await this.decodeWavData(bytes.buffer);
      
      // 添加到缓冲区
      this.appendAudioData(audioData);
      
      this.mediaMap.set(mediaId, {
        data: audioData,
        timestamp: Date.now()
      });
      
      return mediaId;
    } catch (error) {
      console.error('Failed to add WAV data:', error);
      return -1;
    }
  }

  /**
   * 解码 WAV 数据
   */
  async decodeWavData(wavArrayBuffer) {
    const dataView = new DataView(wavArrayBuffer);
    
    // 检查RIFF头
    const riff = String.fromCharCode(
      dataView.getUint8(0),
      dataView.getUint8(1),
      dataView.getUint8(2),
      dataView.getUint8(3)
    );
    
    if (riff !== 'RIFF') {
      throw new Error('Not a valid WAV file');
    }
    
    // 解析WAV格式
    let offset = 12;
    let audioData = null;
    let sampleRate = 24000; // 默认值
    let numChannels = 1;
    let bitsPerSample = 16;
    
    while (offset < dataView.byteLength) {
      const chunkId = String.fromCharCode(
        dataView.getUint8(offset),
        dataView.getUint8(offset + 1),
        dataView.getUint8(offset + 2),
        dataView.getUint8(offset + 3)
      );
      
      const chunkSize = dataView.getUint32(offset + 4, true);
      
      if (chunkId === 'fmt ') {
        // 解析fmt区块
        const audioFormat = dataView.getUint16(offset + 8, true);
        numChannels = dataView.getUint16(offset + 10, true);
        sampleRate = dataView.getUint32(offset + 12, true);
        bitsPerSample = dataView.getUint16(offset + 22, true);
        
        console.log(`WAV Info: format=${audioFormat}, channels=${numChannels}, sampleRate=${sampleRate}, bits=${bitsPerSample}`);
        
        if (audioFormat !== 1) {
          throw new Error('Only PCM WAV format is supported');
        }
        
      } else if (chunkId === 'data') {
        // 找到data区块
        const dataOffset = offset + 8;
        const dataSize = chunkSize;
        
        // 解析音频数据
        audioData = this.extractAudioData(
          dataView, 
          dataOffset, 
          dataSize, 
          numChannels, 
          bitsPerSample
        );
        
        // 如果需要重采样
        if (sampleRate !== this.audioContext.sampleRate) {
          console.log(`Resampling from ${sampleRate}Hz to ${this.audioContext.sampleRate}Hz`);
          audioData = this.resampleAudioData(audioData, sampleRate, this.audioContext.sampleRate, numChannels);
        }
        
        // 更新通道数
        this.numChannels = numChannels;
        
        break;
      }
      
      offset += 8 + chunkSize;
    }
    
    if (!audioData) {
      throw new Error('No audio data found in WAV file');
    }
    
    return audioData;
  }

  /**
   * 从WAV文件中提取音频数据
   */
  extractAudioData(dataView, offset, size, numChannels, bitsPerSample) {
    const bytesPerSample = bitsPerSample / 8;
    const totalSamples = size / bytesPerSample;
    const samplesPerChannel = totalSamples / numChannels;
    
    const floatData = new Float32Array(totalSamples);
    
    if (bitsPerSample === 16) {
      // 16-bit PCM
      for (let i = 0; i < totalSamples; i++) {
        const sample = dataView.getInt16(offset + i * 2, true);
        floatData[i] = sample / 32768.0;
      }
    } else if (bitsPerSample === 8) {
      // 8-bit PCM
      for (let i = 0; i < totalSamples; i++) {
        const sample = dataView.getUint8(offset + i);
        floatData[i] = (sample - 128) / 128.0;
      }
    } else if (bitsPerSample === 24) {
      // 24-bit PCM
      for (let i = 0; i < totalSamples; i++) {
        const sample = dataView.getInt8(offset + i * 3) << 16 |
                      dataView.getUint8(offset + i * 3 + 1) << 8 |
                      dataView.getUint8(offset + i * 3 + 2);
        floatData[i] = sample / 8388608.0;
      }
    } else if (bitsPerSample === 32) {
      // 32-bit float
      for (let i = 0; i < totalSamples; i++) {
        floatData[i] = dataView.getFloat32(offset + i * 4, true);
      }
    } else {
      throw new Error(`Unsupported bits per sample: ${bitsPerSample}`);
    }
    
    return floatData;
  }

  /**
   * 音频重采样
   */
  resampleAudioData(audioData, originalSampleRate, targetSampleRate, numChannels) {
    if (originalSampleRate === targetSampleRate) {
      return audioData;
    }
    
    const ratio = targetSampleRate / originalSampleRate;
    const originalLength = audioData.length;
    const targetLength = Math.round(originalLength * ratio);
    const resampledData = new Float32Array(targetLength);
    
    // 简单线性插值重采样
    for (let i = 0; i < targetLength; i++) {
      const originalIndex = i / ratio;
      const index1 = Math.floor(originalIndex);
      const index2 = Math.min(Math.ceil(originalIndex), originalLength - 1);
      const weight = originalIndex - index1;
      
      if (index1 === index2) {
        resampledData[i] = audioData[index1];
      } else {
        resampledData[i] = audioData[index1] * (1 - weight) + audioData[index2] * weight;
      }
    }
    
    console.log(`Resampled: ${originalLength} samples -> ${targetLength} samples`);
    return resampledData;
  }

  /**
   * 追加音频数据到缓冲区
   */
  appendAudioData(float32Array) {
    if (!this.audioBuffer) {
      this.audioBuffer = new Float32Array(float32Array);
    } else {
      const newBuffer = new Float32Array(this.audioBuffer.length + float32Array.length);
      newBuffer.set(this.audioBuffer);
      newBuffer.set(float32Array, this.audioBuffer.length);
      this.audioBuffer = newBuffer;
    }
    
    console.log(`Audio buffer size: ${this.audioBuffer.length} samples, duration: ${this.getTotalDuration().toFixed(2)}s`);
  }

  /**
   * 获取总音频时长
   */
  getTotalDuration() {
    if (!this.audioBuffer) return 0;
    return this.audioBuffer.length / this.audioContext.sampleRate;
  }

  /**
   * 获取剩余音频时长
   */
  getRemainingDuration() {
    if (!this.audioBuffer) return 0;
    const remainingSamples = this.audioBuffer.length - this.bufferPosition;
    return remainingSamples / this.audioContext.sampleRate;
  }

  /**
   * 获取当前播放位置
   */
  getCurrentTime() {
    if (!this.audioBuffer || this.bufferPosition === 0) return 0;
    return this.bufferPosition / this.audioContext.sampleRate;
  }

  // 其他方法保持不变...
  pause() {
    this.isPlaying = false;
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.suspend();
    }
  }

  resume() {
    this.isPlaying = true;
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.resume();
    }
  }

  stop() {
    this.isPlaying = false;
    this.isStreaming = false;
    this.bufferPosition = 0;
    
    if (this.scriptProcessor) {
      this.scriptProcessor.disconnect();
      this.scriptProcessor = null;
    }
    
    this.audioBuffer = null;
    this.mediaMap.clear();
  }

  destroy() {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}