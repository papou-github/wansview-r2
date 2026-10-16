"""On-demand controller, cached still and loopback-only MPEG-TS bridge."""
import asyncio
from collections import deque
import secrets
import socket
import time
from aiohttp import web
from .session import run_session, RelayTimeout

class Controller:
    def __init__(self, client, device, ffmpeg, task_factory=asyncio.create_task):
        self.client=client
        self.device=device
        self.ffmpeg=ffmpeg
        self.create_task=task_factory
        self.did=device['deviceId']
        self.alias=device.get('display_name','Wansview R2')
        self.token=secrets.token_urlsafe(32)
        self.port=None
        self.runner=None
        self.task=None
        self.stop_event=asyncio.Event()
        self.ready=asyncio.Event()
        self.jpeg=None
        self.last_image=None
        self.error=None
        self.stats={}
        self.status='idle'
        self.deadline=0
        self._listeners=set()
        self._ring=deque()
        self._ring_size=0
        self._viewers=set()
        self._process=None
        self._pump_task=None
        self._thumbnail_task=None
        self._operation=asyncio.Lock()
        self._capture_only=False
        self._closed=False

    @property
    def active(self):
        return self.task is not None and not self.task.done() and time.monotonic()<self.deadline

    def listen(self, callback):
        self._listeners.add(callback)
        return lambda: self._listeners.discard(callback)

    def notify(self):
        for listener in tuple(self._listeners):
            listener()

    async def setup(self):
        app=web.Application()
        app.router.add_get('/'+self.token+'/stream.ts', self._http_stream)
        self.runner=web.AppRunner(app, access_log=None, shutdown_timeout=2)
        await self.runner.setup()
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('127.0.0.1',0))
        sock.setblocking(False)
        self.port=sock.getsockname()[1]
        try:
            await web.SockSite(self.runner,sock).start()
        except BaseException:
            sock.close()
            await self.runner.cleanup()
            raise

    @property
    def stream_url(self):
        return f'http://127.0.0.1:{self.port}/{self.token}/stream.ts'

    async def start(self, capture_only=False):
        async with self._operation:
            if self._closed: return
            if self.active:
                if capture_only: return
                if not self._capture_only: return  # Do not renew the battery lease automatically.
                await self._stop()
            self.stop_event=asyncio.Event()
            self.ready=asyncio.Event()
            self._ring.clear()
            self._ring_size=0
            self.stats={'frames':0,'bytes':0,'attempts':0}
            self.error=None
            self.status='connecting'
            self.deadline=time.monotonic()+(45 if capture_only else 60)
            self._capture_only=capture_only
            self.task=self.create_task(self._run())
            self.notify()

    async def stop(self):
        async with self._operation:
            await self._stop()

    async def _stop(self):
        self.stop_event.set()
        task=self.task
        if task and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task),3)
            except asyncio.TimeoutError:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
        self.status='idle'
        self.notify()

    async def capture(self):
        if self.active:
            if self.jpeg: return
            if self._thumbnail_task:
                await asyncio.shield(self._thumbnail_task)
                if self.jpeg: return
            raise RuntimeError('LiveAlreadyActive')
        previous=self.last_image
        await self.start(capture_only=True)
        if self.task:
            await asyncio.shield(self.task)
        if self.last_image==previous:
            raise RuntimeError('Aucune nouvelle image ; consulter les attributs de la caméra')

    def _config(self):
        value=self.device.get('context',{})
        if isinstance(value,str):
            import json
            value=json.loads(value)
        value=value.get('config',{})
        if isinstance(value,str):
            import json
            value=json.loads(value)
        return value

    async def _run(self):
        try:
            if hasattr(self,'prepare_account'): await self.prepare_account()
            config=self._config()
            gateway=config['appGatewayUrl'].rstrip('/')
            if not gateway.endswith('/api'): gateway+='/api'
            response=await self.client.post('/v1/fetch-infos',
                {'devices':[{'did':self.did,'scopes':[],'isShare':False}]},signed=True,base=gateway)
            infos=response.get('infos',[])
            if len(infos)!=1: raise RuntimeError('UnexpectedCameraInfo')
            key=infos[0].get('info',{}).get('base',{}).get('accessKey')
            if not isinstance(key,str) or not 1<=len(key.encode())<=256:
                raise RuntimeError('MissingCameraKey')
            keepalive=config['appKeepAliveUrl'].rstrip('/')
            if not keepalive.endswith('/api'): keepalive+='/api'
            for attempt in range(2):
                if self.stop_event.is_set() or time.monotonic()>=self.deadline: break
                self.stats['attempts']=attempt+1
                self.notify()
                await self.client.post('/v1/wakeup',{'deviceId':self.did,'timeZone':'Europe/Paris',
                    'deviceMode':self.device['deviceMode'],'vendorCode':self.device['vendorCode']},
                    signed=True,base=keepalive,device_id=self.did)
                try:
                    await run_session(self.did,key,self._frame,self.stop_event,self.deadline,self.stats)
                    break
                except RelayTimeout:
                    if attempt or self.stats.get('frames') or self.deadline-time.monotonic()<5:
                        raise
                    await asyncio.sleep(1)
            if not self.stats.get('frames') and not self.stop_event.is_set():
                raise RelayTimeout()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Only safe class/endpoint metadata; never exception text, camera keys or credentials.
            self.error=type(error).__name__
            hostname=getattr(error,'diagnostic_hostname',None)
            if hostname: self.stats['cloud_hostname']=hostname
            self.status='error'
        finally:
            cleanup=self.create_task(self._finish_media())
            try: await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
            self.ready.set()
            if self.status!='error': self.status='idle'
            self.notify()

    async def _frame(self, raw, codec, fps):
        if self.stop_event.is_set() or time.monotonic()>=self.deadline: return
        if self._thumbnail_task is None:
            self._thumbnail_task=self.create_task(self._make_thumbnail(raw,codec))
        if self._capture_only:
            await self._thumbnail_task
            self.stop_event.set()
            return
        if self._process is None:
            self._process=await asyncio.create_subprocess_exec(self.ffmpeg,
                '-hide_banner','-loglevel','error','-probesize','32768','-analyzeduration','0',
                '-r',str(min(30,max(1,fps))),'-f',codec,'-i','pipe:0','-an','-c:v','copy',
                '-f','mpegts','-mpegts_flags','resend_headers','-muxdelay','0','-muxpreload','0','pipe:1',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            self._pump_task=self.create_task(self._pump())
        self.status='streaming'
        self._process.stdin.write(raw)
        await asyncio.wait_for(self._process.stdin.drain(),3)

    async def _pump(self):
        while True:
            chunk=await self._process.stdout.read(32768)
            if not chunk: break
            self._ring.append(chunk)
            self._ring_size+=len(chunk)
            while self._ring_size>2*1024*1024:
                self._ring_size-=len(self._ring.popleft())
            self.ready.set()
            for queue in tuple(self._viewers):
                if queue.full():
                    self._viewers.discard(queue)
                    while not queue.empty(): queue.get_nowait()
                    queue.put_nowait(None)
                else: queue.put_nowait(chunk)

    async def _make_thumbnail(self,raw,codec):
        process=None
        try:
            process=await asyncio.create_subprocess_exec(self.ffmpeg,'-v','error','-f',codec,
                '-i','pipe:0','-frames:v','1','-vf','scale=960:-2','-f','image2pipe','-vcodec','mjpeg','pipe:1',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            data,_=await asyncio.wait_for(process.communicate(raw),8)
            if process.returncode==0 and data.startswith(b'\xff\xd8') and len(data)<4*1024*1024:
                self.jpeg=data
                self.last_image=time.time()
                self.notify()
        finally:
            if process and process.returncode is None:
                process.kill()
                await process.wait()

    async def _finish_media(self):
        process=self._process
        if process:
            if process.stdin: process.stdin.close()
            try: await asyncio.wait_for(process.wait(),2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self._pump_task:
            await asyncio.gather(self._pump_task,return_exceptions=True)
        if self._thumbnail_task:
            await asyncio.gather(self._thumbnail_task,return_exceptions=True)
        self._process=self._pump_task=self._thumbnail_task=None
        for queue in tuple(self._viewers):
            while queue.full(): queue.get_nowait()
            queue.put_nowait(None)
        self._viewers.clear()

    async def _http_stream(self,request):
        if not self.active or self._capture_only:
            raise web.HTTPServiceUnavailable(text='Direct non activé')
        try: await asyncio.wait_for(self.ready.wait(),35)
        except asyncio.TimeoutError:
            raise web.HTTPGatewayTimeout(text='Caméra non disponible') from None
        if not self.active or not self._ring:
            raise web.HTTPServiceUnavailable(text='Flux indisponible')
        queue=asyncio.Queue(maxsize=128)
        initial=list(self._ring)
        self._viewers.add(queue)
        response=web.StreamResponse(headers={'Content-Type':'video/mp2t','Cache-Control':'no-store'})
        try:
            await response.prepare(request)
            for chunk in initial: await response.write(chunk)
            while self.active:
                chunk=await asyncio.wait_for(queue.get(),5)
                if chunk is None: break
                await response.write(chunk)
        except (ConnectionError,asyncio.TimeoutError,RuntimeError):
            pass
        finally:
            self._viewers.discard(queue)
        return response

    async def close(self):
        self._closed=True
        await self.stop()
        if self.runner:
            await self.runner.cleanup()
