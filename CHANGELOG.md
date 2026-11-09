# Changelog

The package uses semantic versions. Git tags use the `v` prefix; `VERSION` contains the numeric version. Until the native Mint and Internet acceptance checks pass, releases are marked as previews on GitHub.

## 0.1.1 — 2026-11-09

- Correct the English/German panel repository label to Counter-Strike 1.6 Steam.
- Document separate Steam and Non-Steam repositories, platforms and compatibility.
- Native Linux/Steam/Internet acceptance remains open as documented in `docs/TESTING.md`.

## 0.1.0 — 2026-11-05

Initial Linux Mint 22.x preview:

- SteamCMD installation of a public 32-slot Counter-Strike 1.6 server with ReHLDS and Metamod-R.
- AMXX Steam-ID administration, StatsX ranking and two selectable scoring formulas.
- YaPB bots, 13 custom maps, 122 sound commands, nominations and timed map voting.
- Local English/German panel with configuration review, backup/restore and start/stop.
- Internet setup instructions and separate native/external acceptance checklist.
- Checksum-pinned components, isolated fresh installations and automated verification.

Known verification limits: native Mint startup, Steam/VAC authentication, external client connectivity, browser visual walkthrough and multi-client gameplay checks remain open. See [test results](docs/TESTING.md).
