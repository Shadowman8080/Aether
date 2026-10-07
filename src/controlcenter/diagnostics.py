#!/usr/bin/env python3
"""Export an allowlisted support summary, never logs or personal configuration."""
import argparse,json,os,platform,re,shutil,subprocess
from pathlib import Path
SERVICES=('lightdm.service','nimbrel-local.socket','nimbrel-local.service','nimbrel-engine.service','aether-update-check.timer','aether-firewall.service','NetworkManager.service')
STATES={'active','inactive','failed','activating','deactivating','reloading','maintenance','refreshing'}
RESULTS={'success','exit-code','signal','core-dump','timeout','watchdog','start-limit-hit','resources','protocol','oom-kill','exec-condition','condition'}

def service(name):
 try:
  result=subprocess.run(['systemctl','show',name,'--property=ActiveState,Result,NRestarts'],capture_output=True,text=True,timeout=3,check=True)
 except (OSError,subprocess.SubprocessError):return {'available':False}
 data=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
 return {'available':True,'state':data.get('ActiveState') if data.get('ActiveState') in STATES else 'unknown',
  'result':data.get('Result') if data.get('Result') in RESULTS else 'unknown',
  'restarts':int(data['NRestarts']) if re.fullmatch(r'[0-9]{1,9}',data.get('NRestarts','')) else None}

def os_version(path=Path('/etc/os-release')):
 result={}
 try:lines=path.read_text().splitlines()
 except OSError:return result
 for line in lines:
  key,separator,value=line.partition('=');value=value.strip('"')
  if separator and key in ('ID','VERSION_ID','BUILD_ID') and re.fullmatch(r'[A-Za-z0-9._-]{1,80}',value):result[key]=value
 return result

def collect():
 usage=shutil.disk_usage('/')
 return {'schema':1,'scope':'Basic system version, capacities and selected service states only. No logs, users, filenames, IP/MAC addresses, hardware serials, credentials or conversations.',
  'os':os_version(),'architecture':platform.machine(),'kernel':platform.release(),
  'cpu_count':os.cpu_count(),'root_disk_bytes':{'total':usage.total,'free':usage.free},
  'efi_present':Path('/sys/firmware/efi').is_dir(),'tpm_device_present':Path('/dev/tpmrm0').exists(),
  'services':{name:service(name) for name in SERVICES}}

def save(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(data,stream,indent=2);stream.write('\n')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 save(args.output,collect())
 print('Basic diagnostic summary saved. Review it before sharing.')
if __name__=='__main__':main()
