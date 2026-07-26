"""Pseudocode companion to the original ``template/gbn_host.py`` starter.

This file is intentionally not a solution.  It keeps the starter's class,
methods, and state names, while the comments describe the logic that belongs
inside each TODO.
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

        # Sender state:
        # - window_base is the oldest DATA packet not ACKed yet.
        # - next_seq_num is the number to give the next new DATA packet.
        # - unacked_buffer maps each outstanding sequence number to its packet.
        # - app_layer_buffer is a FIFO queue for payloads with no open slot.
        self.window_base = 0
        self.next_seq_num = 0
        self.unacked_buffer = {}
        self.app_layer_buffer = []

        # Receiver state:
        # - expected_seq_num is the only DATA packet that may be delivered.
        # - last_ack_pkt begins as ACK(2^32 - 1), meaning no DATA has arrived.
        self.expected_seq_num = 0
        self.last_ack_pkt = None

    def receive_from_application_layer(self, payload):
        """Buffer and send application data while space remains in the window."""

        # Put payload at the end of app_layer_buffer.
        #
        # WHILE there is a waiting payload AND
        #       next_seq_num < window_base + window_size:
        #     remember whether window_base == next_seq_num (window was empty)
        #     remove the next waiting payload
        #     create DATA(next_seq_num, payload)
        #     save it in unacked_buffer[next_seq_num]
        #     pass it to the network layer
        #     IF the window was empty:
        #         start the one sender timer
        #     increment next_seq_num
        #
        # This same loop is useful after an ACK opens more than one slot.
        pass

    def receive_from_network_layer(self, packet):
        """Handle one DATA or ACK packet received from the network."""

        # Read the leading packet type only if it is present and recognized.
        # If the type is missing or unknown, ignore the packet completely.
        #
        # TRY to unpack the packet exactly.
        # If unpacking fails:
        #     IF its recognizable type was DATA:
        #         resend last_ack_pkt (the sender needs a recovery hint)
        #     RETURN
        #
        # IF this is an ACK:
        #     IF its checksum is bad:
        #         RETURN (a damaged ACK cannot advance the sending window)
        #
        #     ack_num = ACK sequence number
        #     IF ack_num < window_base OR ack_num >= next_seq_num:
        #         RETURN (it is a duplicate, future, or otherwise invalid ACK)
        #
        #     FOR every sequence from window_base through ack_num:
        #         remove it from unacked_buffer
        #     set window_base to ack_num + 1
        #
        #     stop the old timer because its oldest packet was acknowledged
        #     IF outstanding packets still remain:
        #         restart the timer for the new oldest packet
        #     send waiting application payloads into every new open slot
        #     RETURN
        #
        # IF this is DATA:
        #     IF checksum is bad OR sequence number != expected_seq_num:
        #         do not deliver or buffer this DATA
        #         resend last_ack_pkt (duplicate/future DATA needs the last ACK)
        #         RETURN
        #
        #     deliver the UTF-8 payload to the application layer
        #     create and save ACK(expected_seq_num) as last_ack_pkt
        #     send last_ack_pkt to the network
        #     increment expected_seq_num
        pass

    def timer_interrupt(self):
        """Retransmit the outstanding Go-Back-N window after a timeout."""

        # IF window_base >= next_seq_num:
        #     RETURN (the timer event is stale; there is nothing outstanding)
        #
        # restart the sender timer
        # FOR every sequence from window_base through next_seq_num - 1:
        #     resend unacked_buffer[sequence]
        #
        # Go-Back-N retransmits the *whole* outstanding window after timeout.
        pass

    def create_data_pkt(self, seq_num, payload):
        """Return a DATA ``bytes`` packet for integer ``seq_num`` and string payload."""

        # Convert payload to UTF-8 bytes, since payload length is a byte count.
        # Pack a DATA header with checksum set to zero.
        # Calculate the Internet checksum over that header plus payload bytes.
        # Repack the header with the calculated checksum and append the payload.
        pass

    def create_ack_pkt(self, seq_num):
        """Return an ACK ``bytes`` packet for integer ``seq_num``."""

        # Pack ACK(type=ACK, sequence=seq_num, checksum=0).
        # Calculate its Internet checksum.
        # Return the same fixed-size ACK with the checksum filled in.
        pass

    def create_checksum(self, packet):
        """Return the integer 16-bit Internet checksum for packet ``bytes``."""

        # If packet length is odd, add one zero byte for calculation only.
        # Set total to zero.
        # FOR every two-byte, big-endian word:
        #     add the word to total
        #     fold any carry above 16 bits back into total's low 16 bits
        # Fold one final carry, then return the 16-bit one's complement.
        #
        # Running this over an intact packet INCLUDING its checksum returns 0.
        pass

    def unpack_pkt(self, packet):
        """Return the documented DATA or ACK fields as a dictionary."""

        # Require a complete two-byte type field first.
        #
        # IF type is ACK:
        #     require exactly ACK_SIZE bytes; no extra payload is allowed
        #     unpack and return type, sequence number, and checksum
        #
        # IF type is DATA:
        #     require the complete DATA header
        #     unpack type, sequence, checksum, and advertised payload length
        #     require total length == DATA_HEADER_SIZE + advertised length
        #     UTF-8 decode the payload and return every documented field
        #
        # Otherwise reject the packet as an unknown type.
        pass

    def is_corrupt(self, packet):
        """Return whether packet ``bytes`` fail the Internet checksum."""

        # First ensure the packet has a valid shape through unpack_pkt.
        # A packet with a valid checksum but invalid length is still unusable.
        # Then return whether create_checksum(packet) is nonzero.
        pass
