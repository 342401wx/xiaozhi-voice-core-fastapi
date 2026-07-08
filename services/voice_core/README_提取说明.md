# 小乐语音核心服务

这个目录是小乐语音助手使用的核心问答链路，按服务职责整理为 `services/voice_core`，用于承载 ASR、LLM、TTS、意图识别、工具调用和 FastAPI 接口。

如果你要部署和运行 FastAPI 服务，请优先阅读 `README.md`。

## 核心链路

语音问答主流程：

```text
WebSocket 连接 -> hello/listen 控制消息 -> Opus 音频流 -> VAD -> ASR -> Intent/Tools -> LLM -> TTS -> Opus 音频回传
```

关键入口：

- `app.py`：服务启动入口。
- `core/websocket_server.py`：WebSocket 服务入口，负责创建每个连接的 `ConnectionHandler`。
- `core/connection.py`：最核心的连接状态机，维护会话、音频队列、ASR、TTS、LLM、工具调用和对话历史。
- `core/handle/receiveAudioHandle.py`：音频接收、VAD 判断、进入 ASR/聊天流程。
- `core/handle/textHandler/listenMessageHandler.py`：处理 `listen start/stop/detect` 控制消息。
- `core/handle/sendAudioHandle.py`：TTS 状态消息和 Opus 音频包回传。

## 核心模块

- `core/providers/asr`：ASR 适配器，包括 FunASR、本地/云端 ASR 等。
- `core/providers/tts`：TTS 适配器，包括 EdgeTTS、火山、阿里云、腾讯等。
- `core/providers/vad`：VAD 语音活动检测。
- `core/providers/llm`：大模型适配器，DeepSeek/ChatGLM 这类 OpenAI 兼容接口走 `openai/openai.py`。
- `core/providers/intent`：意图识别逻辑。
- `core/providers/memory`：记忆模块。
- `core/providers/tools` 和 `plugins_func`：函数调用、MCP、设备工具等支撑逻辑。
- `config/assets`：绑定码、提示音等流程需要的音频资源。

## 没有复制的内容

- 没有复制 `.conda`、`__pycache__`、日志、运行缓存。
- 没有复制 `data/.config.yaml`，因为里面包含你本地填过的真实 API key。
- 没有复制 ASR 大模型文件，例如 `models/SenseVoiceSmall/model.pt`。

## 配置说明

这里保留的是模板 `config.yaml`，不是你当前正在运行的私有配置。真实运行时要按需填：

- `selected_module.ASR`
- `selected_module.LLM`
- `selected_module.TTS`
- `ASR.FunASR.model_dir`
- `LLM.DeepSeekLLM.api_key`
- `TTS.EdgeTTS.voice`

当前服务目录不包含本地私有模型和密钥。如果要让语音输入完整运行，还需要补模型文件、依赖环境和私有配置。

## FastAPI /ask 接口

已新增 `fastapi_app.py`，用于把提取后的 ASR、LLM、TTS 能力封装成 HTTP 服务。

规范接口文档和 Postman 示例：

- `docs/API接口文档.md`
- `postman/Xiaozhi_Voice_Core_API.postman_collection.json`
- `postman/Xiaozhi_Voice_Core_API.postman_environment.json`

启动方式：

```bash
pip install -r requirements-fastapi.txt
pip install openai edge_tts
uvicorn fastapi_app:app --host 0.0.0.0 --port 8010
```

如果要使用语音输入，还需要安装原项目 ASR 依赖，并准备本地模型：

```bash
pip install pydub funasr modelscope
```

配置方式：

1. 复制 `.env.example` 为 `.env`。
2. 在 `.env` 里填 `XIAOZHI_LLM_API_KEY`，DeepSeek 默认配置如下：
   - `XIAOZHI_LLM_BASE_URL=https://api.deepseek.com`
   - `XIAOZHI_LLM_MODEL=deepseek-chat`
3. 如果要本地语音识别，把 FunASR 模型放到 `models/SenseVoiceSmall`，或用 `XIAOZHI_ASR_MODEL_DIR` 指向模型目录。

服务也会自动读取 `D:\桌面\zuoye\pbl作业\.env`，兼容你现有的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL_NAME` 变量；如果当前目录也有 `.env`，当前目录配置优先。

接口：

- `GET /health`：检查配置和依赖状态。
- `POST /ask`：文本/语音问答，返回回答文本和可播放的语音地址。
- `GET /audio/{filename}`：读取 `/ask` 生成的语音文件。

JSON 文本请求示例：

```bash
curl -X POST http://127.0.0.1:8010/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"你好，介绍一下你自己\",\"return_audio\":true}"
```

Multipart 语音请求示例：

```bash
curl -X POST http://127.0.0.1:8010/ask ^
  -F "audio=@sample.wav" ^
  -F "text=请简短回答" ^
  -F "return_audio=true"
```

返回格式：

```json
{
  "session_id": "...",
  "input_text": "...",
  "answer_text": "...",
  "audio_url": "/audio/ask-xxx.mp3",
  "audio_content_type": "audio/mpeg",
  "audio_base64": null,
  "errors": []
}
```

说明：服务启动不强制初始化 ASR/LLM/TTS，避免模型或依赖缺失时整个 API 起不来；真正调用 `/ask` 时会按需加载对应模块，并在缺少 key、依赖或模型时返回明确错误。
