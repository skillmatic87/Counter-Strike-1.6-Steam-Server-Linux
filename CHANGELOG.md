## 0.2.2 — 2026-11-20

- Chat AI recognizes the full bot name on its own, at the start of a message, or after a greeting such as `hi` or `hey`.
- Directed replies appear privately in the requester's chat, including after the player or bot dies. Team-chat requests require a bot on the same team.

## 0.2.1 — 2026-11-20

- Converted the English bot-chat phrases and reply topics to the YaPB 4.8 configuration format.
- Fixed Chat AI handling of the surrounding quotes in normal GoldSrc player chat.

## 0.2.0 — 2026-11-19

- YaPB 4.8.1432 on ReGameDLL 5.30.0.814. The distribution includes the checksum-pinned YaPB archive.
- Opt-in English Chat AI with on-device Qwen or an OpenAI-compatible endpoint. Both are restricted to direct bot mentions.
- Console and panel starts manage the loopback Chat AI backend for the game session.

## 0.1.3 — 2026-11-10

- English-first bilingual browser panel with assigned game endpoints and copyable connection commands.
- Lowercase public launchers, independent source-package manifest and explicit offline migration with validated rollback.
- Visible server terminals retained; direct Sven Steam starter and cross-platform launch/migration coordination added.
- Configuration, credentials, rankings and third-party engine interfaces are preserved.

# Changelog

## 0.1.2 — 2026-11-09

- Panel starts the server in its own named interactive GNOME Terminal instead of redirecting the whole console into a background file.
- Separate private session recordings and terminal-loss/parent-death protection reuse the tested CS 1.5 recorder as an independent package component.
- Steam authentication, server configuration and ranking files are retained.

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
