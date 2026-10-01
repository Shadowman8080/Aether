#!/usr/bin/env python3
from pathlib import Path
import shutil,sys,subprocess
key,source=sys.argv[1:];src=Path(source)
def call(*args): subprocess.run(args,check=True)
Path('/etc/xml').mkdir(exist_ok=True)
if not Path('/etc/xml/catalog').exists(): call('xmlcatalog','--noout','--create','/etc/xml/catalog')
if key=='docbook-45-xml':
 dest=Path('/usr/share/xml/docbook/xml-dtd-4.5');dest.mkdir(parents=True,exist_ok=True)
 for p in src.iterdir():
  if p.name.startswith('.'): continue
  if p.is_dir(): shutil.copytree(p,dest/p.name,dirs_exist_ok=True)
  else: shutil.copy2(p,dest/p.name)
 catalog=str(dest/'catalog.xml')
 for ver in ('4.1.2','4.2','4.3','4.4','4.5'):
  url='http://www.oasis-open.org/docbook/xml/'+ver
  call('xmlcatalog','--noout','--add','public','-//OASIS//DTD DocBook XML V'+ver+'//EN',url+'/docbookx.dtd',catalog)
  for kind in ('rewriteSystem','rewriteURI'): call('xmlcatalog','--noout','--add',kind,url,'file://'+str(dest),catalog)
 for kind,prefix in [('delegatePublic','-//OASIS//ENTITIES DocBook XML'),('delegatePublic','-//OASIS//DTD DocBook XML'),('delegateSystem','http://www.oasis-open.org/docbook/'),('delegateURI','http://www.oasis-open.org/docbook/')]:
  call('xmlcatalog','--noout','--add',kind,prefix,'file://'+catalog,'/etc/xml/catalog')
else:
 call('patch','-Np1','-i','/sources/lfs-cache/docbook-xsl-nons-1.79.2-stack_fix-1.patch')
 dest=Path('/usr/share/xml/docbook/xsl-stylesheets-nons-1.79.2')
 shutil.copytree(src,dest,dirs_exist_ok=True)
 if not (dest/'VERSION.xsl').exists(): (dest/'VERSION.xsl').symlink_to('VERSION')
 for url in ('http://docbook.sourceforge.net/release/xsl/current/','http://docbook.sourceforge.net/release/xsl/1.79.2/','http://cdn.docbook.org/release/xsl/current/','http://cdn.docbook.org/release/xsl/1.79.2/'):
  for kind in ('rewriteSystem','rewriteURI'): call('xmlcatalog','--noout','--add',kind,url,'file://'+str(dest)+'/','/etc/xml/catalog')
