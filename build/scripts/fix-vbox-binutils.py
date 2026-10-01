from pathlib import Path
p = Path('/opt/aether/scripts/build-vbox.sh')
s = p.read_text()
needle = 'source "$base/build/vbox-$suffix/env.sh"'
block = '''# Keep target archive/link/objcopy tools separate from native build generators.
for tool in GXX3 GCC3 GXX32 GCC32; do
    printf 'TOOL_%s_AR := %s-ar\\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_RANLIB := %s-ranlib\\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_LD_SYSMOD := %s-ld\\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_OBJCOPY := %s-objcopy\\n' "$tool" "$tc" >> LocalConfig.kmk
done
'''
if block not in s:
    s = s.replace(needle, block + needle)
p.write_text(s)
