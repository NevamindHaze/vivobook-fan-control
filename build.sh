#!/bin/bash
# Tests, builds the .deb, and regenerates the signed apt repository in docs/ (served by GitHub Pages).
# Bump Version in packaging/control before each release.
set -eu
cd "$(dirname "$0")"
name=vivobook-fan-control
key="$name apt signing"
version=$(sed -n 's/^Version: //p' packaging/control)

python3 test_fanctl.py

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"  # mktemp's 700 would ship as the mode of the package's root directory
install -Dm644 packaging/control "$stage/DEBIAN/control"
install -Dm755 fanctl.py "$stage/usr/lib/$name/fanctl.py"
install -d "$stage/usr/bin"
ln -s "../lib/$name/fanctl.py" "$stage/usr/bin/$name"
install -Dm644 "packaging/$name.desktop" "$stage/usr/share/applications/$name.desktop"
install -Dm644 "packaging/$name.svg" "$stage/usr/share/icons/hicolor/scalable/apps/$name.svg"
install -Dm644 "packaging/io.github.nevamindhaze.$name.policy" \
  "$stage/usr/share/polkit-1/actions/io.github.nevamindhaze.$name.policy"

mkdir -p docs/pool/main "docs/dists/stable/main/binary-amd64"
dpkg-deb --root-owner-group --build "$stage" "docs/pool/main/${name}_${version}_all.deb"

cd docs
touch .nojekyll
gpg --export "$key" > key.gpg
apt-ftparchive packages pool > dists/stable/main/binary-amd64/Packages
gzip -kf9 dists/stable/main/binary-amd64/Packages
cd dists/stable
apt-ftparchive \
  -o APT::FTPArchive::Release::Suite=stable \
  -o APT::FTPArchive::Release::Codename=stable \
  -o APT::FTPArchive::Release::Components=main \
  -o APT::FTPArchive::Release::Architectures=amd64 \
  release . > /tmp/$name-Release.$$
mv /tmp/$name-Release.$$ Release
gpg --yes --batch -u "$key" --clearsign -o InRelease Release
gpg --yes --batch -u "$key" -abs -o Release.gpg Release
