"""
Thin wrapper around the NVIDIA-hosted Inkling endpoint (OpenAI-compatible).
Every other module calls through here so there's one place that talks to the
model.
"""

from openai import OpenAI

import config

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.NVIDIA_API_KEY:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Run: export NVIDIA_API_KEY=your-key"
            )
        _client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY)
    return _client


def ask_inkling(messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024) -> str:
    """Plain text-in, text-out call."""
    client = get_client()
    completion = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=temperature,
        top_p=0.95,
        max_tokens=max_tokens,
        stream=False,
    )
    return completion.choices[0].message.content


def ask_inkling_with_image(prompt: str, image_b64: str, temperature: float = 0.4) -> str:
    """Vision call: one text prompt + one base64 JPEG image."""
    client = get_client()
    completion = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        temperature=temperature,
        top_p=0.95,
        max_tokens=400,
        stream=False,
    )
    return completion.choices[0].message.content
