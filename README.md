# sony-a7m4-custom-firmware

Custom firmware for the Sony α7 IV (ILCE-7M4). Work in progress — nothing has
been published yet, and there is nothing to flash at the moment. This README
describes the plan and the ground rules that will hold for everything this
project releases.

## What this is

Firmware modifications for the α7 IV, built on top of Sony's own update files:
extra camera capabilities, and the ability to go back to the stock firmware at
any time. Each release will be a firmware file you copy to an SD card and
install through the camera's normal update menu — the same way the official
one is installed.

## Ground rules

- **Only for the α7 IV.** Never install these files on another camera. Check
  the model in the menu before updating (Menu → Setup → Version).
- **Go back first.** Before service, before selling the camera, or any time
  something behaves oddly, reinstall the official Sony firmware — stock files
  always win, and an official update removes everything this project changes.
- **Checksums with every release.** Each published file comes with its
  SHA-256. A file you did not get from this repository, or one whose checksum
  does not match, must not go near the camera.
- **Nothing leaves your camera.** Firmware changes do not touch your photos,
  and the camera's own calibration data stays as Sony wrote it.

## Risks

An interrupted update, or a damaged firmware file, can leave a camera that
will not start or update again, and that would need Sony service. This has not
happened with the files here, but it cannot be ruled out — read the release
notes, use a freshly formatted card, and do not interrupt the camera while it
updates.

## Status

The first release is being prepared. Until a release is published here, this
repository contains no firmware and no instructions beyond this file.

SONY, α, and Alpha are trademarks of Sony Group Corporation. This project is
not made by, endorsed by, or affiliated with Sony. Use of anything published
here is at your own risk.
