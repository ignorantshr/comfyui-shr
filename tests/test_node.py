"""Real ComfyUI V3 integration; opt in with COMFYUI_PATH (no mocks)."""

import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import unittest


@unittest.skipUnless(os.environ.get("COMFYUI_PATH"), "set COMFYUI_PATH for real ComfyUI tests")
class NodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(os.environ["COMFYUI_PATH"]).resolve()))
        import torch
        cls.torch = torch
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "comfyui_shr", root / "__init__.py",
            submodule_search_locations=[str(root)],
        )
        cls.plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.plugin
        spec.loader.exec_module(cls.plugin)
        cls.node = cls.plugin.SHRQwenImage21Resizer

    def run_node(self, image, resolution=64, fit="crop", method="bilinear"):
        return self.node.execute(image, resolution, fit, method).result

    def test_extension_and_schema(self):
        extension = asyncio.run(self.plugin.comfy_entrypoint())
        self.assertEqual(asyncio.run(extension.get_node_list()), [self.node, self.plugin.SHRBatchImages, self.plugin.SHRShowValues])
        schema = self.node.define_schema()
        self.assertEqual(schema.node_id, "SHRQwenImage21Resizer")
        self.assertEqual(len(schema.outputs), 4)
        # Exercise ComfyUI's V3 -> execution schema conversion as well.
        self.assertIn("resolution", self.node.INPUT_TYPES()["required"])

    def test_noop_preserves_tensor_exactly(self):
        image = self.torch.rand(2, 64, 64, 4)
        result, w, h, r = self.run_node(image)
        self.assertIs(result, image)
        self.assertEqual((w, h, r), (64, 64, 64))

    def test_show_values_keeps_lists_separate_and_returns_text(self):
        node = self.plugin.SHRShowValues
        self.assertIn("values", node.INPUT_TYPES()["required"])
        self.assertTrue(node.INPUT_IS_LIST)
        self.assertTrue(node.OUTPUT_NODE)
        self.assertEqual(node.RETURN_TYPES, ["STRING"])
        values = {"value3": [1, 1], "value1": [512, 768], "value2": [512, 1024]}
        output = node.execute(values, ["width\nheight\nbatch_size"])
        expected = "width: [512, 768]\nheight: [512, 1024]\nbatch_size: [1, 1]"
        self.assertEqual(output.result, (expected,))
        self.assertEqual(output.ui.as_dict(), {"text": (expected,)})
        self.assertEqual(values["value1"], [512, 768])

    def test_show_values_order_validation_and_bounded_tensor_summary(self):
        node = self.plugin.SHRShowValues
        tensor = self.torch.empty(1, 10, 20, 3, device="meta")
        values = {"value10": [tensor], "value2": [None], "value1": [True]}
        text, = node.execute(values, [""]).result
        self.assertTrue(text.startswith("value1: True\nvalue2: None\nvalue10: Tensor(shape=(1, 10, 20, 3)"))
        self.assertIn("device=meta", text)
        text, = node.execute({"value1": ["x" * 10000]}, [""]).result
        self.assertLess(len(text), 600)
        for values, labels in (([], [""]), ({"bad": []}, [""]),
                               ({"value1": 1}, [""]), ({}, []), ({}, [1])):
            with self.assertRaises(ValueError):
                node.execute(values, labels)

    def test_image_list_preserves_mixed_images_and_order(self):
        node = self.plugin.SHRBatchImages
        schema = node.define_schema()
        self.assertTrue(schema.is_input_list)
        self.assertTrue(schema.outputs[0].is_output_list)
        self.assertIn("images", node.INPUT_TYPES()["required"])
        template = schema.inputs[0].template
        self.assertEqual(template.min, 1)
        self.assertEqual(template.names, [f"image{i}" for i in range(1, 101)])
        self.assertTrue(node.INPUT_IS_LIST)
        self.assertEqual(node.OUTPUT_IS_LIST, [True])
        first = self.torch.rand(2, 8, 12, 3)
        second = self.torch.rand(3, 9, 7, 4, dtype=self.torch.float64)
        originals = first.clone(), second.clone()
        result, = node.execute({"image1": [first], "image2": [second]}).result
        self.assertEqual(len(result), 5)
        for actual, expected in zip(result, [*first.split(1), *second.split(1)]):
            self.assertEqual(actual.shape, expected.shape)
            self.assertEqual(actual.dtype, expected.dtype)
            self.assertEqual(actual.device, expected.device)
            self.assertTrue(self.torch.equal(actual, expected))
        self.assertTrue(self.torch.equal(first, originals[0]))
        self.assertTrue(self.torch.equal(second, originals[1]))
        # A previous list output can be connected without duplicating images.
        chained, = node.execute({"image1": result, "image2": [first]}).result
        self.assertEqual(len(chained), 7)
        for actual, expected in zip(chained[:5], result):
            self.assertTrue(self.torch.equal(actual, expected))
        self.assertEqual(node.execute({"image1": [], "image2": []}).result, ([],))

    def test_image_list_dynamic_inputs_follow_numeric_order(self):
        node = self.plugin.SHRBatchImages
        inputs = {f"image{i}": [self.torch.full((1, i, 2, 3), float(i))]
                  for i in (10, 3, 1, 100, 2)}
        result, = node.execute(inputs).result
        self.assertEqual([image.shape[1] for image in result], [1, 2, 3, 10, 100])
        for image, index in zip(result, (1, 2, 3, 10, 100)):
            self.assertTrue(self.torch.equal(image, inputs[f"image{index}"][0]))
        for invalid in ([], {"image101": []}, {"other": []}):
            with self.assertRaises(ValueError):
                node.execute(invalid)

    def test_image_list_rejects_invalid_images(self):
        first = self.torch.zeros(1, 8, 12, 3)
        invalid = [None, self.torch.zeros(8, 12, 3),
                   self.torch.zeros(0, 8, 12, 3), self.torch.zeros(1, 8, 12, 1),
                   first.int()]
        for other in invalid:
            for inputs in (([first], [other]), ([other], [first])):
                with self.assertRaises(ValueError):
                    self.plugin.SHRBatchImages.execute(dict(zip(("image1", "image2"), inputs)))
        with self.assertRaises(ValueError):
            self.plugin.SHRBatchImages.execute({"image1": first})

    def test_crop_uses_native_geometry_and_preserves_batch(self):
        import comfy.utils
        image = self.torch.rand(2, 60, 100, 3)
        original = image.clone()
        result, w, h, _ = self.run_node(image)
        expected = comfy.utils.common_upscale(image.movedim(-1, 1), w, h, "bilinear", "center").movedim(1, -1)
        self.assertTrue(self.torch.equal(result, expected))
        self.assertTrue(self.torch.equal(image, original))
        self.assertEqual(result.shape, (2, h, w, 3))

    def test_pad_retains_content_and_transparent_border(self):
        image = self.torch.ones(2, 40, 100, 4)
        result, w, h, _ = self.run_node(image, fit="pad")
        scale = min(w / 100, h / 40)
        sw, sh = round(100 * scale), round(40 * scale)
        left, top = (w - sw) // 2, (h - sh) // 2
        self.assertTrue(self.torch.allclose(result[:, top:top+sh, left:left+sw], self.torch.ones(2, sh, sw, 4)))
        self.assertAlmostEqual(result.sum().item(), 2 * sh * sw * 4, delta=0.01)
        self.assertGreater(w*h, sw*sh)

    def test_all_native_methods_rgb_and_rgba(self):
        for channels in (3, 4):
            for method in ("lanczos", "bicubic", "bilinear", "area", "nearest-exact"):
                for fit in ("crop", "pad"):
                    image = self.torch.rand(2, 45, 77, channels)
                    result, w, h, _ = self.run_node(image, fit=fit, method=method)
                    self.assertEqual(result.shape, (2, h, w, channels))
                    self.assertEqual(result.dtype, image.dtype)
                    self.assertEqual(result.device, image.device)
                    self.assertTrue(self.torch.isfinite(result).all())

    def test_zero_resolution(self):
        result, w, h, r = self.run_node(self.torch.rand(1, 108, 192, 3), resolution=0)
        self.assertEqual((w, h, r), (192, 96, 0))
        self.assertEqual(result.shape, (1, 96, 192, 3))

    def test_invalid_tensor_and_options(self):
        for image in (self.torch.zeros(5), self.torch.zeros(0, 4, 4, 3), self.torch.zeros(1, 4, 4, 1)):
            with self.assertRaises(ValueError):
                self.run_node(image)
        with self.assertRaises(ValueError):
            self.run_node(self.torch.zeros(1, 4, 4, 3), fit="unknown")


if __name__ == "__main__":
    unittest.main()
