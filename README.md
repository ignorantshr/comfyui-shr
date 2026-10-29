# comfyui-shr

SHR 的 ComfyUI 自定义节点包，使用原生 V3 节点 API。当前包含 **Qwen Image 2.1 Resizer**，为 Qwen 图像编辑准备尺寸稳定的画布，缩放复用 `comfy.utils.common_upscale`。

## 节点与目录

```text
comfyui-shr/
├── __init__.py          # 节点包入口，统一注册节点
├── resizer/
│   ├── __init__.py
│   ├── node.py          # Qwen Image 2.1 Resizer 节点定义
│   ├── sizes.py         # 尺寸选择
│   └── image_ops.py     # 原生图像处理
└── tests/
```

后续节点可作为独立模块添加，并在根目录的 `SHRExtension.get_node_list()` 中注册。节点 ID 使用 `SHR` 前缀；当前 Resizer 的 ID 为 `SHRQwenImage21Resizer`。

## 安装

需要包含 `TextEncodeQwenImage21` 的较新 ComfyUI。

把本项目目录放入或软链接到 `ComfyUI/custom_nodes/comfyui-shr`，然后重启 ComfyUI。在节点搜索中查找 **Qwen Image 2.1 Resizer**，分类为 `SHR/image`。

安装目录名统一使用 `comfyui-shr`。

本机软链接示例（将第一个路径替换为你的 ComfyUI 路径）：

```bash
COMFYUI_DIR=/absolute/path/to/ComfyUI
ln -s /Users/haoran.shi/projects/mine/comfyui-shr "$COMFYUI_DIR/custom_nodes/comfyui-shr"
```

## 工作流接法

```text
Load Image → Resizer.image → TextEncodeQwenImage21.image_1
             └─ resolution ─────→ TextEncodeQwenImage21.resolution

TextEncodeQwenImage21.positive / negative / latent → KSampler → VAE Decode
```

将编码节点的 `resolution` 控件转换为输入，再连接本节点的同名输出。采样使用编码节点输出的 `latent`，让生成画布跟随第一张参考图。

若必须手动创建采样 latent，使用本节点输出的 `width`、`height`，并选择适配 Qwen Image 2.1 的 latent 节点。多参考图时，编辑目标应放在 `image_1`。

## 参数

| 参数 | 含义 |
|---|---|
| `image` | ComfyUI IMAGE，支持整批 RGB / RGBA 图片 |
| `resolution` | 默认 1440；正数表示目标面积约为 `resolution²`，支持 32～4096、步长 32；0 仅对齐到 32 |
| `fit = crop` | 使用原生中心裁切和缩放，填满目标画布；可能丢失边缘内容 |
| `fit = pad` | 按比例缩放后居中补边；RGB 补黑，RGBA 补透明黑 |
| `upscale_method` | 原生插值方式，默认 lanczos；也支持 bicubic、bilinear、area、nearest-exact |

输出：`image`、`width`、`height`、`resolution`。

两种使用方式：

- **控制像素预算**：选正数 resolution，并与 Qwen 编码节点保持一致。节点寻找编码器不会再次缩放的尺寸。
- **尽量保留已有画布尺寸**：本节点和编码节点都设为 0，只将宽高调整到最近的 32 倍数。

4096 是参数范围，不是推荐画质档位；高像素预算需要更多推理资源。尺寸已满足条件时直接返回原 IMAGE，不做重复插值。其它情况下，精度和插值行为遵循 ComfyUI 原生实现；其中 lanczos 会经过 Pillow 的 8-bit 图像处理。

## 设计依据

ComfyUI 的 `TextEncodeQwenImage21` 对正数 resolution 使用以下尺寸转换，并在尺寸相同时跳过缩放：

```python
ratio = width / height
new_width = max(32, round(sqrt(resolution**2 * ratio) / 32) * 32)
new_height = max(32, round(sqrt(resolution**2 / ratio) / 32) * 32)
```

本节点寻找该转换的不动点：转换后的尺寸等于输入尺寸。优先选择最接近原图宽高比的尺寸，比例误差相同时优先接近目标面积；不额外偏向预设比例或假设训练分桶。

候选搜索覆盖该公式的全部不动点，而非只尝试一次 resize。令尺寸为 `32k × 32m`、resolution 为 `32n`：不动点至少有一边不超过 n，且整数面积 `km` 落在 `[n²−n, n²+n]`。枚举这一区域，再用编码器原式校验。

设计受 [ComfyUI-BlueBox](https://github.com/zhoutingxi/ComfyUI-BlueBox) 的不动点画布思路启发；本项目独立实现尺寸搜索和标准节点接入。所依据的 [ComfyUI 编码节点](https://github.com/Comfy-Org/ComfyUI/blob/6bfaacc67c2103481e5f0c84d75257cd0581d86a/comfy_extras/nodes_qwen.py#L144) 决定缩放规则。

保证范围是**画布尺寸不再被编码节点改动**，不保证模型生成的内容逐像素不变。与结果比较时，应使用本节点输出的图，而非裁切前原图。本节点不处理独立 MASK；已有遮罩必须同步应用相同几何变换后才能使用。

## 验证

纯尺寸算法测试（仅需 Python 标准库）：

```bash
python3 -m unittest discover -s tests -v
```

完整节点测试需要 ComfyUI 源码及其 Python 依赖，使用同一个 Python 环境执行：

```bash
COMFYUI_PATH=/absolute/path/to/ComfyUI python -m unittest discover -s tests -v
```

未指定 `COMFYUI_PATH` 时会跳过节点集成测试。测试不下载模型、不进行生成推理。

2026-10-26 验证：使用 ComfyUI `0b05cd8a3683cbf0c291b1472bb8b64da41de9ae` 的真实 V3 API 与缩放实现，12 项测试通过。包含注册入口、执行 schema、RGB/RGBA 批处理、全部插值方式、中心裁切、补边、原样返回及尺寸不动点。未启动完整 Web UI 或进行 Qwen 模型推理。
