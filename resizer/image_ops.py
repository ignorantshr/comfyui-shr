"""Use ComfyUI's native resize implementation on BHWC IMAGE batches."""

import torch
import comfy.utils

from .sizes import select_size

METHODS = ("lanczos", "bicubic", "bilinear", "area", "nearest-exact")
FIT_MODES = ("crop", "pad")


def prepare_image(image, resolution, fit, upscale_method):
    if (
        not isinstance(image, torch.Tensor)
        or image.ndim != 4
        or any(v <= 0 for v in image.shape)
        or image.shape[-1] not in (3, 4)
        or not image.is_floating_point()
    ):
        raise ValueError("image must be a non-empty floating-point BHWC RGB/RGBA tensor")
    if fit not in FIT_MODES or upscale_method not in METHODS:
        raise ValueError("unsupported fit mode or upscale method")
    _, height, width, _ = image.shape
    target_w, target_h = select_size(width, height, resolution)
    if (width, height) == (target_w, target_h):
        return image, target_w, target_h, resolution

    samples = image.movedim(-1, 1)
    if fit == "crop":
        result = comfy.utils.common_upscale(
            samples, target_w, target_h, upscale_method, "center"
        )
    else:
        scale = min(target_w / width, target_h / height)
        scaled_w = max(1, min(target_w, round(width * scale)))
        scaled_h = max(1, min(target_h, round(height * scale)))
        resized = comfy.utils.common_upscale(
            samples, scaled_w, scaled_h, upscale_method, "disabled"
        )
        left = (target_w - scaled_w) // 2
        top = (target_h - scaled_h) // 2
        # Black for RGB, transparent black for RGBA; retain batch/device/dtype.
        result = resized.new_zeros((image.shape[0], image.shape[-1], target_h, target_w))
        result[:, :, top : top + scaled_h, left : left + scaled_w] = resized
    return result.movedim(1, -1), target_w, target_h, resolution
