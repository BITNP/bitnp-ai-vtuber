import { Application, Ticker } from "pixi.js";
import { FocusController, Live2DModel, MotionPriority } from "pixi-live2d-display";
import transferParams, { shouldSkip } from "./Patch.js";

const MODEL_ANCHOR = {x: 0.5, y: 0.6}; // supposed to be the center of the model, change it if needed
// TODO: adjust live2d position if needed

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

        // 马尔可夫链状态管理
        this.idleState = 'idle'; // 初始状态改为idle，与stateDurations匹配
        this.stateStartTime = 0;
        this.stateDuration = 0;
        
        // 状态转移矩阵 [from][to] = probability
        this.transitionMatrix = {
            'headShake': { 'headShake': 0.3, 'blink': 0.7 },
            'blink': { 'headShake': 0.3, 'blink': 0.1, 'idle': 0.6 },
            'idle': { 'headShake': 0.1, 'blink': 0.4, 'idle': 0.5 } // 添加idle状态的转移规则
        };
        
        // 各状态持续时间范围 (毫秒)
        this.stateDurations = {
            'headShake': [3000, 6000],
            'blink': [400, 600],
            'idle': [1000, 3000]
        };

        /**
         * 口型同步函数
         * @returns {number} 口型同步值
         */
        this.lipSyncFunc = () => 0;

        const fps = 60;

        this.faceParamExpressionName = null;
        this.faceParamExpressionFrame = 0;

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
            }
        };

        // 初始化状态
        this.startNewState();

        this.faceParamExpressionLoopId = setInterval(() => {
            const time = Date.now();
            
            // 确保呼吸参数始终应用
            const breathCycle = 3000;
            const breath = 0.5 + 0.6 * Math.sin(time / breathCycle * (2 * Math.PI));
            self.dictParams["ParamBreath"] = breath;
            
            // 检查是否需要状态转移
            if (time - this.stateStartTime > this.stateDuration) {
                this.transitionState();
            }
            
            // 执行当前状态的动作
            this.executeCurrentState(time);

            if (!self.faceParamExpressionName) {
                faceParamExpressionReset();
                return;
            }
            const data = self.faceParamExpressionDict[self.faceParamExpressionName].data.data;
            const expFps = self.faceParamExpressionDict[self.faceParamExpressionName].data.fps;

            const frameIndex = Math.round(self.faceParamExpressionFrame * expFps / fps);
            if (frameIndex >= data.length) {
                // faceParamExpressionReset();
                self.faceParamExpressionName = null;
                return;
            }
            const frame = data[frameIndex];
            self.dictParams = transferParams(frame, self.dictParams);
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

    // 开始新状态
    startNewState() {
        this.stateStartTime = Date.now();
        const [minDur, maxDur] = this.stateDurations[this.idleState];
        this.stateDuration = minDur + Math.random() * (maxDur - minDur);
    }

    // 状态转移
    transitionState() {
        const currentState = this.idleState;
        const transitions = this.transitionMatrix[currentState];
        
        // 根据转移概率选择下一个状态
        let random = Math.random();
        let cumulativeProb = 0;
        
        for (const [state, prob] of Object.entries(transitions)) {
            cumulativeProb += prob;
            if (random < cumulativeProb) {
                this.idleState = state;
                this.startNewState();
                break;
            }
        }
    }

    // 执行当前状态的动作
    executeCurrentState(time) {
        const k = 0.2;
        
        switch (this.idleState) {
            case 'headShake':
                this.executeHeadShake(time, k);
                break;
            case 'blink':
                this.executeBlink(time, k);
                break;
            case 'idle':
                // 空闲状态，保持自然姿态
                break;
        }
    }

    // 执行摇头动作
    executeHeadShake(time, k) {
        const idleCycle = 3000;
        const angleX = Math.sin(time / idleCycle * (2 * Math.PI)) * 5;
        const angleZ = Math.cos(time / idleCycle * (2 * Math.PI)) * 3;
        const threshold = 0.1;
        
        if (Math.abs(this.dictParams["ParamAngleX"] - angleX) > threshold) {
            this.dictParams["ParamAngleX"] = this.dictParams["ParamAngleX"] * (1 - k) + angleX * k;
        }
        if (Math.abs(this.dictParams["ParamAngleZ"] - angleZ) > threshold) {
            this.dictParams["ParamAngleZ"] = this.dictParams["ParamAngleZ"] * (1 - k) + angleZ * k;
        }
    }

    // 执行眨眼动作
    executeBlink(time, k) {
        const elapsed = time - this.stateStartTime;
        const progress = Math.min(elapsed / this.stateDuration, 1);
        
        // 使用正弦函数创建平滑的眨眼曲线
        const eyeOpen = Math.cos(progress * Math.PI);
        
        this.dictParams["ParamEyeLOpen"] = this.dictParams["ParamEyeLOpen"] * (1 - k) + eyeOpen * k;
        this.dictParams["ParamEyeROpen"] = this.dictParams["ParamEyeROpen"] * (1 - k) + eyeOpen * k;
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
