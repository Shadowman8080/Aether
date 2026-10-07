from pathlib import Path
import ast,configparser,shlex,shutil,hashlib
b=Path('/opt/aether/build/release-20261006'); root=b/'root'; additions=b/'additions'
shutil.copy2(additions/'vector',root/'usr/bin/vector'); (root/'usr/bin/vector').chmod(0o755)
shutil.copytree(additions/'org.aether.powermenu',root/'usr/share/plasma/plasmoids/org.aether.powermenu',dirs_exist_ok=True)
shutil.copytree(additions/'AetherGlass',root/'usr/share/sounds/AetherGlass',dirs_exist_ok=True)
shutil.copy2(additions/'manage-sounds.py',root/'usr/bin/aether-sounds'); (root/'usr/bin/aether-sounds').chmod(0o755)
for prefix in [root/'etc/skel',root/'home/aether']:
 p=prefix/'.config/kdeglobals'; p.parent.mkdir(parents=True,exist_ok=True)
 c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str
 if p.exists(): c.read(p)
 if not c.has_section('Sounds'):c.add_section('Sounds')
 c['Sounds']['Theme']='AetherGlass'
 with p.open('w') as f:c.write(f,space_around_delimiters=False)
(root/'usr/share/applications/org.aether.Sounds.desktop').write_text('[Desktop Entry]\nType=Application\nName=Aether Sounds\nComment=Choose your desktop sound theme\nExec=kcmshell6 kcm_soundtheme\nIcon=preferences-desktop-sound\nCategories=Settings;DesktopSettings;\n')
tree=ast.parse((additions/'configure-vmware-desktop.py').read_text())
expr=next(n.value.args[1] for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='write' and ast.literal_eval(n.value.args[0])=='/usr/libexec/aether-guest-display-setup')
hook=eval(compile(ast.Expression(expr),'<generated>','eval'),{'shlex':shlex,'x11':'plasmax11'})
p=root/'usr/libexec/aether-guest-display-setup';p.write_text(hook);p.chmod(0o755)
p=root/'etc/os-release';s=p.read_text();s+='\nBUILD_ID="20261006.1"\n';p.write_text(s)
# Remove only build scratch content shipped in the source ISO, not user data.
for p in (root/'tmp').iterdir():
 if p.is_dir() and not p.is_symlink():shutil.rmtree(p)
 else:p.unlink()
# Current sound files and kernel are checked before packaging.
assert 'CONFIG_MOUSE_PS2_VMMOUSE=y' in (root/'boot/config-6.18.54-aether4').read_text()
assert hashlib.sha256((root/'boot/vmlinuz-6.18.54-aether4').read_bytes()).hexdigest()=='ff9040887d03b36795eca5216228a5a1cd92cf674806839cdb5392b5f0c30ade'
assert not (root/'root/.ssh').exists()
assert not (root/'root/.gnupg').exists()
print('Release overlay patched; original ISO remains read-only.')
