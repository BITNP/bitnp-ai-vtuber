<template>
  <div>
    <div
      :class="['mask', masked ? '' : 'display-none']"
      @click="handleMaskClick"
    >
      <div class="logos">
        <img src="@/../public/images/bitnp-logo.png" alt="BitnP Logo" />
        <img
          src="@/../public/images/shumeiniang-ciallo.png"
          alt="Ciallo～(∠・ω< )⌒★"
        />
      </div>
      <div style="font-size: 2rem; font-weight: bold; color: #f2a7b5">
        CLICK TO START
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
      />
    </div>

    <!-- <div class="danmuku-area" ref="danmukuArea"></div> -->
    <div class="user-interface" id="user-interface">
      <!-- UI区域 -->
      <button v-if="!audioEnabled" @click="enableAudioActivities">
        启用音频
      </button>
      <!-- <input
        ref="inputArea"
        type="text"
        v-model="inputText"
        placeholder="请输入..."
      />
      <!-- <button @click="switchMicrophoneMode">{{ (microphoneOn) ? '闭麦' : '开麦' }}</button> -->
    </div>

    <div class="logo-background"></div>

    <audio ref="audioPlayer" src="" hidden></audio>

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
        <Subtitle ref="subtitle" class="subtitle-text" />
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

export default {
  components: {
    Subtitle,
  },
  data() {
    return {
      masked: true, // 是否显示遮罩层, 初始为true，点击后变为false
      microphoneOn: false,
      debug: false,
      audioEnabled: false, // The user needs to interact with the page (by clicking the button) to enable audio

      imageSrc: "",
      inputText: "",
      subtitleHidden: true, // 是否隐藏字幕

      // PPT相关配置
      pptSlides: [], // 存储所有幻灯片图片URL
      currentSlideUrl: "", // 当前显示的幻灯片URL
      currentPptPage: 1, // 当前页码（从1开始）
      totalSlides: 43, // 幻灯片总数
      useRemotePptAssets: false,

      lectureControlPage: "",
      lecturePaused: false,

      showConfigUI: false,
      enableDictation: false,
      enableFullScreen: false,
      allowPauseDictation: true,

      // 性能优化配置
      maxEventQueueSize: 10000, // 事件队列最大值，防止无限增长
      activePreloadCount: 0, // 当前活跃的预加载数
      maxConcurrentPreloads: 3, // 最多同时预加载3张图片
      rafId: null, // 保存 RAF ID 以便清理
      keydownHandler: null, // 保存 keydown 事件处理器以便清理
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
      const baseUrl = "/documents/slides/幻灯片";
      const extension = ".PNG";
      this.baseUrl = baseUrl;
      this.imageExtension = extension;

      // 初始化数组
      this.pptSlides = new Array(this.totalSlides).fill(null);

      // 并发预加载前3页幻灯片，提高初始化速度
      await Promise.all([
        this.preloadSlide(1),
        this.preloadSlide(2),
        this.preloadSlide(3),
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

    // 后台预加载指定范围的幻灯片（带并发限制）
    preloadInBackground(startPage, endPage) {
      const preloadQueue = [];
      for (let i = startPage; i <= endPage; i++) {
        if (i > this.totalSlides) break;
        preloadQueue.push(i);
      }

      // 异步处理预加载队列，限制并发数
      const processQueue = () => {
        while (
          this.activePreloadCount < this.maxConcurrentPreloads &&
          preloadQueue.length > 0
        ) {
          const pageNum = preloadQueue.shift();
          this.activePreloadCount++;
          this.preloadSlide(pageNum)
            .catch((err) =>
              console.log(`[后台预加载] 幻灯片 ${pageNum} 加载失败: ${err}`),
            )
            .finally(() => {
              this.activePreloadCount--;
              if (preloadQueue.length > 0) {
                processQueue();
              }
            });
        }
      };
      processQueue();
    },

    // 加载图片的辅助方法（添加超时处理）
    loadImage(url, timeout = 10000) {
      // 10秒超时
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
        .catch((err) => {
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
        data: { type: "user_input", content: message },
      });
      console.log(`Add text: ${message}`);
    },

    showSubtitle() {
      const subtitle = this.$refs.subtitle;
      if (!subtitle) {
        console.warn("Subtitle ref is null, cannot show subtitle");
        return;
      }

      subtitle.clear();
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
      console.log(
        `[翻页] 当前页码: ${this.currentPptPage}, 目标页码: ${pageNum}`,
      );

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
              new Promise((_, reject) =>
                setTimeout(() => reject(new Error("加载超时")), 15000),
              ),
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
      this.currentSlideUrl = urls[0] || "";
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

    handleMaskClick(e) {
      this.enableAudioActivities();
      const circle = this.$refs.circleRef;
      if (!circle) {
        console.error("Mask circle ref is null");
        return;
      }

      // 添加扩展动画类
      console.log(circle);
      console.log(e);
      circle.setAttribute("cx", e.clientX);
      circle.setAttribute("cy", e.clientY);
      circle.classList.add("ripple-circle");

      // 动画结束后隐藏遮罩层
      circle.addEventListener(
        "animationend",
        () => {
          this.masked = false;
        },
        { once: true },
      );
    },
  },

  mounted() {
    const self = this;

    // shumeiniang Live2d controller
    const config = LIVE2D_CONFIG;
    config.canvas = this.$refs.mainCanvas;
    console.log(config);
    this.live2dController = new Live2dController(config);
    this.live2dController.setup();

    // 初始化PPT幻灯片序列
    this.initPptSlides();

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
                console.log(
                  `[翻页] 幻灯片 ${targetPage} 未加载，开始后台加载...`,
                );
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
              streamAudioPlayer.startStream();
            }
            const mediaData = data["media_data"];
            // 立即更新字幕，不等待事件队列处理
            if (subtitle) {
              subtitle.addDelta(data.content);
            }
            // 添加音频数据并设置媒体ID（记录 promise，避免事件队列先消费）
            data["media_id_promise"] = streamAudioPlayer
              .addWavData(mediaData)
              .then((id) => {
                data["media_id"] = id;
                return id;
              });
          } else if (type === "ppt_assets") {
            this.applyPptAssets(data.urls);
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
      }
    });

    const subtitle = this.$refs.subtitle;

    async function handleSayAloud(message) {
      // 移除重复的字幕更新，字幕已在WebSocket消息处理中即时更新

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

    async function handleBracketTag(message) {
      // TODO
      if (!message || typeof message.content !== "string") {
        return;
      }

      const content = message.content.trim();
      if (!content) {
        return;
      }

      if (!self.live2dController) {
        console.warn("Live2dController not ready, ignore bracket_tag");
        return;
      }

      self.live2dController.setExpression(content);
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

    // 处理事件队列（改进了递归和并发管理）
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
        } else if (message.type === "bracket_tag") {
          handleBracketTag(message).catch((error) =>
            console.error("Error handling bracket_tag:", error),
          );
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
          handleShowImage(message).catch((error) =>
            console.error("Error handling show_image:", error),
          );
        } else if (message.type === "hide_image") {
          // 处理隐藏图片事件
          handleHideImage(message).catch((error) =>
            console.error("Error handling hide_image:", error),
          );
        }
      } catch (error) {
        console.error("Error processing event:", error);
      }
      // 使用 setTimeout 避免无限递归堆积，给事件循环机会
      setTimeout(processEventQueue, 0);
    }
    processEventQueue();

    this.keydownHandler = (e) => {
      if (e.key === "Enter") {
        // 清空事件队列
        while (eventQueue.length > 0) {
          eventQueue.shift();
        }
        this.recordChat(this.inputText);
        this.inputText = "";
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

    console.log("[清理] BasicChattingApp 组件资源已清理");
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
  z-index: 1145141919810;

  justify-content: center;
  align-items: center;
  flex-direction: column;
  gap: 3rem;
  display: flex;

  cursor: pointer;
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
