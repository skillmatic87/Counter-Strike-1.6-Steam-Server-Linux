# Sources, versions and notices

This project adapts the operator's existing [CS 1.5 Non-Steam server installer and local panel](https://github.com/skillmatic87/HL-noSteam). The original project and its operator data remain separate. This repository distributes installer code and selected content, not a repack of Valve's server binaries.

| Component | Source |
| --- | --- |
| Valve HLDS / SteamCMD | [SteamCMD documentation](https://developer.valvesoftware.com/wiki/SteamCMD); official bootstrap from steamcdn-a.akamaihd.net; app 90 `steam_legacy` |
| ReHLDS 3.15.0.896 | [Release and source](https://github.com/rehlds/ReHLDS/tree/3.15.0.896), MIT |
| Metamod-R 1.3.0.149 | [Release and source](https://github.com/rehlds/Metamod-R/tree/1.3.0.149); retain upstream license notices |
| AMXX 1.10-5487 | [Release](https://github.com/alliedmodders/amxmodx/releases/tag/1.10.0.5487), GPLv3 with upstream exceptions; base package includes GPL text and Pawn source |
| YaPB 4.4.957 | [Release and source](https://github.com/yapb/yapb/tree/4.4.957); use this version's bundled license notices |
| YaPB navigation data | [Pinned graph database](https://github.com/yapb/graph/tree/50524d2fd16ffa4c85b1d77fa8d58f6ee410c214), CC BY-SA 4.0; credits/license retained under `_setup` |
| Map Manager 2.5.61 | [Pinned author source](https://github.com/Mistrick/MapManager/tree/ed09e4d78ab5c6cb617b2e37c06a08df2cea7648); compiled without the CS 1.5 adaptation |
| Sank Sounds 1.9.1 | [Pinned author source](https://github.com/ZTHawk/HL1_SankSounds/tree/ed02c30bed512994b98e208c644c1e366b5209e3) |
| Classic sound pack | [StatsMe Soundpack 1.0](https://sourceforge.net/projects/statsme/files/StatsMe%20Add-Ons/Soundpack%201.0/) |

Exact download URLs and SHA-256 values are recorded in the component/content manifests. The ReHLDS and AMXX archive hashes match GitHub release metadata; locally calculated hashes for other archives pin inspected bytes and are not independent authenticity evidence.

The nostalgia content manifest records map archives, navigation resources, retained map-author notices, and operator-selected sounds inherited from the CS 1.5 package. Preserve those credits and notices. New project branding replaces old server-version instructions; original third-party attribution is retained.

Setup retains downloaded archives in its cache and extracted plugin sources under `_setup`. Generated ranking source is kept alongside its bytecode. Do not redistribute a configured server without separately reviewing Valve's terms and the licenses of all included components. No replacement license is asserted for third-party work.
