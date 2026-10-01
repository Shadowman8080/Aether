#!/usr/bin/env python3
from pathlib import Path
import os,subprocess
build=Path('/build/aether-greeter'); build.mkdir(exist_ok=True)
with Path('/build/logs/aether-greeter.log').open('w') as log:
 for command in [
  ['cmake','-S','/recipes/greeter','-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr'],
  ['cmake','--build',str(build),'--parallel',str(os.cpu_count())],
  ['cmake','--install',str(build)]]:
  subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
print('DONE aether-greeter',flush=True)
