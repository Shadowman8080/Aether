#!/usr/bin/env python3
"""Generate a synthetic dpkg ownership database for the Aether rootfs.

The base is Linux From Scratch / BLFS built by jhalfs, so it has no package
manager database at all. dpkg, apt, PackageKit and plasma-discover can be
installed and load, but with an empty /var/lib/dpkg/status they have nothing to
reason about.

This synthesises one dpkg package per built component, with real file ownership
taken from the build metadata that survived:

  * LFS chapter-8 packages : exact per-file lists (size/owner/mode) from
                             native-build-metadata/jhalfs/installed-files/*
  * versions               : var/lib/jhalfs/BLFS/instpkg.xml (LFS+BLFS)
  * desktop packages       : installed paths parsed from
                             native-desktop/logs/*.log -- CMake "-- Installing:",
                             meson "Installing X to Y", and autotools/libtool
                             install lines
  * apt-chain packages     : the components this branch added (dpkg, apt,
                             PackageKit, plasma-discover, ...), matched by
                             install prefix

It is explicitly a synthetic database: it describes ownership so the package
manager can reason about the system, it is not a route to upgrading the base,
and the Maintainer field marks it as such. It is only written into the
disposable chroot rootfs, never into a published image.
"""
import glob
import hashlib
import os
import re
import sys

ROOT = "/opt/aether/build/apt-root"
LFS_FILES = "/opt/aether/build/native-build-metadata/jhalfs/installed-files"
XML = os.path.join(ROOT, "var/lib/jhalfs/BLFS/instpkg.xml")
DLOGS = "/opt/aether/build/native-desktop/logs"
INFO = os.path.join(ROOT, "var/lib/dpkg/info")
STATUS = os.path.join(ROOT, "var/lib/dpkg/status")
MAINTAINER = "Aether synthetic DB <noreply@aether.invalid>"


def sanitize(name):
    n = name.lower().replace("_", "-")
    n = re.sub(r"[^a-z0-9+.\-]", "-", n)
    n = re.sub(r"-+", "-", n).strip("-")
    return n


def normver(v):
    """dpkg requires a version to start with a digit (or an epoch)."""
    v = (v or "").strip()
    if not v:
        return "1.0-aether"
    if not re.match(r"^\d", v):
        v = "0." + v
    return v


# ---- versions from the jhalfs installed-package XML -------------------------
versions = {}
try:
    data = open(XML, encoding="latin-1").read()
    for m in re.finditer(
        r"<package>\s*<name>([^<]+)</name>\s*<version>([^<]*)</version>", data
    ):
        versions[sanitize(m.group(1))] = normver(m.group(2))
except FileNotFoundError:
    print("  warning: %s not found" % XML, file=sys.stderr)

packages = {}


def pkg(name):
    name = sanitize(name)
    if not name:
        return None
    return packages.setdefault(
        name,
        {"version": versions.get(name, "1.0-aether"), "files": set(), "src": ""},
    )


# ---- LFS chapter-8 packages: exact file lists -------------------------------
if os.path.isdir(LFS_FILES):
    for fn in sorted(os.listdir(LFS_FILES)):
        m = re.match(r"\d+-(.+)$", fn)
        if not m:
            continue
        p = pkg(m.group(1))
        if not p:
            continue
        p["src"] = "LFS"
        for line in open(os.path.join(LFS_FILES, fn), encoding="utf-8", errors="replace"):
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0].startswith("/"):
                p["files"].add(parts[0])

# every named jhalfs package gets a stanza even if it has no file list
for n in versions:
    p = pkg(n)
    if p and not p["src"]:
        p["src"] = "BLFS"


# ---- desktop packages: parse install paths out of their build logs ----------
_SKIP_TOKENS = {"install", "sh", "libtool", "cd", "&&", "{", "}", "||", "rm",
                "-c", "--mode=install", "--mode=relink", "--silent"}


def _basename_ok(tok):
    tok = tok.strip("'\"")
    if not tok or tok.startswith("-") or tok.startswith("/"):
        return None
    if tok in _SKIP_TOKENS or "=" in tok or re.fullmatch(r"\d+", tok):
        return None
    return os.path.basename(tok)


def paths_from_line(line):
    """Return the absolute destination paths an install-ish log line writes."""
    out = set()
    m = re.match(r"^-- (?:Installing|Up-to-date): (/.+?)\s*$", line)
    if m:
        return {m.group(1)}
    if line.startswith("Installing "):
        m = re.search(r"\bto (/\S+)\s*$", line)
        if m:
            dest = m.group(1)
            # meson prints "Installing SRC to DIR" when the destination is a
            # directory; the installed file is then DIR/basename(SRC).
            ms = re.match(r"Installing (.*?) to /\S+\s*$", line)
            if ms and os.path.isdir(ROOT + dest):
                base = os.path.basename(ms.group(1).strip().rstrip("/"))
                if base:
                    return {dest.rstrip("/") + "/" + base}
            return {dest}
    # libtool symlink blocks: (cd DIR && { ln -s -f TARGET LINK || ... })
    if "ln -s" in line:
        md = re.search(r"\(cd (\S+) &&", line)
        d = md.group(1) if md else None
        for lm in re.finditer(r"ln -s(?:\s+-\S+)*\s+(\S+)\s+([^\s;|]+)", line):
            link = lm.group(2).strip(";")
            if link.startswith("/"):
                out.add(link)
            elif d:
                out.add(d.rstrip("/") + "/" + link)
        if out:
            return out
    # Boost.Build: common.copy DEST / common.link DEST
    m = re.search(r"\bcommon\.(?:copy|link)\s+(\S+)\s*$", line)
    if m:
        p = m.group(1).strip(";")
        if p.startswith("/"):
            out.add(p)
        return out
    # python distutils / pip: "copying X -> /dest"
    m = re.search(r"\bcopying \S+ -> (/\S+)", line)
    if m:
        return {m.group(1)}
    # generic autotools / libtool install commands
    if ("/usr/bin/install" in line or line.startswith("libtool: install:")
            or ("libtool" in line and "--mode=install" in line)):
        s = re.sub(r"[;})\s]+$", "", line.rstrip()).replace("\\", "")
        toks = s.split()
        mq = re.search(r"'([^']+)'\s*$", s)
        abspaths = [t.strip("'\"") for t in toks
                    if t.strip("'\"").startswith("/")
                    and not t.startswith("/usr/bin/install")
                    and not t.startswith("/bin/sh")]
        if mq:
            d = mq.group(1)
            for t in toks[:-1]:
                b = _basename_ok(t)
                if b:
                    out.add(d.rstrip("/") + "/" + b)
        elif abspaths:
            out.add(abspaths[-1])
    return out


ver_re = re.compile(r"[-_](\d+\.\d+(?:\.\d+)*)\.(?:tar|tgz|txz|zip)")
if os.path.isdir(DLOGS):
    for fn in sorted(os.listdir(DLOGS)):
        if not fn.endswith(".log"):
            continue
        p = pkg(fn[:-4])
        if not p:
            continue
        if not p["src"]:
            p["src"] = "desktop"
        ver = None
        for line in open(os.path.join(DLOGS, fn), encoding="utf-8", errors="replace"):
            line = line.rstrip("\n")
            for path in paths_from_line(line):
                p["files"].add(path)
            if ver is None:
                vm = ver_re.search(line)
                if vm:
                    ver = vm.group(1)
        if ver:
            p["version"] = ver


# ---- the apt chain added by this branch -------------------------------------
def add(name, version, patterns):
    p = pkg(name)
    p["version"] = version
    p["src"] = "apt-chain"
    for pat in patterns:
        for path in glob.glob(ROOT + pat, recursive=True):
            if os.path.isfile(path) or os.path.islink(path):
                p["files"].add(path[len(ROOT):])
    return p


add("dpkg", "1.23.11", [
    "/usr/bin/dpkg*", "/usr/lib/dpkg/**", "/usr/share/dpkg/**",
    "/usr/share/doc/dpkg/**", "/usr/share/man/man1/dpkg*",
    "/usr/share/man/man5/dpkg*", "/usr/share/man/man7/dpkg*",
    "/usr/share/locale/*/LC_MESSAGES/dpkg.mo", "/etc/dpkg/**",
])
add("apt", "3.3.3", [
    "/usr/bin/apt*", "/usr/lib/libapt-*.so*", "/usr/libexec/apt/**", "/usr/lib/apt/**",
    "/usr/include/apt-pkg/**", "/usr/include/apt-inst/**", "/usr/lib/pkgconfig/apt-*.pc",
    "/usr/share/man/man1/apt*", "/usr/share/man/man5/apt*", "/usr/share/man/man7/apt*",
    "/usr/share/man/man8/apt*", "/usr/share/doc/apt/**", "/etc/apt/**",
    "/usr/share/locale/*/LC_MESSAGES/apt.mo",
])
add("packagekit", "1.4.0", [
    "/usr/libexec/packagekitd", "/usr/lib/packagekit-backend/**", "/usr/lib/libpackagekit*",
    "/usr/bin/pkgcli", "/usr/bin/pkcheck", "/usr/bin/pkmon", "/usr/include/packagekit/**",
    "/usr/share/dbus-1/system-services/org.freedesktop.PackageKit*",
    "/usr/share/dbus-1/system.d/org.freedesktop.PackageKit.conf",
    "/usr/share/polkit-1/actions/org.freedesktop.packagekit.*",
    "/usr/share/PackageKit/**", "/usr/lib/systemd/system/packagekit*", "/etc/PackageKit/**",
    "/usr/share/bash-completion/completions/pkcli",
    "/usr/share/man/man1/pkcli*", "/usr/share/man/man8/packagekitd*",
])
add("packagekitqt6", "1.1.4", [
    "/usr/lib/libpackagekitqt6.so*", "/usr/lib/cmake/packagekitqt6/**",
    "/usr/lib/pkgconfig/packagekitqt6.pc", "/usr/include/PackageKitQt/**",
])
add("appstream", "1.0.5", [
    "/usr/lib/libappstream.so*", "/usr/lib/libAppStreamQt.so*",
    "/usr/lib/cmake/AppStreamQt/**", "/usr/bin/appstreamcli", "/usr/include/AppStream/**",
    "/usr/include/AppStreamQt/**", "/usr/lib/pkgconfig/appstream.pc",
    "/usr/share/man/man1/appstreamcli*",
])
add("libxmlb", "0.3.29", [
    "/usr/lib/libxmlb.so*", "/usr/include/libxmlb-2/**", "/usr/lib/pkgconfig/xmlb.pc",
    "/usr/lib/cmake/xmlb/**", "/usr/bin/xb-tool", "/usr/share/man/man1/xb-tool*",
])
add("libyaml", "0.2.5", [
    "/usr/lib/libyaml*", "/usr/include/yaml.h", "/usr/lib/pkgconfig/yaml-0.1.pc",
])
add("jansson", "2.15.1", [
    "/usr/lib/libjansson.so*", "/usr/include/jansson*.h", "/usr/include/jansson/**",
    "/usr/lib/pkgconfig/jansson.pc", "/usr/lib/cmake/jansson/**",
])
add("libmd", "1.1.0", [
    "/usr/lib/libmd.so*", "/usr/lib/pkgconfig/libmd.pc", "/usr/include/md5.h",
    "/usr/include/sha1.h", "/usr/include/sha2.h", "/usr/include/rmd160.h",
])
add("xxhash", "0.8.2", [
    "/usr/lib/libxxhash.so*", "/usr/include/xxhash.h", "/usr/bin/xxhsum", "/usr/bin/xxh128sum",
    "/usr/lib/pkgconfig/libxxhash.pc", "/usr/lib/cmake/xxHash/**", "/usr/share/man/man1/xxhsum*",
])
add("triehash", "0.3", [
    "/usr/bin/triehash", "/usr/share/triehash/**", "/usr/share/man/man1/triehash*",
])
add("libdb5.3", "5.3.28", [
    "/usr/lib/libdb-5.3.so", "/usr/lib/libdb.so", "/usr/include/db.h",
    "/usr/include/db_185.h", "/usr/include/db_cxx.h",
])
add("plasma-discover", "6.3.6", [
    "/usr/bin/plasma-discover*", "/usr/lib/plasma-discover/**", "/usr/plugins/discover/**",
    "/usr/plugins/discover-notifier/**",
    "/usr/plugins/plasma/kcms/systemsettings/kcm_updates.so",
    "/usr/lib/libexec/DiscoverNotifier", "/usr/libexec/DiscoverNotifier",
    "/usr/share/applications/org.kde.discover*",
    "/usr/share/icons/hicolor/*/apps/plasmadiscover.*",
    "/usr/share/metainfo/org.kde.discover*", "/usr/share/libdiscover/**",
    "/usr/share/knotifications6/discoverabstractnotifier.notifyrc",
    "/usr/share/qlogging-categories6/discover.categories",
    "/usr/share/kxmlgui5/plasmadiscover/**",
    "/usr/share/locale/*/LC_MESSAGES/libdiscover.mo",
    "/usr/share/locale/*/LC_MESSAGES/plasma-discover*.mo",
    "/etc/xdg/autostart/org.kde.discover.notifier.desktop",
])


# ---- BLFS/base packages with no surviving per-file log: known install sets ---
def add_base(name, patterns):
    p = pkg(name)
    if not p:
        return
    if not p["src"]:
        p["src"] = "BLFS"
    for pat in patterns:
        for path in glob.glob(ROOT + pat, recursive=True):
            if os.path.isfile(path) or os.path.islink(path):
                p["files"].add(path[len(ROOT):])


add_base("libxml2", [
    "/usr/lib/libxml2.so*", "/usr/bin/xml2-config", "/usr/bin/xmllint",
    "/usr/include/libxml2/**", "/usr/lib/pkgconfig/libxml-2.0.pc",
    "/usr/lib/cmake/libxml2*/**", "/usr/share/man/man1/xml2-config*",
    "/usr/share/man/man1/xmllint*",
])
add_base("libxslt", [
    "/usr/lib/libxslt.so*", "/usr/lib/libexslt.so*", "/usr/bin/xsltproc",
    "/usr/include/libxslt/**", "/usr/include/libexslt/**",
    "/usr/lib/pkgconfig/libxslt.pc", "/usr/lib/pkgconfig/libexslt.pc",
    "/usr/share/man/man1/xsltproc*",
])
add_base("libidn2", [
    "/usr/lib/libidn2.so*", "/usr/include/idn2.h", "/usr/lib/pkgconfig/libidn2.pc",
    "/usr/bin/idn2",
])
add_base("libpsl", [
    "/usr/lib/libpsl.so*", "/usr/include/libpsl.h", "/usr/lib/pkgconfig/libpsl.pc",
    "/usr/bin/psl",
])
add_base("libtasn1", [
    "/usr/lib/libtasn1.so*", "/usr/include/libtasn1.h",
    "/usr/lib/pkgconfig/libtasn1.pc", "/usr/bin/asn1Parser", "/usr/bin/asn1Coding",
    "/usr/bin/asn1Decoding",
])
add_base("libunistring", [
    "/usr/lib/libunistring.so*", "/usr/include/uni*.h", "/usr/include/unitypes.h",
    "/usr/lib/pkgconfig/libunistring.pc",
]
)
add_base("ffmpeg", [
    "/usr/bin/ffmpeg", "/usr/bin/ffprobe", "/usr/bin/ffplay",
    "/usr/lib/libav*.so*", "/usr/lib/libsw*.so*", "/usr/lib/libpostproc.so*",
    "/usr/include/libav*/**", "/usr/include/libswresample/**",
    "/usr/include/libswscale/**", "/usr/lib/pkgconfig/libav*.pc",
    "/usr/lib/pkgconfig/libsw*.pc", "/usr/lib/pkgconfig/libpostproc.pc",
    "/usr/share/ffmpeg/**", "/usr/share/man/man1/ffmpeg*",
])
add_base("cups", [
    "/usr/lib/libcups*.so*", "/usr/lib/cups/**", "/usr/sbin/cups*",
    "/usr/bin/cups*", "/usr/bin/lp*", "/usr/bin/ipptool", "/usr/bin/ppdc",
    "/usr/bin/ppdhtml", "/usr/bin/ppdi", "/usr/bin/ppdmerge", "/usr/bin/ppdpo",
    "/usr/include/cups/**", "/usr/lib/pkgconfig/cups.pc", "/usr/share/cups/**",
    "/etc/cups/**", "/usr/lib/systemd/system/cups*",
])
add_base("dasbus", [
    "/usr/lib/python*/site-packages/dasbus/**",
    "/usr/lib/python*/site-packages/dasbus-*.dist-info/**",
])
add_base("hwdata", ["/usr/share/hwdata/**", "/usr/lib/udev/hwdb.d/**"])
add_base("lfs-release", ["/etc/lfs-release", "/etc/lsb-release", "/etc/os-release"])
add_base("docbook-45-xml", ["/usr/share/xml/docbook/xml-dtd-4.5/**", "/etc/xml/**"])
add_base("docbook-xsl", ["/usr/share/xml/docbook/xsl-stylesheets*/**"])
add_base("kernel", [
    "/boot/vmlinuz*", "/boot/System.map*", "/boot/config*", "/usr/lib/modules/**",
])


# ---- prune to files that actually exist, then write the database ------------
os.makedirs(INFO, exist_ok=True)
for f in os.listdir(INFO):
    if f.endswith((".list", ".md5sums")):
        os.remove(os.path.join(INFO, f))

total_files = 0
md5_cache = {}
md5_files = 0
empty = []
stanzas = []


def file_md5(full):
    if full in md5_cache:
        return md5_cache[full]
    digest = None
    try:
        h = hashlib.md5()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        digest = h.hexdigest()
    except OSError:
        digest = None
    md5_cache[full] = digest
    return digest


for name in sorted(packages):
    p = packages[name]
    existing = set()
    md5lines = []
    size = 0
    for path in p["files"]:
        full = ROOT + path
        if os.path.isfile(full) or os.path.islink(full):
            existing.add(path)
            try:
                size += os.lstat(full).st_size
            except OSError:
                pass
            if os.path.isfile(full) and not os.path.islink(full):
                d = file_md5(full)
                if d:
                    md5lines.append("%s  %s" % (d, path.lstrip("/")))
    if not existing:
        empty.append(name)
    installed_kb = max(1, size // 1024)
    desc = ("synthetic entry for %s; file ownership generated from the "
            "LFS/BLFS/native-desktop build metadata" % (p["src"] or "base"))
    stanzas.append({
        "Package": name,
        "Status": "install ok installed",
        "Priority": "optional",
        "Section": "aether-synthetic",
        "Installed-Size": str(installed_kb),
        "Maintainer": MAINTAINER,
        "Architecture": "amd64",
        "Version": p["version"],
        "Description": desc,
    })
    with open(os.path.join(INFO, name + ".list"), "w") as fh:
        for path in sorted(existing):
            fh.write(path + "\n")
    with open(os.path.join(INFO, name + ".md5sums"), "w") as fh:
        if md5lines:
            fh.write("\n".join(sorted(md5lines)) + "\n")
    md5_files += len(md5lines)
    total_files += len(existing)

with open(STATUS, "w") as fh:
    for d in stanzas:
        for k, v in d.items():
            fh.write("%s: %s\n" % (k, v))
        fh.write("\n")

print("  packages:            %d" % len(packages))
print("  files owned:         %d" % total_files)
print("  md5sum entries:      %d" % md5_files)
print("  packages w/o files:  %d%s" % (
    len(empty), (" (" + ", ".join(empty[:20]) + ")") if empty else ""))
print("  status written:      %s" % STATUS)
print("  info/*.list written: %d" % len([f for f in os.listdir(INFO) if f.endswith(".list")]))
