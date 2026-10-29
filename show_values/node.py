import reprlib

import torch
from comfy_api.latest import io, ui


class ValueRepr(reprlib.Repr):
    def repr_instance(self, value, level):
        if isinstance(value, torch.Tensor):
            return f"Tensor(shape={tuple(value.shape)}, dtype={value.dtype}, device={value.device})"
        return super().repr_instance(value, level)


class SHRShowValues(io.ComfyNode):
    VALUE_INPUTS = tuple(f"value{i}" for i in range(1, 101))

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SHRShowValues",
            display_name="SHR Show Values",
            category="SHR/utils",
            description="自动增加多值输入口，按输入编号逐行显示，不展开合并不同输入的列表。张量只显示形状、类型和设备。长内容会截断。",
            is_input_list=True,
            is_output_node=True,
            inputs=[
                io.Autogrow.Input("values", template=io.Autogrow.TemplateNames(
                    input=io.AnyType.Input("value"), names=list(cls.VALUE_INPUTS), min=1,
                )),
                io.String.Input("labels", default="", multiline=True,
                                tooltip="可选，每行一个标签，依次对应 value1、value2…；空行使用默认名称。"),
            ],
            outputs=[io.String.Output(display_name="text")],
        )

    @classmethod
    def execute(cls, values: io.Autogrow.Type, labels) -> io.NodeOutput:
        if not isinstance(values, dict) or any(name not in cls.VALUE_INPUTS for name in values):
            raise ValueError("values must map value1 through value100 to ComfyUI input lists")
        if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], str):
            raise ValueError("labels must contain one text value")
        names = labels[0].splitlines()
        formatter = ValueRepr()
        formatter.maxlist = formatter.maxtuple = 30
        formatter.maxstring = 500
        formatter.maxother = 160
        formatter.maxlevel = 4
        lines = []
        for index, name in enumerate(cls.VALUE_INPUTS):
            if name not in values:
                continue
            items = values[name]
            if not isinstance(items, list):
                raise ValueError(f"{name} must be a ComfyUI input list")
            label = names[index].strip()[:100] if index < len(names) else ""
            value = items[0] if len(items) == 1 else items
            lines.append(f"{label or name}: {formatter.repr(value)[:4000]}")
        text = "\n".join(lines)
        return io.NodeOutput(text, ui=ui.PreviewText(text))
