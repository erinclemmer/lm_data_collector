import os
from typing import List

import torch
from safetensors import safe_open
from transformers.models.llama.modeling_llama import LlamaConfig, AttentionMaskConverter, LlamaModel

def layers_to_load_by_memory(
        start_layer: int,
        max_memory: int,
        num_layers: int,
        layer_size_cache: List[str]
    ) -> int:
    current_layer = start_layer
    free_memory = max_memory
    next_layer_size = layer_size_cache[current_layer]
    while True:
        current_layer += 1
        if current_layer >= num_layers:
            break
        free_memory -= next_layer_size
        next_layer_size = layer_size_cache[current_layer]
        if free_memory - next_layer_size < 0:
            break
    end_layer = current_layer - 1
    return end_layer

def load_shard_tensor(
        layer_file_cache: dict, 
        model_dir: str,
        layer_name: str, 
        device: str,
        dtype: torch.dtype
    ) -> torch.Tensor:
    if layer_name not in layer_file_cache:
        raise ValueError(f'Could not find layer file for layer {layer_name}')
    file = layer_file_cache[layer_name]
    shard: dict = safe_open(os.path.join(model_dir, file), framework='pt', device=device)
    return shard.get_tensor(layer_name).to(dtype)

def update_causal_mask(
        config: LlamaConfig,
        input_tensor: torch.Tensor,
        cache_position: torch.Tensor
    ):
    if (
        config._attn_implementation == "sdpa"
    ):
        if AttentionMaskConverter._ignore_causal_mask_sdpa(
            None,
            inputs_embeds=input_tensor,
            past_key_values_length=0,
            sliding_window=config.sliding_window,
            is_training=False,
        ):
            return None

    # In case the provided `attention` mask is 2D, we generate a causal mask here (4D).
    return LlamaModel._prepare_4d_causal_attention_mask_with_cache_position(
        None,
        sequence_length=input_tensor.shape[1],
        target_length=input_tensor.shape[1],
        dtype=input_tensor.dtype,
        device=input_tensor.device,
        cache_position=cache_position,
        batch_size=input_tensor.shape[0],
        config=config,
        past_key_values=None,
    )