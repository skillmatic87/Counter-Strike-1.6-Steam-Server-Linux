# Verification and remaining acceptance checks

Preview 0.1.1 targets Linux Mint 22.x x86-64. Automated configuration/assembly checks on a Windows development machine do not establish native Linux execution or public reachability.

## Repository identity review — 2026-11-09

The Steam package has its own repository, separate from CS 1.5 Non-Steam. Version 0.1.1 corrects the English/German panel repository label and the attribution link. All 26 Python tests and the Node configurator checks passed again on Windows. Package payload hashes were checked against the content manifest. This review adds no native Linux, Steam authentication or Internet gameplay evidence; the acceptance items below remain open.

## Development results — 2026-11-05

- 26 Python tests passed, covering settings, package version reporting, archive safety, download integrity, SteamCMD retry limits, A2S challenge exchange, panel HTTP guards, Steam-ID administration, private backup/restore, running-server edit protection and start/stop orchestration.
- Node checks passed for all embedded JavaScript syntax and actual panel configuration transformations, including StatsX and scoring changes.
- Bash syntax checks passed for all three entry scripts.
- Real pinned component assembly passed: ReHLDS/Metamod/AMXX/YaPB Linux binaries, 13 real custom maps plus one synthetic original, navigation files and 122 sound commands.
- Map Manager, Sank Sounds and both CSX scoring programs compiled with the matching upstream AMXX 1.10-5487 Windows compiler. The resulting Pawn bytecode is platform-independent; native Linux compiler execution remains a separate check.
- Formula switching preserved the ranking-data fixture. Installed custom-map spawn capacities were read from actual BSP entity data.
- Browser visual verification was unavailable because local browser use is disabled in this session. Automated JavaScript checks are not a substitute for a visual walkthrough.
- The source ZIP was extracted into a fresh directory; all 25 Python tests and the JavaScript checks passed there as well. Generated server data and credentials are excluded from the archive.

## Repeat automated checks

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
node scripts/test_configurator.cjs
bash -n Setup-Linux.sh Start-Server.sh Start-Panel.sh
```

The optional real-component assembly test uses verified cached Linux archives and the matching upstream AMXX compiler:

```bash
python3 scripts/check_assembly.py --cache-directory downloads
```

It supplies a **synthetic Valve directory** because Valve installation and execution require a native Linux environment. ReHLDS, Metamod, AMXX, YaPB, plugin sources, sounds and custom maps are real pinned downloads. The report identifies this limitation; it does not claim a real SteamCMD installation.

## Required native acceptance on the laptop

- Fresh ZIP extraction and setup on Mint 22.x; retain OS version and `_setup` logs.
- Confirm native SteamCMD installation, Linux plugin compilation, server startup, Steam login and actual VAC status.
- Inspect `version`, `status`, `meta list`, `amxx plugins` and `amxx modules`; no failed loads or runtime errors.
- Join with a Steam CS 1.6 client; verify 32 configured slots. This is not a 32-client load test.
- Authorized Steam ID can use `amxmodmenu`; another Steam account cannot. Verify separate YaPB login.
- Bots play on original and custom maps. Graph presence is not proof of navigation quality.
- Nominations, map voting five minutes before map end, map changes and restart work.
- Two human clients test chat sounds, cooldown/quota, join sound and resource downloads.
- Controlled kills/deaths appear in `/rank` and `/top15`; ranking survives map change, name change and regular shutdown/restart. Test both selectable scoring modes.
- Panel can save/review/restore settings, change administrators and rotate credentials while stopped.
- Follow the Internet guide: direct join and custom downloads from another Internet connection; server-browser listing tested separately.

Native Mint execution, actual Steam/VAC authentication, external connectivity, two-human audio and a 32-client load test remain **open** until recorded here with actual observations.
