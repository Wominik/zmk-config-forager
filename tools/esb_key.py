#!/usr/bin/env python3
"""Create the key file that turns on encryption of the ESB split link.

The firmware built by CI contains no secret. Each device (both halves and
every dongle) reads its key from a small flash block that is written once,
with a UF2 file, the same way firmware is flashed. This script makes that
file. It needs nothing but Python 3 and never touches the network.

    python3 tools/esb_key.py new      create esb-key.uf2 with a fresh random key
    python3 tools/esb_key.py clear    create esb-key-clear.uf2, which removes
                                      the key from a device (back to unencrypted)
    python3 tools/esb_key.py check    verify an existing esb-key.uf2

How to use esb-key.uf2:

  1. Flash the firmware on all devices first (the key block is ignored by
     firmware without CONFIG_ZMK_SPLIT_ESB_CRYPTO, and survives firmware
     updates).
  2. For each device - left half, right half, each dongle: double-tap reset,
     copy esb-key.uf2 onto the drive that appears. The SAME file for all.
  3. Keep esb-key.uf2 somewhere safe and private. It is the key: anyone who
     has it can read and inject keystrokes. A new device (replacement half,
     second dongle) needs this exact file. Do not commit it - *.uf2 files
     named esb-key* are in .gitignore.

A device with a key talks only to devices with the same key. Until all of
them have it, the keyboard will not work - that is also the check that
encryption is on.
"""

import argparse
import os
import secrets
import struct
import sys
import zlib

# Must match the firmware (zmk-feature-split-esb: esb_crypto.c and
# CONFIG_ZMK_SPLIT_ESB_CRYPTO_KEY_ADDR).
KEY_ADDR = 0xE8000
MAGIC = b"ZESBKEY1"
KEY_LEN = 32

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY_ID = 0x00002000
UF2_FAMILY_NRF52840 = 0xADA52840
UF2_PAYLOAD = 256

KEY_FILE = "esb-key.uf2"
CLEAR_FILE = "esb-key-clear.uf2"


def key_block(key: bytes) -> bytes:
    body = MAGIC + key
    return body + struct.pack("<I", zlib.crc32(body))


def uf2_block(addr: int, data: bytes) -> bytes:
    assert len(data) <= UF2_PAYLOAD
    payload = data.ljust(UF2_PAYLOAD, b"\xff")
    head = struct.pack(
        "<IIIIIIII",
        UF2_MAGIC_START0,
        UF2_MAGIC_START1,
        UF2_FLAG_FAMILY_ID,
        addr,
        UF2_PAYLOAD,
        0,  # block number
        1,  # total blocks
        UF2_FAMILY_NRF52840,
    )
    return head + payload.ljust(476, b"\x00") + struct.pack("<I", UF2_MAGIC_END)


def parse(path: str) -> bytes:
    """Return the 256 payload bytes of a one-block UF2 written by this script."""
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) != 512:
        raise ValueError("not a single-block UF2 file")
    m0, m1, flags, addr, size, _, total, family = struct.unpack_from("<IIIIIIII", raw)
    (end,) = struct.unpack_from("<I", raw, 508)
    if (m0, m1, end) != (UF2_MAGIC_START0, UF2_MAGIC_START1, UF2_MAGIC_END):
        raise ValueError("bad UF2 magic")
    if addr != KEY_ADDR or size != UF2_PAYLOAD or total != 1 or family != UF2_FAMILY_NRF52840:
        raise ValueError("not a key file for this firmware")
    return raw[32 : 32 + UF2_PAYLOAD]


def write_private(path: str, data: bytes, force: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def cmd_new(args) -> int:
    path = os.path.join(args.dir, KEY_FILE)
    try:
        write_private(path, uf2_block(KEY_ADDR, key_block(secrets.token_bytes(KEY_LEN))), args.force)
    except FileExistsError:
        print(
            f"{path} already exists. It is your key: a new one would lock out every\n"
            "device that has the old one until it is re-flashed. Use --force to replace it.",
            file=sys.stderr,
        )
        return 1
    print(f"Wrote {path}")
    print("Copy this same file onto every device in bootloader mode (both halves, every dongle).")
    print("Keep it private and backed up; never commit or share it.")
    return 0


def cmd_clear(args) -> int:
    path = os.path.join(args.dir, CLEAR_FILE)
    write_private(path, uf2_block(KEY_ADDR, b""), True)
    print(f"Wrote {path}")
    print("Flashing it removes the key from a device, which then talks unencrypted again.")
    return 0


def cmd_check(args) -> int:
    path = os.path.join(args.dir, KEY_FILE)
    try:
        payload = parse(path)
    except (OSError, ValueError) as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 1
    block = payload[: len(MAGIC) + KEY_LEN + 4]
    body, (crc,) = block[:-4], struct.unpack("<I", block[-4:])
    if not body.startswith(MAGIC) or zlib.crc32(body) != crc:
        print(f"{path}: key block is damaged", file=sys.stderr)
        return 1
    # A short fingerprint lets two copies be compared without showing the key
    print(f"{path}: OK, fingerprint {zlib.crc32(b'fp' + body):08x}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=".", help="where to read/write the files (default: current directory)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("new", help="create esb-key.uf2 with a fresh random key")
    new.add_argument("--force", action="store_true", help="replace an existing esb-key.uf2")
    new.set_defaults(func=cmd_new)
    sub.add_parser("clear", help="create esb-key-clear.uf2").set_defaults(func=cmd_clear)
    sub.add_parser("check", help="verify esb-key.uf2").set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
