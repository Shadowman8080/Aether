from pathlib import Path
r = Path('/opt/aether')
tool = r/'configs/kbuild-tools/GXX3HOST.kmk'
tool.parent.mkdir(parents=True, exist_ok=True)
tool.write_text(Path('/usr/share/kBuild/tools/GXX3.kmk').read_text().replace('GXX3', 'GXX3HOST'))
p = r/'scripts/build-vbox.sh'
s = p.read_text()
s = s.replace("cat > LocalConfig.kmk <<'CFG'", "cat > LocalConfig.kmk <<'CFG'\ninclude /opt/aether/configs/kbuild-tools/GXX3HOST.kmk")
s = s.replace('VBOX_OSE=1 VBOX_SVN_REV=', 'TEMPLATE_VBoxBldProg_TOOL=GXX3HOST TEMPLATE_VBoxAdvBldProg_TOOL=GXX3HOST VBOX_OSE=1 VBOX_SVN_REV=')
p.write_text(s)
