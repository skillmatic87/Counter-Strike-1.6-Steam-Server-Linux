# Consistent package operation

The browser panel starts in English. Select Deutsch or English to change its language; the choice is stored in this browser. Switching languages preserves unsaved settings. Technical logs and setup prompts are English. Original third-party material and operator-entered text are not translated.

The Game address section lists assigned, active LAN IPv4 addresses and the configured UDP port. Use Copy to copy the full `connect IP:Port` command. A wildcard bind, loopback panel URL or missing interface is never advertised as a LAN game address. Multiple matching interfaces are shown separately. No public-IP service is queried.

Each panel start opens a dedicated visible server terminal. For Sven, this is a live-output window: closing it leaves the game running; use Stop in the panel, and Show server terminal to reopen/focus output. CS and DoD use their existing interactive consoles. Start from the graphical desktop on Linux; missing desktop/terminal requirements produce an error instead of a silent background start.

## Upgrade an existing extracted package

1. Stop the game server and close its panel. Keep its existing package directory.
2. Extract the new version into a **separate** directory. Do not overlay the old directory first: on Windows this can overwrite a case-insensitive old filename before a backup can be made.
3. In the new directory run `python3 scripts/migrate_package.py --target /path/to/old/package --check`. For packages supporting Windows, use `migrate-package.cmd --target "D:\Existing package" --check` (Python 3.10+ is required for this optional migration).
4. Review the paths. Run the same command with `--apply`. Recognized package-source files are backed up under numeric object IDs in `.package-migration-backups/`; installed games, settings, credentials, rankings and unknown files are not migration targets. A locally modified/unrecognized package file is a conflict, and preflight changes no package files.
5. If interrupted, use `--recover` from the same new extraction. Recovery checks the complete backup and current bytes before writing, restores original bytes and spelling, and retains its journal on failure. Do not manually edit files while recovery is pending.
6. Open the lowercase `start-panel.sh` or `start-panel.cmd` in the updated old directory. Replace any manually created shortcut that still refers to uppercase public starters. Refresh a Sven Steam installer shortcut using `python3 scripts/setup.py --refresh-shortcut` after stopping the panel/server.

Startup never silently performs this migration. Updated launchers share a lifetime lock with migration. Legacy-process detection supplements that lock; an engine manually launched outside supported launchers or outside the package directory may not be detectable. Migration is explicitly offline. Do not use it on a Git checkout.

## Package updates versus game updates

Package migration updates the installer/panel/scripts and documented package payload only. SteamCMD's stable update refreshes the official Steam game server and is a separate operation. Existing CS 1.5 Linux ZIP updater recovery must complete before package migration.

## Verification

Run the package's documented Python checks. The additional `test_uniform.py` suite covers case spelling, previous/new contents, conflicts, injected interruption, corrupt backup refusal, protection of later edits, staged-write recovery, address filtering and lifetime locks. Native Linux terminal/process tests and real engine/Wine acceptance are reported separately. Mocked/test-process output does not establish a real game server or multiplayer acceptance.

Release maintainers must carry verified historical manifest hashes in `previous_manifests`, alongside known previous payload hashes. Recovery must use the exact preserved source extraction that started the interrupted migration.
