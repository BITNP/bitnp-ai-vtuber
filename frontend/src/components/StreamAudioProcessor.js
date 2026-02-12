class StreamAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.queueOffset = 0;
    this.queueSamples = 0;
    this.playedSamples = 0;
    this.samplesSinceReport = 0;
    this.reportIntervalSamples = Math.max(1, Math.floor(sampleRate * 0.05));
    this.smoothedVolume = 0;
    this.smoothingFactor = 0.5;
    this.underrunCount = 0;

    this.port.onmessage = (event) => {
      const data = event.data || {};
      if (data.type === "enqueue") {
        const buffer = data.audioBuffer;
        if (buffer) {
          const chunk = new Float32Array(buffer);
          if (chunk.length > 0) {
            this.queue.push(chunk);
            this.queueSamples += chunk.length;
          }
        }
      } else if (data.type === "clear") {
        this.queue = [];
        this.queueOffset = 0;
        this.queueSamples = 0;
        this.playedSamples = 0;
        this.samplesSinceReport = 0;
        this.smoothedVolume = 0;
        this.underrunCount = 0;
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    const channel = output[0];
    const frameCount = channel.length;

    let i = 0;
    while (i < frameCount) {
      if (this.queue.length === 0) {
        channel.fill(0, i);
        this.underrunCount += 1;
        break;
      }

      const chunk = this.queue[0];
      const available = chunk.length - this.queueOffset;
      const toCopy = Math.min(frameCount - i, available);

      channel.set(chunk.subarray(this.queueOffset, this.queueOffset + toCopy), i);
      this.queueOffset += toCopy;
      this.queueSamples -= toCopy;
      i += toCopy;

      if (this.queueOffset >= chunk.length) {
        this.queue.shift();
        this.queueOffset = 0;
      }
    }

    this.playedSamples += i;

    let sumSquares = 0;
    let peak = 0;
    for (let idx = 0; idx < frameCount; idx += 1) {
      const value = channel[idx];
      const absValue = value < 0 ? -value : value;
      sumSquares += value * value;
      if (absValue > peak) {
        peak = absValue;
      }
    }

    const rms = Math.sqrt(sumSquares / frameCount);
    const rawVolume = Math.max(rms, peak * 0.7) * 10;
    this.smoothedVolume =
      this.smoothingFactor * rawVolume +
      (1 - this.smoothingFactor) * this.smoothedVolume;

    this.samplesSinceReport += frameCount;
    if (this.samplesSinceReport >= this.reportIntervalSamples) {
      this.samplesSinceReport = 0;
      this.port.postMessage({
        type: "stats",
        volume: this.smoothedVolume,
        playedSamples: this.playedSamples,
        queueSamples: this.queueSamples,
        underrunCount: this.underrunCount,
      });
    }

    return true;
  }
}

registerProcessor("stream-audio-processor", StreamAudioProcessor);
