# Packaging for Fedora

Two ways in: the plain installer and the RPM.

## Plain installer (recommended for now)

```sh
git clone https://github.com/Samuel-Ku/langswitcher-linux
cd langswitcher-linux
./fedora-kde/install.sh --dry-run   # print every command first
./fedora-kde/install.sh
```

That installs into your home, hands the ydotoold socket to your user and binds
the two KDE shortcuts. Nothing outside `~` is touched except a systemd drop-in
for `ydotool`, which `--dry-run` shows you first.

## RPM

```sh
sudo dnf install rpm-build
git archive --prefix=langswitcher-linux-1.2.0/ \
    -o ~/rpmbuild/SOURCES/langswitcher-linux-1.2.0.tar.gz HEAD
rpmbuild -bb fedora-kde/packaging/langswitcher-kde.spec
sudo dnf install ~/rpmbuild/RPMS/noarch/langswitcher-kde-1.2.0-1*.noarch.rpm
```

The package is `noarch` and installs:

| path | what |
|---|---|
| `/usr/bin/kde-convert` | the worker (finds the core at `/usr/share/langswitcher-kde/lib`) |
| `/usr/share/langswitcher-kde/lib/` | `langswitcher.py`, `switch.py`, `layoutswitch.py` (byte-identical to the other bundles) |
| `/usr/share/applications/net.local.langswitcher-*.desktop` | the two KDE command shortcuts, ready to bind |

**What the RPM deliberately does not do:** it does not enable or reconfigure
`ydotoold`, and it does not write `~/.config/kglobalshortcutsrc`. Both are
per-user decisions. After installing:

1. make the ydotoold socket usable by your user — `fedora-kde/install.sh
   --no-shortcuts` does exactly this one step, or do it by hand as described in
   `../README.md`;
2. bind the shortcuts: **System Settings → Keyboard → Shortcuts → Custom**, pick
   the two `net.local.langswitcher-*` entries and assign keys (`install.sh` uses
   `Meta+\`` and `Meta+Shift+\``);
3. run `kde-convert --check` and read the `hints` array.

## Status

The spec has **not been run through `rpmbuild`** — it was written on a machine
without rpm-build, and no Fedora KDE session was available to test the result.
`%check` only exercises the converter, which needs no session. Treat the RPM as
unverified until someone builds and installs it; the plain installer is the path
that has at least been read end to end.
