#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this uninstaller as root: sudo ./uninstall.sh" >&2
    exit 1
fi

rm -f /usr/lib/globalprotect-tray/globalprotect-tray-helper
rmdir /usr/lib/globalprotect-tray 2>/dev/null || true
rm -f /usr/bin/globalprotect-tray
rm -f /usr/share/polkit-1/actions/io.github.brycewalkerdev.globalprotect-tray-app.policy
rm -f /usr/share/polkit-1/actions/io.github.brycewalker.globalprotect-tray.policy
rm -f /usr/share/applications/globalprotect-tray.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/globalprotect-tray.svg
rm -f /usr/share/metainfo/io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml
rm -f /usr/share/metainfo/io.github.brycewalker.globalprotect-tray.metainfo.xml
rm -f /usr/share/licenses/globalprotect-tray/LICENSE
rmdir /usr/share/licenses/globalprotect-tray 2>/dev/null || true

echo "Removed GlobalProtect Tray. User settings and logs were left in place."
