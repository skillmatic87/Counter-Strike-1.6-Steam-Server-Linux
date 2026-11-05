# Installation and local operation

## Supported target

Linux Mint 22.x, x86-64, Python 3.10+, Bash and 32-bit compatibility libraries. Other Linux distributions, ARM and Windows are outside this release. The engine is 32-bit even on a 64-bit laptop.

Install the prerequisite packages listed in the README, then run `bash Setup-Linux.sh` as a normal user. `bash Setup-Linux.sh --check` only checks platform and prerequisites. The installer downloads Valve's official SteamCMD bootstrap, lets it self-update, and installs app 90 with mod `cstrike` on `steam_legacy` using anonymous server login. No personal Steam password is collected by setup.

The bootstrap and third-party archives are checksum-pinned. SteamCMD's self-updated runtime and Valve depots are validated by SteamCMD rather than project SHA-256 pins. Installed app manifests and installation logs are retained under `_setup`.

## Setup options

```bash
bash Setup-Linux.sh --destination "$HOME/CS16Server" --port 27015 --bind-address 0.0.0.0
bash Start-Server.sh "$HOME/CS16Server"
bash Start-Panel.sh "$HOME/CS16Server"
```

Use `0.0.0.0` to listen on all local IPv4 interfaces. An explicit address must be assigned to the laptop, not the router's public IPv4 address. If CS 1.5 already uses UDP 27015 on the same laptop, select another port, such as 27016, and forward that port instead.

For unattended setup, create a private JSON file and run `bash Setup-Linux.sh --settings /path/to/settings.local.json`. Only `AdminSteamID` is mandatory; omitted values use these defaults:

```json
{
  "AdminSteamID": "STEAM_0:1:123456",
  "ServerName": "CS 1.6 Steam Server",
  "Port": 27015,
  "BindAddress": "0.0.0.0",
  "MapMinutes": 30,
  "FriendlyFire": 0,
  "BotTarget": 16,
  "BotDifficulty": 2,
  "SoundCooldown": 3,
  "SoundQuota": 100,
  "RankBots": 0,
  "RankScore": "KillsMinusDeaths"
}
```

Replace the example Steam ID. Boolean settings use 0/1 in JSON. `RankScore` accepts `Kills` or `KillsMinusDeaths`. Ranking starts fresh, persists locally by Steam authentication ID, and does not automatically reset. Enabling bot ranking uses CSX's handling of bots; keep it off for a human-only leaderboard.

## Installation failures

Setup refuses an existing destination. A failed installation retains `.install-incomplete` and diagnostic logs. Preserve it, correct the reported problem and choose a **new** destination on retry. The download cache is reusable. Corrupt cached files are reported instead of silently trusted; move the named file aside and retry. App 90 is retried at most three times if SteamCMD fails or required files are absent.

Do not copy the old CS 1.5 engine or GameDLL into this server. Do not run a generic SteamCMD validation over a configured server: it can replace Metamod/ReHLDS files. Automatic upgrades and content-update/rollback tooling are not included in this first Mint release. Test a fresh installation when upgrading the component manifest.

## Panel and administration

The panel binds only to `127.0.0.1` on an automatically chosen HTTP port. Keep its terminal running while using it. The server continues running when you close the browser page. Normal stopping sends authenticated GoldSrc RCON `quit`; shutdown failure is reported instead of force-killing the server.

Configure game rules, slots, starting map, map rotation/voting, bots, chat-sound switches and timing, ranking and welcome text. Review changes before saving. Saving and restoring require a stopped server and protect against stale file snapshots. Map rotation supports drag-and-drop. Native folder selection is optional; enter the absolute server path if Tk is unavailable.

The Administration tab adds, changes and removes Steam-ID administrators, preserves existing access flags, rotates RCON/YaPB passwords and provides separate private backups. At least one administrator must remain. AMXX uses Steam authentication, not a name or shared password. New administrators receive the same full administration flags as the initial operator.

YaPB has a separate login. Enter `setinfo _ybpw "<password>"` in the client console **before connecting**, then `yb menu`. Read the generated private instructions for the actual password. AMXX administrator status alone does not grant YaPB permissions.

Ranking scoring programs are built during setup. A changed scoring selection is applied at the next start. The panel and generated launcher use the same preparation function. There is no old StatsMe database migration.

## Private files and Steam runtime

Setup uses a private server directory and restrictive file permissions. Keep generated settings, RCON/YaPB credentials, player logs, rankings and `_configurator` backups off GitHub. Back up the complete stopped server directory to preserve statistics and settings.

Steam's SDK may use `~/.steam/sdk32/steamclient.so`. When missing, setup creates a per-user link to this installation's downloaded Steam client library; it preserves an existing file/link. If you later remove this installation, check that link before using another Steam server. The installer does not install a personal Steam desktop client.

No systemd service or crash supervisor is installed. Start manually in a terminal or panel. Configure Mint's power settings so the laptop stays awake while hosting; use wired networking where available. Review heat, power and lid-close behavior locally.
