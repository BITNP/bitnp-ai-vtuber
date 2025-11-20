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

        const breathCycle = 3000;

        this.faceParamExpressionLoopId = setInterval(() => {
            const time = Date.now();
            // const breath = Math.sin(time / breathCycle * (Math.PI)) * Math.sin(time / breathCycle * (Math.PI)); // 计算呼吸参数
            const breath = 0.5 + 0.6 * Math.sin(time / breathCycle * (2 * Math.PI))
            self.dictParams["ParamBreath"] = breath;

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
            requestAnimationFrame(lipSyncLoop);
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

        let nextBlinkTime = -1;
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
                const time = Date.now();
                const idleCycle = 3000;
                const k = 0.2;

                // 头部运动
                const angleX = Math.sin(time / idleCycle * (2 * Math.PI)) * 5;
                const angleZ = Math.cos(time / idleCycle * (2 * Math.PI)) * 3;
                const threshold = 0.1;
                if (Math.abs(dictParams["ParamAngleX"] - angleX) > threshold) {
                    dictParams["ParamAngleX"] = dictParams["ParamAngleX"] * (1 - k) + angleX * k;
                }
                if (Math.abs(dictParams["ParamAngleZ"] - angleZ) > threshold) {
                    dictParams["ParamAngleZ"] = dictParams["ParamAngleZ"] * (1 - k) + angleZ * k;
                }

                // 在 idle 状态下抑制兔耳抖动
                const ear = 0;
                dictParams["Param2"] = 0;
                dictParams["Param3"] = 0;
                // if (Math.abs(dictParams["Param2"] - ear) > 0) {
                //     // dictParams["Param2"] = dictParams["Param2"] * (1 - k) + ear * k;
                //     dictParams["Param2"] = 0;
                // }
                // if (Math.abs(dictParams["Param3"] - ear) > 0) {
                //     dictParams["Param3"] = 0;
                //     // dictParams["Param3"] = dictParams["Param3"] * (1 - k) + ear * k;
                // }

                // 眨眼
                const blinkLength = 400;
                if (time - nextBlinkTime > blinkLength) {
                    nextBlinkTime = time + 3000 + (Math.random() * 4000); // 眨眼间隔 3-7 秒
                } else {
                    const dt = time - nextBlinkTime;
                    let eyeOpen = 1;
                    if (dt > 0) {
                        eyeOpen = 1 - 1.3 * Math.sin(dt / blinkLength * Math.PI);
                    }

                    dictParams["ParamEyeLOpen"] = dictParams["ParamEyeLOpen"] * (1 - k) + eyeOpen * k;
                    dictParams["ParamEyeROpen"] = dictParams["ParamEyeROpen"] * (1 - k) + eyeOpen * k;
                }
            }


            lipSyncLoop();
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
            
        //     // reset model state
        // }, duration);
    }
}
