import base64
import io
from typing import Optional, Tuple
from PIL import Image

from openai import AsyncOpenAI
from openai import (
    APIError,
    APIConnectionError,
    RateLimitError,
    AuthenticationError,
    OpenAIError,
)

from .abstract_vlm import AbstractVLM


class OpenAIVisionModel(AbstractVLM):
    """
    OpenAI vision language model implementation (GPT-4o, GPT-4V, etc.).
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o",
        base_url: Optional[str] = None,
        max_image_size: Tuple[int, int] = (2048, 2048),
        detail_level: str = "auto",
        temperature: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs,  # Support additional parameters via extra='allow'
    ):
        """
        Initialize OpenAI VLM.

        Args:
            api_key: OpenAI API key
            model_name: Model name (default: "gpt-4o")
            base_url: Custom base URL for OpenAI-compatible API
            max_image_size: Maximum image dimensions (width, height)
            detail_level: Image detail level ("low", "high", "auto")
            temperature: Sampling temperature (0.0 to 2.0)
            timeout: Request timeout in seconds
            max_retries: Maximum retries for rate limit errors
            **kwargs: Additional parameters passed to AsyncOpenAI
        """
        self.api_key = api_key
        self.model_name = model_name

        # Validate max_image_size
        if not (isinstance(max_image_size, tuple) and len(max_image_size) == 2):
            raise ValueError("max_image_size must be a tuple of two integers")
        if not all(isinstance(dim, int) and dim > 0 for dim in max_image_size):
            raise ValueError("max_image_size dimensions must be positive integers")
        self.max_image_size = max_image_size

        # Validate detail_level
        if detail_level not in ("low", "high", "auto"):
            raise ValueError('detail_level must be "low", "high", or "auto"')
        self.detail_level = detail_level
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

        # Image processing settings
        self.quality = 85  # Quality setting for JPEG compression

        # Create OpenAI client
        client_kwargs = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        if kwargs:
            client_kwargs.update(kwargs)

        self.client = AsyncOpenAI(**client_kwargs)

    async def preprocess_image(self, image_blob: bytes) -> str:
        """
        Preprocess raw image binary data into OpenAI required format.
        Preserves original format when possible, converts to JPEG only when necessary.

        Args:
            image_blob: Raw image binary data

        Returns:
            Base64 encoded image with appropriate data URL prefix

        Raises:
            ValueError: If image processing fails
        """
        try:
            img = Image.open(io.BytesIO(image_blob))
            
            # Convert to RGB if necessary (for formats like PNG with transparency or CMYK)
            if img.mode in ("RGBA", "P", "LA", "1", "I", "F"):
                # For PNG with transparency, keep as PNG; otherwise convert to RGB
                if img.format == "PNG" and "transparency" in img.info:
                    # Keep PNG format for transparency
                    img = img.convert("RGBA")
                    output_format = "PNG"
                    buffer_format = "PNG"
                else:
                    img = img.convert("RGB")
                    output_format = "JPEG"
                    buffer_format = "JPEG"
            else:
                output_format = img.format or "JPEG"
                buffer_format = "JPEG"  # Use JPEG for compression when saving to buffer

            # Determine target max dimensions based on detail_level
            if self.detail_level == "low":
                target_max = (512, 512)
            else:
                target_max = self.max_image_size

            # Resize preserving aspect ratio (thumbnail modifies in-place)
            img.thumbnail(target_max)

            buf = io.BytesIO()
            if buffer_format == "JPEG":
                # Convert to RGB if saving as JPEG (JPEG doesn't support transparency)
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                img.save(buf, format=buffer_format, quality=self.quality)
            else:
                img.save(buf, format=buffer_format)

            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/{output_format.lower()};base64,{b64}"
        except Exception as e:
            raise ValueError(f"Failed to preprocess image: {e}")

    async def multimodal_request(
        self, 
        inputs: list[dict], 
        prompt: Optional[str] = None
    ) -> str:
        """
        Perform a general multimodal request with various input types using OpenAI vision API.

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

        # Prepare content list with all inputs using the format from the documentation
        content = []
        for inp in inputs:
            if inp["type"] == "image":
                content.append({
                    "type": "input_image",  # Changed to input_image as per the doc
                    "image_url": inp["data"],
                })
            elif inp["type"] == "text":
                content.append({"type": "input_text", "text": inp["content"]})  # Changed to input_text as per the doc
        
        # Add the main prompt as a text element to the content
        # Ensure we always have some text prompt for the model to act on
        final_prompt = prompt if prompt is not None else "请处理这些多模态输入。"
        content.append({"type": "input_text", "text": final_prompt})

        # Create the input structure required by OpenAI API as per the documentation
        input_structure = [
            {
                "role": "user",
                "content": content,
            }
        ]
        print(input_structure)
        try:
            response = await self.client.responses.create(
                model=self.model_name,
                input=input_structure,  # Using input instead of messages as per the doc
                temperature=self.temperature,
            )
            return response.output_text
        except AuthenticationError as e:
            return f"Error: Authentication failed: {e}"
        except RateLimitError as e:
            return f"Error: Rate limit exceeded: {e}"
        except APIConnectionError as e:
            return f"Error: Connection error: {e}"
        except APIError as e:
            return f"Error: API error: {e}"
        except OpenAIError as e:
            return f"Error: OpenAI error: {e}"
        except Exception as e:
            return f"Error: {e}"