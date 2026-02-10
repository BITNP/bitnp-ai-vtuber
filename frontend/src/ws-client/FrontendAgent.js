export default class FrontendAgent extends EventTarget {
    constructor(serverUrl, agentName) {
        super();

        // 确保 serverUrl 是合法的 WebSocket 地址
        if (!/^wss?:\/\//i.test(serverUrl)) {
            // 如果不是以 ws:// 或 wss:// 开头，自动补充协议
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            serverUrl = protocol + serverUrl.replace(/^\/+/, '').replace(/\/+$/, '');
        }

        this.serverUrl = serverUrl;
        this.agentName = agentName;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 3000;
    }

    connect() {
        try {
            this.ws = new WebSocket(`${this.serverUrl}/ws/frontend/${this.agentName}`); // 连接到指定的 agent
            
            this.ws.onopen = () => {
                console.log('WebSocket connection opened');
                this.reconnectAttempts = 0;
                this.dispatchEvent(new CustomEvent('connection', { 
                    detail: { status: 'connected' } 
                }));
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);

                    console.log(message);
                    
                    if (message.data && typeof message.data === 'object' && message.data.type) {
                        // 触发特定事件类型
                        this.dispatchEvent(new CustomEvent(message.data.type, { 
                            detail: message.data 
                        }));
                        
                        // 同时触发通用消息事件
                        this.dispatchEvent(new CustomEvent('message', { 
                            detail: message 
                        }));
                    } else {
                        // 处理没有特定类型的消息
                        this.dispatchEvent(new CustomEvent('message', { 
                            detail: message 
                        }));
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                    this.dispatchEvent(new CustomEvent('error', { 
                        detail: { error: 'Failed to parse message', originalData: event.data } 
                    }));
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket connection closed:', event.code, event.reason);
                this.dispatchEvent(new CustomEvent('connection', { 
                    detail: { status: 'disconnected', code: event.code, reason: event.reason } 
                }));
                
                // 自动重连逻辑
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                    setTimeout(() => this.connect(), this.reconnectInterval);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.dispatchEvent(new CustomEvent('error', { 
                    detail: { error: 'WebSocket connection error', originalError: error } 
                }));
            };

        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.dispatchEvent(new CustomEvent('error', { 
                detail: { error: 'Failed to create connection', originalError: error } 
            }));
        }
    }

    /**
     * 向后端发送数据
     * @param {Object} data - 要发送的数据对象
     * @param {string} data.type - 消息类型
    * @param {*} data.data - 消息内容
     */
    sendData(data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected');
            this.dispatchEvent(new CustomEvent('error', { 
                detail: { error: 'WebSocket is not connected' } 
            }));
            return false;
        }

        try {
            const message = {
                agentName: this.agentName,
                timestamp: Date.now(),
                ...data
            };
            
            this.ws.send(JSON.stringify(message));
            console.log('Data sent successfully:', message);
            return true;
        } catch (error) {
            console.error('Error sending data:', error);
            this.dispatchEvent(new CustomEvent('error', { 
                detail: { error: 'Failed to send data', originalError: error } 
            }));
            return false;
        }
    }

    /**
     * 发送特定类型的消息
     * @param {string} type - 消息类型
     * @param {*} payload - 消息内容
     */
    sendMessage(type, payload) {
        return this.sendData({ type, payload });
    }

    /**
     * 断开连接
     */
    disconnect() {
        if (this.ws) {
            this.reconnectAttempts = this.maxReconnectAttempts; // 停止自动重连
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * 获取连接状态
     * @returns {string} 连接状态
     */
    getConnectionState() {
        if (!this.ws) return 'disconnected';
        
        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }

    /**
     * 添加事件监听器的便捷方法
     * @param {string} eventType - 事件类型
     * @param {Function} callback - 回调函数
     */
    on(eventType, callback) {
        this.addEventListener(eventType, callback);
    }

    /**
     * 移除事件监听器的便捷方法
     * @param {string} eventType - 事件类型
     * @param {Function} callback - 回调函数
     */
    off(eventType, callback) {
        this.removeEventListener(eventType, callback);
    }
}