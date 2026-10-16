"""Small independently implemented subset of the native camera protocol."""
import hashlib
import struct

def rc4(key, data):
    if not key:
        raise ValueError('Empty RC4 key')
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) & 255
        state[i], state[j] = state[j], state[i]
    i = j = 0
    result = bytearray()
    for byte in data:
        i = (i + 1) & 255
        j = (j + state[i]) & 255
        state[i], state[j] = state[j], state[i]
        result.append(byte ^ state[(state[i] + state[j]) & 255])
    return bytes(result)

def auth_payload(access_key, timestamp):
    timestamp &= 0xffffffff
    key = access_key.encode('utf-8')
    digest = hashlib.md5(str(timestamp).encode() + b':' + str(timestamp).encode() + b':' + key).digest()
    plain = digest + struct.pack('<IIB7x', timestamp, timestamp, 1)
    return rc4(key, plain)

def control_datagram(access_key, command, payload, sequence):
    frame = bytearray(48)
    frame[:4] = b'HH01'
    frame[4] = 1
    struct.pack_into('<HI', frame, 6, command, len(payload))
    frame[30] = 127
    body = bytes([0xd1, 0]) + sequence.to_bytes(2, 'big') + bytes(frame) + rc4(access_key.encode('utf-8'), payload)
    return b'\xf1\xd0' + len(body).to_bytes(2, 'big') + body

def auth_datagram(access_key, timestamp):
    # auth_payload already encrypts its structure.
    encrypted = auth_payload(access_key, timestamp)
    return control_datagram(access_key, 150, rc4(access_key.encode('utf-8'), encrypted), 0)

def ack_datagram(channel, sequence):
    body = bytes([0xd1, channel]) + b'\x00\x01' + sequence.to_bytes(2, 'big')
    return b'\xf1\xd1' + len(body).to_bytes(2, 'big') + body

class ControlStream:
    """Reorder channel-zero datagrams and split bounded HH01 control frames."""
    def __init__(self):
        self.next_sequence = 0
        self.pending = {}
        self.buffer = bytearray()

    def feed(self, sequence, data):
        if sequence < self.next_sequence or sequence >= self.next_sequence + 128:
            return []
        self.pending.setdefault(sequence, data)
        while self.next_sequence in self.pending:
            self.buffer.extend(self.pending.pop(self.next_sequence))
            self.next_sequence += 1
        frames = []
        while len(self.buffer) >= 48:
            if self.buffer[:4] not in (b'HH01', b'HH02'):
                # Captured streams contain short zero padding between complete frames.
                offsets = [pos for magic in (b'HH01', b'HH02')
                           if 0 < (pos := self.buffer.find(magic, 1, 20)) <= 16]
                if offsets and not any(self.buffer[:min(offsets)]):
                    del self.buffer[:min(offsets)]
                    continue
                raise RuntimeError('Trame de contrôle inattendue ; arrêt du test')
            size_offset = 12 if self.buffer[:4] == b'HH02' else 8
            size = int.from_bytes(self.buffer[size_offset:size_offset+4], 'little')
            limit = 2 * 1024 * 1024 if self.buffer[:4] == b'HH02' else 65536
            if size > limit:
                raise RuntimeError('Trame de contrôle trop longue ; arrêt du test')
            if len(self.buffer) < 48 + size:
                break
            frame = bytes(self.buffer[:48+size])
            del self.buffer[:48+size]
            frames.append(('media', frame) if frame[:4] == b'HH02' else
                          (int.from_bytes(frame[6:8], 'little'), frame[48:]))
        return frames
