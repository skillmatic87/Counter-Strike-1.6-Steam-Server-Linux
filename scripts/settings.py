"""Shared installation validation and launch-time ranking selection."""
import ipaddress
import json
from pathlib import Path
import re
import socket

DEFAULTS = dict(ServerName='CS 1.6 Steam Server', MapMinutes=30, FriendlyFire=0,
                BotTarget=16, BotDifficulty=2, SoundCooldown=3, SoundQuota=100,
                RankBots=0, RankScore='KillsMinusDeaths', Port=27015,
                BindAddress='0.0.0.0')
RANGES = dict(MapMinutes=(6, 180), FriendlyFire=(0, 1), BotTarget=(0, 32),
              BotDifficulty=(0, 4), SoundCooldown=(0, 300), SoundQuota=(1, 1000),
              RankBots=(0, 1), Port=(1, 65535))


def validate_setting(name, value):
    if name == 'AdminSteamID':
        if not isinstance(value, str) or not re.fullmatch(r'STEAM_0:[01]:[0-9]{1,10}', value):
            raise ValueError('AdminSteamID: use the STEAM_0:X:Y identifier shown by status in the game console.')
        return value
    if name == 'ServerName':
        if not isinstance(value, str) or value != value.strip() or not re.fullmatch(r'[\x20-\x7e]{1,31}', value) or any(c in value for c in '";\\'):
            raise ValueError('ServerName: use 1-31 printable ASCII characters without quotes, semicolons or backslashes.')
        return value
    if name == 'RankScore':
        if value not in ('Kills', 'KillsMinusDeaths'):
            raise ValueError('RankScore: choose Kills or KillsMinusDeaths.')
        return value
    if name == 'BindAddress':
        try:
            address = ipaddress.IPv4Address(value)
        except (ValueError, TypeError):
            raise ValueError('BindAddress: use 0.0.0.0 or an assigned local IPv4 address.') from None
        if not address.is_unspecified and (address.is_loopback or address.is_multicast or address.is_reserved or address.is_link_local):
            raise ValueError('BindAddress must allow Internet clients; use 0.0.0.0 or an assigned LAN IPv4.')
        return str(address)
    if name not in RANGES:
        raise ValueError('Unknown setting: ' + name)
    low, high = RANGES[name]
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)) or not low <= int(value) <= high:
        raise ValueError(f'{name}: enter an integer from {low} to {high}.')
    return int(value)


def get_settings(path=None, overrides=None):
    prompts = dict(ServerName='Server name', AdminSteamID='Administrator Steam ID (STEAM_0:X:Y)',
                   Port='UDP game port', BindAddress='Local bind address', MapMinutes='Map duration in minutes',
                   FriendlyFire='Friendly Fire (yes/no)', BotTarget='Fill with bots to this total player count (0 disables bots)',
                   BotDifficulty='Bot difficulty (0 new, 1 easy, 2 medium, 3 hard, 4 expert)',
                   SoundCooldown='Seconds between chat sounds', SoundQuota='Sound triggers per player per map',
                   RankBots='Include bots in ranking (yes/no)', RankScore='Ranking score (Kills or KillsMinusDeaths)')
    supplied = json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else {}
    if not isinstance(supplied, dict):
        raise ValueError('Settings JSON must be an object.')
    if set(supplied) - set(prompts):
        raise ValueError('Unknown JSON setting(s): ' + ', '.join(sorted(set(supplied) - set(prompts))))
    supplied.update(overrides or {})
    result = {}
    for name, prompt in prompts.items():
        if path:
            result[name] = validate_setting(name, supplied.get(name, DEFAULTS.get(name)))
            continue
        while True:
            default = supplied.get(name, DEFAULTS.get(name))
            shown = ('yes' if default else 'no') if name in ('FriendlyFire', 'RankBots') else default
            value = input(prompt + (f' [{shown}]' if shown is not None else '') + ': ').strip()
            if not value and default is not None:
                value = default
            elif name in ('FriendlyFire', 'RankBots'):
                value = {'yes': 1, 'y': 1, 'no': 0, 'n': 0}.get(str(value).lower(), value)
            try:
                result[name] = validate_setting(name, value)
                break
            except ValueError as error:
                print(error)
    return result


def check_bind(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.bind((address, port))


def prepare_ranking(root):
    """Derive the scoring bytecode from the reviewed JSON before starting HLDS."""
    root = Path(root)
    settings = json.loads((root / 'settings.local.json').read_text(encoding='utf-8-sig'))
    score = validate_setting('RankScore', settings.get('RankScore'))
    source = root / '_setup/ranking' / (score + '.amxx')
    if source.is_symlink() or not source.is_file() or source.stat().st_size < 8:
        raise ValueError('Compiled ranking is missing; installation is incomplete.')
    target = root / 'cstrike/addons/amxmodx/data/csstats.amxx'
    if target.is_symlink() or target.parent.resolve() != (root.resolve() / 'cstrike/addons/amxmodx/data'):
        raise ValueError('Linked ranking paths are not supported.')
    data = source.read_bytes()
    if not target.exists() or target.read_bytes() != data:
        from install_common import atomic_write
        atomic_write(target, data)


if __name__ == '__main__':
    import sys
    prepare_ranking(sys.argv[1])
