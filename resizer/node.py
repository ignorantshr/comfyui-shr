from comfy_api.latest import io

from .image_ops import FIT_MODES, METHODS, prepare_image


class SHRQwenImage21Resizer(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SHRQwenImage21Resizer",
            display_name="Qwen Image 2.1 Resizer",
            category="SHR/image",
            description=(
                "为 Qwen Image 2.1 编辑准备尺寸稳定的预处理节点，支持单张图片或同尺寸图片批次。\n"
                "Qwen 编码节点收到图片后，还会根据自己的 resolution 计算一次需要的尺寸。我们的节点提前选好尺寸，让它算出来的结果与收到的图片一样。\n"
                "将 image 输出接到 TextEncodeQwenImage21 的参考图，resolution 输出接到同名输入。\n"
                "尺寸已符合要求时直接返回原图。尺寸对齐不保证模型生成内容逐像素不变。"
            ),
            inputs=[
                io.Image.Input(
                    "image",
                    tooltip=(
                        "支持单张图片，或上游传入的同尺寸图片批次；批次内每张图使用相同参数处理，输出数量不变。\n"
                        "支持 RGB 彩色图和 RGBA 带透明通道的图。\n"
                        "已有独立遮罩时，需同步对遮罩应用相同的缩放、裁切或补边。"
                    ),
                ),
                io.Int.Input(
                    "resolution", default=1440, min=0, max=4096, step=32,
                    tooltip=(
                        "预设的目标像素总量，不是宽度或长边。\n"
                        "正数：面积约为 resolution²；例如设为 1440，输出图片约为 207 万像素。节点尽量保留原图比例，"
                        "并调整到 QwenImage2.1 在相同 resolution 设置下可直接使用的尺寸。"
                        "根据原图比例选择编码器不会再次缩放的尺寸。\n"
                        "0：仅将原图宽高调整到最近的 32 倍数。\n"
                        "将本节点的 resolution 输出连接到 Qwen 编码节点的同名输入，即可自动同步，无需分别设置。\n"
                        "数值越大，通常推理开销越大。"
                    ),
                ),
                io.Combo.Input(
                    "fit", options=list(FIT_MODES), default="crop",
                    tooltip=(
                        "选择图片适配目标画布的方式。\n"
                        "crop：中心裁切并缩放，填满画布，可能裁掉边缘内容。\n"
                        "pad：按比例缩放后居中补边，保留完整构图；RGB 补黑，RGBA 补透明黑。"
                    ),
                ),
                io.Combo.Input(
                    "upscale_method", options=list(METHODS), default="lanczos",
                    tooltip=(
                        "放大和缩小时使用的像素插值算法，不调用 AI 超分模型。\n"
                        "lanczos：默认，适合照片，细节清晰；原生实现经过 8-bit 图像转换。\n"
                        "bicubic：较平滑，兼顾细节，适合通用缩放。\n"
                        "bilinear：速度快，结果偏柔和。\n"
                        "area：适合缩小图片，通过区域平均减少锯齿。\n"
                        "nearest-exact：不混合像素颜色，适合像素画，放大后有块状感。\n"
                        "尺寸已符合要求时不执行插值。"
                    ),
                ),
            ],
            outputs=[
                io.Image.Output(
                    display_name="image",
                    tooltip="处理后的图片，可接到 Qwen 编码节点的 image_1。与生成结果对比时，以此图为基准。",
                ),
                io.Int.Output(display_name="width", tooltip="处理后的实际宽度，单位为像素，始终为 32 的倍数。"),
                io.Int.Output(display_name="height", tooltip="处理后的实际高度，单位为像素，始终为 32 的倍数。"),
                io.Int.Output(
                    display_name="resolution",
                    tooltip="原样输出本节点的 resolution。连接到 Qwen 编码节点的同名输入，使两者使用相同的尺寸规则。",
                ),
            ],
        )

    @classmethod
    def execute(cls, image, resolution, fit, upscale_method) -> io.NodeOutput:
        return io.NodeOutput(*prepare_image(image, resolution, fit, upscale_method))
