import { Application, Ticker } from "pixi.js";
import { FocusController, Live2DModel, MotionPriority } from "pixi-live2d-display";
import transferParams, { shouldSkip } from "./Patch.js";

const MODEL_ANCHOR = {x: 0.5, y: 0.6}; // supposed to be the center of the model, change it if needed
// TODO: adjust live2d position if needed

// 表情实际驱动的模型参数子集。
const EXPR_DRIVEN_PARAMS = [
    "ParamEyeLOpen", "ParamEyeROpen", "ParamMouthForm",
    "ParamAngleY", "ParamAngleX", "ParamAngleZ",
    "ParamBrowLY", "ParamBrowRY",
    "ParamEyeBallX", "ParamEyeBallY",
];

// 待机动作包络
function smoothstep(x) { return x * x * (3 - 2 * x); }
function holdEnv(p) {                                         
    const r = 0.25;
    if (p < r) return smoothstep(p / r);
    if (p > 1 - r) return smoothstep((1 - p) / r);
    return 1;
}

// 待机偶发动作
// ax/ay/az 为头部角度偏移，ex/ey 为眼球偏移
const IDLE_GESTURES = [
    { name: 'lookLeft',  duration: 1600, offset: p => ({ ax:  6 * holdEnv(p), ex:  0.8 * holdEnv(p) }) },
    { name: 'lookRight', duration: 1600, offset: p => ({ ax: -6 * holdEnv(p), ex: -0.8 * holdEnv(p) }) },
    { name: 'lookUp',    duration: 1400, offset: p => ({ ay:  3 * holdEnv(p), ey:  0.6 * holdEnv(p) }) },
    { name: 'lookDown',  duration: 1400, offset: p => ({ ay: -3 * holdEnv(p), ey: -0.6 * holdEnv(p) }) },
    { name: 'tiltLeft',  duration: 1800, offset: p => ({ az:  5 * holdEnv(p) }) },
    { name: 'tiltRight', duration: 1800, offset: p => ({ az: -5 * holdEnv(p) }) },
    { name: 'nod',       duration: 1700, offset: p => ({ ay: 2.5 * Math.sin(p * Math.PI * 4) * holdEnv(p) }) },
];

function delay(ms) {
    return new Promise(resolve => {
        setTimeout(resolve, ms);
    });
}

/**
 * @typedef {Object} MotionConfig
 * @property {string} group - 动作所属的分组
 * @property {number} order - 动作的排序序号
 * @property {number} duration - 动作持续时间（毫秒）
 */

/**
 * @typedef {Object.<string, MotionConfig>} MotionDictionary
 * 动作名称到动作配置的映射字典
 */

/**
 * @typedef {Object} ExpressionConfig
 * @property {number} order - 表情的排序序号
 */

/**
 * @typedef {Object.<string, ExpressionConfig>} ExpressionDictionary
 * 表情名称到表情配置的映射字典
 */


/**
 * @typedef {Object} FaceParamExpressionConfig
 * @property {string} path - 表情文件(.faceexp.json)的地址
 * @property {number} duration - 表情持续时间
 */

/**
 * @typedef {Object.<string, FaceParamExpressionConfig>} FaceParamExpressionDictionary
 * 表情名称到表情配置的映射字典
 */

/**
 * Live2D 展示插件
 * 提供 launchMotion(motionName) 和 setExpression(expressionName) 两个方法
 */
export default class Live2dController {
    /**
     * @param {string} modelURL Live2D模型路径
     * @param {HTMLCanvasElement} canvas 画布元素
     * @param {MotionDictionary} motionDict 描述所有支持的动作名称，及其在 Live2D 所有动作中的顺序
     * @param {ExpressionDictionary} expressionDict 描述所有支持的表情名称，及其在 Live2D 所有表情中的顺序
     * 
     * @param {FaceParamExpressionDictionary} faceParamExpressionDict 描述所有支持的表情名称，及其在 Live2D 所有表情中的顺序
     */
    constructor({modelURL, canvas, motionDict, expressionDict, faceParamExpressionDict}) {
        const self = this;
        this.firstUpdate = true;
        this.dictParams = {};
        this.initParamDict = {};

        this.modelURL = modelURL;
        this.canvas = canvas;
        this.motionDict = motionDict;
        this.expressionDict = expressionDict;

        // 为此展示项目特化的。 "faceParamExpression" 指通过面捕表情录制脚本 (expression_recorder.py) 录制的表情
        this.faceParamExpressionDict = faceParamExpressionDict;

        this.faceParamExpressionLoopId = null;

        // 待机微动
        this._idlePhase = {
            angleX: Math.random() * Math.PI * 2,
            angleY: Math.random() * Math.PI * 2,
            angleZ: Math.random() * Math.PI * 2,
            bodyY: Math.random() * Math.PI * 2,
            eyeX: Math.random() * Math.PI * 2,
            eyeY: Math.random() * Math.PI * 2,
            browL: Math.random() * Math.PI * 2,
            browR: Math.random() * Math.PI * 2,
            mouth: Math.random() * Math.PI * 2,
        };

        // 眨眼
        this._blinkDuration = 420;                       
        this._blinkIntervalRange = [2500, 5000];         
        this._blinkStart = -1e9;                         
        this._nextBlinkAt = Date.now() + this._randBlinkInterval();

        // 偶发动作调度
        this._gesture = null;                            
        this._gestureIntervalRange = [4000, 9000];       
        this._nextGestureAt = Date.now() + this._randGestureInterval();

        /**
         * 口型同步函数
         * @returns {number} 口型同步值
         */
        this.lipSyncFunc = () => 0;

        const fps = 60;

        this.faceParamExpressionName = null;
        this.faceParamExpressionFrame = 0;

        // 表情淡入淡出状态。 'in' | 'out' | null
        this._exprFadeState = null;
        this._exprFadeStart = 0;
        this._exprFadeDuration = 150; 
        this._exprTotalFrames = 0;    
        this._resetConverged = false; 

        const faceParamExpressionReset = () => {
            // 复位
            // self.dictParams = self.initParamDict;
            const threshold = 0.01;
            let canStop = true;
            for (let paramName in self.initParamDict) {
                if (shouldSkip(paramName)) continue;
                const initVal = self.initParamDict[paramName];
                const curVal = self.dictParams[paramName];
                if (isNaN(curVal)) continue;

                if (Math.abs(curVal - initVal) > threshold) {
                    canStop = false;
                }

                const k = 0.05
                const value = curVal * (1 - k) + initVal * k;
                self.dictParams[paramName] = value;
            }

            if (canStop) {
                // self.faceParamExpressionName = null;
                self._resetConverged = true;
            }
        };

        // 初始化状态
        this.faceParamExpressionLoopId = setInterval(() => {
            const time = Date.now();

            // 确保呼吸参数始终应用
            const breathCycle = 3000;
            const breath = 0.5 + 0.6 * Math.sin(time / breathCycle * (2 * Math.PI));
            self.dictParams["ParamBreath"] = breath;

            const exprName = self.faceParamExpressionName;
            const fadeState = self._exprFadeState;
            const exprActive = exprName !== null || fadeState !== null;

            // 仅在完全空闲时（无表情、无淡入淡出）运行 idle 状态机，
            if (!exprActive) {
                this.executeIdle(time);
                this.executeBlinkSchedule(time);

                if (!self._resetConverged) {
                    faceParamExpressionReset();
                }
                return;
            }

            // 表情播放/淡入淡出
            const entry = self.faceParamExpressionDict[exprName];
            if (!entry) {
                // 名字失效但状态未清，直接归位
                self._exprFadeState = null;
                self._resetConverged = false;
                return;
            }
            const expFps = entry.data.fps;
            const data = entry.data.data;
            const totalFrames = self._exprTotalFrames || data.length;

            const frameIndex = Math.round(self.faceParamExpressionFrame * expFps / fps);

            // 播放到末尾且未在淡出 → 开始淡出
            if (self._exprFadeState === null && frameIndex >= totalFrames) {
                self._exprFadeState = 'out';
                self._exprFadeStart = time;
            }

            // 计算淡入淡出 alpha
            let alpha = 1;
            if (self._exprFadeState === 'in') {
                const t = Math.min((time - self._exprFadeStart) / self._exprFadeDuration, 1);
                alpha = t * t * (3 - 2 * t); // smoothstep
                if (t >= 1) self._exprFadeState = null;
            } else if (self._exprFadeState === 'out') {
                const t = Math.min((time - self._exprFadeStart) / self._exprFadeDuration, 1);
                alpha = 1 - t * t * (3 - 2 * t);
                if (t >= 1) {
                    // 淡出完成
                    self.faceParamExpressionName = null;
                    self._exprFadeState = null;
                    self._resetConverged = false;
                    return;
                }
            }

            // 应用当前帧
            const fi = Math.min(frameIndex, totalFrames - 1);
            if (fi >= 0 && fi < data.length) {
                const frame = data[fi];
                self.dictParams = transferParams(frame, self.dictParams);
                // 把表情驱动参数向初始值方向混合
                if (alpha < 1) {
                    for (const paramName of EXPR_DRIVEN_PARAMS) {
                        const initVal = self.initParamDict[paramName];
                        const curVal = self.dictParams[paramName];
                        if (initVal === undefined || curVal === undefined || isNaN(curVal)) continue;
                        self.dictParams[paramName] = initVal + (curVal - initVal) * alpha;
                    }
                }
            }

            // 确保呼吸参数始终应用
            self.dictParams["ParamBreath"] = breath;
            self.faceParamExpressionFrame += 1;
        }, 1000 / fps);
    }

    /**
     * 设置口型同步函数
     * @param {function} func 口型同步函数，返回值为口型同步值
     */
    setLipSyncFunc(func) {
        this.lipSyncFunc = func;
    }

    // 待机微动：头部偏航/俯仰/翻滚 + 身体摇摆 + 视线漂移 + 眉/嘴微动
    executeIdle(time) {
        const k = 0.12; // 缓动系数
        const p = this._idlePhase;
        const TAU = 2 * Math.PI;

        // 基础漂移目标
        let ax = 4.0 * Math.sin(TAU * time / 7000 + p.angleX);  // 偏航
        let ay = 2.0 * Math.sin(TAU * time / 5500 + p.angleY);  // 俯仰(轻点头)
        let az = 2.5 * Math.sin(TAU * time / 9000 + p.angleZ);  // 翻滚(歪头)
        const by = 2.0 * Math.sin(TAU * time / 8000 + p.bodyY); // 身体摇摆
        let ex = 0.30 * Math.sin(TAU * time / 6000 + p.eyeX);   // 视线 X
        let ey = 0.25 * Math.sin(TAU * time / 4500 + p.eyeY);   // 视线 Y

        // 眉/嘴
        const browL0 = this.initParamDict["ParamBrowLY"] ?? 0;
        const browR0 = this.initParamDict["ParamBrowRY"] ?? 0;
        const mouth0 = this.initParamDict["ParamMouthForm"] ?? 0;
        const browL = browL0 + 0.10 * Math.sin(TAU * time / 6500 + p.browL);
        const browR = browR0 + 0.10 * Math.sin(TAU * time / 7100 + p.browR);
        const mouth = mouth0 + 0.12 * Math.sin(TAU * time / 7500 + p.mouth);

        // 偶发动作叠加（转头/抬头/歪头/点头），offset 自带淡入淡出
        const gest = this._gestureOffset(time);
        if (gest) {
            ax += gest.ax || 0;
            ay += gest.ay || 0;
            az += gest.az || 0;
            ex += gest.ex || 0;
            ey += gest.ey || 0;
        }

        this._easeTo("ParamAngleX", ax, k);
        this._easeTo("ParamAngleY", ay, k);
        this._easeTo("ParamAngleZ", az, k);
        this._easeTo("ParamBodyAngleY", by, k);
        this._easeTo("ParamEyeBallX", ex, k);
        this._easeTo("ParamEyeBallY", ey, k);
        this._easeTo("ParamBrowLY", browL, k);
        this._easeTo("ParamBrowRY", browR, k);
        this._easeTo("ParamMouthForm", mouth, k);
    }

    // 偶发动作：到点触发一个随机动作，返回当前进度下的偏移量（或 null）
    _gestureOffset(time) {
        if (!this._gesture && time >= this._nextGestureAt) {
            const preset = IDLE_GESTURES[Math.floor(Math.random() * IDLE_GESTURES.length)];
            this._gesture = { preset, t0: time };
        }
        if (!this._gesture) return null;

        const preset = this._gesture.preset;
        const progress = (time - this._gesture.t0) / preset.duration;
        if (progress >= 1) {
            this._gesture = null;
            this._nextGestureAt = time + this._randGestureInterval();
            return null;
        }
        return preset.offset(progress);
    }

    _randGestureInterval() {
        const [lo, hi] = this._gestureIntervalRange;
        return lo + Math.random() * (hi - lo);
    }

    // 眨眼调度
    executeBlinkSchedule(time) {
        if (this._blinkStart < 0 && time >= this._nextBlinkAt) {
            this._blinkStart = time;
        }
        if (this._blinkStart >= 0) {
            const progress = Math.min((time - this._blinkStart) / this._blinkDuration, 1);
            const eyeOpen = 1 - Math.sin(progress * Math.PI);
            this.dictParams["ParamEyeLOpen"] = eyeOpen;
            this.dictParams["ParamEyeROpen"] = eyeOpen;
            if (progress >= 1) {
                this._blinkStart = -1e9;
                this._nextBlinkAt = time + this._randBlinkInterval();
            }
        }
    }

    _easeTo(paramName, target, k) {
        const cur = this.dictParams[paramName];
        if (cur === undefined || isNaN(cur)) {
            this.dictParams[paramName] = target;
            return;
        }
        this.dictParams[paramName] = cur * (1 - k) + target * k;
    }

    _randBlinkInterval() {
        const [lo, hi] = this._blinkIntervalRange;
        return lo + Math.random() * (hi - lo);
    }

    async setup() {
        const self = this;

        // if (!agent.actionQueue) {
        //     throw new Error('ActionQueue not found! L2dDisplay plugin is based on ActionQueue. Load ActionQueue in advance!')
        // }

        // Live2D Model and PIXI App Setup
        Live2DModel.registerTicker(Ticker);
        const app = new Application({
            resizeTo: this.canvas,
            view: this.canvas
        });
        // app.view.setAttribute("id", "main-canvas");
        // document.body.appendChild(app.view);
        app.renderer.backgroundAlpha = 0;

        console.log({app})
        console.log(this.modelURL)
        const model = await Live2DModel.from(this.modelURL);
        console.log({model})

        this.model = model;
        this.dictParams = {};

        model.initHeight = model.height;
        model.initWidth = model.width;

        app.stage.addChild(model); // add model to stage

        console.log("L2dDisplay", this); // DEBUG

        // lip sync
        // 口型同步
        function lipSyncLoop() {
            try {
                let value = Number(self.lipSyncFunc());
                try {
                    // Cubism 2: coreModel.setParamFloat
                    model.internalModel.coreModel.setParamFloat("PARAM_MOUTH_OPEN_Y", value);
                } catch(e) {
                    // model.internalModel.coreModel.setParameterValueById('ParamMouthUp', 1);
                    model.internalModel.coreModel.setParameterValueById('ParamA', value, 1.0);
                    model.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', value);
                }
            } catch (e) {
                console.error("Error in lipSyncLoop:", e);
            }
            // requestAnimationFrame(lipSyncLoop); // ?
        }
        // lipSyncLoop();

        const updateModelPosition = () => {
            model.anchor.set(MODEL_ANCHOR.x, MODEL_ANCHOR.y);
            const baseScale = app.view.height / model.initHeight * 2;

            // let modelScale = dictParams.modelScale;
            // if (!modelScale) {
            //     modelScale = 1;
            // }

            let modelScale = 1;
            let dictParams = self.dictParams;

            const scale = modelScale * baseScale;
            model.scale.set(scale, scale);

            // 模型平移
            let translateY = dictParams.modelTranslateY;
            if (!translateY) {
                translateY = 0;
            }
            model.x = app.view.width / 2;
            model.y = app.view.height * (0.5 + translateY);

            // 模型旋转
            let rotation = dictParams.modelRotation;
            if (!rotation) {
                rotation = 0;
            }
            model.rotation = rotation;
        };

        updateModelPosition();

        function handleModelUpdate(model, dictParams) {
            if (self.firstUpdate) {
                // 在首次调用时，获取模型初始化参数，用于重置模型状态
                self.initParamDict = {};
                for (let i in model.internalModel.coreModel._parameterIds) {
                    const name = model.internalModel.coreModel._parameterIds[i];
                    const value = model.internalModel.coreModel._parameterValues[i];
                    self.initParamDict[name] = value;
                }
                self.dictParams = {...self.initParamDict};
                self.firstUpdate = false;
            }

            const isIdle = (!self.faceParamExpressionName);
            if (isIdle) {
                // 在 idle 状态下抑制兔耳抖动
                self.dictParams["Param2"] = 0;
                self.dictParams["Param3"] = 0;
            }

            lipSyncLoop(); // ?
            updateModelPosition();

            // 处理模型更新
            const coreModel = model.internalModel.coreModel;
            for (let paramName in dictParams) {
                if (shouldSkip(paramName)) continue;
                if (!isNaN(dictParams[paramName])) {
                    coreModel.setParameterValueById(paramName, dictParams[paramName]);
                }
            }
        }

        // 覆盖focus函数
        model.internalModel.focusController.old_update = model.internalModel.focusController.update;
        model.internalModel.focusController.update = function (...args) {
            let angleX = self.dictParams["ParamAngleX"];
            if (isNaN(angleX)) {
                angleX = 0;
            }
            let angleY = self.dictParams["ParamAngleY"];
            if (isNaN(angleY)) {
                angleY = 0;
            }

            model.internalModel.focusController.focus(angleX / 30, angleY / 30);
            model.internalModel.focusController.old_update(...args);
        }

        // 覆盖模型的update函数，以实现自定义参数更新
        model.internalModel.coreModel.old_update = model.internalModel.coreModel.update;
        model.internalModel.coreModel.update = function (...args) {
            handleModelUpdate(model, self.dictParams);
            model.internalModel.coreModel.old_update(...args);
        }

        // 响应窗口尺寸变化
        window.addEventListener('resize', () => {
            updateModelPosition();
        });
    }


    /**
     * 开始 Live2D 动作
     * @param {string} motionName 动作名称
     */
    launchMotion(motionName) {
        if (motionName in this.motionDict) {
            // this.model.motion('tap', this.motionDict[motionName].order, MotionPriority.FORCE);
            this.model.motion(this.motionDict[motionName].group, this.motionDict[motionName].order, MotionPriority.FORCE);
        }
    }

    /**
     * 设置 Live2D 表情
     * @param {string} expressionName 表情名称
     */
    setExpression(expressionName) {
        if (expressionName in this.expressionDict) {
            this.model.expression(this.expressionDict[expressionName].order);
        } else if (expressionName in this.faceParamExpressionDict) {
            // support face param expressions
            this.launchFaceParamExpression(expressionName);
        }
    }

    /**
     * 设置面捕参数序列表情 (以便于动作编辑)
     * @param {string} name 表情名称
     */
    launchFaceParamExpression(name) {
        if (!(name in this.faceParamExpressionDict)) return;

        const self = this;
        // clearInterval(this.faceParamExpressionLoopId);
        
        const fps = this.faceParamExpressionDict[name].data.fps;
        const data = this.faceParamExpressionDict[name].data.data; // sequence of face params
        const duration = this.faceParamExpressionDict[name].duration;

        this.faceParamExpressionName = name;
        this.faceParamExpressionFrame = 0;

        // let i = 0;
        // this.faceParamExpressionLoopId = setInterval(() => {
        //     if (i >= data.length) {
        //         clearInterval(self.faceParamExpressionLoopId);
        //         return;
        //     }
        //     const frame = data[i];
        //     self.dictParams = transferParams(frame, self.dictParams);
        //     i += 1;
        // }, 1000 / fps);

        // this.killerTimeoutId = setTimeout(() => {
        //     // clearInterval(self.faceParamExpressionLoopId);
        //     
        //     // reset model state
        // }, duration);
    }
}
