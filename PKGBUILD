# Maintainer: Bryce Walker
pkgname=globalprotect-tray
pkgver=0.2.0
pkgrel=4
pkgdesc="External-browser tray client for GlobalProtect-compatible VPNs"
arch=('any')
url="https://github.com/brycewalkerdev/globalprotect-tray-app"
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
  'io.github.brycewalkerdev.globalprotect-tray-app.policy'
  'io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml'
  'README.md'
  'LICENSE'
)
sha256sums=('090d29e5ad0f250f87319cd21210457fe7c2427071f09f5fa6b755466786d4ea'
            '6d5e913dc943dc548be7bd5644372e628527c17a701166db6ca475965bced1f1'
            'd54209533843413d492622c10877de2bfc32ecc0d8714985edaaf0ef0e866ad4'
            'd6674daefdd9284ed4c83a40596a0e9e650bb7ecbbd01296af678c26e2585191'
            'cfad9b3936b8e304f16c50d6fc69e8861c15f6bfc7795ee9a411b39c75a938ec'
            'f2576dd96e5b1f17671a3c67794b62adc95faa9f43809bfe11d9a1f27ba0c7bb'
            '7a121fadf6d709e3d8c403d5af132832133702ba8d0b0621ea95fa9cf1d80d60'
            '53aa712159c8539042ef0a8e4bd32dcb12b8a50e93da96a62425da27d5f1b24c')

check() {
  python -m py_compile globalprotect_tray.py globalprotect-tray-helper
  desktop-file-validate globalprotect-tray.desktop
  appstreamcli validate --no-net io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml
}

package() {
  install -Dm755 globalprotect_tray.py "$pkgdir/usr/bin/globalprotect-tray"
  install -Dm755 globalprotect-tray-helper \
    "$pkgdir/usr/lib/globalprotect-tray/globalprotect-tray-helper"
  install -Dm644 globalprotect-tray.desktop \
    "$pkgdir/usr/share/applications/globalprotect-tray.desktop"
  install -Dm644 globalprotect-tray.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/globalprotect-tray.svg"
  install -Dm644 io.github.brycewalkerdev.globalprotect-tray-app.policy \
    "$pkgdir/usr/share/polkit-1/actions/io.github.brycewalkerdev.globalprotect-tray-app.policy"
  install -Dm644 io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml \
    "$pkgdir/usr/share/metainfo/io.github.brycewalkerdev.globalprotect-tray-app.metainfo.xml"
  install -Dm644 README.md "$pkgdir/usr/share/doc/globalprotect-tray/README.md"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/globalprotect-tray/LICENSE"
}
