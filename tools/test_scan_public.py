#!/usr/bin/env python3
"""test_scan_public.py - positive and negative controls for tools/scan_public.py (PNG path).

Standard library only. It builds small synthetic PNGs and runs the scanner on them as a program, so the same tests can be
pointed at an older copy of the scanner:

    python3 -I -B tools/test_scan_public.py                                  # tests the scanner next to this file
    SCAN_PUBLIC=/path/to/other/scan_public.py python3 -I -B tools/test_scan_public.py

The "secret" is a made-up 32-character hex string built at run time; no real secret is used. Nothing is deleted:
every case writes into its own new folder under one scratch folder (the SCAN_SCRATCH folder if set, else a new temporary
folder that is left for the operating system to clear). The test never writes inside the repository.
"""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCANNER = os.environ.get("SCAN_PUBLIC", os.path.join(HERE, "scan_public.py"))
FAKE = "0123456789abcdef" * 2                    # 32 hex characters; looks like a token, is not one
SIG = b"\x89PNG\r\n\x1a\n"


def chunk(kind, body, crc=None):
    if crc is None:
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)


IHDR = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
IDAT = chunk(b"IDAT", zlib.compress(b"\x00\x00"))
IEND = chunk(b"IEND", b"")


def png(*middle, head=IHDR, tail=IEND, after=b""):
    return SIG + head + b"".join(middle) + tail + after


def text_chunk(value):
    return chunk(b"tEXt", b"Comment\x00" + value.encode())


def ztxt_chunk(value):
    return chunk(b"zTXt", b"Comment\x00\x00" + zlib.compress(value.encode()))


def itxt_chunk(value, compressed):
    payload = zlib.compress(value.encode()) if compressed else value.encode()
    return chunk(b"iTXt", b"Comment\x00" + bytes([1 if compressed else 0, 0]) + b"\x00\x00" + payload)


class ScanPng(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = os.environ.get("SCAN_SCRATCH")
        if base:
            os.makedirs(base, exist_ok=True)
        cls.base = tempfile.mkdtemp(prefix="scan_png_", dir=base or None)   # never cleaned up by this test
        cls.n = 0

    def run_scan(self, data=None, files=None):
        """Put the PNG (or the given {name: bytes}) in a new folder as docs/proof/..., run the scanner, return (exit, output)."""
        type(self).n += 1
        root = os.path.join(self.base, "case%02d" % self.n)
        os.makedirs(os.path.join(root, "docs", "proof"))
        for name, blob in (files or {"case.png": data}).items():
            with open(os.path.join(root, "docs", "proof", name), "xb") as handle:
                handle.write(blob)
        done = subprocess.run([sys.executable, "-I", "-B", SCANNER, root], capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout

    def assertRule(self, result, rule):
        code, out = result
        self.assertEqual(code, 1, out)
        self.assertIn(": %s:" % rule, out)

    # --- positive controls: a leak must be found ---
    def test_plain_text_chunk_is_detected(self):
        self.assertRule(self.run_scan(png(text_chunk("note " + FAKE))), "token")

    def test_uncompressed_itxt_is_detected(self):
        self.assertRule(self.run_scan(png(itxt_chunk("note " + FAKE, False))), "token")

    def test_compressed_itxt_is_detected(self):
        self.assertRule(self.run_scan(png(itxt_chunk("note " + FAKE, True))), "token")

    def test_ztxt_is_detected(self):
        self.assertRule(self.run_scan(png(ztxt_chunk("note " + FAKE))), "token")

    # --- negative controls: bad structure must fail closed ---
    def test_zlib_bomb_in_ztxt_is_a_finding(self):
        bomb = chunk(b"zTXt", b"Comment\x00\x00" + zlib.compress(b"A" * (2 * 1024 * 1024)))
        self.assertRule(self.run_scan(png(bomb)), "image")

    def test_zlib_bomb_in_itxt_is_a_finding(self):
        bomb = chunk(b"iTXt", b"Comment\x00\x01\x00\x00\x00" + zlib.compress(b"A" * (2 * 1024 * 1024)))
        self.assertRule(self.run_scan(png(bomb)), "image")

    def test_large_text_just_under_the_cap_scans_fast(self):
        big = ztxt_chunk("z" * (900 * 1024))      # not hex, not mixed case: no token finding
        code, out = self.run_scan(png(big))
        self.assertEqual(code, 0, out)

    def test_signature_and_iend_only_is_a_finding(self):
        self.assertRule(self.run_scan(SIG + IEND), "image")

    def test_bad_crc_is_a_finding(self):
        self.assertRule(self.run_scan(png(chunk(b"tEXt", b"Comment\x00ok", crc=0))), "image")

    def test_first_chunk_not_ihdr_is_a_finding(self):
        self.assertRule(self.run_scan(png(head=IDAT)), "image")

    def test_short_ihdr_is_a_finding(self):
        self.assertRule(self.run_scan(png(head=chunk(b"IHDR", b"\x00" * 12))), "image")

    def test_bytes_after_iend_are_a_finding(self):
        self.assertRule(self.run_scan(png(after=b"trailing")), "image")

    def test_missing_iend_is_a_finding(self):
        self.assertRule(self.run_scan(SIG + IHDR + IDAT), "image")

    def test_truncated_chunk_is_a_finding(self):
        self.assertRule(self.run_scan((png(IDAT))[:-6]), "image")

    def test_not_a_png_is_a_finding(self):
        self.assertRule(self.run_scan(b"GIF89a" + b"\x00" * 20), "image")

    # --- clean controls ---
    def test_clean_synthetic_png_passes(self):
        code, out = self.run_scan(png(IDAT, text_chunk("hello"), ztxt_chunk("hello"), itxt_chunk("hello", True)))
        self.assertEqual(code, 0, out)
        self.assertIn("0 finding(s)", out)

    def test_real_proof_images_have_no_findings(self):
        source = os.path.join(REPO, "docs", "proof")
        names = sorted(n for n in os.listdir(source) if n.lower().endswith(".png"))
        self.assertEqual(len(names), 11)
        blobs = {}
        for name in names:
            with open(os.path.join(source, name), "rb") as handle:
                blobs[name] = handle.read()
        code, out = self.run_scan(files=blobs)
        self.assertEqual(code, 0, out)
        self.assertIn("0 finding(s)", out)
        self.assertIn("11 PNG screenshot(s)", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
