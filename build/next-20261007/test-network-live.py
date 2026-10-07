#!/usr/bin/env python3
"""Exercise Home -> Public in disposable network namespaces, never host rules."""
import importlib.machinery,importlib.util,json,os,select,socket,subprocess,sys,threading,time
from pathlib import Path
if os.environ.get('AETHER_NET_TEST')!='1':
 os.execvp('unshare',['unshare','--net','env','AETHER_NET_TEST=1',sys.executable,*sys.argv])
source=Path(sys.argv[1]).resolve()
loader=importlib.machinery.SourceFileLoader('firewall',str(source))
spec=importlib.util.spec_from_loader(loader.name,loader);fw=importlib.util.module_from_spec(spec);loader.exec_module(fw)
def run(*args,**kw):return subprocess.run(args,check=True,**kw)
peer=subprocess.Popen(['unshare','--net','sleep','180'])
clients=[]
try:
 for _ in range(100):
  if os.readlink(f'/proc/{peer.pid}/ns/net')!=os.readlink('/proc/self/ns/net'):break
  time.sleep(.02)
 else:raise RuntimeError('Peer namespace did not start')
 prefix=['nsenter','-t',str(peer.pid),'-n']
 run('ip','link','add','aether-test0','type','veth','peer','name','aether-peer0')
 run('ip','link','set','aether-peer0','netns',str(peer.pid))
 run('ip','addr','add','192.0.2.1/24','dev','aether-test0');run('ip','link','set','aether-test0','up');run('ip','link','set','lo','up')
 run(*prefix,'ip','addr','add','192.0.2.2/24','dev','aether-peer0');run(*prefix,'ip','link','set','aether-peer0','up');run(*prefix,'ip','link','set','lo','up')
 listener=socket.socket();listener.bind(('192.0.2.1',8443));listener.listen()
 def echo():
  while True:
   connection,_=listener.accept()
   def serve(c):
    with c:
     while True:
      data=c.recv(1024)
      if not data:return
      c.sendall(data)
   threading.Thread(target=serve,args=(connection,),daemon=True).start()
 threading.Thread(target=echo,daemon=True).start()
 identity='4c49464d-0000-4000-8000-111111111111'
 config={'tcp':[],'udp':[],'home_tcp':[8443],'trusted_connections':[identity]}
 fw.apply(config,{identity:'aether-test0'})
 client_code="""import socket,sys
s=socket.create_connection(('192.0.2.1',8443),3);s.settimeout(2)
s.sendall(b'home');assert s.recv(4)==b'home';print('HOME_OK',flush=True)
input()
try:
 s.sendall(b'public');data=s.recv(6)
except socket.timeout:print('PUBLIC_BLOCKED',flush=True)
else:raise SystemExit('Existing inbound connection survived trust removal: '+repr(data))
"""
 client=subprocess.Popen([*prefix,sys.executable,'-u','-c',client_code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);clients.append(client)
 if not select.select([client.stdout],[],[],10)[0] or client.stdout.readline().strip()!='HOME_OK':raise RuntimeError('Home connection failed')
 fw.apply(config,{})
 client.stdin.write('\n');client.stdin.flush()
 out,err=client.communicate(timeout=8)
 assert client.returncode==0 and out.strip()=='PUBLIC_BLOCKED',(out,err)
 denied=run(*prefix,sys.executable,'-c',"import socket\ns=socket.socket();s.settimeout(1)\ntry:s.connect(('192.0.2.1',8443))\nexcept (TimeoutError,ConnectionError):pass\nelse:raise SystemExit('Public accepted new inbound connection')")
 # Explicit global exceptions retain their documented behavior.
 config['tcp']=[8443];fw.apply(config,{})
 run(*prefix,sys.executable,'-c',"import socket\ns=socket.create_connection(('192.0.2.1',8443),3);s.sendall(b'ok');assert s.recv(2)==b'ok'")
 print(json.dumps({'home_accept':True,'public_blocks_existing_inbound':True,'public_blocks_new_inbound':True,'explicit_global_port_preserved':True}))
finally:
 for client in clients:
  if client.poll() is None:client.kill();client.wait()
 peer.terminate();peer.wait(timeout=5)
