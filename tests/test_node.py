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
        self.assertEqual(asyncio.run(extension.get_node_list()), [self.node])
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
