from __future__ import annotations

from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch

from app.model_runtime import gpu_residency
from app.models import SdxlT2IRequest
from app.service import image as image_service


class GpuResidencyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        gpu_residency.reset_gpu_residency_for_tests()

    async def asyncTearDown(self) -> None:
        gpu_residency.reset_gpu_residency_for_tests()

    async def test_two_gpus_assign_llm_and_image_to_dedicated_devices(self) -> None:
        with patch.object(gpu_residency, "get_cuda_device_count", return_value=2):
            self.assertEqual(gpu_residency.get_llm_cuda_device_id(True), 0)
            self.assertEqual(gpu_residency.get_image_cuda_device_id(), 1)

    async def test_two_gpus_release_only_previous_llm_on_llm_key_change(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=2):
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                1,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-b",),
                lambda device_id: released.append(("llm-b", device_id)),
            ):
                pass

        self.assertEqual(released, [("llm-a", 0)])

    async def test_two_gpus_release_only_previous_image_on_image_key_change(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=2):
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                1,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                1,
                ("image-b",),
                lambda device_id: released.append(("image-b", device_id)),
            ):
                pass

        self.assertEqual(released, [("image-a", 1)])

    async def test_one_gpu_releases_llm_when_image_needs_gpu(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=1):
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                0,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass

        self.assertEqual(released, [("llm-a", 0)])

    async def test_one_gpu_releases_image_when_llm_needs_gpu(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=1):
            async with gpu_residency.acquire_gpu_model(
                "image",
                0,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass

        self.assertEqual(released, [("image-a", 0)])

    async def test_cpu_llm_does_not_release_gpu_image(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=1):
            async with gpu_residency.acquire_gpu_model(
                "image",
                0,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "llm",
                gpu_residency.get_llm_cuda_device_id(False),
                ("llm-cpu",),
                lambda device_id: released.append(("llm-cpu", device_id)),
            ):
                pass

        self.assertEqual(released, [])

    async def test_multi_gpu_lease_releases_models_on_all_participating_devices(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=2):
            async with gpu_residency.acquire_gpu_model(
                "llm",
                0,
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                1,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model_multi(
                "llm",
                (1, 0),
                ("llm-b",),
                lambda device_id: released.append(("llm-b", device_id)),
            ):
                pass

        self.assertEqual(released, [("llm-a", 0), ("image-a", 1)])

    async def test_single_gpu_lease_releases_multi_gpu_model_once_and_clears_all_devices(self) -> None:
        released: list[tuple[str, int]] = []

        with patch.object(gpu_residency, "get_cuda_device_count", return_value=2):
            async with gpu_residency.acquire_gpu_model_multi(
                "llm",
                (0, 1),
                ("llm-a",),
                lambda device_id: released.append(("llm-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                1,
                ("image-a",),
                lambda device_id: released.append(("image-a", device_id)),
            ):
                pass
            async with gpu_residency.acquire_gpu_model(
                "image",
                0,
                ("image-b",),
                lambda device_id: released.append(("image-b", device_id)),
            ):
                pass

        self.assertEqual(released, [("llm-a", 1)])


class SdxlT2IRequestTest(unittest.TestCase):
    def test_request_model_does_not_expose_manual_device_id(self) -> None:
        self.assertNotIn("device_id", SdxlT2IRequest.model_fields)

    def test_request_model_exposes_output_format(self) -> None:
        self.assertIn("format", SdxlT2IRequest.model_fields)
        self.assertEqual(SdxlT2IRequest(prompts=["a prompt"]).format, "png")


class SdxlT2IServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_generation_returns_requested_jpg_format(self) -> None:
        from PIL import Image

        with tempfile.NamedTemporaryFile() as ckpt_file:
            generated_image = Image.new("RGBA", (8, 8), (255, 0, 0, 128))

            with (
                patch.object(image_service.settings, "sdxl_ckpt_path", ckpt_file.name),
                patch.object(
                    image_service,
                    "generate_images_batch",
                    return_value=([generated_image], [123]),
                ),
            ):
                response = await image_service.generate_sdxl_t2i_images(
                    SdxlT2IRequest(prompts=["a prompt"], format="jpeg"),
                )

        self.assertEqual(response.count, 1)
        self.assertEqual(response.images[0].format, "jpg")
        with Image.open(BytesIO(response.images[0].image_bytes)) as encoded_image:
            self.assertEqual(encoded_image.format, "JPEG")
            self.assertEqual(encoded_image.mode, "RGB")

    async def test_generation_rejects_unsupported_format(self) -> None:
        with self.assertRaises(ValueError) as context:
            await image_service.generate_sdxl_t2i_images(
                SdxlT2IRequest(prompts=["a prompt"], format="webp"),
            )

        self.assertEqual(str(context.exception), "unsupported image format")


if __name__ == "__main__":
    unittest.main()
