# VLM API - Vision Language Model Interface

This module provides a unified interface for interacting with different vision language models (VLMs) that support multimodal inputs (text + images).

## Core Components

### AbstractVLM
The base abstract class defining the core interface for all VLM implementations.

### Supported Providers
- `GlmVisionModel`: GLM-4V-Flash model from Zhipu AI
- `OpenAIVisionModel`: OpenAI GPT-4o, GPT-4V models

## Usage

### Creating a VLM Instance

```python
from vlm_api import create_vlm

# Create GLM vision model
glm_model = create_vlm("glm", api_key="your-api-key")

# Create OpenAI vision model
openai_model = create_vlm("openai", api_key="your-api-key", model_name="gpt-4o")
```

### Processing Multimodal Inputs

The main functionality is accessed through the `process_multimodal_inputs` method:

```python
# Define multimodal inputs
inputs = [
    {"type": "image", "data": image_bytes},  # Raw image bytes
    {"type": "text", "content": "Describe this image"},
    {"type": "image", "data": another_image_bytes}
]

# Process the inputs
result = await model.process_multimodal_inputs(inputs, prompt="Analyze these inputs")
```

### Direct Multimodal Requests

For more control, you can use the `multimodal_request` method with preprocessed inputs:

```python
# Preprocess images first
preprocessed_img = await model.preprocess_image(raw_image_bytes)

# Create inputs with preprocessed data
inputs = [
    {"type": "image", "data": preprocessed_img},
    {"type": "text", "content": "Describe this image"}
]

# Make the request
result = await model.multimodal_request(inputs, prompt="What do you see?")
```

## Key Features

1. **Unified Interface**: Same methods work across different providers
2. **Automatic Image Preprocessing**: Images are automatically converted to the required format
3. **Flexible Input Types**: Support for mixed text and image inputs
4. **Error Handling**: Consistent error responses across providers