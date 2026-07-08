# 小乐语音核心 FastAPI 接口文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 服务名称 | Xiaole Voice Core API |
| 服务入口 | `fastapi_app.py` |
| 默认地址 | `http://127.0.0.1:8010` |
| 接口版本 | `0.1.0` |
| 认证方式 | 当前无认证 |
| 数据格式 | JSON、multipart/form-data、二进制音频文件 |

## 2. 启动方式

在项目目录执行：

```powershell
cd D:\桌面\zuoye\pbl作业\小智ESP32提取\voice-core
python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8010
```

依赖安装：

```powershell
python -m pip install -r requirements-fastapi.txt
```

文本问答和语音合成需要：

- `openai`
- `edge_tts`
- 可用的 OpenAI 兼容大模型 API Key，例如 DeepSeek

语音识别还需要：

- `funasr`
- `modelscope`
- 本地 ASR 模型目录，例如 `models/SenseVoiceSmall`
- `ffmpeg`，用于解码 `mp3`、`m4a`、`webm` 等音频格式

## 3. 环境变量

服务会依次读取以下 `.env` 文件：

1. `D:\桌面\zuoye\pbl作业\.env`
2. `D:\桌面\zuoye\pbl作业\小智ESP32提取\.env`
3. `D:\桌面\zuoye\pbl作业\小智ESP32提取\voice-core\.env`

推荐变量：

| 变量名 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `XIAOZHI_LLM_API_KEY` | 是 | 大模型 API Key | `sk-...` |
| `XIAOZHI_LLM_BASE_URL` | 否 | OpenAI 兼容接口地址 | `https://api.deepseek.com` |
| `XIAOZHI_LLM_MODEL` | 否 | 模型名称 | `deepseek-chat` |
| `XIAOZHI_TTS_VOICE` | 否 | EdgeTTS 音色 | `zh-CN-XiaoxiaoNeural` |
| `XIAOZHI_ASR_MODEL_DIR` | 语音输入时必填 | FunASR 模型目录 | `models/SenseVoiceSmall` |

兼容变量：

| 变量名 | 映射到 |
| --- | --- |
| `OPENAI_API_KEY` | `XIAOZHI_LLM_API_KEY` |
| `OPENAI_BASE_URL` | `XIAOZHI_LLM_BASE_URL` |
| `MODEL_NAME` | `XIAOZHI_LLM_MODEL` |

## 4. 通用约定

### 4.1 请求头

JSON 请求：

```http
Content-Type: application/json; charset=utf-8
```

文件上传请求：

```http
Content-Type: multipart/form-data
```

### 4.2 通用错误格式

FastAPI 默认错误返回：

```json
{
  "detail": "错误说明"
}
```

### 4.3 常见状态码

| 状态码 | 含义 | 常见原因 |
| --- | --- | --- |
| `200` | 请求成功 | 正常返回 |
| `400` | 请求参数或音频识别错误 | 未传文本/音频、音频无法解码、ASR 模型缺失 |
| `404` | 资源不存在 | 语音文件名不存在 |
| `500` | 服务内部错误 | LLM Key 缺失、大模型接口失败、TTS 失败 |

## 5. 健康检查

### 5.1 基本信息

| 项目 | 内容 |
| --- | --- |
| URL | `/health` |
| Method | `GET` |
| Content-Type | 无 |
| 用途 | 检查配置、依赖、ASR 模型和 TTS 音色状态 |

### 5.2 请求示例

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8010/health" -Method Get
```

### 5.3 成功响应示例

```json
{
  "ok": true,
  "config_error": null,
  "selected_module": {
    "ASR": "FunASR",
    "LLM": "DeepSeekLLM",
    "TTS": "EdgeTTS"
  },
  "dependencies": {
    "fastapi": true,
    "uvicorn": true,
    "pydub": true,
    "openai": true,
    "edge_tts": true,
    "funasr": false
  },
  "details": {
    "llm_api_key_configured": true,
    "asr_model_dir": "D:\\桌面\\zuoye\\pbl作业\\小智ESP32提取\\voice-core\\models\\SenseVoiceSmall",
    "asr_model_dir_exists": false,
    "tts_voice": "zh-CN-XiaoxiaoNeural"
  }
}
```

### 5.4 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | boolean | 配置是否能正常加载 |
| `config_error` | string/null | 配置加载错误 |
| `selected_module` | object | 当前选中的 ASR、LLM、TTS 等模块 |
| `dependencies` | object | 运行依赖是否已安装 |
| `details.llm_api_key_configured` | boolean | 是否已配置大模型 Key |
| `details.asr_model_dir` | string/null | 当前 ASR 模型目录 |
| `details.asr_model_dir_exists` | boolean | ASR 模型目录是否存在 |
| `details.tts_voice` | string/null | 当前 TTS 音色 |

## 6. 语音问答接口

### 6.1 基本信息

| 项目 | 内容 |
| --- | --- |
| URL | `/ask` |
| Method | `POST` |
| Content-Type | `application/json` 或 `multipart/form-data` |
| 用途 | 支持文本输入、语音输入，返回回答文本和语音 |

### 6.2 JSON 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 否 | 空 | 用户文本输入 |
| `audio_base64` | string | 否 | 空 | Base64 音频，可带 `data:audio/wav;base64,` 前缀 |
| `audio_filename` | string | 否 | `audio.wav` | Base64 音频对应文件名，用于判断格式 |
| `audio_content_type` | string | 否 | 空 | Base64 音频 MIME 类型 |
| `return_audio` | boolean | 否 | `true` | 是否生成 TTS 语音 |
| `include_audio_base64` | boolean | 否 | `false` | 是否把生成语音也放入响应体 |
| `voice` | string | 否 | 配置音色 | 临时覆盖 EdgeTTS 音色 |
| `session_id` | string | 否 | 自动生成 | 会话 ID，仅保留字母、数字、下划线、中划线 |
| `history` | array | 否 | `[]` | 对话历史，最多取末尾 20 条 |

`history` 格式：

```json
[
  {"role": "user", "content": "你好"},
  {"role": "assistant", "content": "你好呀"}
]
```

### 6.3 JSON 文本请求示例

```json
{
  "text": "你好，用一句话介绍你自己",
  "return_audio": true,
  "include_audio_base64": false,
  "session_id": "demo-session-001",
  "history": []
}
```

### 6.4 JSON Base64 音频请求示例

```json
{
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
  "audio_filename": "question.wav",
  "audio_content_type": "audio/wav",
  "text": "请简短回答",
  "return_audio": true
}
```

说明：当同时传入 `audio_base64` 和 `text` 时，服务会先识别音频，再把补充文本拼接到识别结果后面，一起发给大模型。

### 6.5 multipart/form-data 请求字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `audio` | file | 否 | 音频文件，字段名也兼容 `file` |
| `text` | string | 否 | 文字输入或语音补充说明 |
| `return_audio` | string/boolean | 否 | `true` 或 `false` |
| `include_audio_base64` | string/boolean | 否 | `true` 或 `false` |
| `voice` | string | 否 | 临时覆盖 TTS 音色 |
| `session_id` | string | 否 | 会话 ID |
| `history` | string | 否 | JSON 字符串格式的历史消息 |

### 6.6 multipart/form-data 请求示例

```powershell
curl.exe -X POST "http://127.0.0.1:8010/ask" `
  -F "audio=@sample.wav" `
  -F "text=请简短回答" `
  -F "return_audio=true"
```

### 6.7 成功响应示例

```json
{
  "session_id": "demo-session-001",
  "input_text": "你好，用一句话介绍你自己",
  "answer_text": "你好，我是小乐，一个可以进行语音问答的智能助手。",
  "audio_url": "/audio/ask-demo-session-001-a1b2c3d4.mp3",
  "audio_content_type": "audio/mpeg",
  "audio_base64": null,
  "errors": []
}
```

### 6.8 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | string | 本次会话 ID |
| `input_text` | string | 最终送入大模型的文本，可能来自语音识别、文字输入或二者拼接 |
| `answer_text` | string | 大模型回答文本 |
| `audio_url` | string/null | TTS 生成的音频访问地址 |
| `audio_content_type` | string/null | 音频 MIME 类型，目前通常是 `audio/mpeg` |
| `audio_base64` | string/null | 当 `include_audio_base64=true` 时返回 |
| `errors` | array | 非阻断错误列表，例如 TTS 失败但文本回答成功 |

### 6.9 错误响应示例

未传输入：

```json
{
  "detail": "Provide text, audio multipart field, or audio_base64."
}
```

LLM Key 缺失：

```json
{
  "detail": "LLM failed: LLM API key is not configured. Put XIAOZHI_LLM_API_KEY in .env."
}
```

ASR 模型缺失：

```json
{
  "detail": "ASR failed: ASR model directory does not exist: ... Set XIAOZHI_ASR_MODEL_DIR or copy the FunASR model first."
}
```

## 7. 音频文件接口

### 7.1 基本信息

| 项目 | 内容 |
| --- | --- |
| URL | `/audio/{filename}` |
| Method | `GET` |
| 用途 | 下载或播放 `/ask` 生成的语音文件 |

### 7.2 请求示例

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8010/audio/ask-demo-session-001-a1b2c3d4.mp3" `
  -OutFile ".\answer.mp3"
```

### 7.3 响应

成功时返回音频二进制文件：

```http
HTTP/1.1 200 OK
Content-Type: audio/mpeg
```

文件不存在：

```json
{
  "detail": "Audio file not found."
}
```

非法文件名：

```json
{
  "detail": "Invalid filename."
}
```

## 8. Postman 使用说明

Postman 示例文件位于：

- `postman/Xiaozhi_Voice_Core_API.postman_collection.json`
- `postman/Xiaozhi_Voice_Core_API.postman_environment.json`

导入步骤：

1. 打开 Postman。
2. 点击 `Import`。
3. 导入上面两个 JSON 文件。
4. 在右上角选择环境 `Xiaole Voice Core Local`。
5. 确认 `base_url` 为 `http://127.0.0.1:8010`。
6. 启动本地 FastAPI 服务。
7. 先调用 `Health Check`，再调用 `Ask - Text JSON`。

文件上传示例需要在 Postman 的 `Ask - Audio Multipart` 请求里手动选择本地音频文件，或者修改环境变量 `audio_file_path` 后重新选择文件。

## 9. 联调建议

前端或硬件端推荐流程：

1. 调用 `/health`，确认 `ok=true`，且 `llm_api_key_configured=true`。
2. 文本输入直接调用 `/ask` JSON。
3. 麦克风录音后优先上传 `wav`，降低音频解码问题。
4. 播放返回的 `audio_url`，完整地址为 `base_url + audio_url`。
5. 如果硬件端不方便二次请求音频文件，可以传 `include_audio_base64=true`，直接从响应体里取语音。
