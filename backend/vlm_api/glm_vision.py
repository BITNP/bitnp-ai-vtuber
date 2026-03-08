import asyncio
import base64
import io
import functools
from typing import Optional
import requests
from PIL import Image

from .abstract_vlm import AbstractVLM


class GlmVisionModel(AbstractVLM):
    """
    GLM-4V-Flash vision language model implementation.
    """

    def __init__(self, api_key: str, model_name: str = "glm-4v-flash", timeout: int = 60):
        """
        Initialize GLM VLM.

        Args:
            api_key: GLM API key
            model_name: Model name (default: glm-4v-flash)
            timeout: Request timeout in seconds (default: 60)
        """
        self.api_key = api_key
        self.model_name = model_name
        self.url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.max_image_size = (1024, 1024)
        self.output_format = "JPEG"
        self.quality = 85
        self.timeout = timeout  # 设置超时时间

    async def preprocess_image(self, image_blob: bytes) -> str:
        """
        Preprocess raw image binary data into GLM-4V-Flash required format.

        Converts image to RGB, resizes to max 1024x1024, encodes as JPEG with 85% quality,
        and returns as data:image/jpeg;base64,{b64} string.

        Args:
            image_blob: Raw image binary data

        Returns:
            Base64 encoded image with data:image/jpeg;base64, prefix

        Raises:
            ValueError: If image processing fails
        """
        try:
            img = Image.open(io.BytesIO(image_blob))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(self.max_image_size)

            buf = io.BytesIO()
            img.save(buf, format=self.output_format, quality=self.quality)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            raise ValueError(f"Failed to preprocess image: {e}")

    async def multimodal_request(
        self, 
        inputs: list[dict], 
        prompt: Optional[str] = None
    ) -> str:
        """
        Perform a general multimodal request with various input types using GLM-4V-Flash.

        Args:
            inputs: List of input elements, each with type and content
                   Example: [
                       {"type": "image", "data": "data:image/jpeg;base64,..."},
                       {"type": "text", "content": "some text"},
                       {"type": "image", "data": "data:image/png;base64,..."}
                   ]
            prompt: Optional text prompt for the vision model API.

        Returns:
            String response from the vision model API.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Use provided prompt or default to generic multimodal processing
        prompt_text = prompt if prompt is not None else "请处理这些多模态输入。"

        # Prepare content list with all inputs followed by the prompt
        content = []
        for inp in inputs:
            if inp["type"] == "image":
                content.append({"type": "image_url", "image_url": {"url": inp["data"]}})
            elif inp["type"] == "text":
                content.append({"type": "text", "text": inp["content"]})
        
        # Handle both new and legacy input types for compatibility
        processed_content = []
        for item in content:
            if item["type"] == "input_image":
                # Convert to GLM format
                processed_content.append({
                    "type": "image_url", 
                    "image_url": {"url": item["data"]}
                })
            elif item["type"] == "input_text":
                # Convert to GLM format
                processed_content.append({"type": "text", "text": item["content"]})
            elif item["type"] == "image":
                # Legacy format - convert to GLM format
                processed_content.append({
                    "type": "image_url", 
                    "image_url": {"url": item["data"]}
                })
            elif item["type"] == "text":
                # Legacy format - convert to GLM format
                processed_content.append({"type": "text", "text": item["content"]})
            else:
                # Pass through other types as-is
                processed_content.append(item)
        
        content = processed_content
        content.append({"type": "text", "text": prompt_text})

        data = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "stream": False,
            "temperature": 0.1,
        }

        loop = asyncio.get_event_loop()
        try:
            # 使用timeout包装请求，防止长时间等待
            import time
            def make_request():
                return requests.post(self.url, headers=headers, json=data, timeout=self.timeout)
            
            resp = await loop.run_in_executor(None, make_request)

            if resp.status_code != 200:
                return f"报错{resp.status_code}"
            response_content = resp.json()["choices"][0]["message"]["content"]

            # Return raw content, caller should handle IGNORE_IMAGE if needed
            if response_content is None:
                return "报错Empty response from GLM API"
            return response_content

        except requests.exceptions.Timeout:
            return f"报错Request timed out after {self.timeout} seconds"
        except Exception as e:
            return f"报错{e}"