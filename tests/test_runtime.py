"""Offline tests: emulated camera, real ffmpeg and loopback HTTP; no credentials."""
import asyncio
import importlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'custom_components'/'wansview_r2'
pkg=types.ModuleType('r2_test_package')
pkg.__path__=[str(PACKAGE)]
sys.modules[pkg.__name__]=pkg
protocol=importlib.import_module('r2_test_package.camera_protocol')
wire=importlib.import_module('r2_test_package.wire')
session=importlib.import_module('r2_test_package.session')
controller_module=importlib.import_module('r2_test_package.controller')

DID='TESTCAMERA'
KEY='OFFLINE-TEST-KEY'

def make_video():
    return subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i',
        'testsrc2=size=320x240:rate=15','-frames:v','1','-c:v','libx264','-preset','ultrafast',
        '-tune','zerolatency','-pix_fmt','yuv420p','-f','h264','pipe:1'])

def media_frame(raw):
    header=bytearray(48)
    header[:4]=b'HH02'
    struct.pack_into('<H',header,6,2)
    struct.pack_into('<I',header,12,len(raw))
    header[25]=15
    return bytes(header)+raw

class FakeNetwork:
    def __init__(self,raw):
        self.queue=asyncio.Queue()
        self.raw=raw
        self.peer=(session.RELAYS[0][0],14000)
        self.nonce=bytes.fromhex('12345678')
        self.allocated=False
        self.ready=False
        self.sent=[]
        self.closed=False

    async def send(self,data,peer):
        self.sent.append((data,peer))
        if data[:2]==b'\xf1\x72' and not self.allocated:
            self.allocated=True
            await self.queue.put((bytes.fromhex('f1730008')+self.nonce+struct.pack('!H',14000)+bytes(2),session.RELAYS[0]))
        elif data[:2]==b'\xf1\x80':
            assert data[96:100]==self.nonce
            await self.queue.put((bytes.fromhex('f1820014')+data[80:100],peer))
        elif data[:2]==b'\xf1\x83' and not self.ready:
            self.ready=True
            response=bytearray(92)
            response[:4]=bytes.fromhex('f1840058')
            wire.identity(response,4,DID)
            await self.queue.put((bytes(response),self.peer))
        elif data[:2]==b'\xf1\xd0':
            command=int.from_bytes(data[14:16],'little')
            if command==150:
                expected=protocol.auth_datagram(KEY,int.from_bytes(protocol.rc4(KEY.encode(),data[56:])[16:20],'little'))
                assert expected==data
                response=bytearray(48)
                response[:4]=b'HH01'
                response[4]=1
                struct.pack_into('<HI',response,6,151,4)
                response+=protocol.rc4(KEY.encode(),bytes(4))
                await self.queue.put((b'\xf1\xd0'+(len(response)+4).to_bytes(2,'big')+b'\xd1\0\0\0'+response,self.peer))
            elif command==256:
                assert protocol.rc4(KEY.encode(),data[56:])==bytes(4)
                frame=media_frame(self.raw)
                pieces=[frame[i:i+211] for i in range(0,len(frame),211)]
                order=list(range(len(pieces)))
                if len(order)>2: order[0],order[1]=order[1],order[0]
                for index in order:
                    body=b'\xd1\0'+(index+1).to_bytes(2,'big')+pieces[index]
                    packet=b'\xf1\xd0'+len(body).to_bytes(2,'big')+body
                    await self.queue.put((packet,self.peer))
                    if index==0: await self.queue.put((packet,self.peer))

    async def receive(self):
        return await asyncio.wait_for(self.queue.get(),.2)

    def close(self): self.closed=True

class OfflineTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls): cls.raw=make_video()

    async def test_protocol_full_session_and_cleanup(self):
        network=FakeNetwork(self.raw)
        stop=asyncio.Event()
        frames=[]
        async def receive(raw,codec,fps):
            frames.append(raw)
            stop.set()
        stats={}
        await session.run_session(DID,KEY,receive,stop,time.monotonic()+3,stats,lambda:network)
        self.assertEqual(frames,[self.raw])
        self.assertTrue(stats['authenticated'])
        self.assertTrue(network.closed)
        commands=[int.from_bytes(p[14:16],'little') for p,peer in network.sent if p[:2]==b'\xf1\xd0']
        self.assertEqual(commands,[150,256,258])
        self.assertTrue(any(p==b'\xf1\xf0\0\0' for p,peer in network.sent))

    async def test_idle_no_wake_http_and_real_media(self):
        from aiohttp import ClientSession
        class Cloud:
            def __init__(self): self.calls=[]
            async def post(self,route,*args,**kwargs):
                self.calls.append(route)
                if route=='/v1/fetch-infos': return {'infos':[{'info':{'base':{'accessKey':KEY}}}]}
                return {}
        cloud=Cloud()
        device={'deviceId':DID,'deviceMode':'NAV','vendorCode':'GLY',
            'context':{'config':{'appGatewayUrl':'https://test.ajcloud.net','appKeepAliveUrl':'https://test.ajcloud.net'}}}
        manager=controller_module.Controller(cloud,device,'ffmpeg')
        attempts=[]
        async def fake_session(did,key,on_frame,stop,deadline,stats):
            attempts.append(1)
            if len(attempts)==1: raise session.RelayTimeout()
            for i in range(35):
                if stop.is_set() or time.monotonic()>=deadline: break
                stats['frames']=stats.get('frames',0)+1
                await on_frame(self.raw,'h264',15)
                await asyncio.sleep(.03)
        try:
            await manager.setup()
            async with ClientSession() as browser:
                async with browser.get(manager.stream_url) as response:
                    self.assertEqual(response.status,503)
                self.assertEqual(cloud.calls,[])
                with patch.object(controller_module,'run_session',fake_session):
                    await manager.start()
                    lease=manager.deadline
                    await manager.start()
                    self.assertEqual(manager.deadline,lease)
                    async with browser.get(manager.stream_url) as response:
                        self.assertEqual(response.status,200)
                        ts=await response.read()
                    await manager.task
                self.assertEqual(len(attempts),2)
                self.assertTrue(manager.jpeg.startswith(b'\xff\xd8'))
                self.assertEqual(cloud.calls.count('/v1/wakeup'),2)
                result=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height',
                    '-of','json','pipe:0'],input=ts,stdout=subprocess.PIPE,check=True)
                streams=json.loads(result.stdout)['streams']
                self.assertEqual(streams[0]['codec_name'],'h264')
                self.assertEqual(streams[0]['width'],320)
                before=len(cloud.calls)
                async with browser.get(manager.stream_url) as response:
                    self.assertEqual(response.status,503)
                self.assertEqual(len(cloud.calls),before)
                self.assertIsNone(manager._process)
        finally:
            await manager.close()

    async def test_timeout_closes_socket_without_video(self):
        class Silent(FakeNetwork):
            async def send(self,data,peer): self.sent.append((data,peer))
        network=Silent(self.raw)
        with self.assertRaises(session.RelayTimeout):
            await session.run_session(DID,KEY,lambda *args:None,asyncio.Event(),time.monotonic()+.05,{},lambda:network)
        self.assertTrue(network.closed)
        self.assertFalse(any(p[:2]==b'\xf1\xd0' for p,peer in network.sent))

if __name__=='__main__': unittest.main()
