# Wansview R2 for Home Assistant

Experimental Home Assistant integration for Wansview / Galayou R2 Pro battery-powered cameras.
Version 0.1.3 adds cloud battery monitoring.

- On-demand snapshots, cached in memory.
- A single Play/Stop control for live video, with automatic shutdown after one minute.
- Dashboard previews do not wake the camera.
- Battery percentage, with cloud polling every 30 minutes and a measurement timestamp.
- One camera per integration entry; multiple entries are supported.

Connects through Wansview Cloud / AJCloud and Internet relay servers. No local RTSP stream is provided. Automatic relay discovery is not yet implemented. PIR events and audio are not yet supported. This is an independent project, not affiliated with the manufacturer.

## Install with HACS

1. In HACS, open the three-dot menu and select **Custom repositories**.
2. Add `https://github.com/papou-github/wansview-r2` and select **Integration** as the category.
3. Find **Wansview R2**, download it, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Wansview R2**.
5. Enter your Wansview Cloud credentials and select your camera.

If you already installed the integration manually, keep your existing configuration entry and the `custom_components/wansview_r2` directory. HACS should manage this same integration. After downloading through HACS, restart Home Assistant and check that your account and entities are still present. Do not create a second copy of the integration.

## Usage

**Refresh image** (currently labelled **Actualiser l’image**) requests a snapshot and then closes the session. The image remains cached until Home Assistant restarts or a new snapshot is captured.

**Live** (currently labelled **Direct**) starts a session lasting up to 60 seconds, including connection time. Press it again to stop early. The control displays Play when stopped and Stop while connecting or streaming. Taking a snapshot alone does not activate this control.

To view live video, enable **Direct**, then open the camera entity. Do not enable stream preloading or use a permanently live dashboard preview.

Your credentials are stored in Home Assistant's configuration. Integration diagnostics exclude credentials, camera keys and images. Do not publish network captures or logs containing secrets.

See [INSTALLATION.md](INSTALLATION.md) for detailed installation and troubleshooting instructions (French).
See [PUBLICATION.md](PUBLICATION.md) for repository publishing instructions (French).

## Validation status

Snapshots and video were tested on CAMSAM with the first Home Assistant version of this integration. The single Play/Stop control was added in version 0.1.1. Offline protocol and FFmpeg conversion tests are included.

HACS installation and updates should be checked on your own setup. This project is installed as a custom HACS repository; it is not listed in the default HACS catalogue.

## Credits

Created by Papou. Wansview, Galayou and Home Assistant names and logos belong to their respective owners.

## Battery monitoring

The Battery sensor reads cached cloud metadata on startup and every 30 minutes.
It never calls the wakeup endpoint or opens a camera session. The value may
therefore be older than the last cloud check. Its `measurement_time` attribute
is the camera measurement timestamp, not the time Home Assistant fetched it.
Cloud failures make the battery sensor unavailable; video controls remain independent.
The `batteryAlarm` protocol value is not interpreted as a low-battery alert.

## Updating to 0.1.3

Upload this repository content to GitHub, keeping `custom_components` at the
root. In HACS, update information and redownload (or install release v0.1.3),
then restart Home Assistant. Keep existing configuration entries and entities.
The icon is included under `custom_components/wansview_r2/brand/icon.png`.
