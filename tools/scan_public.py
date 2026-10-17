#!/usr/bin/env python3
"""scan_public.py - fail (exit 1) if the repository holds anything that should not be public.

Standard library only. Read-only: it never writes or changes a file.

Usage:   python3 -I -B tools/scan_public.py [repo_root]      (default: the folder above tools/)

Checks (each hit prints  path:line: rule: matched text):
  ipv4        IPv4 address, except 127.0.0.1 and 0.0.0.0
  email       e-mail address
  token       hex run of 32 or more characters, or a random-looking base64-style run of 32 or more
  key         a public-key line (ssh-ed25519 or ssh-rsa followed by base64) or a PEM armour line
  ocid        cloud-vendor resource id
  home_path   an absolute path under the users folder of a Mac
  uuid        UUID
  number      9 to 10 digit number (looks like a chat id)
  name        a dropped name (agents, people, organisations, projects)
  vendor      the name of the cloud vendor that hosts our VPS (write "a cloud VPS" or "the host")
  host_path   our real service path prefix (use /srv/example/... in examples)
  uid         a real container or service-account uid written as a number (use 1000 in examples)
  release     an internal release or module name
  version     a version tag with a two-digit minor (v0.2x or higher) or a tunnel-client style 0.0.NN; our own v0.1 label is allowed
  framework   an agent-framework or machine nickname (say "container agent" or use PC1, PC2, VPS1, VPS2, VPS3)
  island      a real machine label (use PC1, PC2, VPS1, VPS2, VPS3)
  port        one of the real loopback ports of the original deployment (use placeholders)
  image       a file under docs/proof/ that fails the PNG structure check (signature, IHDR first, every chunk CRC, IEND last,
              nothing after it, text chunks decodable within a 1 MiB cap). A PNG that passes has its text metadata
              (tEXt, zTXt, iTXt; compressed text is decoded first) scanned; its pixels are NOT scanned and must be checked by eye

Names are NOT stored in this repository, not even as digests. Maintainers keep a private JSON file
{"distinct": [...], "ambiguous": [...]} that holds the first 16 hex characters of the sha256 of each lower-case name,
or of each lower-case adjacent word pair for a two-word name. Point the environment variable CROSSROAD_SCAN_NAMES at
that file to switch the name rule on. Without it the name rule is off and the scanner says so on stderr.

Names that are also ordinary English words (the AMBIGUOUS set) match only when written in Capitalised or UPPER case, or
inside quotes. That keeps an everyday variable name from failing the scan while still catching an agent of that name.

A line that holds the text EXAMPLE next to a token or number is a placeholder and is skipped for those two rules.
"""
import hashlib
import json
import os
import re
import sys


def load_names():
    path = os.environ.get("CROSSROAD_SCAN_NAMES")
    if not path:
        sys.stderr.write("name rule off: set CROSSROAD_SCAN_NAMES to a private name-hash file\n")
        return frozenset(), frozenset()
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return frozenset(data.get("distinct", ())), frozenset(data.get("ambiguous", ()))


DISTINCT_HASHES, AMBIGUOUS_HASHES = load_names()

SKIP_DIRS = {".git", "__pycache__", "retained"}
TEXT_LIMIT = 4 * 1024 * 1024

RULES = [
    ("ipv4", re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")),
    ("email", re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("token", re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{32,}={0,2}(?![A-Za-z0-9+/=_-])")),
    ("key", re.compile(r"ssh-(?:ed25519|rsa)\s+AAAA|BEGIN [A-Z ]*KEY")),
    ("ocid", re.compile(r"ocid1\.[a-z0-9_.-]+", re.I)),
    ("home_path", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("number", re.compile(r"(?<![\w.])\d{9,10}(?![\w.])")),
    # patterns below are written in pieces so that this file does not trip its own rules
    ("vendor", re.compile("(?i)" + "or" + "acle")),
    ("host_path", re.compile("/srv/" + "crossroad")),
    ("uid", re.compile(r"\b1(?:0000|002)\b(?=.*)")),
    ("release", re.compile("turn" + "49|hermes_" + "v21|crossroad_" + "address|p3" + "[bc]-|m1_send_" + "v6|mail_reader_" + "v9")),
    ("version", re.compile(r"\bv0\.[2-9]\d\b|(?<![\d.])0\.0\.\d{2}(?![\d.])|(?<![\d.])0\.1\.[1-9](?![\d.])")),
    ("port", re.compile(r"\b8(?:766|080)\b")),
    ("island", re.compile(r"\b[Mm][14]\b")),
    ("framework", re.compile(r"(?i)\bhermes\b")),
]
UID_CONTEXT = re.compile(r"uid|gid|user|owner", re.I)
WORD = re.compile(r"[A-Za-z0-9]+")


def digest(word):
    return hashlib.sha256(word.encode("utf-8")).hexdigest()[:16]


def name_hits(line):
    hits = []
    words = list(WORD.finditer(line))
    for i, m in enumerate(words):
        word = m.group(0)
        low = word.lower()
        if digest(low) in DISTINCT_HASHES:
            hits.append(word)
        elif digest(low) in AMBIGUOUS_HASHES:
            capital = word[:1].isupper() and (word[1:].islower() or word[1:] == "" or word.isupper())
            before = line[m.start() - 1] if m.start() > 0 else ""
            after = line[m.end()] if m.end() < len(line) else ""
            quoted = before in "\"'" and before != "" and before == after
            if (capital and len(word) > 1) or quoted:
                hits.append(word)
        if i + 1 < len(words):
            between = line[m.end():words[i + 1].start()]
            if between and re.fullmatch(r"[ _-]+", between):
                pair = low + " " + words[i + 1].group(0).lower()
                if digest(pair) in DISTINCT_HASHES:
                    hits.append(word + between + words[i + 1].group(0))
    return hits


def scan_line(line):
    hits = []
    for rule, rx in RULES:
        for m in rx.finditer(line):
            text = m.group(0)
            if rule == "ipv4" and text in ("127.0.0.1", "0.0.0.0"):
                continue
            if rule == "uid" and not UID_CONTEXT.search(line):
                continue                           # a large number with no uid context (a rate cap, for example) is fine
            if rule in ("token", "number") and "EXAMPLE" in line.upper():
                continue
            if rule == "token":
                is_hex = re.fullmatch(r"[0-9a-fA-F]+", text) is not None
                mixed = (re.search(r"[a-z]", text) and re.search(r"[A-Z]", text) and re.search(r"\d", text))
                if not (is_hex or mixed or re.search(r"[+=]", text)):
                    continue                       # snake_case, hyphenated words and paths are names, not secrets
            hits.append((rule, text))
    for text in name_hits(line):
        hits.append(("name", text))
    return hits


def is_text(path):
    try:
        with open(path, "rb") as handle:
            return b"\x00" not in handle.read(2048)
    except OSError:
        return False


IMAGE_DIR = os.path.join("docs", "proof")
IMAGE_LIMIT = 2 * 1024 * 1024
TEXT_DECODE_LIMIT = 1024 * 1024                  # most text one PNG may decode to, all chunks together; more is a finding
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _inflate(blob, budget):
    """Decompress a zlib stream with a hard output cap. Return (text, error); error is None on success."""
    import zlib
    try:
        d = zlib.decompressobj()
        out = d.decompress(blob, budget + 1)
        if len(out) > budget or d.unconsumed_tail:
            return None, "compressed text decodes to more than the %d byte cap" % TEXT_DECODE_LIMIT
        if not d.eof:
            return None, "compressed text stream is incomplete"
        return out, None
    except zlib.error as exc:
        return None, "compressed text is not valid zlib (%s)" % exc


def png_inspect(path):
    """Walk a PNG and return (texts, problems).
    texts    = the text found in its metadata chunks: tEXt, zTXt, and iTXt (compressed iTXt and zTXt are decoded, with a cap).
    problems = reasons the file is not accepted; an empty list means the structure checked out:
               PNG signature, IHDR first (13 bytes), every chunk length inside the file, every chunk CRC correct,
               IEND (0 bytes) last, nothing after it, text chunks well formed and decodable within the cap.
    Pixels are never read; masking in the pixels must be checked by eye. Any other problem fails closed."""
    import struct
    import zlib
    with open(path, "rb") as handle:
        data = handle.read(IMAGE_LIMIT + 1)
    if len(data) > IMAGE_LIMIT:
        return [], ["larger than the %d byte image limit" % IMAGE_LIMIT]
    if not data.startswith(PNG_SIGNATURE):
        return [], ["no PNG signature"]
    texts, problems, pos, first, budget = [], [], len(PNG_SIGNATURE), True, TEXT_DECODE_LIMIT
    while True:
        if pos + 12 > len(data):
            return texts, problems + ["file ends before IEND (truncated chunk)"]
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if pos + 12 + length > len(data):
            return texts, problems + ["chunk %r length runs past the end of the file" % kind]
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if crc != zlib.crc32(kind + body) & 0xFFFFFFFF:
            return texts, problems + ["chunk %r has a bad CRC" % kind]
        if first and (kind != b"IHDR" or length != 13):
            return texts, problems + ["first chunk is not a 13 byte IHDR"]
        if not first and kind == b"IHDR":
            return texts, problems + ["second IHDR chunk"]
        first = False
        if kind in (b"tEXt", b"zTXt", b"iTXt"):
            fields, err = None, None
            if kind == b"tEXt":
                fields = [body]
            elif kind == b"zTXt":
                parts = body.split(b"\x00", 1)
                if len(parts) != 2 or len(parts[1]) < 1 or parts[1][0] != 0:
                    err = "malformed zTXt chunk"
                else:
                    text, err = _inflate(parts[1][1:], budget)
                    fields = [parts[0], text] if err is None else None
                    budget -= len(text or b"")
            else:
                parts = body.split(b"\x00", 1)
                rest = parts[1] if len(parts) == 2 else b""
                if len(parts) != 2 or len(rest) < 2 or rest[0] not in (0, 1):
                    err = "malformed iTXt chunk"
                else:
                    flag, method, rest = rest[0], rest[1], rest[2:]
                    lang = rest.split(b"\x00", 1)
                    trans = lang[1].split(b"\x00", 1) if len(lang) == 2 else []
                    if len(trans) != 2:
                        err = "malformed iTXt chunk"
                    elif flag == 1 and method != 0:
                        err = "iTXt chunk uses an unknown compression method"
                    elif flag == 1:
                        text, err = _inflate(trans[1], budget)
                        fields = [parts[0], lang[0], trans[0], text] if err is None else None
                        budget -= len(text or b"")
                    else:
                        fields = [parts[0], lang[0], trans[0], trans[1]]
            if err is None and budget < 0:
                err = "text chunks decode to more than the %d byte cap" % TEXT_DECODE_LIMIT
            if err is not None:
                return texts, problems + [err]
            texts.append(" ".join(f.decode("utf-8", "replace").replace("\x00", " ") for f in fields))
        pos += 12 + length
        if kind == b"IEND":
            if length != 0:
                problems.append("IEND chunk is not empty")
            if pos != len(data):
                problems.append("%d byte(s) after IEND" % (len(data) - pos))
            return texts, problems


def main(argv):
    root = os.path.abspath(argv[1]) if len(argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    count_files = 0
    findings = []
    images = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root)
            for part in rel.split(os.sep):                         # file and folder names count too
                for rule, text in scan_line(part):
                    findings.append((rel, 0, rule, text))
            if rel.startswith(IMAGE_DIR + os.sep) and name.lower().endswith(".png"):
                chunks, problems = png_inspect(path)               # a reviewed screenshot: check its structure, scan its metadata, list it for a human
                for problem in problems:
                    findings.append((rel, 0, "image", problem))
                if problems:
                    continue
                images.append(rel)
                for chunk in chunks:
                    for rule, text in scan_line(chunk):
                        findings.append((rel, 0, rule, text))
                continue
            if os.path.getsize(path) > TEXT_LIMIT or not is_text(path):
                findings.append((rel, 0, "binary_or_large", "not scanned as text"))
                continue
            count_files += 1
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    for rule, text in scan_line(line):
                        findings.append((rel, number, rule, text))
    for rel, number, rule, text in findings:
        print("%s:%d: %s: %s" % (rel, number, rule, text[:80]))
    print("scanned %d text files, %d finding(s)" % (count_files, len(findings)))
    if images:
        print("%d PNG screenshot(s) under docs/proof: metadata scanned, pixels NOT scanned; a person must look at each one" % len(images))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
