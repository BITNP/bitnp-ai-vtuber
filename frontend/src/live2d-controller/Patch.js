const EXCEPTION_PARAMS = ["ParamMouthOpenY", "Param2", "Param3"];

export function shouldSkip(paramName) {
    return EXCEPTION_PARAMS.includes(paramName);
}

class ParamTransfer {
    /**
     * 用于将面捕参数迁移为模型参数
     * @param {string} faceParamName 面捕参数名
     * @param {string} modelParamName 模型参数名
     * @param {number} scale 缩放系数
     * @param {number} bias 偏置
     * @param {number} modelDefault 模型默认值
     */
    constructor(faceParamName, modelParamName, scale = 1, bias = 0, modelDefault = 0, active_function = undefined) {
        this.faceParamName = faceParamName;
        this.modelParamName = modelParamName;
        this.scale = scale;
        this.bias = bias;
        this.modelDefault = modelDefault;

        if (active_function == undefined) {
            active_function = x => x;
        }
        this.active_function = active_function;
    }

    transfer(faceParamValue) {
        return this.active_function(faceParamValue * this.scale + this.bias);
    }
}

const PARAM_TRANSFER_MAP = [
    // 眨眼
    new ParamTransfer("eyeBlinkLeft", "ParamEyeLOpen", -2, 1, 1),
    new ParamTransfer("eyeBlinkRight", "ParamEyeROpen", -2, 1, 1),

    // 张嘴
    new ParamTransfer("jawOpen", "ParamMouthOpenY", 2, 0, 0),
    // 口型
    new ParamTransfer("mouthWidth", "ParamMouthForm", 1 / 0.11, -3.45, 0),

    // 头部运动
    new ParamTransfer("rotatePitch", "ParamAngleY", 2, 0, 0),
    new ParamTransfer("rotateYaw", "ParamAngleX", -1, 0, 0),
    new ParamTransfer("rotateRoll", "ParamAngleZ", 1, 0, 0),

    // 眉毛运动
    new ParamTransfer("browOuterUpLeft", "ParamBrowLY", 2, -1, 0),
    new ParamTransfer("browOuterUpRight", "ParamBrowRY", 2, -1, 0),

    // 眼球运动
    new ParamTransfer("eyesX", "ParamEyeBallX", 1.5, 0, 0),
    new ParamTransfer("eyesY", "ParamEyeBallY", 3, 0, 0),

    // 模型缩放
    // new ParamTransfer("faceSize", "modelScale", 2, 0, 1), // 效果不佳，因为脸的大小总会发生变化

    // 模型位移
    new ParamTransfer("rotatePitch", "modelTranslateY", -0.001, 0, 0),

    // 模型旋转
    new ParamTransfer("rotateRoll", "modelRotation", 0.003, 0, 0),

    // new ParamTransfer("rotatePitch", "ParamBodyAngleY", 1, 0, 0),
    // new ParamTransfer("rotateYaw", "ParamBodyAngleX", -1, 0, 0),
    // new ParamTransfer("rotateRoll", "ParamBodyAngleZ", 1, 0, 0),
]

export default function transferParams(faceParams, modelParams) {
    // 将面捕参数迁移为模型参数
    const data = faceParams;
    const dictParams = modelParams;

    for (let paramTransfer of PARAM_TRANSFER_MAP) {
        if (shouldSkip(paramTransfer.modelParamName)) continue; // 跳过部分参数

        if (data[paramTransfer.faceParamName] == undefined) {
            dictParams[paramTransfer.modelParamName] = paramTransfer.modelDefault;
        } else {
            // dictParams[paramTransfer.modelParamName] = paramTransfer.transfer(data[paramTransfer.faceParamName]);

            // 简单的参数平滑化
            let targetValue = paramTransfer.transfer(data[paramTransfer.faceParamName]);
            let originalValue = dictParams[paramTransfer.modelParamName];
            if (originalValue == undefined) {
                originalValue = paramTransfer.modelDefault;
            }
            const k = 0.2
            dictParams[paramTransfer.modelParamName] = targetValue * k + originalValue * (1 - k);
        }
    }

    return dictParams;
}