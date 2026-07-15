from PIL import Image

from export_worker import ExportWorker


def test_export_worker_honors_selected_jpg_quality(tmp_path):
    source = tmp_path / "noise.png"
    image = Image.effect_noise((512, 512), 100).convert("RGB")
    image.save(source)
    sizes = {}

    for quality in (20, 95):
        output_dir = tmp_path / str(quality)
        output_dir.mkdir()
        results = []
        worker = ExportWorker(
            [str(source)], str(output_dir), "jpg", False, quality,
            renderer=lambda _path, source_image=image: [source_image.copy()],
        )
        worker.succeeded.connect(results.append)
        worker.run()
        assert results
        sizes[quality] = results[0]["size_bytes"]

    assert sizes[95] > sizes[20]
