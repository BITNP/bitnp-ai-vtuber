function nextTick(callback) {
  return Promise.resolve().then(callback);
}

/**
 * Audio loading, playing, and real time volume calculating.
 */
export default class AudioBank extends EventTarget {
    constructor() {        

        super();

        /** @type {Object<string, string>} */
        this.sources = {}; // id -> source

        /** @type {string} */
        this.currAudioId = null;

        /** @type {number} */
        this.volume = 0;
        this.freq = 0;

        /** @type {AudioContext} */
        this.audioContext = new AudioContext();
        
        /** @type {AnalyserNode} */
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.connect(this.audioContext.destination);

        /** @type {HTMLDivElement} */
        this.audioContainer = document.createElement('div');
        document.body.appendChild(this.audioContainer);

        /** @type {number} */
        this.uidCounter = 0;

        // TODO: try requestAnimationFrame
        setInterval(() => {
            // this.volume = (this.getVolume() - 55) / 30;
            const {volume, freq} = this.getVolumeAndPitch();
            this.volume = (volume - 55) / 30;
            this.freq = freq;
        }, 10);
    }

    handleUserGesture() {
        // 确保浏览器支持 suspend 和 resume
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                console.log('AudioContext available!');
            });
        }
    }

    uid() {
        this.uidCounter++;
        return `audio${this.uidCounter}`;
    }

    getAudioElement(id) {
        return this.audioContainer.querySelector(`#${id}`);
    }

    add(source) {
        const id = this.uid();
        this.sources[id] = source;

        const audio = document.createElement('audio');
        audio.setAttribute("id", id);
        audio.setAttribute("src", source);
        audio.setAttribute("crossOrigin", "anonymous");
        // audio.setAttribute("controls", ""); // [debug]
        this.audioContainer.appendChild(audio);

        const self = this;
        nextTick(() => {
            let audio = self.getAudioElement(id);

            try {
                audio.load();
            } catch(e) {
                console.warn(e);
            }
            nextTick(() => {
                // let context = this.audioContext; // audio context
                let sourceNode = self.audioContext.createMediaElementSource(audio);
                sourceNode.connect(self.analyser); // 连接sourceNode到analyser
            });

        });

        return id;
    }

    remove(id) {
        let audio = this.getAudioElement(id);
        if (audio) {
            audio.remove();
        }

        if (this.sources[id] === undefined) return;
        delete this.sources[id];
    }

    clear() {
        this.sources = {};

        Array.from(this.audioContainer.children).forEach(child => {
            if (child.tagName === 'AUDIO') {
                const audioSrc = child.src;
                if (audioSrc.startsWith('blob:')) {
                    source.revokeObjectsource(audioSrc); // 释放内存
                }
                child.remove();
            }
        });

        this.dispatchEvent(new Event('clear'));

        // this.audioContainer.innerHTML = "";
    }

    async play(id, autoRemove = true) { // 播放音频并等待播放结束
        return new Promise((resolve, reject) => {

            let audio = this.getAudioElement(id);

            if (this.sources[id] === undefined || !audio) {
                reject(`Audio not exist or not ready! (id: ${id})`);
                return;
            }

            this.currAudioId = id;

            console.log("play audio");

            try {
                audio.load();
                audio.play().catch((e) => {
                    console.warn("Audio play failed!", e);
                    this.currAudioId = null;
                    reject(e);
                });
                console.log({audio})
            } catch(e) {
                this.currAudioId = null;
                reject(e);
                return;
            }
            audio.addEventListener('ended', async () => {
                this.currAudioId = null;
                if (autoRemove) {
                    this.remove(id);
                }
                resolve();
            }, { once: true }); // 该listener只触发一次

            this.addEventListener('clear', async () => {
                resolve();
            }, { once: true });
        });
    }

    getVolume() {

        // 先判断id指向的audio是否可用
        let id = this.currAudioId;
        if (!id) return 0;
        let audio = this.getAudioElement(id);
        if (!audio) return 0;
        let index = this.sources.indexOf(id);
        if (index === -1) {
            return 0;
        }

        let analyser = this.analyser;

        // 创建一个数组来存储频率数据
        let frequencyData = new Uint8Array(analyser.frequencyBinCount);

        // 获取当前频率数据
        analyser.getByteFrequencyData(frequencyData);
        
        // 计算音量大小（这里使用所有频率的平均值作为音量大小的一个近似）
        let sum = 0;
        for (let i = 0; i < frequencyData.length; i++) {
            sum += frequencyData[i];
        }
        let average = sum / frequencyData.length;
        
        // 输出音量大小
        // console.log("Current volume: " + average);
        return average;
    }

    getVolumeAndPitch() {
        // 先判断source指向的audio是否可用
        let id = this.currAudioId;
        if (!id) return { volume: 0, freq: 0 };
        let audio = this.getAudioElement(id);
        if (!audio) return { volume: 0, freq: 0 };

        let analyser = this.analyser;

        // 创建一个数组来存储频率数据
        let frequencyData = new Uint8Array(analyser.frequencyBinCount);

        // 获取当前频率数据
        analyser.getByteFrequencyData(frequencyData);
        
        // 计算音量大小（所有频率的平均值）
        let sum = 0;
        for (let i = 0; i < frequencyData.length; i++) {
            sum += frequencyData[i];
        }
        let average = sum / frequencyData.length;

        // 估算主频（找到能量最高的频率）
        let maxVolume = 0;
        let maxIndex = 0;
        for (let i = 0; i < frequencyData.length; i++) {
            if (frequencyData[i] > maxVolume) {
                maxVolume = frequencyData[i];
                maxIndex = i;
            }
        }

        // 将频率索引转换为实际频率（Hz）
        // analyser的频率范围是0到sampleRate/2，均匀分布在frequencyBinCount个区间
        const sampleRate = analyser.context.sampleRate; // 通常是44100Hz
        const freq = (maxIndex / analyser.frequencyBinCount) * (sampleRate / 2);

        return {
            volume: average,
            freq: freq
        };
    }
}
