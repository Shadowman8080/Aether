from pathlib import Path
r = Path('/opt/aether')
s = (r/'scripts/test-boot-arm64.py').read_text()
s = s.replace("'-nic', 'none'", "'-nic', 'user,model=virtio-net-pci'")
s = s.replace('boot-arm64-uefi.log', 'boot-network-arm64-uefi.log')
s = s.replace("b'/etc/init.d/S99aether selftest\\n'", "b\"ip -4 addr show dev eth0; if ping -c 1 -W 3 10.0.2.2; then echo AETHER_NET_PASS; fi; /etc/init.d/S99aether selftest\\n\"")
s = s.replace("assert b'AETHER_SELFTEST_PASS' in data", "assert b'10.0.2.15/' in data, 'DHCP lease missing'\n    assert b'\\r\\nAETHER_NET_PASS\\r\\n' in data, 'Gateway test failed'\n    assert b'AETHER_SELFTEST_PASS' in data")
(r/'scripts/test-network-arm64.py').write_text(s)
