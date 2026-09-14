# Fedora spec for the KDE Plasma bundle of LangSwitcher.
#
# Build (from a checkout of the repository):
#   git archive --prefix=langswitcher-linux-1.1.0/ \
#       -o ~/rpmbuild/SOURCES/langswitcher-linux-1.1.0.tar.gz HEAD
#   rpmbuild -bb fedora-kde/packaging/langswitcher-kde.spec
#
# The package installs the command and the two KDE command shortcuts. It does not
# enable ydotoold and does not write any user configuration: handing the ydotoold
# socket to a user and binding a shortcut are per-user decisions. Run
# fedora-kde/install.sh for those, or do them from System Settings.
Name:           langswitcher-kde
Version:        1.1.0
Release:        1%{?dist}
Summary:        Fix text typed in the wrong keyboard layout (KDE Plasma)

License:        MIT
URL:            https://github.com/Samuel-Ku/langswitcher-linux
Source0:        langswitcher-linux-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3
Requires:       python3
Requires:       wl-clipboard
Requires:       ydotool
Requires:       glib2
Requires:       libnotify

%description
LangSwitcher converts a word typed in the wrong keyboard layout (ghbdsn ->
привіт) and switches the active layout to match, so the next word is already in
the right language.

This is the KDE Plasma bundle. Plasma 6 has no supported way for a script to
watch the keyboard, so conversion is hotkey-driven: select the text, press the
shortcut. The replacement is injected with ydotool (uinput), because wtype needs
zwp_virtual_keyboard_v1 - a wlroots protocol KWin does not implement - and the
layout is switched through org.kde.keyboard, one interface for both Wayland and
X11 sessions.

%prep
%autosetup -n langswitcher-linux-%{version}

%build
# Nothing to build: the core is stdlib-only Python and the worker is bash.

%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_datadir}/langswitcher-kde/lib
install -d %{buildroot}%{_datadir}/applications
install -m 755 fedora-kde/bin/kde-convert %{buildroot}%{_bindir}/kde-convert
install -m 644 fedora-kde/lib/langswitcher.py fedora-kde/lib/switch.py \
    fedora-kde/lib/layoutswitch.py %{buildroot}%{_datadir}/langswitcher-kde/lib/
install -m 644 fedora-kde/packaging/net.local.langswitcher-selection.desktop \
    fedora-kde/packaging/net.local.langswitcher-line.desktop \
    %{buildroot}%{_datadir}/applications/

%check
# The converter needs no session; only the injection and the layout switch do, so
# this is the part that can honestly be checked at build time.
printf 'ghbdsn' | python3 %{buildroot}%{_datadir}/langswitcher-kde/lib/switch.py \
    --layouts en,uk,pl | grep -qx 'привіт'

%files
%{_bindir}/kde-convert
%{_datadir}/langswitcher-kde
%{_datadir}/applications/net.local.langswitcher-selection.desktop
%{_datadir}/applications/net.local.langswitcher-line.desktop
%doc fedora-kde/README.md

%changelog
* Sun Sep 14 2026 Samuel-Ku <shtopor02@gmail.com> - 1.1.0-1
- KDE Plasma bundle: hotkey worker on ydotool, org.kde.keyboard layout switch
