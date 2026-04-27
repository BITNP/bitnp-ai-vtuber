<template>
    <!-- <div style="width: 100%; height: 100%; margin: 0; padding: 0;"> -->
    <span>
        {{ display }}
    </span>
    <!-- </div> -->
</template>

<script>
export default {
    name: 'Subtitle',
    props: {
        enable: {
            type: Boolean,
            default: true,
        },
        dynamic: {
            type: Boolean,
            default: true,
        }
    },
    data() {
        return {
            display: '',
            target: '',
            speed: 10, // 默认characters per second
            duration: 0, // 音频时长（秒）
            startTime: null, // 开始时间
            updateInterval: null, // 更新间隔ID
        }
    },

    methods: {
        setSubtitle(subtitle, duration = 0) {
            this.target = String(subtitle);
            this.duration = duration;
            this.startTime = Date.now();
            
            if (!this.dynamic) {
                this.display = this.target;
            }
        },

        addDelta(delta) {
            /**
             * Add a delta to the target subtitle.
             * @param {string} delta - The delta to add.
             */
            if (!this.dynamic) return;
            this.target += String(delta);
        },

        clear() {
            this.setSubtitle('');
        },

        updateDisplay() {
            if (!this.dynamic) return;
            
            if (!this.enable || this.display === this.target) {
                return;
            }
            
            if (this.duration > 0 && this.target.length > 0) {
                // 根据音频时长计算当前应该显示的文本长度
                const elapsedTime = (Date.now() - this.startTime) / 1000;
                const progress = Math.min(elapsedTime / this.duration, 1);
                const targetLength = Math.floor(progress * this.target.length);
                this.display = this.target.slice(0, targetLength);
            } else {
                // 使用默认速度
                this.display = this.target.slice(0, this.display.length + 1);
            }
        }
    },

    mounted() {
        const self = this;
        // 设置更短的更新间隔以获得更平滑的效果
        this.updateInterval = setInterval(() => {
            self.updateDisplay();
        }, 50); // 20fps更新频率
    },
    
    beforeUnmount() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }
}
</script>