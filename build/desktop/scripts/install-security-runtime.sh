#!/bin/bash
# Copy the source-built cryptsetup/LVM runtime from a completed security-edition
# root into the desktop root.  This is deliberately separate from install-assets:
# the crypto tools must come from the source-built security system, not from a
# host package or a developer overlay.
set -euo pipefail
root=${1:?Usage: install-security-runtime.sh /path/to/offline/aether-root}
root=$(realpath -e "$root")
security=${AETHER_SECURITY_ROOT:-/opt/aether/security-system}
security=$(realpath -e "$security")
[[ "$root" != / && -f "$root/etc/os-release" ]] || {
    echo 'An offline Aether root is required.' >&2
    exit 1
}
grep -q 'ID=aether' "$root/etc/os-release" || {
    echo 'Target is not an Aether root.' >&2
    exit 1
}
[[ -x "$security/usr/sbin/cryptsetup" && -x "$security/usr/sbin/lvm" ]] || {
    echo "The security root has no source-built cryptsetup/lvm: $security" >&2
    echo 'Complete the security-edition package stage before the desktop image.' >&2
    exit 1
}

for program in cryptsetup lvm dmsetup blkid; do
    test -x "$security/usr/sbin/$program" || {
        echo "Missing source-built /usr/sbin/$program in $security" >&2
        exit 1
    }
done

install -d -o 0 -g 0 -m 755 "$root/usr/sbin" "$root/usr/lib" \
    "$root/etc/lvm" "$root/etc/lvm/profile" \
    "$root/usr/share/aether/security-runtime"
for program in cryptsetup lvm dmsetup blkid; do
    install -D -o 0 -g 0 -m 755 "$security/usr/sbin/$program" "$root/usr/sbin/$program"
done
for program in vgchange lvchange pvscan vgscan lvscan lvs vgs pvs lvcreate lvremove \
               pvcreate vgcreate vgremove vgextend lvreduce lvextend; do
    ln -sfn lvm "$root/usr/sbin/$program"
done

# Resolve the tools against the security root, not the build host.  A missing
# dependency is an error: the signed installed UKI must not silently depend on
# a host library that is absent from the image.
mapfile -t libraries < <(
    for program in cryptsetup lvm dmsetup; do
        LD_LIBRARY_PATH="$security/usr/lib:$security/lib" \
            ldd "$security/usr/sbin/$program" 2>/dev/null
    done | awk '
        /=> \// { print $3 }
        /^[[:space:]]*\/.* \(/ { print $1 }
    ' | sort -u
)
host_fallbacks=0
for library in "${libraries[@]}"; do
    case "$library" in
        "$security"/*)
            relative=${library#"$security"}
            install -D -o 0 -g 0 -m 755 "$library" "$root/$relative"
            ;;
        /lib/*|/lib64/*|/usr/lib/*|/usr/lib64/*)
            case "$(basename "$library")" in
                libc.so.*|libm.so.*|libpthread.so.*|libdl.so.*|librt.so.*|ld-linux*)
                    continue
                    ;;
            esac
            if [ "${AETHER_ALLOW_HOST_SECURITY_LIBS:-0}" != 1 ]; then
                echo "security-runtime: dependency is not source-built: $library" >&2
                echo 'Set AETHER_ALLOW_HOST_SECURITY_LIBS=1 only for a labelled lab build.' >&2
                exit 1
            fi
            destination="$root${library}"
            if [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
                install -D -o 0 -g 0 -m 755 "$library" "$destination"
                echo "security-runtime: copied host fallback $library" >&2
            fi
            host_fallbacks=1
            ;;
        *)
            echo "security-runtime: unexpected resolved library: $library" >&2
            exit 1
            ;;
    esac
done

if [ -d "$security/etc/lvm/profile" ]; then
    cp -a "$security/etc/lvm/profile/." "$root/etc/lvm/profile/"
fi
for file in lvm.conf lvmlocal.conf; do
    [ -f "$security/etc/lvm/$file" ] && install -D -o 0 -g 0 -m 644 \
        "$security/etc/lvm/$file" "$root/etc/lvm/$file"
done

# Record the provenance used by the signed-asset builder.  This marker is only
# written after all binaries and libraries have been copied successfully.
cryptsetup_sha=$(sha256sum "$root/usr/sbin/cryptsetup" | awk '{print $1}')
lvm_sha=$(sha256sum "$root/usr/sbin/lvm" | awk '{print $1}')
if [ "$host_fallbacks" = 0 ]; then
    host_fallback_label=no
else
    host_fallback_label=yes
fi
cat >"$root/usr/share/aether/security-runtime/source-built" <<EOF
source=security-system
security_root=$security
host_library_fallbacks=$host_fallback_label
cryptsetup_sha256=$cryptsetup_sha
lvm_sha256=$lvm_sha
generated_at=$(date -u +%FT%TZ)
EOF
chmod 644 "$root/usr/share/aether/security-runtime/source-built"

if [ -x "$root/usr/sbin/ldconfig" ] || [ -x "$root/sbin/ldconfig" ]; then
    chroot "$root" /sbin/ldconfig 2>/dev/null || chroot "$root" /usr/sbin/ldconfig
fi
echo "source-built security runtime installed from $security"
