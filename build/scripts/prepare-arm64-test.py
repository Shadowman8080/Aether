from pathlib import Path
base = Path('/opt/aether')
p = (base/'scripts/test-boot-x86.py').read_text()
start = p.index("firmware = ")
end = p.index('proc = subprocess.Popen')
p = p[:start] + '''firmware = 'uefi'
log_path = base/'logs/boot-arm64-uefi.log'
variables = base/'build/test-arm64-uefi-vars.fd'
shutil.copyfile('/usr/share/AAVMF/AAVMF_VARS.fd', variables)
cmd = ['qemu-system-aarch64', '-machine', 'virt', '-accel', 'tcg',
       '-cpu', 'cortex-a53', '-smp', '2', '-m', '1024', '-display', 'none',
       '-serial', 'stdio', '-monitor', 'none', '-no-reboot', '-nic', 'none',
       '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/AAVMF/AAVMF_CODE.fd',
       '-drive', f'if=pflash,format=raw,file={variables}',
       '-device', 'virtio-scsi-pci,id=scsi0',
       '-drive', f'if=none,id=cd0,format=raw,media=cdrom,readonly=on,file={base}/images/aether-0.1.1-arm64-vm.iso',
       '-device', 'scsi-cd,drive=cd0,bus=scsi0.0,bootindex=1']
''' + p[end:]
p = p.replace('time.monotonic() + 300', 'time.monotonic() + 600')
(base/'scripts/test-boot-arm64.py').write_text(p)
