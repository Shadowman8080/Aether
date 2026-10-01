AETHER_VMTOOLS_VERSION = 13.1.0-25218885
AETHER_VMTOOLS_SOURCE = open-vm-tools-$(AETHER_VMTOOLS_VERSION).tar.gz
AETHER_VMTOOLS_SITE = https://github.com/vmware/open-vm-tools/releases/download/stable-13.1.0
AETHER_VMTOOLS_LICENSE = LGPL-2.1
AETHER_VMTOOLS_LICENSE_FILES = COPYING
AETHER_VMTOOLS_DEPENDENCIES = host-pkgconf host-nfs-utils libglib2 libtirpc libfuse3 $(TARGET_NLS_DEPENDENCIES)
ifeq ($(BR2_TOOLCHAIN_USES_GLIBC),y)
AETHER_VMTOOLS_DEPENDENCIES += libxcrypt
endif
AETHER_VMTOOLS_CONF_OPTS = --without-x --without-icu --without-dnet \
	--without-pam --without-ssl --without-xml2 --without-xmlsec1 \
	--disable-vgauth --disable-containerinfo --disable-deploypkg \
	--disable-resolutionkms --disable-vmwgfxctrl --without-kernel-modules
AETHER_VMTOOLS_CONF_ENV = LIBS="$(TARGET_NLS_LIBS)" CFLAGS="$(TARGET_CFLAGS) -std=gnu11"

# Correct shell assignments in the upstream release configure script.
define AETHER_VMTOOLS_FIX_CONFIGURE
	$(SED) 's/enable_vgauth = "no"/enable_vgauth="no"/g' $(@D)/configure
endef
AETHER_VMTOOLS_POST_PATCH_HOOKS += AETHER_VMTOOLS_FIX_CONFIGURE

define AETHER_VMTOOLS_INSTALL_INIT_SYSV
	$(INSTALL) -D -m755 $(BR2_EXTERNAL_AETHER_PATH)/package/aether-vmtools/S50vmtoolsd $(TARGET_DIR)/etc/init.d/S50vmtoolsd
	$(INSTALL) -D -m755 package/openvmtools/shutdown $(TARGET_DIR)/sbin/shutdown
endef
$(eval $(autotools-package))
