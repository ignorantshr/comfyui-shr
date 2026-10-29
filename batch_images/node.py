import torch
from comfy_api.latest import io


class SHRBatchImages(io.ComfyNode):
    IMAGE_INPUTS = tuple(f"image{i}" for i in range(1, 101))

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SHRBatchImages",
            display_name="Image List (No Resize)",
            category="SHR/image",
            description=(
                "连接图片后自动增加输入口，按输入编号顺序合并为图片列表，批次拆为单张图片。"
                "允许不同尺寸，保留原始像素，不缩放、裁切、补边或转换通道。普通下游节点逐张处理。"
            ),
            is_input_list=True,
            inputs=[io.Autogrow.Input(
                "images",
                template=io.Autogrow.TemplateNames(
                    input=io.Image.Input("image"),
                    names=list(cls.IMAGE_INPUTS),
                    min=1,
                ),
            )],
            outputs=[io.Image.Output(display_name="image", is_output_list=True)],
        )

    @classmethod
    def execute(cls, images: io.Autogrow.Type) -> io.NodeOutput:
        if not isinstance(images, dict) or any(name not in cls.IMAGE_INPUTS for name in images):
            raise ValueError("images must map image1 through image100 to ComfyUI IMAGE lists")
        result = []
        for name in cls.IMAGE_INPUTS:
            if name not in images:
                continue
            batches = images[name]
            if not isinstance(batches, list):
                raise ValueError(f"{name} must be a ComfyUI IMAGE list")
            for index, image in enumerate(batches):
                if (
                    not isinstance(image, torch.Tensor)
                    or image.ndim != 4
                    or any(v <= 0 for v in image.shape)
                    or image.shape[-1] not in (3, 4)
                    or not image.is_floating_point()
                ):
                    raise ValueError(f"{name}[{index}] must be a non-empty floating-point BHWC RGB/RGBA tensor")
                result.extend(image.split(1, dim=0))
        return io.NodeOutput(result)
