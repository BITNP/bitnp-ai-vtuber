<template>
    <div>
        <div class="background-image"></div>
        <div class="danmuku-area" ref="danmukuArea"></div>
        <div class="user-interface" id="user-interface">
            <!-- UI区域 -->
            <button v-if="!audioEnabled" @click="enableAudioActivities">启用音频</button>
            <input ref="inputArea" type="text" v-model="inputText" placeholder="请输入...">
            <!-- <button @click="switchMicrophoneMode">{{ (microphoneOn) ? '闭麦' : '开麦' }}</button> -->
        </div>

        <div class="logo-background"></div>

        <audio ref="audioPlayer" src="" hidden></audio>

        <div ref="configUI" :class="showConfigUI ? 'config-ui' : 'config-ui config-ui-hidden'">
            <!--  -->
            <h1 class="config-title">设置菜单</h1>
            <span>按“=”键随时唤出此菜单</span>
            <br>
            <br>

            <label>
                <input type="checkbox" v-model="enableDictation">
                启用听写
            </label><br>

            <label>
                <input type="checkbox" v-model="enableFullScreen">
                全屏模式
            </label><br>

            <label>
                <input type="checkbox" v-model="allowPauseDictation">
                在 AI 说话时禁用语音识别
            </label><br>
            
        </div>

        <div class="subtitle-area">
            <div ref="subtitleContainer1" class="subtitle-container subtitle-container-hidden">
                <div ref="subtitleInnerContainer1" class="subtitle-inner-container">
                    <span ref="subtitle1" class="subtitle"></span>
                </div>
            </div>
        </div>

        <div class="canvas-container">
            <canvas ref="mainCanvas" id="mainCanvas" class="main_canvas"></canvas>
        </div>

        <div v-if="debug" class="visualize-area">
            <!-- 数据可视化区域 -->
            <div v-if="actionQueueWatcher" class="action-queue">
                <div v-for="(action, i) in actionQueueWatcher" :key="i" class="action-container">
                    <span> 动作类型: {{ action.type }} <br>
                        内容: {{ action.data }}
                    </span>
                </div>
            </div>

            <div v-if="resourcesWatcher" class="resource-bank">
                <!-- {{ resourceManager.resourceBank }} <br>
                {{ resourceManager.resourceIds }} -->
                <div v-for="(resource, i) in resourcesWatcher" :key="i" class="resource-container">
                    <!-- {{ resourceManager.get(id) }} -->
                    <span> 资源类型: {{ resource.type }} <br>
                        是否就绪: {{ resource.ready }} <br>
                        内容: {{ resource.data }}
                    </span>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import Live2dController from '@/live2d-controller/Live2dController';
import LIVE2D_CONFIG from '@/agent-presets/shumeiniang/live2dConfig.js'
import FrontendAgent from '@/ws-client/FrontendAgent';
import AudioBank from '@/components/AudioBank';

export default {
    components: {
        // ... 
    },
    data() {
        return {
            microphoneOn: false,
            debug: false,
            audioEnabled: false, // The user needs to interact with the page (by clicking the button) to enable audio

            imageSrc: "",
            inputText: "",

            // app vars
            showConfigUI: false,
            enableDictation: false,
            enableFullScreen: false,
            allowPauseDictation: true,
        };
    },

    watch: {
        enableFullScreen(newVal) {
            if (newVal) {
                this.enterFullscreen();
            } else {
                this.exitFullscreen();
            }
        }
    },

    methods: {
        enterFullscreen() {
            const element = document.documentElement; // 整个页面全屏
            const requestMethod =
                element.requestFullscreen ||
                element.webkitRequestFullscreen ||
                element.mozRequestFullScreen ||
                element.msRequestFullscreen;

            if (requestMethod) {
                requestMethod.call(element).catch((err) => {
                    console.error("全屏失败:", err);
                    this.enableFullScreen = false; // 失败时重置状态
                });
            }
        },

        exitFullscreen() {
            const exitMethod =
                document.exitFullscreen ||
                document.webkitExitFullscreen ||
                document.mozCancelFullScreen ||
                document.msExitFullscreen;

            if (exitMethod) {
                exitMethod.call(document);
            }
        },

        enableAudioActivities() {
            if (!this.audioBank) {
                return;
            }
            this.audioBank.handleUserGesture();
            this.audioEnabled = true;
        },

        async recordChat(message) {
            /**
             * 将用户输入记录在userInputBuffer中
             * @param message String
             */
            this.wsClient.sendData({
                type: "event",
                data: {type: "user_input", content: message},
            });
            console.log(`Add text: ${message}`);
        },
    },

    mounted() {
        // shumeiniang Live2d controller
        const config = LIVE2D_CONFIG;
        config.canvas = this.$refs.mainCanvas;
        console.log(config)
        const live2dController = new Live2dController(config);
        live2dController.setup();

        const serverUrl = "localhost:8000"
        const agentName = "shumeiniang"
        const client = new FrontendAgent(serverUrl, agentName);
        client.connect();

        this.wsClient = client;

        const audioBank = new AudioBank();
        this.audioBank = audioBank;

        live2dController.setLipSyncFunc(() => {
            return audioBank.volume;
        });

        const eventQueue = [];
        client.on("message", (message) => {
            console.log("on message", message);
            if (message.detail && message.detail.data && message.detail.data.type) {
                const event = message.detail.data
                const type = event.type;
                if (type === "say_aloud") {
                    const mediaData = event["media_data"];
                    const id = audioBank.add(`data:audio/wav;base64,${mediaData}`); // base64 wav media data
                    event["media_id"] = id;
                }
            }

            eventQueue.push(message);
        });

        async function handleSayAloud(message) {
            // TODO
            // const mediaData = message["media_data"];
            // console.log("handleSayAloud", message);
            const mediaId = message["media_id"];
            await audioBank.play(mediaId);
        }

        async function handleBracketTag(message) {
            // TOOD
            live2dController.setExpression(message.content);
        }

        async function processEventQueue() {
            try {
                if (eventQueue.length === 0) {
                    requestAnimationFrame(processEventQueue);
                    return
                }

                const event = eventQueue.shift();
                const message = event.detail.data;

                console.log("processing message from server:", message); // DEBUG

                if (message.type === "say_aloud") {
                    await handleSayAloud(message);
                } else if (message.type === "bracket_tag") {
                    await handleBracketTag(message);
                }
            } catch (error) {
                console.error("Error processing event:", error);
            }
            requestAnimationFrame(processEventQueue);
        }
        processEventQueue();

        this.$refs.inputArea.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                // 清空事件队列
                eventQueue.length = 0;
                // audioBank.clear();
                this.recordChat(this.inputText);
                this.inputText = "";
            }
        });
    },
};
</script>

<style>
#app {
    position: absolute;
    left: 0;
    top: 0;
    width: 100vw;
    height: 100vh;
    font-family: Avenir, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-align: center;
    color: #2c3e50;
}

.danmuku-area {
    position: fixed;
    width: 30vw;
    height: 100vh;
    /* border: 1px solid black; */
    overflow-y: scroll;
}
.danmuku-area::-webkit-scrollbar {
    display: none;
}

.canvas-container {
    box-sizing: content-box;
    position: fixed;
    margin: 0;
    padding: 0;
    /* display: flex; */
    /* 使用flex布局 */
    width: 100%;
    /* 充满屏幕宽度 */
    height: 100vh;
    /* 充满屏幕高度 */
}

.left-section,
.right-section {
    flex: 1;
    /* 均等分配空间 */
    height: 100%;
    /* 继承容器高度 */
    position: relative;
}

.main_canvas {
    position: fixed;
    margin: 0;
    padding: 0;
    width: 100vw; /* modified */
    height: 100vh;
    left: 0;
    top: 0;
}

.canvas {
    position: absolute;
    margin: 0;
    padding: 0;
    display: block;
    /* 避免canvas默认inline带来的空白间隙 */
    width: 100%;
    /* 充满父容器 */
    height: 100%;
    /* 充满父容器 */

    opacity: 1;
    transform: translateX(0);
    transition: opacity 0.5s ease, transform 0.5s ease;
}

.canvas_hidden {
    transform: translateX(-50px);
    opacity: 0;
}



.user-interface {
    z-index: 999999;
    position: fixed;
    width: 90vw;
    /* 1vw = 视口宽的的1% */
    max-width: 600px;
    left: 50vw;
    top: 100vh;
    transform: translate(-50%, -150%);
    /* border: 1px solid black; */
    /* background-color: yellow; */
    /* -webkit-app-region: drag; */
}

.user-interface>* {
    border-radius: 10px;
    margin: 10px;
    font-family: Avenir, Helvetica, Arial, sans-serif;
    font-size: 2em;
}

.user-interface>input {
    width: 80%;
    max-width: 800px;
}

.subtitle-area {
    position: fixed;
    z-index: 998;
    margin: 0;
    left: 0;
    padding: 0;
    width: 50vw;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: last baseline;

    perspective: 1000px; /* 3D 透视焦距 */
}

@keyframes subtitle-hover {
    0% { transform: rotateY(20deg) rotateX(-20deg) translate(100px, -300px);}
    25% { transform: rotateY(25deg) rotateX(-15deg) translate(100px, -280px);}
    50% { transform: rotateY(20deg) rotateX(-20deg) translate(100px, -300px);}
    75% { transform: rotateY(15deg) rotateX(-25deg) translate(100px, -320px);}
    100% { transform: rotateY(20deg) rotateX(-20deg) translate(100px, -300px);}
}

@keyframes subtitle-hide {
    0% { transform: rotateY(20deg) rotateX(-20deg) translate(100px, -300px);}
    100% { transform: rotateY(0deg) rotateX(90deg) translate(0, 0);}
}

.subtitle-container {
    margin-left: 10%;
    width: 80%;
    margin-right: 10%;

    padding-top: 20px;
    padding-bottom: 30px;
    padding-left: 40px;
    padding-right: 40px;

    text-align: left;

    aspect-ratio: 907/200;
    background-image: url("@/assets/tooltip.png");
    background-size: 100% 100%;
    background-repeat: no-repeat;

    opacity: 1;
    z-index: 1000;
    transform-style: preserve-3d;
    transform: rotateY(20deg) rotateX(-20deg) translate(100px, -300px);
    animation: subtitle-hover 10s infinite linear 0.5s;
    transition: opacity 0.5s ease, transform 0.5s ease;
}

.subtitle-container-hidden {
    opacity: 0;
    transform: rotateY(20deg) rotateX(90deg) translate(0, 0);
    transition: opacity 0.5s ease, transform 0.5s ease;
    animation: subtitle-hide 0.5s ease-out;
}

.subtitle-inner-container {
    width: 100%;
    height: 100%;
    overflow-y: scroll;
}
.subtitle-inner-container::-webkit-scrollbar {
  display: none; /* 完全隐藏滚动条 */
}

.subtitle {
    font-size: 2em;
    font-weight: 1000;
    -webkit-text-stroke: 1px rgb(255, 255, 255);
    text-shadow: 2px 2px rgb(43, 38, 43);
    user-select: none;
    color: rgb(56, 225, 255);
}

/* stt subtitle container */

@keyframes subtitle-hover-stt {
    0% { transform: rotateY(-20deg) rotateX(-20deg) translate(-100px, 0);}
    25% { transform: rotateY(-25deg) rotateX(-15deg) translate(-100px, 0);}
    50% { transform: rotateY(-20deg) rotateX(-20deg) translate(-100px, 0);}
    75% { transform: rotateY(-15deg) rotateX(-25deg) translate(-100px, 0);}
    100% { transform: rotateY(-20deg) rotateX(-20deg) translate(-100px, 0);}
}

@keyframes subtitle-hide-stt {
    0% { transform: rotateY(-20deg) rotateX(-20deg) translate(100px, 0);}
    100% { transform: rotateY(0deg) rotateX(90deg) translate(0, 0);}
}

.subtitle-area.stt {
    position: fixed;
    margin: 0;
    left: 50vw;
    padding-top: 10vh;
    width: 50vw;
    height: 100vh;

    align-items: first baseline;
}
.subtitle-container.stt {
    transform: rotateY(-20deg) rotateX(-20deg) translate(-100px, 0);
    animation: none;
    transition: opacity 0.5s ease, transform 0.5s ease;
    animation: subtitle-hover-stt 10s infinite linear 0.5s;
}

.subtitle-container-hidden.stt {
    transform: rotateY(-20deg) rotateX(90deg) translate(0, 0);
    animation: subtitle-hide-stt 0.5s ease-out;
}

.visualize-area {
    position: absolute;
    z-index: 2;
    right: 5%;
    width: 20vw;
}

.action-queue {
    position: relative;
    width: 100%;
}

.action-container {
    position: relative;
    margin: 5px;
    width: 100%;
    border: 1px solid black;
    background: rgb(116, 116, 238);
    border-radius: 10px;
    color: white;
}

.resource-bank {
    position: relative;
    width: 100%;
}

.resource-container {
    position: relative;
    margin: 5px;
    width: 100%;
    border: 1px solid black;
    background: rgb(238, 116, 179);
    border-radius: 10px;
    color: white;
}

.background-image {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    /* background-image: url('@/assets/bg01020.png'); */
    background: linear-gradient(to top, rgb(4, 4, 38), rgb(44, 26, 90));
    background-position: center;
    background-repeat: no-repeat;
    background-size: cover;
    z-index: -1
}

.iframe {
    position: fixed;
    border: none;
    background-color: transparent;
    z-index: 998;
    top: 0;
    right: 0;
    width: 50vw;
    height: 100vh;
}

.config-ui {
    border: #2c3e50;
    background-color: rgb(28, 0, 57);
    border-radius: 10px;
    padding: 10px;
    color: white;
    position: fixed;
    top: 25vh;
    left: 25vw;
    width: 50vw;
    height: 50vh;
    opacity: 1;
    z-index: 9999;
    transform: translate(0, 0);
    transition: opacity 0.5s ease, transform 0.5s ease;
}

.config-ui-hidden {
    opacity: 0;
    transform: translate(0, 1000px);
}

.camera-container {
    z-index: 5;
    position: fixed;
    right: 0vw;
    width: 25vw;
}

.camera-image {
    width: 100%;
    height: 100%;
    border-radius: 10px;
}

.logo-background {
    position: fixed;
    width: 30vw;
    left: 35vw;
    top: 20vh;
    aspect-ratio: 647/493;

    background-image: url("@/assets/logo_background.png");
    background-size: 100% 100%;
    background-repeat: no-repeat;
}
</style>