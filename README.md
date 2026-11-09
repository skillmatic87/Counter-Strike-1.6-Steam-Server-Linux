# Counter-Strike 1.6 Steam Server for Linux Mint

A standalone installer for a **32-slot public Steam server on Linux Mint 22.x x86-64**, with bots, chat sounds, custom maps, persistent StatsX ranking, nominations, map voting and a local English/German browser panel.

**Preview 0.1.1.** Automated checks and real-component assembly are documented in [test results](docs/TESTING.md). Native Mint startup, Steam authentication, VAC status and external Internet access require the acceptance checks there. A successful installation alone does not establish Internet reachability.

The central package version is recorded in [VERSION](VERSION), with changes in [CHANGELOG.md](CHANGELOG.md). Download versioned previews from [GitHub Releases](https://github.com/skillmatic87/Counter-Strike-1.6-Steam-Server-Linux/releases). Each release uses a matching `v` tag and includes an installer ZIP plus a SHA-256 checksum. Future package changes must increment `VERSION` and update the changelog; existing releases are kept unchanged.

## Separate Steam and Non-Steam repositories

| Edition | Repository | Platforms and source branch |
| --- | --- | --- |
| Counter-Strike 1.5 Non-Steam | [HL-noSteam](https://github.com/skillmatic87/HL-noSteam) | Windows: `main`; Linux Mint: `linux-mint-server` |
| Counter-Strike 1.6 Steam | [Counter-Strike-1.6-Steam-Server-Linux](https://github.com/skillmatic87/Counter-Strike-1.6-Steam-Server-Linux) | Linux Mint: `main` |

These are separate server packages. CS 1.5 uses the historical WON/LAN server and compatible clients. CS 1.6 uses SteamCMD, Steam clients and Steam-ID administration. Install each in its own directory; their engines, administrators and ranking files are not interchangeable. The Steam package currently supplies a Linux installer only.

The Non-Steam repository keeps its historical `HL-noSteam` URL and ZIP folder names to preserve the archive identity expected by Linux package updaters. Follow the package update instructions when upgrading older ZIPs.

## Install

1. Download this repository's ZIP or clone it, then extract it into a writable directory.
2. Open a terminal in that directory. Install the prerequisites once:

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install python3 ca-certificates iproute2 libc6:i386 libgcc-s1:i386 libstdc++6:i386 zlib1g:i386
```

3. As your regular user, run:

```bash
bash Setup-Linux.sh
bash Start-Server.sh
```

Setup asks for the administrator's **STEAM_0:X:Y** ID and displays editable defaults. Use `status` while connected to a Counter-Strike Steam server to find this ID. Initial installation downloads Valve server files through SteamCMD and checksum-pinned third-party components. Allow at least 4 GiB free space. Keep the repository files together.

Run `bash Start-Panel.sh` to configure and start/stop the server in your browser. The panel is local to the laptop; it is not a public administration website. `Configure-Server.html` opened directly offers a read-only preview and portable game profiles.

The server installs into a new `CS16Server-Linux` directory. Existing directories are never overwritten. Setup does not install a game client, change your router/firewall, or add a system service.

## Play over the Internet

Forward **UDP 27015** from your router to the laptop, and allow it in Mint's firewall if enabled. Use the port chosen during setup if changed. A publicly reachable IPv4 connection is required for direct IPv4 access. Follow [Internet setup and troubleshooting](docs/INTERNET.md), then test with a Steam client on a different Internet connection.

Players use regular Steam Counter-Strike 1.6. No shared game password is configured. Read private `CS16Server-Linux/ADMIN.local.txt` for AMXX, separate YaPB login and RCON instructions; do not publish that directory.

## Included

- ReHLDS 3.15.0.896 on Valve HLDS `steam_legacy`; original CS 1.6 GameDLL.
- Metamod-R 1.3.0.149 and AMXX 1.10-5487 with the Counter-Strike addon.
- YaPB 4.4.957, Map Manager 2.5.61 and Sank Sounds 1.9.1.
- The existing nostalgia pack: 13 custom maps, 122 chat-sound commands, join sound and selectable English botchat.
- Steam-ID administrator access and ranking; map vote five minutes before map end.

Custom-map spawn counts constrain rotation/voting. A 32-slot server does not imply that every map has 32 spawn points. Bot graphs are supplied; navigation quality still requires gameplay checks.

See [installation and panel operation](docs/INSTALL.md), [Internet setup](docs/INTERNET.md), [third-party sources](docs/THIRD-PARTY.md) and [verification](docs/TESTING.md).
