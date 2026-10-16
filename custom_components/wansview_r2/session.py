"""Bounded, cancellable session using the validated R2 wire protocol."""
import asyncio
import os
import socket
import time
from .camera_protocol import ControlStream, ack_datagram, auth_datagram, control_datagram, rc4
from .wire import SERVERS, identity, relay_request, relay_join, relay_target

RELAYS = [('172.235.190.14', 12300), ('172.236.209.56', 12300)]

class RelayTimeout(Exception):
    pass

class CameraAuthenticationError(Exception):
    pass

class UdpNetwork:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 0))
        self.sock.setblocking(False)
        self.loop = asyncio.get_running_loop()

    async def send(self, data, peer):
        await self.loop.sock_sendto(self.sock, data, peer)

    async def receive(self):
        return await asyncio.wait_for(self.loop.sock_recvfrom(self.sock, 4096), .2)

    def close(self):
        self.sock.close()

async def run_session(device_id, key, on_frame, stop, deadline, stats, network_factory=UdpNetwork):
    """Deliver Annex B frames until stop/deadline; never write media or keys to disk."""
    network = network_factory()
    allocations = {}
    requests = {}
    targets = {}
    selected = None
    auth = None
    auth_acked = False
    video_acked = False
    auth_tries = video_tries = 0
    video_packet = None
    auth_at = video_at = None
    first_frame = False
    stream = ControlStream()
    started = time.monotonic()
    next_send = 0
    last_media = None
    try:
        while not stop.is_set() and time.monotonic() < deadline:
            now = time.monotonic()
            if selected is None and now-started >= 16:
                raise RelayTimeout()
            if auth_at is not None and video_at is None and now-auth_at >= 8:
                raise RelayTimeout()
            if video_at is not None and last_media is None and now-video_at >= 10:
                raise RelayTimeout()
            if last_media is not None and now-last_media >= 8:
                raise RelayTimeout()
            if now >= next_send:
                if selected is None:
                    for peer in RELAYS:
                        if peer[0] not in {ip for ip, port in allocations}:
                            for data in (b'\xf1\x00\0\0', b'\xf1\x70\0\0', b'\xf1\x72\0\0'):
                                await network.send(data, peer)
                    for peer in SERVERS:
                        await network.send(b'\xf1\x00\0\0', peer)
                        for packet in requests.values():
                            await network.send(packet, peer)
                    for peer, nonce in targets.items():
                        await network.send(relay_join(device_id, nonce, peer), peer)
                else:
                    if not auth_acked and auth_tries < 5:
                        await network.send(auth, selected)
                        auth_tries += 1
                    if video_packet and not video_acked and video_tries < 5:
                        await network.send(video_packet, selected)
                        video_tries += 1
                    await network.send(b'\xf1\xe0\0\0', selected)
                next_send = now + 1
            try:
                data, peer = await network.receive()
            except asyncio.TimeoutError:
                continue
            if len(data)<4 or data[0]!=0xf1 or int.from_bytes(data[2:4], 'big')!=len(data)-4:
                continue
            if selected is not None:
                if peer != selected:
                    continue
                if data[:2] == b'\xf1\xf0':
                    if not first_frame: raise RelayTimeout()
                    break
                if data[:2] == b'\xf1\xe0':
                    await network.send(b'\xf1\xe1\0\0', peer)
                if data[:4] == bytes.fromhex('f1830054') and len(data)==88:
                    if data[8:11]==b'ajy' and data[20:84].split(b'\0',1)[0]==device_id.encode() and data[4:8]==targets.get(peer):
                        ready=bytearray(92)
                        ready[:4]=bytes.fromhex('f1840058')
                        identity(ready,4,device_id)
                        await network.send(ready,peer)
                if data[:2] == b'\xf1\xd1' and len(data)>=8 and data[4:6]==b'\xd1\0':
                    count=int.from_bytes(data[6:8], 'big')
                    if len(data)==8+2*count:
                        sequences={int.from_bytes(data[i:i+2],'big') for i in range(8,len(data),2)}
                        auth_acked |= 0 in sequences
                        video_acked |= 1 in sequences
                if data[:2] != b'\xf1\xd0' or len(data)<8 or data[4]!=0xd1:
                    continue
                channel=data[5]
                sequence=int.from_bytes(data[6:8], 'big')
                # Do not acknowledge unbuffered data beyond the reordering window.
                if channel == 0 and sequence >= stream.next_sequence + 128:
                    continue
                await network.send(ack_datagram(channel,sequence),peer)
                if channel != 0:
                    continue
                for command, payload in stream.feed(sequence,data[8:]):
                    if command == 151 and len(payload)==4:
                        status=int.from_bytes(rc4(key.encode(),payload),'little',signed=True)
                        if status != 0: raise CameraAuthenticationError()
                        auth_acked=True
                        stats['authenticated']=True
                        if video_packet is None:
                            video_packet=control_datagram(key,256,bytes(4),1)
                            await network.send(video_packet,peer)
                            video_tries=1
                            video_at=time.monotonic()
                    elif command == 257:
                        video_acked=True
                    elif command == 'media' and video_at is not None:
                        codec=int.from_bytes(payload[6:8],'little')
                        raw=payload[48:]
                        if codec not in (2,3):
                            continue
                        if not first_frame:
                            if payload[24]!=0 or not raw.startswith((b'\0\0\0\1',b'\0\0\1')):
                                continue
                            first_frame=True
                        last_media=time.monotonic()
                        stats['frames']=stats.get('frames',0)+1
                        stats['bytes']=stats.get('bytes',0)+len(raw)
                        stats['codec']='h264' if codec==2 else 'hevc'
                        await on_frame(raw,stats['codec'],payload[25] or 15)
                continue
            if peer in RELAYS and data[:4]==bytes.fromhex('f1710000'):
                await network.send(b'\xf1\x72\0\0',peer)
            if peer in RELAYS and data[:4]==bytes.fromhex('f1730008') and len(data)==12:
                port=int.from_bytes(data[8:10],'big')
                target=(peer[0],port)
                if port and target not in allocations and len(allocations)<4:
                    allocations[target]=data[4:8]
                    packet=relay_request(device_id,data[4:8],target)
                    requests[target]=packet
                    for server in SERVERS:
                        await network.send(packet,server)
            if peer in SERVERS:
                offer=relay_target(data)
                if offer:
                    target,nonce=offer
                    if target in allocations and nonce == allocations[target]:
                        targets[target]=nonce
                        await network.send(b'\xf1\x00\0\0',target)
                        await network.send(relay_join(device_id,nonce,target),target)
            if peer in allocations and data[:4]==bytes.fromhex('f1840058') and len(data)==92:
                if data[4:7]==b'ajy' and data[16:80].split(b'\0',1)[0]==device_id.encode():
                    selected=peer
                    auth=auth_datagram(key,int(time.time()))
                    auth_at=time.monotonic()
                    await network.send(auth,peer)
                    auth_tries=1
        if not first_frame and not stop.is_set():
            raise RelayTimeout()
    finally:
        if selected is not None:
            try:
                if video_packet is not None:
                    await asyncio.wait_for(network.send(control_datagram(key,258,b'',2),selected),1)
                await asyncio.wait_for(network.send(b'\xf1\xf0\0\0',selected),1)
            except (OSError,asyncio.TimeoutError):
                pass
        network.close()
