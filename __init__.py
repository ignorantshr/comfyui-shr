from comfy_api.latest import ComfyExtension, io

from .resizer.node import SHRQwenImage21Resizer


class SHRExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SHRQwenImage21Resizer]


async def comfy_entrypoint() -> SHRExtension:
    return SHRExtension()
