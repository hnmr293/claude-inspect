console.log('connected', $SERVER_URL);

const url = $SERVER_URL;
const reconnectDelay = 1000; // 1s

function connectWebSocket() {
    delete window.__socket;
    delete window.__send;
    const socket = new WebSocket(url);
    socket.addEventListener('open', function(e) {
        console.log(`connected: ${url}`, e);
        window.__send?.((new TextEncoder()).encode('event: ping\ndata: {"type": "ping"}\n\n'));
    });
    socket.addEventListener('close', function(e) {
        console.log(`disconnected: ${url}`, e);
        console.log(`Attempting to reconnect in ${reconnectDelay/1000} seconds...`);
        setTimeout(connectWebSocket, reconnectDelay);
    });
    socket.addEventListener('error', function(event) {
        console.warn('websocket error', event);
    });
    socket.addEventListener('message', function(event) {
        console.debug(event);
        const obj = JSON.parse(event.data);
        const op = obj.op;
        const args = obj.args ?? [];
        //const ev = new CustomEvent('operation', {detail: {op, args}});
        //document.dispatchEvent(ev);
        window.__operations.push({op, args});
    });
    window.__socket = socket;
    window.__send = function(event) {
        if (window.__socket?.readyState === WebSocket.OPEN) {
            window.__socket.send(event);
        }
    };
}

if (window.__socket === void 0) {
    try {
        connectWebSocket();
    } catch (error) {
        console.error(error);
        delete window.__socket;
        delete window.__send;
    }
}

if (window.__fetch === void 0) {
    // hook SSE
    orig_fetch = window.fetch;
    window.fetch = async function(...args) {
        const response = await orig_fetch.apply(window, args);
        const contentType = response?.headers.get('Content-Type');
        if (contentType?.includes('text/event-stream') && response.body) {
            const orig_getReader = response.body.getReader;
            response.body.getReader = function (...args) {
                const reader = orig_getReader.apply(response.body, ...args);
                const orig_read = reader.read;
                reader.read = async function (...args) {
                    const read_result = await orig_read.apply(reader, args);
                    if (!read_result) {
                        return read_result;
                    }
                    const { done, value } = read_result;
                    if (!done && value !== undefined && value !== void 0) {
                        //console.log(value);
                        window.__send?.(value);
                    }
                    return read_result;
                };
                return reader;
            };
        }
        return response;
    };
}

if (window.__operations === void 0) {
    window.__operations = [];
    setTimeout(process, 10);
}

const operations = ($OPERATIONS);

async function process1() {
    if (window.__operations.length > 0) {
        const {op, args} = window.__operations[0];
        console.log('operation:', op, args);
        const func = operations[op];
        if (func) {
            try {
                await func(...args);
                return true;
            } catch (error) {
                console.log(error);
                return false;
            }
        }

        console.error('operation not found', op);
        return true;
    }
}

function process() {
    try {
        if (process1()) {
            window.__operations.shift();
        }
    } catch (e) {
        // delete all operations
        console.error(e);
        window.__operations.splice(0);
        if (window.__send) {
            const errMsg = 'event: error\ndata: {"type": "error", "error": {"type": "javascript_error", "message": ' + JSON.stringify(e.toString()) + '}}\n\n';
            const errObj = (new TextEncoder()).encode(errMsg);
            window.__send?.(errObj);
        }
        throw e;
    } finally {
        setTimeout(process, 10);
    }
}

console.log("ready!");