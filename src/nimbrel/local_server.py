#!/usr/bin/env python3
"""Aether-only local gateway. OS users access a Unix socket; inference is private."""
import http.client,json,os,socket,socketserver,struct,threading,urllib.request,time
from pathlib import Path
from server import Handler,State
ENGINE='/run/nimbrel-engine/engine.sock'
class UnixConnection(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect(ENGINE)
class UnixHandler(urllib.request.HTTPHandler):
 def http_open(self,req):return self.do_open(UnixConnection,req)
class LocalHandler(Handler):
 def authorized(self):
  _,uid,_=struct.unpack('3i',self.connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
  return uid==0 or uid>=1000
 def do_POST(self):
  if self.path!='/v1/answer':return self.reply(404,{'error':'Not found.'})
  return super().do_POST()
 def do_GET(self):
  if self.path!='/v1/capabilities':return self.reply(404,{'error':'Not found.'})
  if not self.authorized():return self.reply(403,{'error':'A local desktop account is required.'})
  from server import TASKS
  ready=False
  try:
   with self.server.state.opener.open('http://localhost/health',timeout=2) as r:ready=r.status==200
  except (OSError,urllib.error.URLError):pass
  return self.reply(200,{'name':'Nimbrel','model':'Qwen3.5 0.8B','local':True,'ready':ready,'tasks':list(TASKS),'context_chars':12000,'vision':False,'speech_to_text':False,'image_generation':False,'command_execution':False})
class LocalServer(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
 daemon_threads=True
 request_queue_size=8
 def __init__(self,*args,**kw):
  self.slots=threading.BoundedSemaphore(16);self.activity_lock=threading.Lock();self.active=0;self.last_activity=time.monotonic();super().__init__(*args,**kw)
 def process_request(self,req,addr):
  if not self.slots.acquire(False):self.shutdown_request(req);return
  with self.activity_lock:self.active+=1;self.last_activity=time.monotonic()
  try:super().process_request(req,addr)
  except Exception:
   with self.activity_lock:self.active-=1
   self.slots.release();raise
 def process_request_thread(self,req,addr):
  try:super().process_request_thread(req,addr)
  finally:
   with self.activity_lock:self.active-=1;self.last_activity=time.monotonic()
   self.slots.release()
path=Path('/run/nimbrel/api.sock')
activated=os.environ.get('LISTEN_PID')==str(os.getpid()) and os.environ.get('LISTEN_FDS')=='1'
if activated:
 server=LocalServer(str(path),LocalHandler,bind_and_activate=False)
 server.socket.close();server.socket=socket.socket(fileno=3)
 if server.socket.family!=socket.AF_UNIX or not server.socket.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN):raise RuntimeError('Invalid activation socket')
else:
 path.unlink(missing_ok=True);server=LocalServer(str(path),LocalHandler);path.chmod(0o666)
server.state=State('/var/lib/nimbrel','http://localhost','nimbrel-local')
server.state.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),UnixHandler())
def idle_exit():
 while True:
  time.sleep(30)
  with server.activity_lock:idle=server.active==0 and time.monotonic()-server.last_activity>600
  if idle:server.shutdown();return
if activated:threading.Thread(target=idle_exit,daemon=True).start()
server.serve_forever()
