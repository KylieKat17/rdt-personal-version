"""Student starter for a full-duplex Go-Back-N protocol endpoint.

Read PROTOCOL.md before implementing these methods.  Keep the public class,
method names, constructor signature, and packet formats unchanged; you may add
private helper methods and state as needed.
"""

from __future__ import annotations

import struct
from enum import IntEnum


MAX_UNSIGNED_INT = (1 << 32) - 1
DATA_HEADER_FORMAT = "!HIHI"
ACK_FORMAT = "!HIH"
DATA_HEADER_SIZE = struct.calcsize(DATA_HEADER_FORMAT)
ACK_SIZE = struct.calcsize(ACK_FORMAT)


class PacketType(IntEnum):
    DATA = 0
    ACK = 1


class GBNHost:
    """One endpoint containing both the sender and receiver GBN state."""

    def __init__(self, simulator, entity, timer_interval, window_size):
        self.simulator = simulator
        self.entity = entity
        self.timer_interval = timer_interval
        self.window_size = window_size

        # Sender state.  A dictionary avoids treating absolute sequence
        # numbers as indexes into a fixed-size list.
        self.window_base = 0
        self.next_seq_num = 0
        self.unacked_buffer = {}
        self.app_layer_buffer = []

        # Receiver state.  The initial cumulative ACK represents "nothing
        # received yet" and is repeated for corrupt or out-of-order DATA.
        self.expected_seq_num = 0
        self.last_ack_pkt = self.create_ack_pkt(MAX_UNSIGNED_INT)

    def receive_from_application_layer(self, payload):
        """Buffer and send application data while space remains in the window."""

        self.app_layer_buffer.append(payload)
        self._fill_window()

    def receive_from_network_layer(self, packet):
        """Handle one DATA or ACK packet received from the network."""

        # A malformed DATA packet is handled like corrupt DATA: it cannot be
        # delivered, but repeating the latest ACK helps its sender recover.
        packet_type = self._packet_type(packet)
        if packet_type is None:
            return

        try:
            fields = self.unpack_pkt(packet)
        except (TypeError, ValueError, UnicodeDecodeError, struct.error):
            if packet_type == PacketType.DATA:
                self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt)
            return

        if fields["packet_type"] == PacketType.ACK:
            if self.is_corrupt(packet):
                return
            ack_num = fields["seq_num"]
            if not (self.window_base <= ack_num < self.next_seq_num):
                return

            for sequence in range(self.window_base, ack_num + 1):
                self.unacked_buffer.pop(sequence, None)
            self.window_base = ack_num + 1
            self.simulator.stop_timer(self.entity)
            if self.window_base < self.next_seq_num:
                self.simulator.start_timer(self.entity, self.timer_interval)
            self._fill_window()
            return

        if fields["packet_type"] != PacketType.DATA:
            return

        if self.is_corrupt(packet) or fields["seq_num"] != self.expected_seq_num:
            self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt)
            return

        self.simulator.pass_to_application_layer(self.entity, fields["payload"])
        self.last_ack_pkt = self.create_ack_pkt(self.expected_seq_num)
        self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt)
        self.expected_seq_num += 1

    def timer_interrupt(self):
        """Retransmit the outstanding Go-Back-N window after a timeout."""

        if self.window_base >= self.next_seq_num:
            return
        self.simulator.start_timer(self.entity, self.timer_interval)
        for sequence in range(self.window_base, self.next_seq_num):
            self.simulator.pass_to_network_layer(
                self.entity, self.unacked_buffer[sequence]
            )

    def create_data_pkt(self, seq_num, payload):
        """Return a DATA ``bytes`` packet for integer ``seq_num`` and string payload."""

        if not isinstance(payload, str):
            raise TypeError("payload must be a string")
        payload_bytes = payload.encode("utf-8")
        header = struct.pack(
            DATA_HEADER_FORMAT, PacketType.DATA, seq_num, 0, len(payload_bytes)
        )
        checksum = self.create_checksum(header + payload_bytes)
        return struct.pack(
            DATA_HEADER_FORMAT, PacketType.DATA, seq_num, checksum, len(payload_bytes)
        ) + payload_bytes

    def create_ack_pkt(self, seq_num):
        """Return an ACK ``bytes`` packet for integer ``seq_num``."""

        packet = struct.pack(ACK_FORMAT, PacketType.ACK, seq_num, 0)
        checksum = self.create_checksum(packet)
        return struct.pack(ACK_FORMAT, PacketType.ACK, seq_num, checksum)

    def create_checksum(self, packet):
        """Return the integer 16-bit Internet checksum for packet ``bytes``."""

        if not isinstance(packet, bytes):
            raise TypeError("packet must be bytes")
        if len(packet) % 2:
            packet += b"\x00"
        total = 0
        for offset in range(0, len(packet), 2):
            total += (packet[offset] << 8) | packet[offset + 1]
            total = (total & 0xFFFF) + (total >> 16)
        total = (total & 0xFFFF) + (total >> 16)
        return (~total) & 0xFFFF

    def unpack_pkt(self, packet):
        """Return the documented DATA or ACK fields as a dictionary."""

        if not isinstance(packet, bytes) or len(packet) < 2:
            raise ValueError("packet is missing its type field")
        packet_type = struct.unpack("!H", packet[:2])[0]
        if packet_type == PacketType.ACK:
            if len(packet) != ACK_SIZE:
                raise ValueError("ACK packet has an invalid size")
            _, seq_num, checksum = struct.unpack(ACK_FORMAT, packet)
            return {"packet_type": PacketType.ACK, "seq_num": seq_num, "checksum": checksum}
        if packet_type == PacketType.DATA:
            if len(packet) < DATA_HEADER_SIZE:
                raise ValueError("DATA packet is shorter than its header")
            _, seq_num, checksum, payload_length = struct.unpack(
                DATA_HEADER_FORMAT, packet[:DATA_HEADER_SIZE]
            )
            if len(packet) != DATA_HEADER_SIZE + payload_length:
                raise ValueError("DATA packet payload length does not match its size")
            payload = packet[DATA_HEADER_SIZE:].decode("utf-8")
            return {
                "packet_type": PacketType.DATA,
                "seq_num": seq_num,
                "checksum": checksum,
                "payload_length": payload_length,
                "payload": payload,
            }
        raise ValueError("unknown packet type")

    def is_corrupt(self, packet):
        """Return whether packet ``bytes`` fail the Internet checksum."""

        try:
            self.unpack_pkt(packet)
        except (TypeError, ValueError, UnicodeDecodeError, struct.error):
            return True
        return self.create_checksum(packet) != 0

    def _packet_type(self, packet):
        """Return a recognized wire type when the leading field is present."""

        if not isinstance(packet, bytes) or len(packet) < 2:
            return None
        packet_type = struct.unpack("!H", packet[:2])[0]
        return PacketType(packet_type) if packet_type in PacketType._value2member_map_ else None

    def _fill_window(self):
        """Move queued application messages into all currently available slots."""

        while (
            self.app_layer_buffer
            and self.next_seq_num < self.window_base + self.window_size
        ):
            was_idle = self.window_base == self.next_seq_num
            payload = self.app_layer_buffer.pop(0)
            packet = self.create_data_pkt(self.next_seq_num, payload)
            self.unacked_buffer[self.next_seq_num] = packet
            self.simulator.pass_to_network_layer(self.entity, packet)
            if was_idle:
                self.simulator.start_timer(self.entity, self.timer_interval)
            self.next_seq_num += 1
