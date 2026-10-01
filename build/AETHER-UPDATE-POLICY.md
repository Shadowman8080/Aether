# Aether update policy

Confirmed by the user on 2026-09-28:

- Check for updates automatically.
- Ask before installing updates, including security updates.
- Do not restart automatically to finish an update.
- Keep development downloads private in Cloudflare R2.
- Never distribute the R2 publisher credential in an ISO, VM image, or client configuration.

## Verified implementation status

This is a recorded product decision, not an installed update service.

The existing host-side pacman repository test successfully installs and removes a signed test package and rejects unsigned packages, modified packages, and a modified database. Its temporary development signing key is not a production trust root.

The current desktop root does not contain pacman, Flatpak, or OSTree. Most software was installed directly from source, without package ownership records. Do not attach Arch or Ubuntu repositories or perform a package upgrade against this unmanaged base.

R2 currently holds private installer artifacts, not a usable operating-system update repository. The publisher credential must remain on the build VM. Client read access, production signing and trust provisioning, package ownership/migration, interrupted-update recovery, and desktop notification integration remain to be implemented and tested before automatic checks can be enabled.

OS update work must preserve the current user disk and be tested on a separate image first. Build with all available CPUs. The build VM had 2.7 GiB available at the most recent inspection; verify capacity before starting another image build.
