#!/usr/bin/env python3
"""Real-component integration check with a synthetic Valve base, never a runtime claim."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import time

import install_cs16_linux as installer
from install_common import extract, write_text
from settings import DEFAULTS


def fixture_valve(server, steamcmd):
    """Supply only the minimum fixture base; SteamCMD is not invoked in this check."""
    for relative in ('cstrike/dlls/cs.so', 'libsteam_api.so', 'steamclient.so'):
        target = server / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'\x7fELF\x01' + b'FIXTURE-NOT-EXECUTABLE')
    write_text(server / 'cstrike/liblist.gam', 'game "Counter-Strike"\ngamedll_linux "dlls/cs.so"\n')
    write_text(server / 'cstrike/motd.txt', 'Original Valve CS 1.6 welcome message fixture.\n')
    entities = ('{\n"classname" "worldspawn"\n}\n' + ''.join(
        '{\n"classname" "info_player_' + ('start' if i % 2 else 'deathmatch') + '"\n}\n' for i in range(32))).encode()
    header = struct.pack('<iii', 30, 124, len(entities)) + bytes(112)
    path = server / 'cstrike/maps/de_dust2.bsp'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entities)
    write_text(server / '_setup/valve-build.json', '{"fixture":true,"steamcmdExecuted":false}\n')


def check(server):
    plugins = (server / 'cstrike/addons/amxmodx/configs/plugins.ini').read_text()
    for name in ('statsx', 'mapmanager', 'sank_sounds'):
        assert name+'.amxx' in plugins
        assert (server / f'cstrike/addons/amxmodx/plugins/{name}.amxx').stat().st_size > 100
    assert 'mapchooser.amxx' not in plugins
    assert 'mapmanager_cs15' not in (server / 'cstrike/addons/amxmodx/scripting/mapmanager.sma').read_text(encoding='utf-8-sig')
    launch = (server / 'Start-CS16.sh').read_text()
    assert '+sv_lan 0' in launch and '+maxplayers 32' in launch
    assert '-insecure' not in launch and '-nomaster' not in launch
    assert '"ce"' in (server / 'cstrike/addons/amxmodx/configs/users.ini').read_text()
    stats = (server / 'cstrike/addons/amxmodx/configs/csstats.cfg').read_text()
    assert 'csstats_rank 1' in stats and 'csstats_rankbots 0' in stats
    assert 'exec addons/amxmodx/configs/csstats.cfg' in (server / 'cstrike/addons/amxmodx/configs/amxx.cfg').read_text()
    sounds = (server / 'cstrike/addons/amxmodx/configs/SND-LIST.CFG').read_text()
    assert len([line for line in sounds.splitlines() if line and line[0].islower() and '; sound/' in line]) == 122
    assert 'SND_JOIN; sound/lan/welcome.wav' in sounds
    assert not (server / '.install-incomplete').exists()
    maps = list((server / 'cstrike/maps').glob('*.bsp'))
    assert len(maps) == 14, len(maps)  # one synthetic original + thirteen real custom maps
    for bsp in maps:
        assert (server / f'cstrike/addons/yapb/data/graph/{bsp.stem}.graph').is_file()
        assert 2 <= installer.bsp_capacity(bsp) <= 32
    for name in ('Kills', 'KillsMinusDeaths'):
        assert (server / f'_setup/ranking/{name}.amxx').stat().st_size > 100
    assert 'Steam ID' in (server / 'ADMIN.local.txt').read_text()
    # Applying another formula derives bytecode without resetting persisted ranking data.
    settings = json.loads((server / 'settings.local.json').read_text())
    data = server / 'cstrike/addons/amxmodx/data/csstats.dat'
    data.write_bytes(b'persisted-ranking-fixture')
    first = (server / 'cstrike/addons/amxmodx/data/csstats.amxx').read_bytes()
    settings['RankScore'] = 'Kills'
    write_text(server / 'settings.local.json', json.dumps(settings))
    installer.prepare_ranking(server)
    assert first != (server / 'cstrike/addons/amxmodx/data/csstats.amxx').read_bytes()
    assert data.read_bytes() == b'persisted-ranking-fixture'
    print(f'Assembly passed: {len(maps)} maps, 122 sound commands, Steam-ID access, four plugin compilations. Valve base is synthetic; no HLDS or Steam runtime test.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-directory', type=Path, default=installer.ROOT / 'downloads')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    cache = args.cache_directory.absolute()
    compiler = None
    if os.name == 'nt':
        archive = cache / 'amxmodx-1.10.0-git5487-base-windows.zip'
        if not archive.exists():
            parser.error('Windows assembly needs the matching upstream AMXX Windows compiler archive in the cache; it is a development-only prerequisite.')
        work = installer.ROOT / 'runtime/windows-compiler'
        if not (work / 'addons/amxmodx/scripting/amxxpc.exe').exists():
            extract(archive, work)
        compiler = work / 'addons/amxmodx/scripting/amxxpc.exe'
    target = (args.destination or installer.ROOT / ('runtime/assembly-' + str(time.time_ns()))).absolute()
    settings = dict(DEFAULTS, AdminSteamID='STEAM_0:1:123456')
    installer.assemble(target, cache, settings, compiler=compiler, valve_installer=fixture_valve, native_base=False)
    check(target)
    print('Fixture installation: '+str(target))


if __name__ == '__main__':
    main()
