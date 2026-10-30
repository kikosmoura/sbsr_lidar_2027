"""Testes espaciais e de transferência com servidor HTTP local, sem GeoSampa."""

import io
import errno
import random
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import requests
from shapely.geometry import MultiPolygon, Polygon, box

import baixar_lidar_geosampa as app


def point_zip(size=512):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("MDT_3312-431_1000.laz", b"LASF" + random.Random(42).randbytes(size))
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests += 1
        body = self.server.body
        if self.path == "/html" or (self.path == "/retry" and self.server.requests == 1):
            body = b"<html>indisponivel</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
        elif self.path == "/fake":
            body = b"<html>download inexistente</html>"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
        else:
            range_header = self.headers.get("Range")
            if range_header and self.path != "/ignore":
                start = int(range_header.removeprefix("bytes=").removesuffix("-"))
                if start >= len(body):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(body)}")
                    self.end_headers()
                    return
                self.send_response(206)
                reported = start + 1 if self.path == "/bad-range" else start
                self.send_header("Content-Range", f"bytes {reported}-{len(body)-1}/{len(body)}")
                body = body[start:]
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.path == "/truncated":
            body = body[:1024 * 1024 + 10]
            self.close_connection = True
        self.wfile.write(body)


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "3312-431.zip"
        self.partial = self.path.with_suffix(".zip.part")
        self.server.body = point_zip()
        self.server.requests = 0
        self.session = requests.Session()
        self.addCleanup(self.session.close)

    def task(self, route="/zip"):
        return {"arquivo": str(self.path), "url": self.base + route}

    def test_download_validate_and_reuse_without_network(self):
        self.assertEqual(app.download(self.session, self.task(), 1, 3), ("baixado", len(self.server.body)))
        self.assertEqual(self.path.read_bytes(), self.server.body)
        self.assertFalse(self.partial.exists())
        self.assertEqual(app.download(self.session, self.task(), 1, 3)[0], "existente")
        self.assertEqual(self.server.requests, 1)

    def test_resumes_range(self):
        self.partial.write_bytes(self.server.body[:100])
        app.download(self.session, self.task(), 1, 3)
        self.assertEqual(self.path.read_bytes(), self.server.body)

    def test_restarts_when_range_ignored(self):
        self.partial.write_bytes(self.server.body[:100])
        app.download(self.session, self.task("/ignore"), 1, 3)
        self.assertEqual(self.path.read_bytes(), self.server.body)

    def test_complete_partial_is_promoted_without_network(self):
        self.partial.write_bytes(self.server.body)
        self.assertEqual(app.download(self.session, self.task(), 1, 3)[0], "baixado")
        self.assertEqual(self.server.requests, 0)

    def test_416_for_complete_partial(self):
        self.partial.write_bytes(self.server.body)
        self.assertEqual(app.transfer(self.session, self.base + "/zip", self.partial, 3), len(self.server.body))

    def test_416_for_corrupt_partial_is_removed(self):
        self.partial.write_bytes(b"X" * len(self.server.body))
        with self.assertRaises(app.DownloadError):
            app.transfer(self.session, self.base + "/zip", self.partial, 3)
        self.assertFalse(self.partial.exists())

    def test_html_and_disguised_html_are_rejected(self):
        for route in ("/html", "/fake"):
            with self.subTest(route=route), self.assertRaises(app.DownloadError):
                app.download(self.session, self.task(route), 1, 3)
            self.assertFalse(self.path.exists())
            self.assertFalse(self.partial.exists())

    def test_malformed_content_range_is_rejected(self):
        self.partial.write_bytes(self.server.body[:100])
        with self.assertRaises(app.DownloadError):
            app.download(self.session, self.task("/bad-range"), 1, 3)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.partial.exists())

    def test_corrupt_zip_crc_is_rejected(self):
        body = bytearray(self.server.body)
        location = body.index(b"LASF") + 4
        body[location] ^= 255
        self.server.body = bytes(body)
        with self.assertRaises(app.DownloadError):
            app.download(self.session, self.task(), 1, 3)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.partial.exists())

    def test_wrong_las_header_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("dados.laz", b"not a point cloud")
        self.server.body = buffer.getvalue()
        with self.assertRaises(app.DownloadError):
            app.download(self.session, self.task(), 1, 3)

    def test_interruption_keeps_partial_then_resumes(self):
        self.server.body = point_zip(size=2 * 1024 * 1024)
        with self.assertRaises(requests.RequestException):
            app.download(self.session, self.task("/truncated"), 1, 3)
        self.assertFalse(self.path.exists())
        self.assertGreater(self.partial.stat().st_size, 0)
        self.assertLess(self.partial.stat().st_size, len(self.server.body))
        app.download(self.session, self.task(), 1, 3)
        self.assertEqual(self.path.read_bytes(), self.server.body)

    def test_retry_after_server_error(self):
        with patch.object(app.time, "sleep"):
            app.download(self.session, self.task("/retry"), 2, 3)
        self.assertEqual(self.server.requests, 2)
        self.assertEqual(self.path.read_bytes(), self.server.body)

    def test_copies_previous_valid_zip_without_network_and_preserves_original(self):
        previous = Path(self.temp.name) / "antiga"
        original = previous / self.path.parent.name / self.path.name
        original.parent.mkdir(parents=True)
        original.write_bytes(self.server.body)
        status, size = app.download(self.session, self.task(), 1, 3, previous)
        self.assertEqual((status, size), ("reaproveitado", len(self.server.body)))
        self.assertEqual(self.path.read_bytes(), self.server.body)
        self.assertEqual(original.read_bytes(), self.server.body)
        self.assertFalse(self.partial.exists())
        self.assertEqual(self.server.requests, 0)

    def test_copies_previous_partial_then_resumes_and_preserves_original(self):
        previous = Path(self.temp.name) / "antiga"
        original = previous / self.path.parent.name / self.partial.name
        original.parent.mkdir(parents=True)
        original.write_bytes(self.server.body[:100])
        app.download(self.session, self.task(), 1, 3, previous)
        self.assertEqual(self.path.read_bytes(), self.server.body)
        self.assertEqual(original.read_bytes(), self.server.body[:100])
        self.assertEqual(self.server.requests, 1)

    def test_corrupt_previous_zip_is_not_reused(self):
        previous = Path(self.temp.name) / "antiga"
        original = previous / self.path.parent.name / self.path.name
        original.parent.mkdir(parents=True)
        original.write_bytes(b"invalid")
        app.download(self.session, self.task(), 1, 3, previous)
        self.assertEqual(self.path.read_bytes(), self.server.body)
        self.assertEqual(original.read_bytes(), b"invalid")
        self.assertEqual(self.server.requests, 1)

    def test_full_destination_during_copy_preserves_original(self):
        previous = Path(self.temp.name) / "antiga"
        original = previous / self.path.parent.name / self.path.name
        original.parent.mkdir(parents=True)
        original.write_bytes(self.server.body)
        with patch.object(app.shutil, "copyfile", side_effect=OSError(errno.ENOSPC, "No space left")):
            with self.assertRaises(OSError):
                app.download(self.session, self.task(), 1, 3, previous)
        self.assertEqual(original.read_bytes(), self.server.body)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.server.requests, 0)


class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.grid_path = self.root / "grade.gpkg"
        self.aoi_path = self.root / "aoi.gpkg"
        self.grid = gpd.GeoDataFrame(
            {"cd_quadric": ["3312-431", "3312-432", "3312-433"], "an_levanta": [2020]*3},
            geometry=[box(330000, 7397000, 330100, 7397100),
                      box(330100, 7397000, 330200, 7397100),
                      box(330300, 7397000, 330400, 7397100)], crs="EPSG:31983"
        )
        self.grid.to_file(self.grid_path)
        self.aoi = gpd.GeoDataFrame(geometry=[
            box(330010, 7397010, 330020, 7397020),
            box(330030, 7397030, 330040, 7397040),
            MultiPolygon([box(330090, 7397090, 330110, 7397110), box(331000, 7398000, 331010, 7398010)])
        ], crs="EPSG:31983")
        self.aoi.to_file(self.aoi_path)

    def test_intersection_multipolygons_deduplication_and_full_tiles(self):
        selected = app.select_tiles(self.aoi_path, self.grid_path)
        self.assertEqual(selected.quadricula.tolist(), ["3312-431", "3312-432"])
        self.assertTrue(selected.geometry.iloc[0].equals(self.grid.geometry.iloc[0]))
        self.assertEqual(len(app.make_plan(selected, ["MDT", "MDS"], self.root)), 4)

    def test_reprojection(self):
        self.aoi.to_crs(4326).to_file(self.root / "latlon.gpkg")
        selected = app.select_tiles(self.root / "latlon.gpkg", self.grid_path)
        self.assertEqual(selected.quadricula.tolist(), ["3312-431", "3312-432"])

    def test_boundary_contact_counts_as_intersection(self):
        gpd.GeoDataFrame(geometry=[box(330200, 7397020, 330210, 7397030)], crs=self.grid.crs).to_file(self.aoi_path)
        selected = app.select_tiles(self.aoi_path, self.grid_path)
        self.assertEqual(selected.quadricula.tolist(), ["3312-432"])

    def test_invalid_polygon_is_repaired(self):
        bowtie = Polygon([(330010, 7397010), (330030, 7397030), (330010, 7397030),
                           (330030, 7397010), (330010, 7397010)])
        gpd.GeoDataFrame(geometry=[bowtie], crs=self.grid.crs).to_file(self.aoi_path)
        self.assertEqual(app.select_tiles(self.aoi_path, self.grid_path).quadricula.tolist(), ["3312-431"])

    def test_missing_crs_is_rejected(self):
        no_crs = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)])
        with patch.object(app.gpd, "read_file", return_value=no_crs), self.assertRaisesRegex(ValueError, "CRS ausente"):
            app.read_polygons(self.aoi_path, "AOI")

    def test_empty_intersection(self):
        gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs=self.grid.crs).to_file(self.aoi_path)
        self.assertTrue(app.select_tiles(self.aoi_path, self.grid_path).empty)

    def test_plan_exports_qgis_layer_and_product_urls(self):
        selected = app.select_tiles(self.aoi_path, self.grid_path)
        plan = app.make_plan(selected, ["MDT", "MDS"], self.root)
        app.save_plan(selected, plan, self.root)
        # Repetir a listagem deve substituir a camada, sem duplicar registros.
        app.save_plan(selected, plan, self.root)
        self.assertEqual(len(gpd.read_file(self.root / "quadriculas_selecionadas.gpkg")), 2)
        self.assertIn("/Download/File/125?key=cd_quadricula&value=3312-431", plan[0]["url"])
        self.assertIn("/Download/File/719?key=cd_quadricula&value=3312-431", plan[1]["url"])
        self.assertNotEqual(plan[0]["arquivo"], plan[1]["arquivo"])

    def test_main_stops_on_full_disk_instead_of_trying_next_download(self):
        with patch.object(app, "download", side_effect=OSError(errno.ENOSPC, "No space left")) as mocked:
            with patch.object(app, "append_result") as append:
                with self.assertLogs(app.LOG, level="ERROR") as logs:
                    result = app.main(["--aoi", str(self.aoi_path), "--grade", str(self.grid_path),
                                       "--saida", str(self.root / "saida")])
        self.assertEqual(result, 1)
        mocked.assert_called_once()
        append.assert_not_called()
        self.assertIn("Sem espaço no destino", " ".join(logs.output))

    def test_unmounted_drive_does_not_create_output_or_fall_back(self):
        mount = self.root / "hd_desconectado"
        output = mount / "sbbr_lidar_2027"
        with patch.object(app, "EXTERNAL_DRIVE", mount):
            with patch.object(app, "save_plan") as save:
                with self.assertLogs(app.LOG, level="ERROR") as logs:
                    result = app.main(["--aoi", str(self.aoi_path), "--grade", str(self.grid_path),
                                       "--saida", str(output), "--listar"])
        self.assertEqual(result, 1)
        save.assert_not_called()
        self.assertFalse(output.exists())
        self.assertIn("HD externo não está montado", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
