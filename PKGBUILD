# Maintainer: Bryce Walker
pkgname=globalprotect-tray
pkgver=0.2.0
pkgrel=2
pkgdesc="External-browser tray client for GlobalProtect-compatible VPNs"
arch=('any')
url="https://github.com/brycewalker/globalprotect-tray"
license=('MIT')
depends=(
  'globalprotect-openconnect'
  'libayatana-appindicator'
  'libnotify'
  'polkit'
  'python'
  'python-gobject'
  'pyside6'
  'xdg-utils'
)
makedepends=('appstream' 'desktop-file-utils')
install=globalprotect-tray.install
source=(
  'globalprotect_tray.py'
  'globalprotect-tray-helper'
  'globalprotect-tray.desktop'
  'globalprotect-tray.svg'
  'io.github.brycewalker.globalprotect-tray.policy'
  'io.github.brycewalker.globalprotect-tray.metainfo.xml'
  'README.md'
  'LICENSE'
)
sha256sums=('090d29e5ad0f250f87319cd21210457fe7c2427071f09f5fa6b755466786d4ea'
            '6d5e913dc943dc548be7bd5644372e628527c17a701166db6ca475965bced1f1'
            'd54209533843413d492622c10877de2bfc32ecc0d8714985edaaf0ef0e866ad4'
            'd6674daefdd9284ed4c83a40596a0e9e650bb7ecbbd01296af678c26e2585191'
            'cd7fa860d22ede6ea3dc12385eb6df1594f2f8549f74eab3cc305688324eb398'
            'c7dd72934c2c5a9b76f7a864d3ec2d7f856958f1a6bb8d4dce9de479ac7eb9b7'
            '482c4adc052f5fa4d0f70363eb63c07d8eafc8c4c9a2b46b586cfb826b59badc'
            '53aa712159c8539042ef0a8e4bd32dcb12b8a50e93da96a62425da27d5f1b24c')

check() {
  python -m py_compile globalprotect_tray.py globalprotect-tray-helper
  desktop-file-validate globalprotect-tray.desktop
  appstreamcli validate --no-net io.github.brycewalker.globalprotect-tray.metainfo.xml
}

package() {
  install -Dm755 globalprotect_tray.py "$pkgdir/usr/bin/globalprotect-tray"
  install -Dm755 globalprotect-tray-helper \
    "$pkgdir/usr/lib/globalprotect-tray/globalprotect-tray-helper"
  install -Dm644 globalprotect-tray.desktop \
    "$pkgdir/usr/share/applications/globalprotect-tray.desktop"
  install -Dm644 globalprotect-tray.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/globalprotect-tray.svg"
  install -Dm644 io.github.brycewalker.globalprotect-tray.policy \
    "$pkgdir/usr/share/polkit-1/actions/io.github.brycewalker.globalprotect-tray.policy"
  install -Dm644 io.github.brycewalker.globalprotect-tray.metainfo.xml \
    "$pkgdir/usr/share/metainfo/io.github.brycewalker.globalprotect-tray.metainfo.xml"
  install -Dm644 README.md "$pkgdir/usr/share/doc/globalprotect-tray/README.md"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/globalprotect-tray/LICENSE"
}
