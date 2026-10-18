#!/usr/bin/env python3
"""A bare-bones offline-mode Minecraft client for the integration test.

It logs in, stays connected (answering keep-alives and teleports) and does
nothing else until the server sends it a chat message containing a command:

    tellraw <name> "bot:use"                start using the held item (drinks a potion)
    tellraw <name> "bot:use_on <x> <y> <z>" use the held item on the top of a block

That's enough for the test to have a real player drink a potion, which command
blocks and RCON can't do. Packet ids come from the server's own `--reports`
output for the target version (see integration_test.sh), so the only protocol
knowledge here is the shape of the handful of packets we use.

Usage: bot.py <host> <port> <name> <packets.json> <protocol version>
"""

import json
import re
import socket
import struct
import sys
import uuid
import zlib


def varint(n: int) -> bytes:
    n &= 0xFFFFFFFF
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def string(s: str) -> bytes:
    data = s.encode()
    return varint(len(data)) + data


def block_pos(x: int, y: int, z: int) -> int:
    # 26 bits each of x and z, 12 bits of y, as a signed long
    n = (x & 0x3FFFFFF) << 38 | (z & 0x3FFFFFF) << 12 | (y & 0xFFF)
    return n - (1 << 64) if n >= 1 << 63 else n


class Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def varint(self) -> int:
        n = shift = 0
        while True:
            b = self.data[self.pos]
            self.pos += 1
            n |= (b & 0x7F) << shift
            if not b & 0x80:
                return n - (1 << 32) if n >= 1 << 31 else n
            shift += 7

    def string(self) -> str:
        length = self.varint()
        s = self.data[self.pos:self.pos + length].decode()
        self.pos += length
        return s

    def rest(self) -> bytes:
        return self.data[self.pos:]


class Bot:
    def __init__(self, host: str, port: int, name: str, packets: dict, protocol: int):
        self.sock = socket.create_connection((host, port))
        self.buf = b""
        self.compression = -1
        self.name = name
        self.ids = {
            phase: {direction: {k.removeprefix("minecraft:"): v["protocol_id"] for k, v in entries.items()}
                    for direction, entries in dirs.items()}
            for phase, dirs in packets.items()
        }
        self.phase = "handshake"
        self.sequence = 0
        self.send("intention", varint(protocol) + string(host) + struct.pack(">H", port) + varint(2))
        self.phase = "login"
        offline_uuid = uuid.uuid3(uuid.NAMESPACE_OID, "OfflinePlayer:" + name)
        self.send("hello", string(name) + offline_uuid.bytes)

    def send(self, packet: str, payload: bytes = b"") -> None:
        data = varint(self.ids[self.phase]["serverbound"][packet]) + payload
        if self.compression >= 0:
            # Below the threshold a packet goes uncompressed, marked with data length 0
            if len(data) >= self.compression:
                data = varint(len(data)) + zlib.compress(data)
            else:
                data = varint(0) + data
        self.sock.sendall(varint(len(data)) + data)

    def read_packet(self) -> tuple[str | None, Reader]:
        while True:
            r = Reader(self.buf)
            try:
                length = r.varint()
                if len(self.buf) - r.pos >= length:
                    frame = self.buf[r.pos:r.pos + length]
                    self.buf = self.buf[r.pos + length:]
                    break
            except IndexError:
                pass
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("server closed the connection")
            self.buf += chunk

        r = Reader(frame)
        if self.compression >= 0:
            data_length = r.varint()
            r = Reader(zlib.decompress(r.rest()) if data_length else r.rest())
        packet_id = r.varint()
        names = {v: k for k, v in self.ids[self.phase]["clientbound"].items()}
        return names.get(packet_id), r

    def run(self) -> None:
        while True:
            packet, r = self.read_packet()
            handler = getattr(self, f"on_{self.phase}_{packet}", None)
            if handler:
                handler(r)

    # --- login ---
    def on_login_login_compression(self, r: Reader) -> None:
        self.compression = r.varint()

    def on_login_login_disconnect(self, r: Reader) -> None:
        raise ConnectionError(f"login refused: {r.string()}")

    def on_login_login_finished(self, r: Reader) -> None:
        self.send("login_acknowledged")
        self.phase = "configuration"

    # --- configuration ---
    def on_configuration_select_known_packs(self, r: Reader) -> None:
        # Claim the same packs the server has so it skips sending their contents
        self.send("select_known_packs", r.rest())

    def on_configuration_keep_alive(self, r: Reader) -> None:
        self.send("keep_alive", r.rest())

    def on_configuration_ping(self, r: Reader) -> None:
        self.send("pong", r.rest())

    def on_configuration_finish_configuration(self, r: Reader) -> None:
        self.send("finish_configuration")
        self.phase = "play"
        # Without this the server treats the player as still loading the world
        self.send("player_loaded")
        print(f"{self.name} joined", flush=True)

    # --- play ---
    def on_play_keep_alive(self, r: Reader) -> None:
        self.send("keep_alive", r.rest())

    def on_play_ping(self, r: Reader) -> None:
        self.send("pong", r.rest())

    def on_play_player_position(self, r: Reader) -> None:
        # Teleport id, position, velocity, yaw and pitch; confirm by echoing the
        # id, position and rotation back. The test only sees absolute teleports.
        teleport_id = r.varint()
        x, y, z, _, _, _, yaw, pitch = struct.unpack(">ddddddff", r.rest()[:56])
        self.send("accept_teleportation", varint(teleport_id) + struct.pack(">dddff", x, y, z, yaw, pitch))

    def on_play_chunk_batch_finished(self, r: Reader) -> None:
        self.send("chunk_batch_received", struct.pack(">f", 20.0))

    def on_play_disconnect(self, r: Reader) -> None:
        raise ConnectionError("kicked from the server")

    def on_play_system_chat(self, r: Reader) -> None:
        # The message is an NBT text component; the command text appears in it verbatim
        text = r.rest()
        use_on = re.search(rb"bot:use_on (-?\d+) (-?\d+) (-?\d+)", text)
        if use_on:
            x, y, z = map(int, use_on.groups())
            self.sequence += 1
            # Main hand, block position, face (up), cursor inside the block, not inside
            # it, no world border hit, then sequence
            self.send("use_item_on", varint(0) + struct.pack(">q", block_pos(x, y, z)) + varint(1)
                      + struct.pack(">fff??", 0.5, 1.0, 0.5, False, False) + varint(self.sequence))
            print(f"{self.name} using held item on {x} {y} {z}", flush=True)
        elif b"bot:use" in text:
            self.sequence += 1
            # Main hand, then sequence, then the player's yaw and pitch
            self.send("use_item", varint(0) + varint(self.sequence) + struct.pack(">ff", 0.0, 0.0))
            print(f"{self.name} using held item", flush=True)


def main() -> int:
    host, port, name, packets_path, protocol = sys.argv[1:6]
    with open(packets_path) as f:
        packets = json.load(f)
    try:
        Bot(host, int(port), name, packets, int(protocol)).run()
    except (ConnectionError, OSError) as e:
        print(f"{name} disconnected: {e}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
