<template>
    <div>
        <div class="background-image"></div>
        
        <!-- PPT展示区域 -->
        <div class="ppt-container">
            <img 
                v-if="currentSlideUrl" 
                :src="currentSlideUrl" 
                :alt="`幻灯片 ${currentPptPage}`"
                class="ppt-slide"
            />
        </div>
        
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

            <div class="lecture-controls">
                <h2>讲稿控制</h2>
                <div class="lecture-buttons">
                    <button @click="toggleLecturePause">{{ lecturePaused ? '继续' : '暂停' }}</button>
                    <button @click="sendLectureControl('prev')">上一页</button>
                    <button @click="sendLectureControl('next')">下一页</button>
                    <button @click="sendLectureControl('replay')">重播当前页</button>
                </div>
                <div class="lecture-goto">
                    <input type="number" v-model="lectureControlPage" placeholder="页码" min="1">
                    <button @click="gotoLecturePage">跳转</button>
                </div>
            </div>
            
        </div>


        <div ref="subtitleContainer" :class="['subtitle-container', { 'subtitle-container-hidden': subtitleHidden }]">
            <div> <!-- placeholder --> </div>
            <div ref="subtitleInnerContainer" class="subtitle-inner-container">
                <Subtitle ref="subtitle" class="subtitle-text" />
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
                <!-- {{ resourceManager.resourceBank }} <br> -->
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
import Subtitle from '@/components/Subtitle.vue';
import StreamAudioPlayer from '@/components/StreamAudioPlayer.js';

export default {
    components: {
        Subtitle
    },
    data() {
        return {
            microphoneOn: false,
            debug: false,
            audioEnabled: false, // The user needs to interact with the page (by clicking the button) to enable audio

            imageSrc: "",
            inputText: "",
            subtitleHidden: true, // 是否隐藏字幕
            
            // PPT相关配置
            pptSlides: [],  // 存储所有幻灯片图片URL
            currentSlideUrl: '',  // 当前显示的幻灯片URL
            currentPptPage: 1,  // 当前页码（从1开始）
            totalSlides: 10,  // 幻灯片总数
            useRemotePptAssets: false,

            lectureControlPage: "",
            lecturePaused: false,

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
        
        // 初始化PPT幻灯片图片序列
        async initPptSlides() {
            if (this.useRemotePptAssets) {
                return;
            }
            this.totalSlides = 100; // 设置一个合理的最大值，避免重复检测
            this.pptSlides = [];
            this.isPreloading = true;
            this.preloadedSlides = new Set(); // 记录已预加载的幻灯片
            
            // 使用中文命名格式：幻灯片1.PNG, 幻灯片2.PNG...
            const baseUrl = '/documents/slides/幻灯片';
            const extension = '.PNG';
            this.baseUrl = baseUrl;
            this.imageExtension = extension;
            
            // 初始化数组
            this.pptSlides = new Array(this.totalSlides).fill(null);
            
            // 并发预加载前3页幻灯片，提高初始化速度
            await Promise.all([
                this.preloadSlide(1),
                this.preloadSlide(2),
                this.preloadSlide(3)
            ]);
            
            // 初始化完成后显示第一页
            if (this.pptSlides[0]) {
                this.currentPptPage = 1;
                this.currentSlideUrl = this.pptSlides[0];
            }
            
            this.isPreloading = false;
            
            // 后台预加载更多幻灯片（4-10页），不阻塞UI
            this.preloadInBackground(4, 10);
        },
        
        // 后台预加载指定范围的幻灯片
        preloadInBackground(startPage, endPage) {
            const preloadPromises = [];
            for (let i = startPage; i <= endPage; i++) {
                if (i > this.totalSlides) break;
                // 使用setTimeout分散加载，避免一次性占用太多资源
                setTimeout(() => {
                    this.preloadSlide(i).catch(err => console.log(`[后台预加载] 幻灯片 ${i} 加载失败: ${err}`));
                }, (i - startPage) * 500); // 每500ms加载一张
            }
        },
        
        // 加载图片的辅助方法（添加超时处理）
        loadImage(url, timeout = 10000) { // 10秒超时
            return new Promise((resolve, reject) => {
                const img = new Image();
                const timer = setTimeout(() => {
                    reject(new Error(`图片加载超时: ${url}`));
                }, timeout);
                
                img.onload = () => {
                    clearTimeout(timer);
                    resolve();
                };
                
                img.onerror = () => {
                    clearTimeout(timer);
                    reject(new Error(`图片加载失败: ${url}`));
                };
                
                img.src = url;
            });
        },
        
        // 预加载单张幻灯片的方法（根据页码）
        async preloadSlide(pageNum) {
            // 检查页码是否有效
            if (pageNum < 1 || pageNum > this.totalSlides) {
                return;
            }
            
            // 如果已经预加载过，直接返回
            if (this.preloadedSlides.has(pageNum)) {
                return;
            }
            
            try {
                const slideUrl = this.useRemotePptAssets
                    ? this.pptSlides[pageNum - 1]
                    : `${this.baseUrl}${pageNum}${this.imageExtension}`;

                if (!slideUrl) {
                    return;
                }
                await this.loadImage(slideUrl);
                
                // 存储预加载的幻灯片URL
                this.pptSlides[pageNum - 1] = slideUrl;
                this.preloadedSlides.add(pageNum);
                console.log(`已预加载幻灯片 ${pageNum}`);
            } catch (e) {
                // 幻灯片加载失败
                this.pptSlides[pageNum - 1] = null;
                console.log(`幻灯片 ${pageNum} 加载失败`);
            }
        },
        
        // 按需预加载方法：预加载当前页的前后各一张（非阻塞方式）
        preloadAroundCurrentPage() {
            const currentPage = this.currentPptPage;
            
            // 使用Promise.all并行预加载，不阻塞主线程
            const preloadPromises = [];
            
            // 预加载前一页
            if (currentPage > 1) {
                preloadPromises.push(this.preloadSlide(currentPage - 1));
            }
            
            // 预加载后一页
            if (currentPage < this.totalSlides) {
                preloadPromises.push(this.preloadSlide(currentPage + 1));
            }
            
            // 并行预加载，不等待完成
            Promise.all(preloadPromises)
                .then(() => {
                    console.log(`[预加载] 当前页 ${currentPage} 的前后页预加载完成`);
                })
                .catch(err => {
                    console.log(`[预加载] 部分幻灯片预加载失败: ${err}`);
                });
        },

        enableAudioActivities() {
            this.streamAudioPlayer.init();
            // if (!this.audioBank) {
            //     return;
            // }
            // this.audioBank.handleUserGesture();
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

        showSubtitle() {
            const subtitle = this.$refs.subtitle;
            if (!subtitle) {
                console.warn('Subtitle ref is null, cannot show subtitle');
                return;
            }
            
            subtitle.clear();
            this.subtitleHidden = false;

            setTimeout(() => {
                if (subtitle) {
                    subtitle.enable = true;
                }
            }, 1000)
        },

        hideSubtitle() {
            const subtitle = this.$refs.subtitle;
            this.subtitleHidden = true;
        },

        // 新增图片显示方法
        showImage(imageUrl) {
            this.currentImage = imageUrl;
            const imageContainer = this.$refs.imageContainer;
            if (imageContainer) {
                imageContainer.style.backgroundImage = `url('${imageUrl}')`;
            }
        },

        // 新增隐藏图片方法
        hideImage() {
            this.currentImage = "";
            const imageContainer = this.$refs.imageContainer;
            if (imageContainer) {
                imageContainer.style.backgroundImage = "none";
            }
        },

        // 新增图片显示方法
        showImage(imageUrl) {
            this.currentImage = imageUrl;
            const imageContainer = this.$refs.imageContainer;
            if (imageContainer) {
                imageContainer.style.backgroundImage = `url('${imageUrl}')`;
            }
        },

        // 新增隐藏图片方法
        hideImage() {
            this.currentImage = "";
            const imageContainer = this.$refs.imageContainer;
            if (imageContainer) {
                imageContainer.style.backgroundImage = "none";
            }
        },
        
        // PPT相关方法
        async handleFlipPptPage(pageNum) {
            console.log(`[翻页] 开始翻页到PPT第${pageNum}页`);
            console.log(`[翻页] 当前页码: ${this.currentPptPage}, 目标页码: ${pageNum}`);
            
            // 确保页码是数字类型
            const targetPage = parseInt(pageNum, 10);
            
            // 验证页码是否在有效范围内
            if (targetPage >= 1 && targetPage <= this.totalSlides) {
                // 检查该页码的幻灯片是否已预加载
                if (this.pptSlides[targetPage - 1]) {
                    // 立即切换幻灯片
                    console.log(`[翻页] 幻灯片 ${targetPage} 已预加载，立即切换`);
                    this.currentPptPage = targetPage;
                    this.currentSlideUrl = this.pptSlides[targetPage - 1];
                    console.log(`[翻页] 已切换到幻灯片 ${targetPage}`);
                } else {
                    // 如果未加载，先加载再切换
                    console.log(`[翻页] 幻灯片 ${targetPage} 未加载，开始加载...`);
                    try {
                        console.time(`[翻页] 加载幻灯片${targetPage}耗时`);
                        await Promise.race([
                            this.preloadSlide(targetPage),
                            new Promise((_, reject) => setTimeout(() => reject(new Error('加载超时')), 15000))
                        ]);
                        console.timeEnd(`[翻页] 加载幻灯片${targetPage}耗时`);
                        
                        if (this.pptSlides[targetPage - 1]) {
                            console.log(`[翻页] 幻灯片 ${targetPage} 加载成功，切换幻灯片`);
                            this.currentPptPage = targetPage;
                            this.currentSlideUrl = this.pptSlides[targetPage - 1];
                            console.log(`[翻页] 已切换到幻灯片 ${targetPage}`);
                        } else {
                            console.error(`[翻页] 幻灯片 ${targetPage} 加载失败`);
                        }
                    } catch (e) {
                        console.error(`[翻页] 幻灯片 ${targetPage} 加载超时或失败: ${e}`);
                    }
                }
                
                // 预加载新当前页的前后各一张
                this.preloadAroundCurrentPage();
            } else {
                console.error(`[翻页] 无效的页码: ${targetPage}`);
            }
        },

        applyPptAssets(urls) {
            if (!Array.isArray(urls) || urls.length === 0) {
                return;
            }
            this.useRemotePptAssets = true;
            this.pptSlides = urls;
            this.totalSlides = urls.length;
            this.currentPptPage = 1;
            this.currentSlideUrl = urls[0] || '';
            this.preloadedSlides = new Set();
            this.preloadSlide(1);
            this.preloadAroundCurrentPage();
        },

        sendLectureControl(action, payload = {}) {
            if (!this.wsClient) {
                return;
            }
            this.wsClient.sendData({
                type: "event",
                data: {
                    type: "lecture_control",
                    action,
                    ...payload,
                },
            });
        },

        toggleLecturePause() {
            const nextAction = this.lecturePaused ? "resume" : "pause";
            this.sendLectureControl(nextAction);
            this.lecturePaused = !this.lecturePaused;
        },

        gotoLecturePage() {
            const pageNum = parseInt(this.lectureControlPage, 10);
            if (!Number.isNaN(pageNum) && pageNum > 0) {
                this.sendLectureControl("goto", { page_num: pageNum });
            }
        },

    },

    mounted() {
        const self = this;

        // shumeiniang Live2d controller
        const config = LIVE2D_CONFIG;
        config.canvas = this.$refs.mainCanvas;
        console.log(config)
        const live2dController = new Live2dController(config);
        live2dController.setup();
        
        // 初始化PPT幻灯片序列
        this.initPptSlides();

        const serverUrl = "localhost:8000"
        const agentName = "shumeiniang"
        const client = new FrontendAgent(serverUrl, agentName);
        client.connect();

        this.wsClient = client;

        const streamAudioPlayer = new StreamAudioPlayer();
        this.streamAudioPlayer = streamAudioPlayer;

        live2dController.setLipSyncFunc(() => {
            return streamAudioPlayer.volume;
        });

        const eventQueue = [];
        client.on("message", (message) => {
            if (message.detail && message.detail.data) {
                const data = message.detail.data;
                if (data.type) {
                    const type = data.type;
                    
                    // 优先处理翻页事件，不经过事件队列 - 设置为最高优先级
                        if (type === "flip_ppt_page") {
                            // 立即处理翻页事件，不等待任何异步操作
                            console.time(`翻页到第${data.page_num}页耗时`);
                            
                            // 同步检查幻灯片是否已预加载
                            const targetPage = parseInt(data.page_num, 10);
                            if (targetPage >= 1 && targetPage <= this.totalSlides) {
                                if (this.pptSlides[targetPage - 1]) {
                                    // 如果已预加载，立即切换（同步操作）
                                    this.currentPptPage = targetPage;
                                    this.currentSlideUrl = this.pptSlides[targetPage - 1];
                                    console.log(`[翻页] 幻灯片 ${targetPage} 已预加载，立即切换`);
                                    console.timeEnd(`翻页到第${data.page_num}页耗时`);
                                    
                                    // 在后台异步加载其他幻灯片，不阻塞翻页
                                    this.preloadAroundCurrentPage();
                                } else {
                                    // 如果未预加载，在后台加载，不阻塞翻页
                                    console.log(`[翻页] 幻灯片 ${targetPage} 未加载，开始后台加载...`);
                                    this.handleFlipPptPage(targetPage).then(() => {
                                        console.timeEnd(`翻页到第${data.page_num}页耗时`);
                                    });
                                    
                                    // 显示加载提示（可选）
                                    this.currentSlideUrl = null; // 或显示加载占位符
                                }
                            }
                            
                            return; // 翻页事件直接处理，不加入队列
                        }
                    
                    if (type === "say_aloud") {
                        if (!streamAudioPlayer.isStreaming) {
                            streamAudioPlayer.startStream()
                        }
                        const mediaData = data["media_data"];
                        // 立即更新字幕，不等待事件队列处理
                        if (subtitle) {
                            subtitle.addDelta(data.content);
                        }
                        // 添加音频数据并设置媒体ID
                        streamAudioPlayer.addWavData(mediaData)
                        .then(id => {
                            data["media_id"] = id;
                        });
                    } else if (type === "ppt_assets") {
                        this.applyPptAssets(data.urls);
                    }
                }
            }

            eventQueue.push(message);
        });

        const subtitle = this.$refs.subtitle;

        async function handleSayAloud(message) {
            // 移除重复的字幕更新，字幕已在WebSocket消息处理中即时更新

            // play audio 不等待播放完成，避免阻塞事件队列
            const mediaId = message["media_id"];
            if (mediaId) {
                // 异步播放音频，不阻塞事件处理
                streamAudioPlayer.waitUntilFinish(mediaId)
                .then(() => {
                    if (message.is_last && message.seq != null) {
                        self.wsClient.sendData({
                            type: "event",
                            data: {
                                type: "audio_playback_finished",
                                seq: message.seq,
                                media_id: mediaId,
                            },
                        });
                    }
                })
                .catch(error => console.error("Error playing audio:", error));
            }
        }

        async function handleBracketTag(message) {
            // TOOD
            live2dController.setExpression(message.content);
        }

        async function handleShowImage(message) {
            // 处理显示图片事件
            const imageUrl = message.content;
            self.showImage(imageUrl);
        }

        async function handleHideImage(message) {
            // 处理隐藏图片事件
            self.hideImage();
        }

        // 只声明一次in_response变量
        let in_response = false;

        // 使用setTimeout代替requestAnimationFrame，避免渲染帧阻塞
        async function processEventQueue() {
            try {
                if (eventQueue.length === 0) {
                    setTimeout(processEventQueue, 0);
                    return;
                }

                const event = eventQueue.shift();
                const message = event.detail.data;

                console.log("processing message from server:", message); // DEBUG

                if (!message.type) {
                    setTimeout(processEventQueue, 0);
                    return;
                }

                // 非阻塞处理各个事件类型
                if (message.type === "say_aloud") {
                    // 不等待语音播放完成，避免阻塞事件队列
                    handleSayAloud(message).catch(error => console.error("Error handling say_aloud:", error));
                } else if (message.type === "bracket_tag") {
                    handleBracketTag(message).catch(error => console.error("Error handling bracket_tag:", error));
                } else if (message.type === "start_of_response") {
                    // start of response
                    self.showSubtitle();
                    in_response = true;
                } else if (message.type === "end_of_response") {
                    // end of response
                    in_response = false;
                    console.log("end of response", message.response);
                    // 移除自动隐藏字幕的逻辑，保持字幕框一直显示
                    // setInterval(() => {
                    //     if (!in_response) {
                    //         self.hideSubtitle();
                    //     }
                    // }, 1000);
                } else if (message.type === "show_image") {
                    // 处理显示图片事件
                    handleShowImage(message).catch(error => console.error("Error handling show_image:", error));
                } else if (message.type === "hide_image") {
                    // 处理隐藏图片事件
                    handleHideImage(message).catch(error => console.error("Error handling hide_image:", error));
                }
            } catch (error) {
                console.error("Error processing event:", error);
            }
            // 使用setTimeout立即继续处理下一个事件，不等待渲染帧
            setTimeout(processEventQueue, 0);
        }
        processEventQueue();

        this.$refs.inputArea.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                // 清空事件队列
                while (eventQueue.length > 0) {
                    eventQueue.shift();
                }
                this.recordChat(this.inputText);
                this.inputText = "";
            }
        });

        window.addEventListener("keydown", (e) => {
            if (e.target && e.target.tagName === "INPUT") {
                return;
            }

            if (e.code === "Space") {
                e.preventDefault();
                this.toggleLecturePause();
            } else if (e.code === "ArrowRight") {
                this.sendLectureControl("next");
            } else if (e.code === "ArrowLeft") {
                this.sendLectureControl("prev");
            } else if (e.code === "KeyR") {
                this.sendLectureControl("replay");
            }
        });

        // subtitle scroll
        const subtitleInnerContainer = this.$refs.subtitleInnerContainer;

        const scrollToBottomLoop = () => {
            // loop scroll subtitleInnerContainer to bottom (in smooth behavior)
            const currentScrollTop = subtitleInnerContainer.scrollTop + subtitleInnerContainer.clientHeight;
            const targetScrollTop = subtitleInnerContainer.scrollHeight;
            if (currentScrollTop < targetScrollTop) {
                subtitleInnerContainer.scrollTo({
                    top: targetScrollTop,
                    behavior: "smooth",
                });
            }
            requestAnimationFrame(scrollToBottomLoop);
        }
        scrollToBottomLoop();
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

/* PPT容器样式 */
.ppt-container {
    position: fixed;
    top: 5vh;
    left: 11vw;
    width: 60vw;
    height: 60vh;
    background-color: white;
    border: 1px solid #ccc;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 5;
    overflow: hidden; 
}

/* PPT幻灯片样式 */
.ppt-slide {
    width: 100%;
    height: 100%;
    object-fit: contain;  
    overflow: hidden;  
}

.canvas-container {
    position: fixed;
    bottom: 0vh;
    right: 1vw;
    width: 30vw;
    height: 50vh;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    z-index: 10;
    overflow: hidden;
}

.main_canvas {
    position: relative;
    width: 100%;
    height: 100%; 
    bottom: 0; 
    object-fit: contain;
}

.canvas {
    position: absolute;
    margin: 0;
    padding: 0;
    display: block;
    width: 100%;
    height: 100%;
    opacity: 1;
    transform: translateX(0);
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


.subtitle-container {
    position: fixed;
    left: 10vw;
    bottom: 10vh;
    width: 60vw;
    min-height: 15vh;
    max-height: 20vh;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 15px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(10px);
    padding: 20px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    padding: 15px;
}

.subtitle-container-hidden {
    opacity: 0;
    transform: rotateY(20deg) rotateX(90deg) translate(0, 0);
    transition: opacity 0.5s ease, transform 0.5s ease;
    animation: subtitle-hide 0.5s ease-out;
}

.subtitle-inner-container {
    /* position: relative; */
    /* margin-left: 10%; */
    width: 100%;
    height: 100%;
    overflow-y: scroll;
}
.subtitle-inner-container::-webkit-scrollbar {
  display: none; /* 完全隐藏滚动条 */
}

.subtitle-text {
    font-size: 2em;
    font-weight: 500;
    user-select: none;
    color: rgb(0, 0, 0);
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
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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

.lecture-controls {
    margin-top: 20px;
    text-align: left;
}

.lecture-buttons button,
.lecture-goto button {
    margin-right: 10px;
}

.lecture-goto {
    margin-top: 10px;
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
    opacity: 0;
    /* 隐藏logo背景，因为我们现在有图片显示区域 */
}

/* 新增图片显示区域样式 */
.image-display-area {
    position: fixed;
    width: 80vw;
    height: 50vh;
    left: 10vw;
    top: 10vh;
    z-index: 10;
}

.image-container {
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: 10px;
    background-size: contain;
    background-position: center;
    background-repeat: no-repeat;
}
</style>