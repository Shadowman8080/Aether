# Aether power menu

The login screen has one Power button containing Sleep, Restart, and Shut Down.
LightDM supplies machine capabilities; unsupported actions are disabled. Restart
and shutdown require confirmation. Lock is intentionally absent before login.

The Plasma top panel uses org.aether.powermenu. It exposes Lock Computer, Sleep,
Restart, and Shut Down through Plasma SessionManagement. Power actions use the
session's capability checks. Restart/shutdown force Plasma's confirmation prompt;
sleep follows Plasma's normal suspend and lock handling.

Both Aether desktop layouts include the applet. The Plasma update script adds it
once to an existing top panel without resetting the user's layout. Users with a
custom layout without a top panel can add the Aether Power widget manually.

Build the greeter with scripts/build-aether-greeter.py inside the Aether build
chroot; it uses every available CPU. Install desktop assets with the existing
scripts/install-assets.sh against an offline Aether root. The QML applet is
architecture-independent; the greeter must be compiled for each target.
