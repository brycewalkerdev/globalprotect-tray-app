#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root: sudo ./install.sh" >&2
    exit 1
fi

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Clean up files from pre-publication builds that used the old project ID.
rm -f /usr/share/polkit-1/actions/io.github.brycewalker.globalprotect-tray.policy
rm -f /usr/share/metainfo/io.github.brycewalker.globalprotect-tray.metainfo.xml

install -d -m 0755 /usr/lib/globalprotect-tray
install -m 0755 "$project_dir/globalprotect-tray-helper" /usr/lib/globalprotect-tray/globalprotect-tray-helper
install -m 0755 "$project_dir/globalprotect_tray.py" /usr/bin/globalprotect-tray
install -m 0644 "$project_dir/io.github.brycewalkerdev.globalprotect-tray-app.policy" /usr/share/polkit-1/actions/io.github.brycewalkerdev.globalprotect-tray-app.policy
install -m 0644 "$project_dir/globalprotect-tray.desktop" /usr/share/applications/globalprotect-tray.desktop
install -d -m 0755 /usr/share/icons/hicolor/scalable/apps /usr/share/metainfo /usr/share/licenses/globalprotect-tray
install -m 0644 "$project_dir/globalprotect-tray.svg" /usr/share/icons/hicolor/scalable/apps/globalprotect-tray.svg
install -m 0644 "$project_dir/io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml" /usr/share/metainfo/io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml
install -m 0644 "$project_dir/LICENSE" /usr/share/licenses/globalprotect-tray/LICENSE
chown root:root \
    /usr/lib/globalprotect-tray/globalprotect-tray-helper \
    /usr/bin/globalprotect-tray \
    /usr/share/polkit-1/actions/io.github.brycewalkerdev.globalprotect-tray-app.policy \
    /usr/share/applications/globalprotect-tray.desktop \
    /usr/share/icons/hicolor/scalable/apps/globalprotect-tray.svg \
    /usr/share/metainfo/io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml \
    /usr/share/licenses/globalprotect-tray/LICENSE

echo "Installed GlobalProtect Tray."
echo "Launch it from the application menu or run: globalprotect-tray"
