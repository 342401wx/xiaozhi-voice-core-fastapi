from __future__ import annotations

import asyncio
import os
import sys
import wave
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_ROOT / "services" / "voice_core"
CONFIG_PATH = SERVER_DIR / "config.yaml"
OUT_DIR = PROJECT_ROOT / "runtime" / "asr_tts_verify"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def wav_to_pcm_bytes(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        return wav.readframes(wav.getnframes())


async def verify_asr(config: dict) -> tuple[bool, str]:
    os.chdir(SERVER_DIR)
    sys.path.insert(0, str(SERVER_DIR))

    from funasr import AutoModel
    from core.providers.asr.utils import lang_tag_filter

    asr_name = config["selected_module"]["ASR"]
    asr_config = config["ASR"][asr_name]
    audio_path = SERVER_DIR / "config" / "assets" / "wakeup_words.wav"
    pcm_bytes = wav_to_pcm_bytes(audio_path)
    model = AutoModel(
        model=asr_config["model_dir"],
        vad_kwargs={"max_single_segment_time": 30000},
        disable_update=True,
        hub="hf",
    )
    result = await asyncio.to_thread(
        model.generate,
        input=pcm_bytes,
        cache={},
        language="auto",
        use_itn=True,
        batch_size_s=60,
    )
    filtered = lang_tag_filter(result[0]["text"])
    text = filtered.get("content") or str(filtered)

    ok = bool(text.strip())
    return ok, f"ASR module={asr_name}, audio={audio_path.name}, pcm_bytes={len(pcm_bytes)}, text={text}"


async def verify_tts(config: dict) -> tuple[bool, str]:
    os.chdir(SERVER_DIR)
    sys.path.insert(0, str(SERVER_DIR))

    import edge_tts

    tts_name = config["selected_module"]["TTS"]
    tts_config = config["TTS"][tts_name]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUT_DIR / "tts_edge_verify.mp3"
    if output_file.exists():
        output_file.unlink()

    communicate = edge_tts.Communicate(
        "你好，这是语音合成接口验证。",
        voice=tts_config.get("voice", "zh-CN-XiaoxiaoNeural"),
    )
    await communicate.save(str(output_file))

    ok = output_file.exists() and output_file.stat().st_size > 1024
    return ok, f"TTS module={tts_name}, voice={tts_config.get('voice')}, file={output_file}, bytes={output_file.stat().st_size if output_file.exists() else 0}"


async def main() -> int:
    config = load_config()
    print(f"config={CONFIG_PATH}")
    print(f"selected ASR={config['selected_module']['ASR']}")
    print(f"selected TTS={config['selected_module']['TTS']}")

    asr_ok, asr_message = await verify_asr(config)
    print(("ASR OK: " if asr_ok else "ASR FAIL: ") + asr_message)

    tts_ok, tts_message = await verify_tts(config)
    print(("TTS OK: " if tts_ok else "TTS FAIL: ") + tts_message)

    if asr_ok and tts_ok:
        print("RESULT: ASR/TTS interface verification passed.")
        return 0

    print("RESULT: ASR/TTS interface verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
