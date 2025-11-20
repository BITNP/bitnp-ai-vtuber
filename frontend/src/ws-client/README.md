# FrontendAgent 使用指南

## 概述

FrontendAgent 是一个基于 WebSocket 的前端代理类，用于与后端进行实时通信。它继承自 EventTarget，支持事件驱动的编程模式。

## 主要功能

1. **WebSocket 连接管理**：自动连接、重连机制
2. **事件监听**：支持监听服务端推送的各种事件类型
3. **数据发送**：向后端发送结构化数据
4. **错误处理**：完善的错误处理和状态管理

## 基本用法

### 1. 创建实例

```javascript
import FrontendAgent from './ws_client/FrontendAgent.js';

const agent = new FrontendAgent('ws://localhost:8080', 'MyAgent');
```

### 2. 连接到服务器

```javascript
agent.connect();
```

### 3. 监听事件

```javascript
// 监听连接状态变化
agent.addEventListener('connection', (event) => {
    console.log('Connection status:', event.detail.status);
});

// 监听所有消息
agent.addEventListener('message', (event) => {
    console.log('Received message:', event.detail);
});

// 监听特定类型的事件
agent.addEventListener('chat_response', (event) => {
    console.log('Chat response:', event.detail.payload);
});

// 使用便捷方法
agent.on('custom_event', (event) => {
    console.log('Custom event:', event.detail);
});
```

### 4. 发送数据

```javascript
// 方法1：使用 sendMessage
agent.sendMessage('user_input', {
    message: 'Hello, server!',
    timestamp: Date.now()
});

// 方法2：使用 sendData
agent.sendData({
    type: 'config_update',
    payload: { language: 'zh-CN' }
});
```

## API 参考

### 构造函数

```javascript
new FrontendAgent(serverUrl, agentName)
```

- `serverUrl`: WebSocket 服务器地址
- `agentName`: 代理名称

### 主要方法

#### `connect()`
连接到 WebSocket 服务器

#### `sendData(data)`
向后端发送数据
- `data`: 包含 `type` 字段的数据对象
- 返回: `boolean` - 发送是否成功

#### `sendMessage(type, payload)`
发送特定类型的消息
- `type`: 消息类型字符串
- `payload`: 消息内容
- 返回: `boolean` - 发送是否成功

#### `disconnect()`
断开连接并停止自动重连

#### `getConnectionState()`
获取当前连接状态
- 返回: `string` - 'connected', 'connecting', 'disconnected', 'closing', 'unknown'

#### `on(eventType, callback)`
添加事件监听器的便捷方法

#### `off(eventType, callback)`
移除事件监听器的便捷方法

### 事件类型

#### 内置事件

- `connection`: 连接状态变化
  - `detail.status`: 'connected' | 'disconnected'
  - `detail.code`: 关闭代码（仅断开时）
  - `detail.reason`: 关闭原因（仅断开时）

- `message`: 接收到任何消息
  - `detail`: 完整的消息对象

- `error`: 错误事件
  - `detail.error`: 错误描述
  - `detail.originalError`: 原始错误对象

#### 自定义事件

服务端可以发送任何包含 `data.type` 字段的消息，FrontendAgent 会自动触发对应类型的事件。

例如，服务端发送：
```json
{
    "data": {
        "type": "chat_response",
        "content": "Hello!",
        "timestamp": 1234567890
    }
}
```

前端可以监听：
```javascript
agent.addEventListener('chat_response', (event) => {
    console.log(event.detail.content); // "Hello!"
});
```

## 自动重连

FrontendAgent 内置自动重连机制：
- 最大重连次数：5次
- 重连间隔：3秒
- 连接成功后重置重连计数器

## 错误处理

所有错误都会触发 `error` 事件，包括：
- WebSocket 连接错误
- 消息解析错误
- 数据发送错误

## 使用示例

完整的使用示例请参考 `FrontendAgentExample.js` 文件。

## 注意事项

1. 确保后端发送的消息格式正确，包含 `data.type` 字段
2. 在组件销毁时调用 `disconnect()` 方法避免内存泄漏
3. 监听 `connection` 事件来处理连接状态变化
4. 使用 `getConnectionState()` 检查连接状态后再发送数据