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
    },
    data() {
        return {
            display: '',
            target: '',
            speed: 10, // characters per second
        }
    },

    methods: {
        setSubtitle(subtitle) {
            this.target = String(subtitle);
            this.display = '';
        },

        addDelta(delta) {
            /**
             * Add a delta to the target subtitle.
             * @param {string} delta - The delta to add.
             */
            this.target += String(delta);
        },

        clear() {
            this.setSubtitle('');
        }
    },

    mounted() {
        const self = this;
        setInterval(() => {
            if (self.enable && self.display !== self.target) {
                self.display = self.target.slice(0, self.display.length + 1);
            }
        }, 1000 / self.speed);
    }
}
</script>