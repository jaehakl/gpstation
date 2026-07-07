from __future__ import annotations

import asyncio
import ctypes
import gc
import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from model_runtime.gpu_residency import acquire_gpu_model, get_llm_cuda_device_id
from settings import settings

#LLM_REPO_ID = "LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF"
#LLM_MODEL_FILENAME = "EXAONE-4.0-1.2B-Q4_K_M.gguf"
LLM_REPO_ID = ""
LLM_MODEL_FILENAME = "supergemma4-26b-uncensored-fast-v2-Q4_K_M.gguf"
LLM_CONTEXT_SIZE = 4096
LLM_N_THREADS = 0
LLM_MAX_TOKENS = 512
LLM_TEMPERATURE = 0.5
LLM_TOP_P = 0.9
LLM_MAX_SOURCE_TEXT_LENGTH = 8000
LLM_MIN_MAX_TOKENS = 16
LLM_MAX_MAX_TOKENS = 1024
LLM_MIN_TEMPERATURE = 0.0
LLM_MAX_TEMPERATURE = 2.0
LLM_SPLIT_MODE_NONE = 0

_prompt_llm_lock = asyncio.Lock()
PromptLlmModelKey = tuple[str, str, str, int, int, int, int | None, int | None]
_prompt_llm_model_key: PromptLlmModelKey | None = None
_prompt_llm: Any | None = None
_llm_dll_directory_handles: list[Any] = []
_llm_loaded_dlls: list[Any] = []


@dataclass(frozen=True)
class PromptLlmConfig:
    model_path: str
    repo_id: str
    model_filename: str
    context_size: int
    n_gpu_layers: int
    n_threads: int
    main_gpu: int | None
    split_mode: int | None
    model_key: PromptLlmModelKey
    max_tokens: int
    temperature: float
    top_p: float


async def generate_prompt_with_llm(
    messages: list[dict[str, str]],
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format_json: bool = True,
) -> str:
    config = build_prompt_llm_config(max_tokens=max_tokens, temperature=temperature)
    async with acquire_gpu_model("llm", config.main_gpu, config.model_key, release_llm_runtime):
        async with _prompt_llm_lock:
            return await asyncio.to_thread(
                _generate_prompt_with_llm_locked,
                config,
                messages,
                response_format_json,
            )


async def ask_llm(
    system_message: str,
    question: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    trimmed_system_message = system_message.strip()
    trimmed_question = question.strip()
    if not trimmed_system_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="system_message is required")
    if not trimmed_question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question is required")
    if len(trimmed_system_message) > LLM_MAX_SOURCE_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"system_message must be {LLM_MAX_SOURCE_TEXT_LENGTH} characters or fewer",
        )
    if len(trimmed_question) > LLM_MAX_SOURCE_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"question must be {LLM_MAX_SOURCE_TEXT_LENGTH} characters or fewer",
        )
    answer = await generate_prompt_with_llm(
        [
            {"role": "system", "content": trimmed_system_message},
            {"role": "user", "content": trimmed_question},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        response_format_json=False,
    )
    if not answer.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM returned empty answer")
    return answer


def build_prompt_llm_config(
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> PromptLlmConfig:
    resolved_max_tokens = LLM_MAX_TOKENS if max_tokens is None else max_tokens
    if not LLM_MIN_MAX_TOKENS <= resolved_max_tokens <= LLM_MAX_MAX_TOKENS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "max_tokens must be between "
                f"{LLM_MIN_MAX_TOKENS} and {LLM_MAX_MAX_TOKENS}"
            ),
        )

    resolved_temperature = LLM_TEMPERATURE if temperature is None else temperature
    if not LLM_MIN_TEMPERATURE <= resolved_temperature <= LLM_MAX_TEMPERATURE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "temperature must be between "
                f"{LLM_MIN_TEMPERATURE} and {LLM_MAX_TEMPERATURE}"
            ),
        )

    model_path_value = settings.llm_model_path.strip()
    if model_path_value:
        model_path = settings.resolve_ai_path(model_path_value)
        try:
            model_path_value = str(model_path.resolve(strict=True))
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"prompt LLM model file not found: {model_path}",
            ) from exc

    repo_id = LLM_REPO_ID.strip()
    model_filename = LLM_MODEL_FILENAME.strip()
    if not model_path_value and (not repo_id or not model_filename):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="prompt LLM repo id and model filename are required",
        )

    use_gpu = settings.llm_use_max_gpu
    main_gpu = get_llm_cuda_device_id(use_gpu)
    n_gpu_layers = -1 if use_gpu else 0
    split_mode = LLM_SPLIT_MODE_NONE if main_gpu is not None else None
    model_key = (
        model_path_value,
        repo_id,
        model_filename,
        LLM_CONTEXT_SIZE,
        n_gpu_layers,
        LLM_N_THREADS,
        main_gpu,
        split_mode,
    )
    return PromptLlmConfig(
        model_path=model_path_value,
        repo_id=repo_id,
        model_filename=model_filename,
        context_size=LLM_CONTEXT_SIZE,
        n_gpu_layers=n_gpu_layers,
        n_threads=LLM_N_THREADS,
        main_gpu=main_gpu,
        split_mode=split_mode,
        model_key=model_key,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        top_p=LLM_TOP_P,
    )


def reset_llm_runtime_for_tests() -> None:
    release_llm_runtime()


def release_llm_runtime(device_id: int | None = None) -> None:
    global _prompt_llm_model_key, _prompt_llm

    llm = _prompt_llm
    _prompt_llm = None
    _prompt_llm_model_key = None
    if llm is not None:
        close = getattr(llm, "close", None)
        if callable(close):
            close()
        del llm
    gc.collect()


def _parse_llm_json_object(
    raw_output: str,
    empty_detail: str,
    invalid_detail: str,
) -> dict[str, Any]:
    raw_output = raw_output.strip()
    if not raw_output:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=empty_detail)

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}")
        if json_start < 0 or json_end <= json_start:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=invalid_detail,
            ) from exc
        try:
            payload = json.loads(raw_output[json_start:json_end + 1])
        except json.JSONDecodeError as nested_exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=invalid_detail,
            ) from nested_exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=invalid_detail)
    return payload


def _generate_prompt_with_llm_locked(
    config: PromptLlmConfig,
    messages: list[dict[str, str]],
    response_format_json: bool,
) -> str:
    llm = _get_prompt_llm_locked(config)
    completion_kwargs: dict[str, Any] = {
        "messages": messages,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
    }
    if response_format_json:
        completion_kwargs["response_format"] = {"type": "json_object"}
    response = llm.create_chat_completion(**completion_kwargs)
    if not isinstance(response, dict):
        return ""

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    return content if isinstance(content, str) else ""


def _get_prompt_llm_locked(config: PromptLlmConfig) -> Any:
    global _prompt_llm_model_key, _prompt_llm

    model_key = config.model_key
    if _prompt_llm is not None and _prompt_llm_model_key != model_key:
        release_llm_runtime()

    if _prompt_llm is None:
        try:
            _add_llm_dll_directories()
            from llama_cpp import Llama
        except (ModuleNotFoundError, OSError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "llama-cpp-python is not available or failed to load its native libraries. "
                    "Install a wheel that matches this machine, then restart the API server."
                ),
            ) from exc

        llama_kwargs: dict[str, Any] = {
            "n_ctx": config.context_size,
            "n_gpu_layers": config.n_gpu_layers,
            "verbose": False,
        }
        if config.n_threads > 0:
            llama_kwargs["n_threads"] = config.n_threads
        if config.main_gpu is not None:
            llama_kwargs["main_gpu"] = config.main_gpu
        if config.split_mode is not None:
            llama_kwargs["split_mode"] = config.split_mode

        if config.model_path:
            _prompt_llm = Llama(
                model_path=config.model_path,
                **llama_kwargs,
            )
        else:
            _prompt_llm = Llama.from_pretrained(
                repo_id=config.repo_id,
                filename=config.model_filename,
                **llama_kwargs,
            )
        _prompt_llm_model_key = model_key
    return _prompt_llm


def _add_llm_dll_directories() -> None:
    if _llm_loaded_dlls:
        return

    llama_lib_paths: list[Path] = []
    llama_cpp_spec = importlib.util.find_spec("llama_cpp")
    if llama_cpp_spec is not None and llama_cpp_spec.submodule_search_locations is not None:
        for location in llama_cpp_spec.submodule_search_locations:
            dll_path = Path(location) / "lib"
            if dll_path.exists():
                llama_lib_paths.append(dll_path)
                if hasattr(os, "add_dll_directory"):
                    _llm_dll_directory_handles.append(os.add_dll_directory(str(dll_path)))

    nvidia_lib_paths: list[Path] = []
    nvidia_spec = importlib.util.find_spec("nvidia")
    if nvidia_spec is not None and nvidia_spec.submodule_search_locations is not None:
        for location in nvidia_spec.submodule_search_locations:
            for dll_path in (
                Path(location) / "cu13" / "bin" / "x86_64",
                Path(location) / "cu13" / "lib",
            ):
                if dll_path.exists():
                    nvidia_lib_paths.append(dll_path)
                    if hasattr(os, "add_dll_directory"):
                        _llm_dll_directory_handles.append(os.add_dll_directory(str(dll_path)))

    load_kwargs = {"mode": ctypes.RTLD_GLOBAL} if hasattr(ctypes, "RTLD_GLOBAL") else {}
    for dll_name in ("libcudart.so.13", "cudart64_13.dll", "libcublasLt.so.13", "libcublas.so.13", "cublas64_13.dll"):
        for dll_path in nvidia_lib_paths:
            full_path = dll_path / dll_name
            if full_path.exists():
                _llm_loaded_dlls.append(ctypes.CDLL(str(full_path), **load_kwargs))
                break

    for dll_name in (
        "ggml-base.dll",
        "ggml-cpu.dll",
        "ggml-cuda.dll",
        "ggml.dll",
        "llama.dll",
        "libggml-base.so",
        "libggml-cpu.so",
        "libggml-cuda.so",
        "libggml.so",
        "libllama.so",
    ):
        for dll_path in llama_lib_paths:
            full_path = dll_path / dll_name
            if full_path.exists():
                _llm_loaded_dlls.append(ctypes.CDLL(str(full_path), **load_kwargs))
                break
