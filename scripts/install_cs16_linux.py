#!/usr/bin/env python3
"""Install a fresh native Counter-Strike 1.6 Steam server for Linux Mint 22.x."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import struct
import subprocess
import sys

from install_common import (download, extract, read_json, safe_path, verified_bytes,
                            write_text)
from settings import DEFAULTS, get_settings, check_bind, prepare_ranking
from project_version import VERSION

ROOT = Path(__file__).resolve().parents[1]
CLASSIC_SOUNDS = ('dominating doublekill firstblood godlike headshot humiliation '
                  'killingspree monsterkill multikill perfect prepare rampage '
                  'ultrakill unstoppable').split()
PLUGINS = ('admin admincmd adminhelp multilingual menufront cmdmenu plmenu mapsmenu '
           'pluginmenu adminchat antiflood adminvote pausecfg statscfg statsx '
           'mapmanager sank_sounds').split()
DEPENDENCIES = '''sudo dpkg --add-architecture i386
sudo apt update
sudo apt install python3 ca-certificates iproute2 libc6:i386 libgcc-s1:i386 libstdc++6:i386 zlib1g:i386'''


def components():
    return {e['id']: e for e in read_json(ROOT / 'scripts/components.json')['components']}


def replace_cvars(path, values):
    text = path.read_text(encoding='latin1')
    for key, value in values.items():
        pattern = r'(?m)^' + re.escape(key) + r'\s+[^\r\n]*'
        text, count = re.subn(pattern, lambda _: key + ' ' + value, text)
        if not count:
            text += '\n' + key + ' ' + value + '\n'
    write_text(path, text.replace('\r\n', '\n'))


def single_root(path):
    roots = list(path.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError(f'Unexpected source archive layout: {path}')
    return roots[0]


def check_libraries(server, paths):
    environment = os.environ.copy()
    environment['LD_LIBRARY_PATH'] = str(server) + ':' + environment.get('LD_LIBRARY_PATH', '')
    failures = []
    for relative in paths:
        run = subprocess.run(['ldd', str(server / relative)], env=environment, capture_output=True, text=True)
        if run.returncode or 'not found' in run.stdout + run.stderr:
            failures.append(relative + ':\n' + run.stdout + run.stderr)
    if failures:
        raise ValueError('Missing/incompatible 32-bit libraries:\n' + '\n'.join(failures) + '\n' + DEPENDENCIES)


def base_complete(server):
    required = ('hlds_linux', 'engine_i486.so', 'filesystem_stdio.so', 'libsteam_api.so',
                'cstrike/liblist.gam', 'cstrike/dlls/cs.so', 'cstrike/maps/de_dust2.bsp',
                'cstrike/models/v_ak47.mdl', 'valve/halflife.wad')
    return all((server / name).is_file() and (server / name).stat().st_size for name in required)


def install_valve(server, steamcmd):
    for attempt in range(1, 4):
        print(f'Installing Valve HLDS steam_legacy (attempt {attempt}/3)...', flush=True)
        command = ['bash', str(steamcmd / 'steamcmd.sh'), '+force_install_dir', str(server),
                   '+login', 'anonymous', '+app_set_config', '90', 'mod', 'cstrike',
                   '+app_update', '90', '-beta', 'steam_legacy', 'validate', '+quit']
        with (server / f'_setup/steamcmd-attempt-{attempt}.log').open('wb') as output:
            run = subprocess.run(command, cwd=steamcmd, stdout=output, stderr=subprocess.STDOUT)
        if run.returncode == 0 and base_complete(server):
            break
    else:
        raise ValueError('SteamCMD did not install the complete server after three attempts. See _setup/steamcmd-attempt-*.log. Retry with a new destination; downloaded archives are cached.')
    manifests = list((server / 'steamapps').glob('appmanifest_*.acf'))
    report = dict(appId=90, mod='cstrike', branch='steam_legacy',
                  manifests={p.name:p.read_text(encoding='utf-8', errors='replace') for p in manifests})
    write_text(server / '_setup/valve-build.json', json.dumps(report, indent=2) + '\n')
    steam_client = steamcmd / 'linux32/steamclient.so'
    if not steam_client.is_file():
        raise ValueError('SteamCMD runtime is missing linux32/steamclient.so.')
    shutil.copyfile(steam_client, server / 'steamclient.so')
    licenses = list(server.glob('*[Ll][Ii][Cc][Ee][Nn]*')) + list(server.glob('*[Ee][Uu][Ll][Aa]*'))
    write_text(server / '_setup/valve-notices.txt', 'Valve server files are downloaded directly through SteamCMD, not redistributed by this project.\nPreserve all upstream files and notices.\nDetected notices: ' + ', '.join(p.name for p in licenses if p.is_file()) + '\n')


def compile_one(compiler, source, output, includes, log):
    output.parent.mkdir(parents=True, exist_ok=True)
    compiler.chmod(0o755)
    run = subprocess.run([str(compiler), str(source), *['-i' + str(p) for p in includes], '-o' + str(output)],
                         cwd=compiler.parent, capture_output=True, text=True, errors='replace')
    write_text(log, run.stdout + run.stderr)
    if run.returncode or re.search(r'error [0-9]|Compilation aborted|compile failed', run.stdout + run.stderr, re.I) or not output.is_file():
        raise ValueError(f'Plugin compilation failed. See {log}')


def compile_plugins(server, compiler=None):
    work = server / '_setup'
    amxx = server / 'cstrike/addons/amxmodx'
    maps, sank = single_root(work / 'mapmanager'), single_root(work / 'sank')
    compiler = compiler or amxx / 'scripting/amxxpc'
    includes = [amxx / 'scripting/include', maps / 'include']
    for source, name in ((maps / 'mapmanager.sma', 'mapmanager'), (sank / 'sank_sounds.sma', 'sank_sounds')):
        compile_one(compiler, source, amxx / f'plugins/{name}.amxx', includes, work / f'{name}-compile.txt')
        shutil.copyfile(source, amxx / 'scripting' / source.name)
    shutil.copyfile(maps / 'mapmanager.txt', amxx / 'data/lang/mapmanager.txt')
    shutil.copyfile(maps / 'mapmanager.cfg', amxx / 'configs/mapmanager.cfg')
    replace_cvars(amxx / 'configs/mapmanager.cfg', {'mapm_start_vote_before_end':'5'})
    # CSX loads this small scoring program separately from normal AMXX plugins.
    for score, expression in (('Kills', 'stats[0]'), ('KillsMinusDeaths', 'stats[0] - stats[1]')):
        source = work / f'ranking/{score}.sma'
        write_text(source, '#include <amxmodx>\npublic get_score(stats[11], body[MAX_BODYHITS]) { return ' + expression + '; }\n')
        compile_one(compiler, source, source.with_suffix('.amxx'), includes, source.with_suffix('.log'))


def bsp_capacity(path):
    """Count actual player starts rather than assuming every map supports 32."""
    with path.open('rb') as stream:
        header = stream.read(124)
        if len(header) != 124 or struct.unpack_from('<i', header)[0] != 30:
            raise ValueError(f'Unsupported BSP header: {path.name}')
        offset, length = struct.unpack_from('<ii', header, 4)
        if offset < 124 or not 0 < length <= 4 * 1024 * 1024 or offset + length > path.stat().st_size:
            raise ValueError(f'Invalid BSP entities: {path.name}')
        stream.seek(offset)
        text = stream.read(length).decode('latin1')
    starts = re.findall(r'"classname"\s+"info_player_(?:start|deathmatch)"', text)
    if len(starts) < 2:
        raise ValueError('Not enough player spawns in ' + path.name)
    return min(32, len(starts))


def install_content(server, cache):
    import zipfile
    manifest = read_json(ROOT / 'content/pack.json')
    managed = []
    def put(entry, data):
        verified_bytes(data, entry['sha256'], entry['target'])
        target = safe_path(server, entry['target'])
        if target.exists() and target.read_bytes() != data:
            if entry.get('preserveExisting'):
                return
            presentation = entry['target'] in ('cstrike/motd.txt', 'cstrike/addons/yapb/conf/lang/en_chat.cfg')
            # Only fresh destinations reach this function. Replace the downloaded
            # Valve/YaPB welcome defaults, never an operator's existing server.
            if not presentation:
                raise ValueError(f'Content would overwrite a different file: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        managed.append(dict(path=entry['target'], sha256=entry['sha256']))
    for entry in manifest['localFiles']:
        put(entry, safe_path(ROOT / 'content', entry['source']).read_bytes())
    for package in manifest['packages']:
        archive = download(package, cache)
        if package['kind'] == 'raw' and len(package['files']) == 1:
            put(package['files'][0], archive.read_bytes())
        elif package['kind'] == 'zip':
            with zipfile.ZipFile(archive) as z:
                for entry in package['files']:
                    matches = [m for m in z.infolist() if m.filename.replace('\\', '/') == entry['source']]
                    if len(matches) != 1 or matches[0].file_size > 64 * 1024 * 1024:
                        raise ValueError('Missing, duplicate or oversized content member.')
                    put(entry, z.read(matches[0]))
        else:
            raise ValueError('Unknown content package layout.')
    path = server / 'cstrike/addons/amxmodx/configs/SND-LIST.CFG'
    text = path.read_text(encoding='ascii')
    join = manifest.get('joinSound', '')
    if join and join not in [s['path'] for s in manifest['sounds']]:
        raise ValueError('Join sound is not a verified sound.')
    text = re.sub(r'(?m)^SND_JOIN;[^\n]*', lambda _: 'SND_JOIN; ' + join, text)
    text += ''.join(f"{s['keyword']}; {s['path']}\n" for s in manifest['sounds'])
    write_text(path, text)
    write_text(server / '_content/installed.json', json.dumps(dict(schemaVersion=1, id=manifest['id'], files=managed), indent=2)+'\n')


def configure(server, settings):
    amxx = server / 'cstrike/addons/amxmodx'
    rcon, bot_password = secrets.token_hex(15), secrets.token_hex(15)
    write_text(server / 'VERSION', VERSION + '\n')
    write_text(server / 'settings.local.json', json.dumps(settings, indent=2)+'\n')
    write_text(server / 'cstrike/server.cfg', f'''// Counter-Strike 1.6 Steam Internet server
hostname "{settings['ServerName']}"
sv_lan 0
sv_password ""
rcon_password "{rcon}"
sv_allowdownload 1
sv_allowupload 0
sv_region 3
mp_timelimit {settings['MapMinutes']}
mp_friendlyfire {settings['FriendlyFire']}
mp_maxrounds 0
mp_winlimit 0
log on
''')
    write_text(amxx / 'configs/users.ini', f'"{settings["AdminSteamID"]}" "" "abcdefghijklmnopqrstu" "ce"\n')
    write_text(amxx / 'configs/csstats.cfg', f'csstats_rank 1\ncsstats_rankbots {settings["RankBots"]}\ncsstats_reset 0\ncsstats_maxsize 100000\n')
    replace_cvars(amxx / 'configs/amxx.cfg', {'amx_client_languages':'1'})
    with (amxx / 'configs/amxx.cfg').open('a', encoding='ascii') as stream:
        stream.write('\nexec addons/amxmodx/configs/csstats.cfg\n')
    write_text(amxx / 'configs/stats.ini', 'KillerChat\nShowAttackers\nShowVictims\nSayHP\nSayStatsMe\nSayRankStats\nSayMe\nSayRank\nSayTop15\nSayStatsAll\n')
    replace_cvars(server / 'cstrike/addons/yapb/conf/yapb.cfg', {
        'yb_quota':str(settings['BotTarget']), 'yb_quota_mode':'"fill"',
        'yb_difficulty':str(settings['BotDifficulty']), 'yb_autovacate':'1',
        'yb_password':f'"{bot_password}"', 'yb_password_key':'"_ybpw"'})
    write_text(amxx / 'configs/SND-LIST.CFG', f'SND_MAX; {settings["SoundQuota"]}\nSND_MAX_DUR; 180.0\n'
               f'SND_WARN; {max(1, settings["SoundQuota"]-3)}\nSND_JOIN;\nSND_EXIT;\n'
               f'SND_DELAY; {settings["SoundCooldown"]}\nSND_MODE; 15\nSND_OBEY_DUR; 7\n'
               'EXACT_MATCH; 1\nADMINS_ONLY; 0\nDISPLAY_KEYWORDS; 1\nFREEZE_TIME_CON; 0\n'+
               ''.join(f'{s}; sound/misc/{s}.wav\n' for s in CLASSIC_SOUNDS))
    write_text(server / 'ADMIN.local.txt', f'''Private administrator instructions. Do not publish.
Administrator Steam ID: {settings['AdminSteamID']}
AMXX: sign into this Steam account, connect, then enter amxmodmenu.
YaPB uses a separate login. Before connecting, enter:
setinfo _ybpw "{bot_password}"
After connecting: yb menu
RCON password: {rcon}
Panel changes may replace credentials; see its Administration tab.
''')


def finalize(server, settings, entries, native_base=True):
    game = server / 'cstrike'
    graphs = single_root(server / '_setup/graphs') / 'graph'
    capacities = []
    for bsp in sorted((game / 'maps').glob('*.bsp')):
        graph = game / 'addons/yapb/data/graph' / (bsp.stem + '.graph')
        if not graph.is_file():
            source = graphs / graph.name
            if not source.is_file():
                raise ValueError('Bot graph missing: ' + bsp.stem)
            shutil.copyfile(source, graph)
        capacities.append(dict(name=bsp.stem, maxPlayers=bsp_capacity(bsp)))
    write_text(game / 'mapcycle.txt', ''.join(f'{m["name"]} "\\minplayers\\0\\maxplayers\\{m["maxPlayers"]}"\n' for m in capacities))
    write_text(game / 'addons/amxmodx/configs/maps.ini', ''.join(f'{m["name"]} 0 {m["maxPlayers"]}\n' for m in capacities))
    write_text(server / '_setup/maps.json', json.dumps(capacities, indent=2)+'\n')
    (server / '_setup/tools').mkdir(exist_ok=True)
    for name in ('settings.py', 'install_common.py', 'project_version.py'):
        shutil.copyfile(ROOT / 'scripts' / name, server / '_setup/tools' / name)
    prepare_ranking(server)
    write_text(server / 'Start-CS16.sh', '#!/usr/bin/env bash\nset -euo pipefail\n'
               'cd -- "$(dirname -- "${BASH_SOURCE[0]}")"\n'
               'if [[ -e .install-incomplete ]]; then echo "Installation is incomplete." >&2; exit 1; fi\n'
               'if (( EUID == 0 )); then echo "Run as a regular user." >&2; exit 1; fi\n'
               'python3 _setup/tools/settings.py "$PWD"\n'
               'export LD_LIBRARY_PATH="$PWD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
               f'exec ./hlds_linux -game cstrike -port {settings["Port"]} +ip {settings["BindAddress"]} '
               '+sv_lan 0 +maxplayers 32 +map de_dust2 "$@"\n', 0o700)
    write_text(server / 'COMPONENTS-linux.json', json.dumps(dict(schemaVersion=1, packageVersion=VERSION, components=list(entries.values())), indent=2)+'\n')
    shutil.copyfile(ROOT / 'docs/THIRD-PARTY.md', server / 'THIRD-PARTY.md')
    (server / 'hlds_linux').chmod(0o755)
    # Steam's SDK uses this per-user location; preserve existing client installations.
    if sys.platform == 'linux' and native_base:
        sdk = Path.home() / '.steam/sdk32'
        sdk.mkdir(parents=True, exist_ok=True)
        client = sdk / 'steamclient.so'
        if not client.exists() and not client.is_symlink():
            client.symlink_to(server / 'steamclient.so')
    (server / '.install-incomplete').unlink()


def assemble(server, cache, settings, compiler=None, valve_installer=install_valve, native_base=True):
    if server.exists() or server.is_symlink():
        raise ValueError('Destination already exists. Choose a new directory.')
    entries = components()
    archives = {key:download(entry, cache) for key,entry in entries.items()}
    server.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_text(server / '.install-incomplete', 'Setup is incomplete. Do not start.\n')
    work = server / '_setup'
    work.mkdir(exist_ok=True)
    for key in ('steamcmd', 'rehlds', 'metamod', 'amxx', 'cstrike', 'bots', 'sounds', 'sank', 'mapmanager', 'graphs'):
        extract(archives[key], work / key)
    if sys.platform == 'linux':
        check_libraries(work / 'steamcmd', ['linux32/steamcmd'])
    valve_installer(server, work / 'steamcmd')
    shutil.copytree(work / 'rehlds/bin/linux32', server, dirs_exist_ok=True)
    for key in ('metamod', 'amxx', 'cstrike', 'bots'):
        shutil.copytree(work / key / 'addons', server / 'cstrike/addons', dirs_exist_ok=True)
    shutil.copytree(work / 'sounds/sound', server / 'cstrike/sound', dirs_exist_ok=True)
    required = ('hlds_linux', 'engine_i486.so', 'cstrike/dlls/cs.so',
                'cstrike/addons/metamod/metamod_i386.so',
                'cstrike/addons/amxmodx/dlls/amxmodx_mm_i386.so',
                'cstrike/addons/amxmodx/modules/csx_amxx_i386.so',
                'cstrike/addons/amxmodx/modules/cstrike_amxx_i386.so', 'cstrike/addons/yapb/bin/yapb.so')
    for relative in required:
        if (server / relative).read_bytes()[:5] != b'\x7fELF\x01':
            raise ValueError('Expected 32-bit Linux ELF: '+relative)
    if sys.platform == 'linux':
        native_paths = required if native_base else ()
        check_libraries(server, (*native_paths, 'cstrike/addons/amxmodx/scripting/amxxpc', 'cstrike/addons/amxmodx/scripting/amxxpc32.so'))
    compile_plugins(server, compiler)
    amxx = server / 'cstrike/addons/amxmodx'
    write_text(amxx / 'configs/plugins.ini', ''.join(name+'.amxx\n' for name in PLUGINS))
    write_text(server / 'cstrike/addons/metamod/plugins.ini', 'linux addons/amxmodx/dlls/amxmodx_mm_i386.so\nlinux addons/yapb/bin/yapb.so\n')
    liblist = server / 'cstrike/liblist.gam'
    text, count = re.subn(r'(?m)^gamedll_linux\s+"[^"]+"', 'gamedll_linux "addons/metamod/metamod_i386.so"', liblist.read_text(encoding='ascii'))
    if count != 1:
        raise ValueError('Expected one gamedll_linux entry.')
    write_text(liblist, text)
    configure(server, settings)
    install_content(server, cache)
    for key in ('graphLicense', 'graphCredits', 'graphReadme'):
        shutil.copyfile(archives[key], work / entries[key]['file'])
    finalize(server, settings, entries, native_base=native_base)


def preflight():
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('Run on x86-64 Linux Mint 22.x; Windows and ARM are not supported.')
    if os.geteuid() == 0:
        raise ValueError('Run setup as a regular user, without sudo.')
    release = dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    version = release.get('VERSION_ID','').strip('"')
    if release.get('ID','').strip('"') != 'linuxmint' or not (version == '22' or version.startswith('22.')):
        raise ValueError('This installer targets Linux Mint 22.x. See docs/INSTALL.md.')
    if not Path('/lib/ld-linux.so.2').exists() or not shutil.which('ldd'):
        raise ValueError('32-bit Linux support is missing. Install prerequisites:\n'+DEPENDENCIES)
    if not shutil.which('bash'):
        raise ValueError('Bash is required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='Counter-Strike-1.6-Steam-Server-Linux ' + VERSION)
    parser.add_argument('--destination', type=Path, default=ROOT / 'CS16Server-Linux')
    parser.add_argument('--cache-directory', type=Path, default=ROOT / 'downloads')
    parser.add_argument('--settings', type=Path, help='Private JSON; AdminSteamID is required, other values have defaults')
    parser.add_argument('--bind-address')
    parser.add_argument('--port', type=int)
    parser.add_argument('--check', action='store_true', help='Only check platform and prerequisites')
    args = parser.parse_args()
    preflight()
    if args.check:
        print('Mint 22.x x86-64 and 32-bit prerequisite check passed. No installation performed.')
        return
    os.umask(0o077)
    destination = args.destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination already exists. Choose a new directory.')
    ancestor = destination.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < 4 * 1024**3:
        raise ValueError('At least 4 GiB free space is required for setup and cached downloads.')
    settings = get_settings(args.settings, {k:v for k,v in dict(BindAddress=args.bind_address, Port=args.port).items() if v is not None})
    check_bind(settings['BindAddress'], settings['Port'])
    print('Installing a 32-slot public Steam server with these settings:\n'+json.dumps(settings, indent=2), flush=True)
    assemble(destination, args.cache_directory.expanduser().absolute(), settings)
    print(f'Installed: {destination}\nStart: bash "{destination / "Start-CS16.sh"}"\n'
          f'Local query: python3 scripts/server_query.py 127.0.0.1 --port {settings["Port"]}\n'
          'Internet access still requires router/firewall setup and an external-client test. See docs/INTERNET.md.\n'
          f'Private instructions: {destination / "ADMIN.local.txt"}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError, subprocess.SubprocessError) as error:
        print(f'Setup stopped: {error}', file=sys.stderr)
        sys.exit(1)
