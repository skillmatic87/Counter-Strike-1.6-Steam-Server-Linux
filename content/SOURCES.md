# Content provenance

Inspected on 2026-11-03. Exact URLs and SHA-256 values are in [pack.json](pack.json). Hashes identify inspected files; they do not independently authenticate archive provenance.

- Maps: [Half-Life.fr Counter-Strike archive](https://www.half-life.fr/cs/maps/), original GoldSrc BSP version 30. Archive text/resource notices are retained under installed `_content/notices/<map>/`. BSP files are unmodified. Obsolete absolute Windows paths in RES lists are replaced by relative resource lists; original RES files are retained as notices. Standard Half-Life sky assets come from a compatible client's original `valve/pak0.pak`.
- `de_rats_2001`: map description credits Chris Spain, with playtesting by [SKR8]Gunslinger. This is the actual Rats 2001 BSP, not a renamed `de_rats`.
- Twelve navigation graphs: [official YaPB database](https://github.com/yapb/graph), revision `50524d2fd16ffa4c85b1d77fa8d58f6ee410c214`. Graphs are unmodified. The base installer retains the CC BY-SA 4.0 license, credits and README in `_setup`.
- `de_rats_2001.graph`: generated locally by YaPB 4.4.957 auto-analysis against the inspected 1,695,404-byte BSP; 546 nodes. Stored in Git to avoid analysis during installation. Route quality remains a playtesting item.
- Sounds: the operator supplied an existing Day of Defeat Source server-download collection for this pack. Each selected relative source filename and original SHA-256 is recorded. The 268-file collection contains 264 distinct hashes. Original clip authors and redistribution terms are not established by filenames or their presence in a download directory; no new license is asserted for the clips.
- Processing: copies converted with FFmpeg to PCM signed 16-bit mono at 22050 Hz, metadata stripped, bounded peak adjustment toward -3 dBFS and a limiter. Original files were not edited. Local Faster Whisper base transcription helped selection; it is not a reliable verbatim description and does not replace listening.
- Expansion on 2026-11-04: all 80 further files marked by the operator were included, without trimming their duration. The manifest preserves each original selection number and source checksum. Three keyword collisions were resolved as `camper_agc`, `benny_cp` and `haha_cp`; existing commands keep their mappings. The pack now contains 108 clips, giving 122 keywords with the 14 original defaults.

Selected audio assets and the generated graph are included in Git. Server executables, credentials, the complete source sound collection, transcription model/environment, map ZIPs and raw test logs remain outside tracked project files.

## Shared server presentation, 2026-11-04

The English bot-chat template retains the original YaPB 4.4.957 file and adds project-authored LAN-style lines, including repository and installation references. The parser in that pinned YaPB version selects 838 messages across its regular banks and 42 reply topics. This CS 1.6 edition adapts the MOTD and installation links for Linux Mint and the new repository. Both templates are pinned in the manifest. Setup only installs into a new destination and replaces the freshly downloaded Valve/YaPB welcome defaults; it never updates an existing operator server.

The join announcement reuses the existing `cp/welcome.wav` selection, installed as `sound/lan/welcome.wav`; it is not a newly sourced sound. VOX authorship is unconfirmed. No Matrix clips or newly suggested song excerpts are added by this update.
