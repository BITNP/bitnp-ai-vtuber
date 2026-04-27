<template>

  <!-- 启用音频按钮 -->
  <div v-if="!audioEnabled" class="audio-button-container" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 99999;">
    <button @click="enableAudioActivities" style="font-size: 2rem; padding: 20px 40px; background-color: rgba(255,255,255,0.8); border: none; border-radius: 10px; cursor: pointer; font-weight: bold;">
      启用音频
    </button>
  </div>

  <div>
    <div
      :class="['mask', masked ? '' : 'display-none']"
    >
      <video
        src="@/../public/images/pre-background.mp4"
        width="1280"
        height="720"
        style="width: 100vw; height: 100vh; object-fit: cover;"
        autoplay
        loop
        muted
      >
      </video>
      
      <!-- 倒计时显示 -->
      <div class="countdown" style="position: absolute; top: 50px; left: 100px; font-size: 3rem; font-weight: bold; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); text-align: left;">
        <span style="font-size: 4rem;">{{ liveTitle }}</span>
        <br>
        距离直播开始还有 {{ countdownMinutes.toString().padStart(2, '0') }}:{{ countdownSeconds.toString().padStart(2, '0') }}
      </div>
      
      <!-- 直播主题 -->
      <div class="live-title" style="position: absolute; bottom: 40px; right: 40px; font-size: 3rem; font-weight: bold; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); text-align: right;">
        {{ organizer }}
      </div>
      
      <svg class="animation-mask">
        <mask id="ripple-mask">
          <rect width="100%" height="100%" fill="white" />
          <circle id="mask-circle" ref="circleRef" cx="0" cy="0" r="0" />
        </mask>
      </svg>
    </div>

    <div class="background-image"></div>

    <!-- PPT展示区域 -->
    <div class="ppt-container">
      <img
        v-if="currentSlideUrl"
        :src="currentSlideUrl"
        :alt="`幻灯片 ${currentPptPage}`"
        class="ppt-slide"
        @load="handlePptLoaded"
      />
    </div>

    <!-- 互动区域 -->
    <div v-if="isInteraction" class="interaction-container">
      <div class="interaction-header">
        <h2>{{ interactionTitle }}</h2>
        <div class="interaction-timer">{{ interactionTimeLeft }}秒</div>
      </div>
      <div class="interaction-input">
        <input
          ref="inputArea"
          type="text"
          v-model="inputText"
          placeholder="请输入你的问题..."
          @keyup.enter="sendUserInput"
        />
        <button @click="sendUserInput">发送</button>
      </div>
    </div>

    <!-- <div class="user-interface" id="user-interface">
      <button v-if="!audioEnabled" @click="enableAudioActivities">
        启用音频
      </button>
    </div> -->

    <div class="logo-background"></div>

    <audio ref="audioPlayer" src="" hidden> </audio>

    <div
      ref="configUI"
      :class="showConfigUI ? 'config-ui' : 'config-ui config-ui-hidden'"
    >
      <!--  -->
      <h1 class="config-title">设置菜单</h1>
      <span>按“=”键随时唤出此菜单</span>
      <br />
      <br />

      <label>
        <input type="checkbox" v-model="enableDictation" />
        启用听写 </label
      ><br />

      <label>
        <input type="checkbox" v-model="enableFullScreen" />
        全屏模式 </label
      ><br />

      <label>
        <input type="checkbox" v-model="allowPauseDictation" />
        在 AI 说话时禁用语音识别 </label
      ><br />

      <div class="lecture-controls">
        <h2>讲稿控制</h2>
        <div class="lecture-buttons">
          <button @click="toggleLecturePause">
            {{ lecturePaused ? "继续" : "暂停" }}
          </button>
          <button @click="sendLectureControl('prev')">上一页</button>
          <button @click="sendLectureControl('next')">下一页</button>
          <button @click="sendLectureControl('replay')">重播当前页</button>
        </div>
        <div class="lecture-goto">
          <input
            type="number"
            v-model="lectureControlPage"
            placeholder="页码"
            min="1"
          />
          <button @click="gotoLecturePage">跳转</button>
        </div>
      </div>
    </div>

    <div
      ref="subtitleContainer"
      :class="[
        'subtitle-container',
        { 'subtitle-container-hidden': subtitleHidden },
      ]"
    >
      <div><!-- placeholder --></div>
      <div ref="subtitleInnerContainer" class="subtitle-inner-container">
        <Subtitle ref="subtitle" class="subtitle-text" :dynamic="true" />
      </div>
    </div>

    <div class="canvas-container">
      <canvas ref="mainCanvas" id="mainCanvas" class="main_canvas"></canvas>
    </div>

    <div v-if="debug" class="visualize-area">
      <!-- 数据可视化区域 -->
      <div v-if="actionQueueWatcher" class="action-queue">
        <div
          v-for="(action, i) in actionQueueWatcher"
          :key="i"
          class="action-container"
        >
          <span>
            动作类型: {{ action.type }} <br />
            内容: {{ action.data }}
          </span>
        </div>
      </div>

      <div v-if="resourcesWatcher" class="resource-bank">
        <!-- {{ resourceManager.resourceBank }} <br> -->
        <div
          v-for="(resource, i) in resourcesWatcher"
          :key="i"
          class="resource-container"
        >
          <!-- {{ resourceManager.get(id) }} -->
          <span>
            资源类型: {{ resource.type }} <br />
            是否就绪: {{ resource.ready }} <br />
            内容: {{ resource.data }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Live2dController from "@/live2d-controller/Live2dController";
import LIVE2D_CONFIG from "@/agent-presets/shumeiniang/live2dConfig.js";
import FrontendAgent from "@/ws-client/FrontendAgent";
import Subtitle from "@/components/Subtitle.vue";
import StreamAudioPlayer from "@/components/StreamAudioPlayer.js";

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

export default {
  components: {
    Subtitle,
  },
  data() {
    return {
      masked: true, // 是否显示遮罩层, 初始为true，倒计时结束后变为false
      microphoneOn: false,
      debug: false,
      audioEnabled: false, // The user needs to interact with the page (by clicking the button) to enable audio
      currentSubtitle: "", // 当前显示的字幕文本

      imageSrc: "",
      inputText: "",
      subtitleHidden: false, // 是否隐藏字幕

      // 倒计时相关
      countdownTarget: null, // 倒计时目标时间
      countdownMinutes: 0, // 剩余分钟
      countdownSeconds: 0, // 剩余秒数
      countdownTimer: null, // 倒计时定时器

      // 直播主题
      liveTitle: "“智绘反诈”AIGC大赛线上培训会",

      // 组织者
      organizer: "网络开拓者协会技术部",

      // PPT相关配置
      currentSlideUrl: "", // 当前显示的幻灯片URL
      currentPptPage: 1, // 当前页码（从1开始）

      lectureControlPage: "",
      lecturePaused: false,

      showConfigUI: false,
      enableDictation: false,
      enableFullScreen: false,
      allowPauseDictation: true,

      // 互动相关配置
      isInteraction: false,
      interactionTitle: "互动时间",
      interactionDuration: 0,
      interactionTimeLeft: 0,
      interactionTarget: null,
      interactionTimer: null,

      // 字幕更新相关
      subtitleUpdatePromise: null, // 保存字幕更新的Promise
      subtitleUpdateAbort: false, // 控制字幕更新是否被取消

      // 性能优化配置
      maxEventQueueSize: 1000, // 事件队列最大值，防止无限增长
      rafId: null, // 保存 RAF ID 以便清理
      keydownHandler: null, // 保存 keydown 事件处理器以便清理
      messageHandler: null, // 保存 WebSocket 消息处理器以便清理
    };
  },

  watch: {
    enableFullScreen(newVal) {
      if (newVal) {
        this.enterFullscreen();
      } else {
        this.exitFullscreen();
      }
    },
  },

  methods: {
    enterFullscreen() {
      const element = document.documentElement; // 整个页面全屏
      const requestMethod = element.requestFullscreen || element.webkitRequestFullscreen || element.mozRequestFullScreen || element.msRequestFullscreen;

      if (requestMethod) {
        requestMethod.call(element).catch((err) => {
          console.error("全屏失败:", err);
          this.enableFullScreen = false; // 失败时重置状态
        });
      }
    },

    exitFullscreen() {
      const exitMethod = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;

      if (exitMethod) {
        exitMethod.call(document);
      }
    },

    enableAudioActivities() {
      // 初始化音频播放器，确保符合浏览器的自动播放政策
      console.log('尝试启用音频');
      return new Promise((resolve, reject) => {
        this.streamAudioPlayer.init().then((success) => {
          if (success) {
            this.audioEnabled = true;
            console.log('音频已启用');
            resolve(true);
          } else {
            console.error('音频初始化失败');
            resolve(false);
          }
        }).catch((error) => {
          console.error('音频启用失败:', error);
          reject(error);
        });
      });
    },

    // 初始化倒计时
    initCountdown() {
      // DEBUG: 设置目标时间为当前时间后2分钟
      this.countdownTarget = new Date();
      this.countdownTarget.setSeconds(this.countdownTarget.getSeconds() + 120);
      
      // 开始倒计时
      this.updateCountdown();
      this.countdownTimer = setInterval(() => {
        this.updateCountdown();
      }, 500);
    },

    // 更新倒计时
    updateCountdown() {
      const now = new Date();
      const diff = Math.max(0, this.countdownTarget - now);
      
      this.countdownMinutes = Math.floor(diff / 60000);
      this.countdownSeconds = Math.floor((diff % 60000) / 1000);
      
      // 倒计时结束
      if (diff === 0) {
        this.endCountdown();
      }
    },

    // 结束倒计时并开始直播
    async endCountdown() {
      clearInterval(this.countdownTimer);
      this.countdownTimer = null;
      
      // // 尝试启用音频
      // if (!this.audioEnabled) {
      //   try {
      //     await this.enableAudioActivities();
      //   } catch (error) {
      //     console.error('音频初始化失败，将继续无音频播放:', error);
      //   }
      // }
      
      // 隐藏遮罩层
      this.masked = false;
      
      // 发送开始播放信号给后端
      if (this.wsClient) {
        this.wsClient.sendData({
          type: "event",
          data: { type: "start_playback" },
        });
      }
    },

    async sendUserInput() {
      if (this.inputText.trim() === "") return;

      this.currentSubtitle = "";
      
      this.wsClient.sendData({
        type: "event",
        data: { type: "user_input", content: this.inputText },
      });
      console.log(`Add text: ${this.inputText}`);
      this.inputText = "";
    },

    showSubtitle() {
      const subtitle = this.$refs.subtitle;
      if (!subtitle) {
        console.warn("Subtitle ref is null, cannot show subtitle");
        return;
      }

      // subtitle.clear();
      this.subtitleHidden = false;

      setTimeout(() => {
        if (subtitle) {
          subtitle.enable = true;
        }
      }, 1000);
    },

    hideSubtitle() {
      const subtitle = this.$refs.subtitle;
      this.subtitleHidden = true;
    },

    // 处理PPT加载完成
    handlePptLoaded() {
      console.log(`PPT page ${this.currentPptPage} loaded`);
      // 发送PPT播放完成信号给后端
      this.wsClient.sendData({
        type: "event",
        data: { type: "ppt_playback_finished" },
      });
      this.currentSubtitle = "";
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



    // 开始互动倒计时
    startInteractionTimer(duration) {
      this.interactionDuration = duration;
      this.interactionTarget = new Date();
      this.interactionTarget.setSeconds(this.interactionTarget.getSeconds() + duration);
      
      if (this.interactionTimer) {
        clearInterval(this.interactionTimer);
      }
      
      this.updateInteractionCountdown();
      this.interactionTimer = setInterval(() => {
        this.updateInteractionCountdown();
      }, 500);
    },

    // 更新互动倒计时
    updateInteractionCountdown() {
      const now = new Date();
      const diff = Math.max(0, this.interactionTarget - now);
      
      this.interactionTimeLeft = Math.ceil(diff / 1000);
      
      // 倒计时结束
      if (diff === 0) {
        clearInterval(this.interactionTimer);
        this.endInteraction();
      }
    },

    // 结束互动
    endInteraction() {
      this.isInteraction = false;
      if (this.interactionTimer) {
        clearInterval(this.interactionTimer);
        this.interactionTimer = null;
      }
      // 发送互动结束信号给后端
      this.wsClient.sendData({
        type: "event",
        data: { type: "interaction_finished" },
      });
    },
    
    // 根据时间戳显示字幕
    startTimestampSubtitle(text, timestamps, mediaId) {
      console.log("DEBUG text:", text);
      const subtitle = this.$refs.subtitle;
      if (!subtitle) {
        console.warn("Subtitle ref is null, cannot show subtitle");
        return;
      }
      
      // 清空字幕
      // subtitle.clear();
      this.subtitleHidden = false;
      
      // 取消之前可能正在运行的字幕更新
      if (this.subtitleUpdatePromise) {
        this.subtitleUpdateAbort = true;
      }
      this.subtitleUpdateAbort = false;
      
      // 按时间顺序处理时间戳
      const sortedTimestamps = [...timestamps].sort((a, b) => a.begin_index - b.begin_index);
      
      // 为每个单词设置定时器
      console.log("DEBUG set promise", text, sortedTimestamps);
      const self = this;
      this.subtitleUpdatePromise = (async () => {
        let lastTime = 0;
        let lastIndex = -1;
        
        for (const timestamp of sortedTimestamps) {
          if (this.subtitleUpdateAbort) {
            break;
          }
          
          if (timestamp.begin_index <= lastIndex) {
            continue;
          }

          lastIndex = timestamp.begin_index;

          const delayTime = timestamp.begin_time - lastTime;

          lastTime = timestamp.begin_time;
          await delay(delayTime);
          
          if (this.subtitleUpdateAbort) {
            break;
          }
          
          self.currentSubtitle += timestamp.text;
          console.log("DEBUG subtitle setSubtitle:", self.currentSubtitle);
          subtitle.setSubtitle(self.currentSubtitle);
        }
      })();
      
      // // 确保字幕在音频结束后保持显示
      // const streamAudioPlayer = this.streamAudioPlayer;
      // if (streamAudioPlayer && mediaId > 0) {
      //   streamAudioPlayer.waitUntilFinish(mediaId).then(() => {
      //     // 音频播放完成，保持最终字幕
      //     subtitle.setSubtitle(text);
      //   });
      // }
    },
  },

  mounted() {
    const self = this;

    // 初始化倒计时
    this.initCountdown();

    // shumeiniang Live2d controller
    const config = LIVE2D_CONFIG;
    config.canvas = this.$refs.mainCanvas;
    console.log(config);
    this.live2dController = new Live2dController(config);
    this.live2dController.setup();

    const serverUrl = "localhost:8000";
    const agentName = "shumeiniang";
    const client = new FrontendAgent(serverUrl, agentName);
    client.connect();

    this.wsClient = client;

    const streamAudioPlayer = new StreamAudioPlayer();
    this.streamAudioPlayer = streamAudioPlayer;

    this.live2dController.setLipSyncFunc(() => {
      return streamAudioPlayer.volume;
    });

    const eventQueue = [];
    this.messageHandler = (message) => {
      if (message.detail && message.detail.data) {
        const data = message.detail.data;
        if (data.type) {
          const type = data.type;

          // 处理PPT显示事件
          if (type === "show_ppt") {
            const pageNum = data.page_num;
            const mediaData = data.media_data;
            const format = data.format;
            
            // 构建data URL
            const imageUrl = `data:image/${format};base64,${mediaData}`;
            this.currentPptPage = pageNum;
            // 清理旧的PPT图片URL，释放内存
            this.currentSlideUrl = null;
            // 强制垃圾回收
            if (window.gc) {
              window.gc();
            }
            // 设置新的PPT图片URL
            this.currentSlideUrl = imageUrl;
            console.log(`[PPT] 显示幻灯片 ${pageNum}`);
            return;
          }

          // 处理字幕事件
          if (type === "subtitle") {
            // const subtitle = this.$refs.subtitle;
            // if (subtitle) {
            //   subtitle.setSubtitle(data.content);
            // }
          }

          // 处理语音事件
          if (type === "say_aloud") {
            console.log("处理语音事件:", data);
            if (!streamAudioPlayer) {
              console.error('StreamAudioPlayer not initialized');
              // 发送音频播放完成信号，继续处理下一个命令
              this.wsClient.sendData({
                type: "event",
                data: {
                  type: "audio_playback_finished",
                  seq: data.seq,
                  media_id: -1,
                },
              });
              return;
            }
            
            if (!streamAudioPlayer.isStreaming) {
              try {
                streamAudioPlayer.startStream();
              } catch (error) {
                console.error('Failed to start stream:', error);
                // 发送音频播放完成信号，继续处理下一个命令
                this.wsClient.sendData({
                  type: "event",
                  data: {
                    type: "audio_playback_finished",
                    seq: data.seq,
                    media_id: -1,
                  },
                });
                return;
              }
            }
            
            const mediaData = data["media_data"];
            // 添加音频数据
            if (mediaData) {
              console.log('添加音频数据，大小:', mediaData.length);
              data["media_id_promise"] = streamAudioPlayer
                .addWavData(mediaData)
                .then((id) => {
                  console.log('音频数据添加成功，ID:', id);
                  if (id === -1) {
                    console.warn('Failed to add audio data, skipping playback');
                    // 发送音频播放完成信号，继续处理下一个命令
                    this.wsClient.sendData({
                      type: "event",
                      data: {
                        type: "audio_playback_finished",
                        seq: data.seq,
                        media_id: id,
                      },
                    });
                    return null;
                  }
                  data["media_id"] = id;
                  // 清理音频数据，释放内存
                  data["media_data"] = null;
                  // 强制垃圾回收（如果支持）
                  if (typeof window.gc === 'function') {
                    window.gc();
                  }
                  
                  // 如果有时间戳信息，启动字幕逐字显示
                  if (data.timestamps && data.timestamps.length > 0) {
                    this.startTimestampSubtitle(data.content, data.timestamps, id);
                  } else {
                    // 没有时间戳，直接显示完整字幕
                    const subtitle = this.$refs.subtitle;
                    if (subtitle && data.content) {
                      this.currentSubtitle += data.content;
                      subtitle.setSubtitle(this.currentSubtitle);
                    }
                  }
                  
                  return id;
                })
                .catch((error) => {
                  console.error('Error adding audio data:', error);
                  // 发送音频播放完成信号，继续处理下一个命令
                  this.wsClient.sendData({
                    type: "event",
                    data: {
                      type: "audio_playback_finished",
                      seq: data.seq,
                      media_id: -1,
                    },
                  });
                  return null;
                });
            } else {
              console.log('没有音频数据，直接发送播放完成信号');
              // 没有音频数据，直接发送播放完成信号
              this.wsClient.sendData({
                type: "event",
                data: {
                  type: "audio_playback_finished",
                  seq: data.seq,
                  media_id: -1,
                },
              });
            }
          }

          // 处理互动开始事件
          if (type === "interaction_start") {
            this.isInteraction = true;
            this.interactionTitle = "互动时间";
            this.startInteractionTimer(data.duration);
            console.log(`[互动] 开始互动，持续 ${data.duration} 秒`);
            return;
          }

          // 处理错误事件
          if (type === "error") {
            console.error(`[错误] ${data.message}`);
            return;
          }
        }
      }

      // 限制事件队列大小，防止无限增长
      if (eventQueue.length < this.maxEventQueueSize) {
        eventQueue.push(message);
      } else {
        console.warn(
          `[警告] 事件队列已满 (${this.maxEventQueueSize})，丢弃新消息`,
        );
        // 清空队列，避免内存占用过高
        eventQueue.length = 0;
      }
    };
    client.on("message", this.messageHandler);

    const subtitle = this.$refs.subtitle;

    async function handleSayAloud(message) {
      // play audio 不等待播放完成，避免阻塞事件队列
      let mediaId = message["media_id"];
      if (!mediaId && message["media_id_promise"]) {
        try {
          mediaId = await message["media_id_promise"];
        } catch (error) {
          console.error("Error resolving media_id:", error);
        }
      }
      if (mediaId && mediaId > 0) {
        // 异步播放音频，不阻塞事件处理
        streamAudioPlayer
          .waitUntilFinish(mediaId)
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
          .catch((error) => console.error("Error playing audio:", error));
      }
    }

    // 只声明一次in_response变量
    let in_response = false;

    // 处理事件队列
    async function processEventQueue() {
      try {
        if (eventQueue.length === 0) {
          // 使用 setTimeout 代替立即递归，给事件循环喘息机会
          setTimeout(processEventQueue, 10);
          return;
        }

        const event = eventQueue.shift();
        const message = event?.detail?.data;

        console.log("processing message from server:", message); // DEBUG

        if (!message || !message.type) {
          setTimeout(processEventQueue, 0);
          return;
        }

        // 非阻塞处理各个事件类型
        if (message.type === "say_aloud") {
          // 不等待语音播放完成，避免阻塞事件队列
          handleSayAloud(message).catch((error) =>
            console.error("Error handling say_aloud:", error),
          );
        } else if (message.type === "start_of_response") {
          // start of response
          self.showSubtitle();
          in_response = true;
        } else if (message.type === "end_of_response") {
          // end of response
          in_response = false;
          console.log("end of response", message.response);
        }
      } catch (error) {
        console.error("Error processing event:", error);
      }
      // 使用 setTimeout 避免无限递归堆积，给事件循环机会
      setTimeout(processEventQueue, 0);
    }
    processEventQueue();

    this.keydownHandler = (e) => {
      if (e.key === "Enter" && this.isInteraction) {
        this.sendUserInput();
      }

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
    };
    window.addEventListener("keydown", this.keydownHandler);

    // subtitle scroll
    const subtitleInnerContainer = this.$refs.subtitleInnerContainer;

    const scrollToBottomLoop = () => {
      // 自动滚动字幕容器到底部
      if (subtitleInnerContainer) {
        const currentScrollTop =
          subtitleInnerContainer.scrollTop + subtitleInnerContainer.clientHeight;
        const targetScrollTop = subtitleInnerContainer.scrollHeight;
        
        // 如果内容超过容器高度，自动滚动到底部
        if (currentScrollTop < targetScrollTop) {
          subtitleInnerContainer.scrollTo({
            top: targetScrollTop,
            behavior: "smooth",
          });
        }
      }
      this.rafId = requestAnimationFrame(scrollToBottomLoop);
    };
    this.rafId = requestAnimationFrame(scrollToBottomLoop);
  },

  beforeUnmount() {
    // 清理 RAF 回调
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
    }

    // 清理 window 事件监听器
    if (this.keydownHandler) {
      window.removeEventListener("keydown", this.keydownHandler);
    }

    // 清理 WebSocket 消息处理器
    if (this.wsClient && this.messageHandler) {
      // 移除消息监听器
      this.wsClient.off("message", this.messageHandler);
    }

    // 关闭 WebSocket 连接
    if (this.wsClient && this.wsClient.close) {
      this.wsClient.close();
    }

    // 停止音频播放器
    if (this.streamAudioPlayer && this.streamAudioPlayer.destroy) {
      this.streamAudioPlayer.destroy();
    }

    // 销毁 Live2dController
    if (this.live2dController && this.live2dController.destroy) {
      this.live2dController.destroy();
    }

    // 清理互动计时器
    if (this.interactionTimer) {
      clearInterval(this.interactionTimer);
    }

    // 清理倒计时计时器
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
    }

    // 清理 PPT 图片URL，释放内存
    this.currentSlideUrl = null;

    // 强制垃圾回收
    if (window.gc) {
      window.gc();
    }

    console.log("[清理] OnlineTeacher 组件资源已清理");
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
  position: absolute;
  top: 5vh;
  left: 3vw;
  width: 80vw;
  /* height: 60vh; */
  aspect-ratio: 16 / 9;
  background-color: black;
  /* border: 1px solid #ccc; */
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

/* 互动区域样式 */
.interaction-container {
  position: absolute;
  top: 1vh;
  right: 1vw;
  width: 30vw;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 15px;
  z-index: 25;
}

.interaction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.interaction-header h2 {
  margin: 0;
  font-size: 1.2em;
  color: #333;
}

.interaction-timer {
  font-size: 1.2em;
  font-weight: bold;
  color: #e74c3c;
}

.interaction-input {
  display: flex;
  gap: 10px;
}

.interaction-input input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 1em;
}

.interaction-input button {
  padding: 10px 20px;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 5px;
  font-size: 1em;
}

.interaction-input button:hover {
  background-color: #2980b9;
}

.canvas-container {
  position: absolute;
  bottom: 0;
  right: 0;
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

.user-interface > * {
  border-radius: 10px;
  margin: 10px;
  font-family: Avenir, Helvetica, Arial, sans-serif;
  font-size: 2em;
}

.user-interface > input {
  width: 80%;
  max-width: 800px;
}

.subtitle-container {
  position: absolute;
  left: 8vw;
  bottom: 4vh;
  width: calc(100vw - 16.5vw - 25vw);
  min-height: 7.5vh;
  max-height: 7.5vh;
  background: rgba(255, 255, 255, 0.663);
  border-radius: 1.5vh;
  box-shadow: 0 0.8vh 3.2vh rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(5px);
  padding: 2vh;
  z-index: 20;
  display: flex;
  flex-direction: column;
  padding: 1.5vh;
}

.subtitle-container-hidden {
  opacity: 0;
  transform: rotateY(20deg) rotateX(90deg) translate(0, 0);
  transition:
    opacity 0.5s ease,
    transform 0.5s ease;
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
  background: linear-gradient(#F9E8E7 60%, #EEEEF1);
  background-position: center;
  background-repeat: no-repeat;
  background-size: cover;
  z-index: -1;
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
  transition:
    opacity 0.5s ease,
    transform 0.5s ease;
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

.mask {
  background-color: #f2dfe2;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 999;

  justify-content: center;
  align-items: center;
  flex-direction: column;
  gap: 3rem;
  display: flex;

  mask-image: url(#ripple-mask);
  mask-mode: luminance;
}
.mask .logos {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20px;
}

.logos img {
  height: 20rem;
}

.mask .animation-mask {
  display: relative;
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
}

@keyframes ripple-expand {
  0% {
    r: 0%;
  }
  100% {
    r: 150%;
  }
}

.ripple-circle {
  animation: ripple-expand 1s ease-in-out forwards;
}

.display-none {
  display: none !important;
}

#mask-circle {
  fill: #000000;
}
</style>