import asyncio
import base64
import io
import json
import os
import re
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse


PROJECT_ROOT = Path(__file__).resolve().parent
AUDIO_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "fastapi_audio"
ASR_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "fastapi_asr"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


def _env_is_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return any(marker in value for marker in ["你的", "你"]) or "your-" in lowered


def _load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        current_value = os.environ.get(key)
        if current_value is None or _env_is_placeholder(current_value):
            os.environ[key] = value


for _dotenv_path in [
    PROJECT_ROOT.parent.parent / ".env",
    PROJECT_ROOT.parent / ".env",
    PROJECT_ROOT / ".env",
]:
    _load_dotenv_file(_dotenv_path)


app = FastAPI(
    title="Xiaozhi Voice Core API",
    description="Extracted Xiaozhi ASR + LLM + TTS service.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_CONFIG_CACHE: Optional[dict[str, Any]] = None
_LLM_CLIENT = None
_ASR_MODEL = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _safe_session_id(value: Optional[str]) -> str:
    raw = value or uuid.uuid4().hex
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", raw)
    return safe[:64] or uuid.uuid4().hex


def _is_placeholder(value: Optional[str]) -> bool:
    return _env_is_placeholder(value)


def _as_project_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def _selected_provider_config(config: dict[str, Any], group: str) -> tuple[str, dict[str, Any]]:
    selected = config.get("selected_module", {}).get(group)
    if not selected:
        raise RuntimeError(f"{group} provider is not selected.")
    provider_config = config.get(group, {}).get(selected)
    if not isinstance(provider_config, dict):
        raise RuntimeError(f"{group}.{selected} is not configured.")
    return selected, provider_config


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(config)
    selected = config.setdefault("selected_module", {})

    llm_api_key = (
        _env("XIAOZHI_LLM_API_KEY")
        or _env("DEEPSEEK_API_KEY")
        or _env("OPENAI_API_KEY")
    )
    llm_provider = _env("XIAOZHI_LLM_PROVIDER")
    if llm_provider:
        selected["LLM"] = llm_provider
    elif llm_api_key:
        selected["LLM"] = "DeepSeekLLM"

    selected_llm = selected.get("LLM")
    if selected_llm and selected_llm in config.get("LLM", {}):
        llm_config = config["LLM"][selected_llm]
        if llm_api_key:
            llm_config["api_key"] = llm_api_key
        llm_base_url = (
            _env("XIAOZHI_LLM_BASE_URL")
            or _env("DEEPSEEK_BASE_URL")
            or _env("OPENAI_BASE_URL")
            or ("https://api.deepseek.com" if selected_llm == "DeepSeekLLM" else None)
        )
        if llm_base_url:
            llm_config["base_url"] = llm_base_url
            llm_config["url"] = llm_base_url
        llm_model = (
            _env("XIAOZHI_LLM_MODEL")
            or _env("DEEPSEEK_MODEL")
            or _env("OPENAI_MODEL")
            or _env("MODEL_NAME")
            or ("deepseek-chat" if selected_llm == "DeepSeekLLM" else None)
        )
        if llm_model:
            llm_config["model_name"] = llm_model

    tts_provider = _env("XIAOZHI_TTS_PROVIDER")
    if tts_provider:
        selected["TTS"] = tts_provider
    selected_tts = selected.get("TTS")
    if selected_tts and selected_tts in config.get("TTS", {}):
        tts_config = config["TTS"][selected_tts]
        tts_voice = _env("XIAOZHI_TTS_VOICE")
        if tts_voice:
            tts_config["voice"] = tts_voice
        tts_config["output_dir"] = str(AUDIO_OUTPUT_DIR)

    asr_provider = _env("XIAOZHI_ASR_PROVIDER")
    if asr_provider:
        selected["ASR"] = asr_provider
    selected_asr = selected.get("ASR")
    if selected_asr and selected_asr in config.get("ASR", {}):
        asr_config = config["ASR"][selected_asr]
        asr_model_dir = _env("XIAOZHI_ASR_MODEL_DIR")
        if asr_model_dir:
            asr_config["model_dir"] = asr_model_dir
        if asr_config.get("model_dir"):
            asr_config["model_dir"] = _as_project_path(asr_config["model_dir"])
        asr_config["output_dir"] = str(ASR_OUTPUT_DIR)

    config["delete_audio"] = False
    return config


def get_config() -> dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    from config.config_loader import load_config

    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_CACHE = _apply_env_overrides(load_config())
    return _CONFIG_CACHE


def _get_llm_client_and_config():
    global _LLM_CLIENT
    config = get_config()
    selected, provider_config = _selected_provider_config(config, "LLM")
    api_key = provider_config.get("api_key")
    if _is_placeholder(api_key):
        raise RuntimeError(
            "LLM API key is not configured. Put XIAOZHI_LLM_API_KEY in .env."
        )
    base_url = provider_config.get("base_url") or provider_config.get("url")
    if _LLM_CLIENT is None:
        import httpx
        import openai

        timeout_config = provider_config.get("timeout")
        if isinstance(timeout_config, dict):
            timeout = httpx.Timeout(
                pool=timeout_config.get("pool", 2.0),
                connect=timeout_config.get("connect", 3.0),
                write=timeout_config.get("write", 5.0),
                read=timeout_config.get("read", 60.0),
            )
        elif isinstance(timeout_config, (int, float)) and timeout_config > 0:
            timeout = httpx.Timeout(timeout_config)
        else:
            timeout = httpx.Timeout(120.0)
        _LLM_CLIENT = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return _LLM_CLIENT, selected, provider_config


def _get_tts_config() -> tuple[str, dict[str, Any]]:
    config = get_config()
    return _selected_provider_config(config, "TTS")


def _get_asr_model_and_config():
    global _ASR_MODEL
    config = get_config()
    selected, provider_config = _selected_provider_config(config, "ASR")
    provider_type = provider_config.get("type", selected)
    if provider_type != "fun_local":
        raise RuntimeError(
            f"FastAPI audio input currently supports FunASR local only, got {selected}."
        )

    model_dir = provider_config.get("model_dir")
    if model_dir and not Path(model_dir).exists():
        raise RuntimeError(
            f"ASR model directory does not exist: {model_dir}. "
            "Set XIAOZHI_ASR_MODEL_DIR or copy the FunASR model first."
        )

    if _ASR_MODEL is None:
        from funasr import AutoModel

        _ASR_MODEL = AutoModel(
            model=model_dir,
            vad_kwargs={"max_single_segment_time": 30000},
            disable_update=True,
            hub="hf",
        )
    return _ASR_MODEL, selected, provider_config


def _normalize_history(history: Any) -> list[dict[str, str]]:
    if isinstance(history, str) and history.strip():
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            return []
    if not isinstance(history, list):
        return []

    messages: list[dict[str, str]] = []
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content is not None:
            messages.append({"role": role, "content": str(content)})
    return messages


def _build_dialogue(
    config: dict[str, Any], input_text: str, history: Any
) -> list[dict[str, str]]:
    system_prompt = config.get("prompt") or "You are a helpful voice assistant."
    return (
        [{"role": "system", "content": system_prompt}]
        + _normalize_history(history)
        + [{"role": "user", "content": input_text}]
    )


def _call_llm(session_id: str, input_text: str, history: Any = None) -> str:
    config = get_config()
    client, selected, provider_config = _get_llm_client_and_config()
    dialogue = _build_dialogue(config, input_text, history)

    request_params: dict[str, Any] = {
        "model": provider_config.get("model_name"),
        "messages": dialogue,
        "stream": True,
    }
    for key in ["max_tokens", "temperature", "top_p", "frequency_penalty"]:
        value = provider_config.get(key)
        if value not in (None, ""):
            request_params[key] = value
    base_url = provider_config.get("base_url") or provider_config.get("url") or ""
    if any(domain in base_url for domain in ["aliyuncs.com", "bigmodel.cn", "moonshot.cn", "volces.com"]):
        if "bigmodel.cn" in base_url:
            request_params.setdefault("extra_body", {}).update({"thinking": {"type": "disabled"}})
        elif "aliyuncs.com" in base_url:
            request_params.setdefault("extra_body", {}).update({"enable_thinking": False})
        else:
            request_params.setdefault("extra_body", {}).update({"thinking": {"type": "disabled"}})

    chunks = []
    stream = client.chat.completions.create(**request_params)
    is_active = True
    try:
        for chunk in stream:
            delta = chunk.choices[0].delta if getattr(chunk, "choices", None) else None
            content = getattr(delta, "content", "") if delta else ""
            if not content:
                continue
            if "<think>" in content:
                is_active = False
                content = content.split("<think>")[0]
            if "</think>" in content:
                is_active = True
                content = content.split("</think>")[-1]
            if is_active:
                chunks.append(content)
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
    answer = "".join(chunks).strip()
    if not answer:
        raise RuntimeError("LLM returned an empty answer.")
    return answer


async def _answer_text(session_id: str, input_text: str, history: Any = None) -> str:
    return await asyncio.to_thread(_call_llm, session_id, input_text, history)


def _format_hint(filename: Optional[str], content_type: Optional[str]) -> Optional[str]:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext:
        return {"mpeg": "mp3", "mpga": "mp3", "wave": "wav"}.get(ext, ext)
    if content_type and "/" in content_type:
        subtype = content_type.split(";", 1)[0].split("/", 1)[1].lower()
        if subtype in {"octet-stream", "x-wav"}:
            return "wav" if subtype == "x-wav" else None
        return {"mpeg": "mp3", "mpga": "mp3", "wave": "wav"}.get(subtype, subtype)
    return None


async def _audio_to_pcm(
    audio_bytes: bytes, filename: Optional[str], content_type: Optional[str]
) -> bytes:
    if not audio_bytes:
        raise RuntimeError("Uploaded audio is empty.")

    def convert() -> bytes:
        from pydub import AudioSegment

        hint = _format_hint(filename, content_type)
        segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=hint)
        segment = segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        return segment.raw_data

    try:
        return await asyncio.to_thread(convert)
    except Exception as exc:
        raise RuntimeError(
            "Audio decode failed. Install ffmpeg for mp3/webm/m4a input, "
            "or upload a valid wav file."
        ) from exc


def _asr_text_content(value: Any) -> str:
    if isinstance(value, dict):
        content = value.get("content")
        return str(content).strip() if content is not None else json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value).strip()


def _lang_tag_filter(text: str) -> Any:
    tag_pattern = r"<\|([^|]+)\|>"
    all_tags = re.findall(tag_pattern, text or "")
    clean_text = re.sub(tag_pattern, "", text or "").strip()
    if not all_tags:
        return clean_text
    return {
        "content": clean_text,
        "language": all_tags[0] if len(all_tags) > 0 else "zh",
        "emotion": all_tags[1] if len(all_tags) > 1 else "NEUTRAL",
    }


async def _transcribe_audio(
    session_id: str,
    audio_bytes: bytes,
    filename: Optional[str],
    content_type: Optional[str],
) -> str:
    pcm_bytes = await _audio_to_pcm(audio_bytes, filename, content_type)
    model, _, _ = _get_asr_model_and_config()

    def transcribe() -> Any:
        return model.generate(
            input=pcm_bytes,
            cache={},
            language="auto",
            use_itn=True,
            batch_size_s=60,
        )

    result = await asyncio.to_thread(transcribe)
    raw_text = ""
    if isinstance(result, list) and result:
        raw_text = str(result[0].get("text", ""))
    else:
        raw_text = str(result or "")
    text = _asr_text_content(_lang_tag_filter(raw_text))
    if not text:
        raise RuntimeError("ASR returned an empty result.")
    return text


async def _synthesize_audio(
    session_id: str, answer_text: str, voice: Optional[str] = None
) -> Path:
    selected, provider_config = _get_tts_config()
    provider_type = provider_config.get("type", selected)
    if provider_type != "edge":
        raise RuntimeError(
            f"FastAPI audio output currently supports EdgeTTS only, got {selected}."
        )
    import edge_tts

    selected_voice = voice or provider_config.get("private_voice") or provider_config.get("voice")
    if not selected_voice:
        raise RuntimeError("TTS voice is not configured.")

    extension = ".mp3"
    output_file = AUDIO_OUTPUT_DIR / f"ask-{session_id}-{uuid.uuid4().hex[:8]}{extension}"
    communicate = edge_tts.Communicate(answer_text, voice=selected_voice)
    with output_file.open("wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError("TTS generated an empty audio file.")
    return output_file


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".ogg":
        return "audio/ogg"
    return "application/octet-stream"


async def _parse_request(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    payload: dict[str, Any] = {
        "text": None,
        "audio_bytes": None,
        "audio_filename": None,
        "audio_content_type": None,
        "return_audio": True,
        "include_audio_base64": False,
        "voice": None,
        "session_id": None,
        "history": None,
    }

    if "application/json" in content_type:
        try:
            body = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        payload.update(
            {
                "text": body.get("text"),
                "return_audio": _parse_bool(body.get("return_audio"), True),
                "include_audio_base64": _parse_bool(
                    body.get("include_audio_base64"), False
                ),
                "voice": body.get("voice"),
                "session_id": body.get("session_id"),
                "history": body.get("history"),
                "audio_filename": body.get("audio_filename") or "audio.wav",
                "audio_content_type": body.get("audio_content_type"),
            }
        )
        audio_base64 = body.get("audio_base64")
        if audio_base64:
            if "," in audio_base64:
                audio_base64 = audio_base64.split(",", 1)[1]
            try:
                payload["audio_bytes"] = base64.b64decode(audio_base64)
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Invalid audio_base64.") from exc
        return payload

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        audio = form.get("audio") or form.get("file")
        payload.update(
            {
                "text": form.get("text"),
                "return_audio": _parse_bool(form.get("return_audio"), True),
                "include_audio_base64": _parse_bool(
                    form.get("include_audio_base64"), False
                ),
                "voice": form.get("voice"),
                "session_id": form.get("session_id"),
                "history": form.get("history"),
            }
        )
        if hasattr(audio, "read") and hasattr(audio, "filename"):
            payload["audio_bytes"] = await audio.read()
            payload["audio_filename"] = audio.filename
            payload["audio_content_type"] = getattr(audio, "content_type", None)
        return payload

    try:
        body = await request.body()
    except Exception:
        body = b""
    if body:
        payload["text"] = body.decode("utf-8", errors="ignore")
    return payload


@app.get("/health")
async def health():
    config_error = None
    selected: dict[str, Any] = {}
    details: dict[str, Any] = {}
    try:
        config = get_config()
        selected = dict(config.get("selected_module", {}))
        _, llm_config = _selected_provider_config(config, "LLM")
        _, asr_config = _selected_provider_config(config, "ASR")
        _, tts_config = _selected_provider_config(config, "TTS")
        details = {
            "llm_api_key_configured": not _is_placeholder(llm_config.get("api_key")),
            "asr_model_dir": asr_config.get("model_dir"),
            "asr_model_dir_exists": bool(
                asr_config.get("model_dir") and Path(asr_config["model_dir"]).exists()
            ),
            "tts_voice": tts_config.get("voice") or tts_config.get("private_voice"),
        }
    except Exception as exc:
        config_error = str(exc)

    dependencies = {}
    for name in ["fastapi", "uvicorn", "pydub", "openai", "edge_tts", "funasr"]:
        try:
            __import__(name)
            dependencies[name] = True
        except Exception:
            dependencies[name] = False

    return {
        "ok": config_error is None,
        "config_error": config_error,
        "selected_module": selected,
        "dependencies": dependencies,
        "details": details,
    }


@app.post("/ask")
async def ask(request: Request):
    payload = await _parse_request(request)
    session_id = _safe_session_id(payload.get("session_id"))
    typed_text = str(payload.get("text") or "").strip()
    input_text_parts = []
    errors = []

    if payload.get("audio_bytes"):
        try:
            input_text_parts.append(
                await _transcribe_audio(
                    session_id,
                    payload["audio_bytes"],
                    payload.get("audio_filename"),
                    payload.get("audio_content_type"),
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"ASR failed: {exc}") from exc

    if typed_text:
        input_text_parts.append(typed_text)

    input_text = "\n".join(part for part in input_text_parts if part).strip()
    if not input_text:
        raise HTTPException(
            status_code=400,
            detail="Provide text, audio multipart field, or audio_base64.",
        )

    try:
        answer_text = await _answer_text(session_id, input_text, payload.get("history"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM failed: {exc}") from exc

    audio_url = None
    audio_base64 = None
    audio_content_type = None
    if payload.get("return_audio"):
        try:
            audio_file = await _synthesize_audio(
                session_id, answer_text, payload.get("voice")
            )
            audio_url = f"/audio/{audio_file.name}"
            audio_content_type = _media_type(audio_file)
            if payload.get("include_audio_base64"):
                audio_base64 = base64.b64encode(audio_file.read_bytes()).decode("ascii")
        except Exception as exc:
            errors.append(f"TTS failed: {exc}")

    return JSONResponse(
        {
            "session_id": session_id,
            "input_text": input_text,
            "answer_text": answer_text,
            "audio_url": audio_url,
            "audio_content_type": audio_content_type,
            "audio_base64": audio_base64,
            "errors": errors,
        }
    )


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    path = AUDIO_OUTPUT_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(path, media_type=_media_type(path), filename=filename)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8010, reload=False)
