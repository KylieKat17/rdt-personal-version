# Go-Back-N Host Pseudocode

This is a logic guide for `gbn_host.py`. It preserves the starter file's
methods and state names, but deliberately uses pseudocode rather than working
Python. Read it alongside `PROTOCOL.md` and the original starter in
`template/gbn_host.py`.

## State created in `__init__`

```text
store simulator, local entity, timer interval, and window size

# Sender state
window_base = 0                  # oldest DATA not cumulatively ACKed
next_seq_num = 0                 # sequence number for next new DATA
unacked_buffer = empty mapping   # sequence number -> already-made DATA packet
app_layer_buffer = empty queue   # payloads waiting for a window slot

# Receiver state
expected_seq_num = 0             # only this DATA can be delivered next
last_ack_pkt = ACK(MAX_UNSIGNED_INT)
                                # means "no DATA has been received yet"
```

## `receive_from_application_layer(payload)`

```text
put payload at the end of app_layer_buffer

WHILE app_layer_buffer is not empty
      AND next_seq_num is inside the sender window:

    was_idle = (window_base == next_seq_num)
              # no outstanding DATA before this send

    remove the oldest payload from app_layer_buffer
    make DATA(next_seq_num, payload)
    save it in unacked_buffer[next_seq_num]
    send it to the network

    IF was_idle:
        start the single sender timer

    next_seq_num = next_seq_num + 1
```

The `WHILE` loop is also useful as a private helper (for example,
`_fill_window`) because a cumulative ACK can open more than one slot.

## `receive_from_network_layer(packet)`

```text
read the packet's leading type field, if it exists

IF the type is unknown or missing:
    ignore the packet
    RETURN

TRY to unpack the packet exactly:
    # ACK must be exactly 8 bytes.
    # DATA must have its complete 12-byte header and exactly its advertised
    # UTF-8 payload length.
IF unpacking fails:
    IF its known type was DATA:
        resend last_ack_pkt
    RETURN

IF packet is an ACK:
    IF packet is corrupt:
        ignore it
        RETURN

    ack_num = ACK's sequence number
    IF ack_num is older than window_base OR ack_num was never sent yet:
        ignore it                         # duplicate or impossible ACK
        RETURN

    FOR every sequence from window_base through ack_num:
        remove that sequence from unacked_buffer

    window_base = ack_num + 1
    stop the current timer

    IF there is still outstanding DATA:
        start a new timer for the new oldest DATA

    fill any newly opened window slots with waiting application payloads
    RETURN

IF packet is DATA:
    IF packet is corrupt OR packet.sequence != expected_seq_num:
        do not deliver or buffer this DATA
        resend last_ack_pkt               # duplicate ACK / GBN recovery hint
        RETURN

    deliver packet.payload to the application
    last_ack_pkt = ACK(expected_seq_num)
    send last_ack_pkt to the network
    expected_seq_num = expected_seq_num + 1
```

## `timer_interrupt()`

```text
IF there are no outstanding packets:
    RETURN                                # harmless stale timer event

start the single sender timer again

FOR every sequence from window_base up to (but not including) next_seq_num:
    resend unacked_buffer[sequence]
```

This is the defining Go-Back-N behavior: a timeout retransmits the whole
outstanding window, not only the oldest packet.

## `create_data_pkt(seq_num, payload)`

```text
convert payload string to UTF-8 bytes
make a DATA header containing:
    type = DATA
    sequence number = seq_num
    checksum = 0
    payload length = number of UTF-8 bytes

checksum = Internet checksum over (zero-checksum header + payload bytes)

return the same header with checksum filled in, followed by payload bytes
```

## `create_ack_pkt(seq_num)`

```text
make ACK(type=ACK, sequence=seq_num, checksum=0)
calculate the Internet checksum over that temporary packet
return ACK with the calculated checksum filled in
```

## `create_checksum(packet)`

```text
IF packet has an odd number of bytes:
    append one zero byte for calculation only

total = 0
FOR each consecutive pair of bytes:
    interpret the pair as one big-endian 16-bit word
    add the word to total
    fold any carry above bit 16 back into the low 16 bits

fold any final carry once more
return one's complement of total, limited to 16 bits
```

When this function is called on an intact packet that already contains its
stored checksum, it returns zero.

## `unpack_pkt(packet)` and `is_corrupt(packet)`

```text
unpack_pkt:
    require at least a complete type field
    IF type is ACK:
        require exactly ACK_SIZE bytes
        return packet type, sequence number, and checksum
    IF type is DATA:
        require a complete DATA header
        read advertised payload length
        require exact total packet length: header size + advertised length
        decode the payload as UTF-8
        return all DATA fields
    otherwise, reject as an unknown packet type

is_corrupt:
    IF unpack_pkt rejects the packet:
        return true
    return (create_checksum(packet) is not zero)
```
