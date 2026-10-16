import socket
import ipaddress

SERVERS = [('159.65.95.225', 60722), ('46.101.112.157', 60722), ('139.162.158.202', 60722)]

def identity(packet, offset, did):
    raw = did.encode('ascii')
    if not 1 <= len(raw) <= 59:
        raise RuntimeError('Longueur identifiant incompatible')
    packet[offset:offset+3] = b'ajy'
    packet[offset+12:offset+12+len(raw)] = raw

def relay_request(did, nonce, relay):
    p = bytearray(100)
    p[:4] = bytes.fromhex('f1800060')
    identity(p, 4, did)
    p[80:82] = (2).to_bytes(2, 'big')
    p[82:84] = relay[1].to_bytes(2, 'little')
    p[84:88] = socket.inet_aton(relay[0])[::-1]
    p[96:100] = nonce
    return bytes(p)

def relay_join(did, nonce, endpoint):
    p = bytearray(88)
    p[:4] = bytes.fromhex('f1830054')
    p[4:8] = nonce
    identity(p, 8, did)
    p[84:88] = bytes.fromhex('00011400')
    # Native SDK writes the relay destination sockaddr in network-converted form.
    p[68:70] = (2).to_bytes(2, 'big')
    p[70:72] = endpoint[1].to_bytes(2, 'little')
    p[72:76] = socket.inet_aton(endpoint[0])[::-1]
    return bytes(p)

def relay_target(data):
    if len(data) != 24 or data[:4] != bytes.fromhex('f1820014'):
        return None
    if data[4:6] != bytes.fromhex('0002'):
        return None
    ip = socket.inet_ntoa(data[8:12][::-1])
    port = int.from_bytes(data[6:8], 'little')
    if not ipaddress.ip_address(ip).is_global or not 1 <= port <= 65535:
        return None
    return (ip, port), data[20:24]

