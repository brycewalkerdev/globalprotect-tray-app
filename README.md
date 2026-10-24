# GlobalProtect Tray

A small, free Linux tray client for
[`globalprotect-openconnect`](https://github.com/yuezk/GlobalProtect-openconnect).
Authentication happens in your normal browser, so password-manager extensions,
WebAuthn, biometrics, and security keys work.

The application supports GlobalProtect portals and direct gateways. New
profiles automatically detect the server type and whether legacy OpenSSL
compatibility is required.

## Features

- Native left- and right-click tray menu on KDE Plasma/Wayland
- External Chrome, Chromium, Firefox, or system-browser authentication
- Automatic portal/direct-gateway fallback
- Automatic legacy OpenSSL compatibility retry
- Connection state, desktop notifications, and login autostart
- Dedicated `globalprotectcallback:` URL handler
- Narrow root helper controlled by Polkit

## Requirements

- `globalprotect-openconnect` (`gpauth` and `gpclient`)
- Python 3, PySide6, PyGObject, and Ayatana AppIndicator
- Polkit, `pkexec`, `xdg-mime`, and `notify-send`
- A StatusNotifier/AppIndicator-compatible desktop tray

On Arch Linux these are provided by `globalprotect-openconnect`,
`pyside6`, `python-gobject`, `libayatana-appindicator`, `polkit`,
`xdg-utils`, and `libnotify`.

## Arch package

Build and install the included package with:

```sh
makepkg -si
```

Pacman will own the application, helper, Polkit policy, icon, desktop entry,
metadata, and license. The included `PKGBUILD` is suitable for an AUR package
after publishing this source in an AUR Git repository.

## Manual install

```sh
sudo ./install.sh
globalprotect-tray
```

On first launch, enter the HTTPS portal or gateway address. The recommended
defaults automatically detect the server type and OpenSSL compatibility. Use
an explicit mode only when automatic detection is unsuitable.

The browser may ask permission to open **GlobalProtect Tray** after successful
authentication (or **GP Connect** with newer `gpauth` versions). Accepting it
returns the authentication result to `gpauth`.

The tray detects `gpauth auth-callback` support and uses the upstream callback
handler when available, retaining the TCP callback for older releases. Some
upstream packages quote `/usr/bin/gpclient` in `gpgui.desktop`, which can make
`xdg-mime` reject the handler and authentication fail before opening a browser.
For that exact launcher, the tray creates a user-level desktop entry with the
unnecessary quotes removed. It preserves the upstream metadata, leaves system
package files untouched, and never overwrites an existing user desktop entry.

## Settings and diagnostics

Use **Settings…** to change the server, browser, connection mode, OpenSSL mode,
and login autostart. Browser values accepted by `gpauth` include `default`,
`chrome`, `chromium`, `firefox`, or a full executable path.

```sh
globalprotect-tray --check
```

Diagnostics report dependencies, helper installation, tray availability, VPN
state, and the tunnel log location. Full authentication errors are stored under
`~/.local/state/globalprotect-tray/`; SAML responses are not logged.

## Security model

The package installs a root-owned helper and a narrowly scoped Polkit action.
Active local desktop users may invoke the helper without an administrator
password. The helper can only:

- start `gpclient` for a validated HTTPS server with a successful SAML result
  supplied on standard input; or
- ask `gpclient` to disconnect.

It cannot run arbitrary executables, VPN scripts, or additional `gpclient`
arguments. Review `globalprotect-tray-helper` and the `.policy` file before
installing if desired.

## Development disclosure

This project was created agentically using OpenAI Codex under human direction.
Its implementation, packaging, tests, and documentation were produced primarily
through AI-assisted development. Because the application installs a privileged
helper and Polkit policy, users and package maintainers should independently
review those components before installation. The software is provided without
warranty under the MIT License.

## Manual uninstall

Packages should be removed with the system package manager. For a manual
installation:

```sh
sudo ./uninstall.sh
```

User settings and logs are retained. Disable autostart first, or remove
`~/.config/autostart/globalprotect-tray.desktop`.

## License

MIT
