set -euo pipefail
base=/opt/aether
out=$base/build/kernel-6.18.54
src=$base/sources/linux-6.18.54
mkdir -p "$base/security" "$base/logs/security"
test -f "$base/security/kernel-before-security.config" || cp "$out/.config" "$base/security/kernel-before-security.config"
for opt in VETH ZRAM ZSMALLOC NF_TABLES NF_TABLES_INET NF_TABLES_IPV4 NF_TABLES_IPV6 NFT_CT NFT_COUNTER NFT_LOG NFT_LIMIT NFT_REJECT NFT_REJECT_INET NFT_NAT NFT_MASQ NFT_FIB_INET NFT_FIB_IPV4 NFT_FIB_IPV6 NFT_COMPAT NETFILTER_NETLINK_LOG SECURITYFS SECURITY_PATH SECURITY_APPARMOR SECURITY_YAMA SECURITY_LANDLOCK SECURITY_LOCKDOWN_LSM SECURITY_DMESG_RESTRICT SLAB_FREELIST_RANDOM SLAB_FREELIST_HARDENED HARDENED_USERCOPY FORTIFY_SOURCE RANDOMIZE_KSTACK_OFFSET_DEFAULT INIT_ON_ALLOC_DEFAULT_ON INTEL_IOMMU_DEFAULT_ON IOMMU_DEFAULT_DMA_STRICT DM_VERITY DM_CRYPT CRYPTO_AES_NI_INTEL CRYPTO_XTS CRYPTO_AES CRYPTO_SHA256 CRYPTO_SHA512 CRYPTO_USER_API_HASH CRYPTO_USER_API_SKCIPHER EFI_CAPSULE_LOADER EFI_DISABLE_PCI_DMA MODULE_SIG MODULE_SIG_SHA512; do
 "$src/scripts/config" --file "$out/.config" --enable "$opt"
done
"$src/scripts/config" --file "$out/.config" --disable X86_VERBOSE_BOOTUP --disable SECURITY_SELINUX --disable IOMMU_DEFAULT_DMA_LAZY --set-str LSM 'landlock,lockdown,yama,integrity,apparmor,bpf' --set-str LOCALVERSION '-aether4'
make -C "$src" O="$out" olddefconfig
for opt in CRYPTO_AES_NI_INTEL VETH ZRAM ZSMALLOC NF_TABLES NF_TABLES_INET SECURITY_APPARMOR SECURITY_YAMA SECURITY_LANDLOCK HARDENED_USERCOPY FORTIFY_SOURCE SLAB_FREELIST_HARDENED; do grep -qx "CONFIG_${opt}=y" "$out/.config"; done
make -C "$src" O="$out" -j"$(nproc)" bzImage modules
stage=$base/build/security-kernel-stage
mkdir -p "$stage/boot"
make -C "$src" O="$out" -j"$(nproc)" INSTALL_MOD_PATH="$stage" modules_install
release=$(make -s -C "$src" O="$out" kernelrelease)
install -m644 "$out/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$out/.config" "$stage/boot/config-$release"
install -m644 "$out/System.map" "$stage/boot/System.map-$release"
printf '%s\n' "$release" > "$stage/kernel-release"
cp "$out/.config" "$base/security/kernel-x86_64.config"
echo SECURITY_KERNEL_BUILD_PASS
