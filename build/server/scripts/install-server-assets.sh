#!/bin/bash
# Install the Aether Server edition (assets, role catalog, backend) into an
# offline Aether root. The graphical installer binary itself comes from the
# CMake build in src/server/installer.
set -euo pipefail
root=${1:?Usage: install-server-assets.sh /path/to/offline/aether-root}
root=$(realpath -e "$root")
[[ "$root" != / && -f "$root/etc/os-release" ]] || { echo 'An offline Aether root is required.' >&2; exit 1; }
grep -q 'Aether' "$root/etc/os-release" || { echo 'Target is not an Aether root.' >&2; exit 1; }

base=$(realpath "$(dirname "$0")/../../..")   # repository top level
assets=$(realpath "$base/src/server/assets")
roles=$(realpath "$base/src/server/roles")
backend=$(realpath "$base/src/server/backend")

# 1. Static assets: desktop entry, polkit rule, /etc/issue, /etc/motd,
#    default firewall state and the first-boot secret preparation unit.
while IFS= read -r -d '' source; do
    install -d -o 0 -g 0 -m 755 "$root/${source#"$assets/"}"
done < <(find "$assets" -mindepth 1 -type d -print0)
while IFS= read -r -d '' source; do
    install -D -o 0 -g 0 -m 644 "$source" "$root/${source#"$assets/"}"
done < <(find "$assets" -type f -print0)
chmod 755 "$root/usr/libexec/aether-server-firstboot"
rm -rf "$root/etc/motd.d/aether-pending-join"

# 2. The data-driven role catalog and its per-role configuration templates.
#    The catalog keeps its source name in the repo and its installed name here;
#    both the installer UI and the backend read the installed copy.
install -D -o 0 -g 0 -m 644 "$roles/catalog.json" "$root/usr/share/aether/server/roles.json"
install -d -o 0 -g 0 -m 755 "$root/usr/share/aether/server/configs"
while IFS= read -r -d '' source; do
    install -D -o 0 -g 0 -m 644 "$source" "$root/usr/share/aether/server/configs/${source#"$roles/configs/"}"
done < <(find "$roles/configs" -type f -print0)

# 3. The privileged backend and its shared module.
install -D -o 0 -g 0 -m 755 "$backend/aether-server-install" "$root/usr/libexec/aether-server-install-backend"
install -D -o 0 -g 0 -m 644 "$backend/server_roles.py" "$root/usr/libexec/server_roles.py"

# 4. The launcher and the post-install directory tool.
install -D -o 0 -g 0 -m 755 "$base/src/server/installer/aether-server-setup" "$root/usr/bin/aether-server-setup"
install -D -o 0 -g 0 -m 755 "$base/src/server/installer/aether-directory" "$root/usr/bin/aether-directory"

# 5. The catalog must parse before we call this image built.
chroot "$root" /usr/bin/python3 /usr/libexec/aether-server-install-backend --validate

echo 'Aether Server assets installed; run configure-server.py to finish the image.'