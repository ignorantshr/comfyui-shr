from comfy_api.latest import ComfyExtension, io

from .resizer.node import SHRQwenImage21Resizer
from .batch_images.node import SHRBatchImages
from .show_values.node import SHRShowValues

WEB_DIRECTORY = "./web"


class SHRExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SHRQwenImage21Resizer, SHRBatchImages, SHRShowValues]


async def comfy_entrypoint() -> SHRExtension:
    return SHRExtension()
