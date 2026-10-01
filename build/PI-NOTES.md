# Raspberry Pi build constraints

Board selection is pending: Raspberry Pi 4/400, Pi 5, or both. No Pi image has been built or tested.

The existing Buildroot 2026.08 Pi 4 and Pi 5 reference configurations pin Raspberry Pi Linux commit `21b410140c47ffab5668399f6f143c7d7b935c8b`, whose Makefile identifies Linux 6.12.61:
https://raw.githubusercontent.com/raspberrypi/linux/21b410140c47ffab5668399f6f143c7d7b935c8b/Makefile

The ARM64 VM glibc configure log explicitly uses `--enable-kernel=6.18`. Do not reuse that userspace/toolchain unchanged with a 6.12 Pi kernel. Use a source-built toolchain configured for the chosen Pi kernel baseline, or a verified newer Pi kernel with all required board support. Do not inherit the stock Pi defconfig's prebuilt Bootlin toolchain: Aether's toolchain must be built from source.

Pi outputs should be board-specific SD-card images with appropriate firmware, device trees, boot configuration, and an ext4 root filesystem. They are not PC/UEFI ISOs. Physical boot validation requires the selected Pi hardware. Keep VM guest integration out of the critical Pi boot path.
