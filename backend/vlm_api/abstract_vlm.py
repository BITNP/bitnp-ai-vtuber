from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class AbstractVLM(ABC):
    """
    Abstract base class for Vision Language Models (VLM).
    Provides core functionality for multimodal (text + image) requests.
    """

    @abstractmethod
    async def preprocess_image(self, image_blob: bytes) -> str:
        """
        Preprocess raw image binary data into the format required by this VLM.

        Args:
            image_blob: Raw image binary data

        Returns:
            Preprocessed image data (usually base64 string) in the format
            expected by this VLM's multimodal_request() method.

        Raises:
            ValueError: If image processing fails
        """
        pass

    @abstractmethod
    async def multimodal_request(
        self, 
        inputs: List[Dict[str, Any]], 
        prompt: Optional[str] = None
    ) -> str:
        """
        Perform a general multimodal request with various input types.

        Args:
            inputs: List of input elements, each with type and content
                   Example: [
                       {"type": "image", "data": "base64_string"},
                       {"type": "text", "content": "some text"},
                       {"type": "image", "data": "another_base64_string"}
                   ]
            prompt: Optional text prompt for the vision model API.

        Returns:
            String response from the vision model API.
        """
        pass