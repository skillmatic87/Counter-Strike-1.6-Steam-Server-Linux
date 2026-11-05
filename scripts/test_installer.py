import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import install_cs16_linux as installer
import install_common as common
from settings import DEFAULTS, validate_setting, get_settings, prepare_ranking


class InstallerTests(unittest.TestCase):
    def test_package_version_cli_and_metadata(self):
        import sys
        from project_version import VERSION
        self.assertEqual((installer.ROOT/'VERSION').read_text().strip(),VERSION)
        run=subprocess.run([sys.executable,str(installer.ROOT/'scripts/install_cs16_linux.py'),'--version'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0)
        self.assertIn(VERSION,run.stdout)
        self.assertIn('## '+VERSION,(installer.ROOT/'CHANGELOG.md').read_text(encoding='utf-8'))
    def test_steam_ids_are_authentication_ids(self):
        for bad in ('Alice', 'STEAM_ID_PENDING', 'BOT', 'STEAM_1:1:42', 'STEAM_0:2:1', 'STEAM_0:1:4\nquit', '76561198000000000', None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                validate_setting('AdminSteamID', bad)
        self.assertEqual(validate_setting('AdminSteamID', 'STEAM_0:1:123456'), 'STEAM_0:1:123456')

    def test_injection_and_ranges(self):
        for bad in ('', ' x', 'x";quit', 'x\nquit', 'x\\cfg', 'x'*32):
            with self.assertRaises(ValueError): validate_setting('ServerName', bad)
        for key,(low,high) in __import__('settings').RANGES.items():
            for bad in (low-1, high+1, True, 1.5, None):
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError): validate_setting(key,bad)

    def test_settings_defaults_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text(json.dumps({'AdminSteamID':'STEAM_0:1:42'}))
            self.assertEqual(get_settings(path), dict(DEFAULTS, AdminSteamID='STEAM_0:1:42'))
            path.write_text('{"AdminName":"old name"}')
            with self.assertRaises(ValueError): get_settings(path)

    def test_bind_validation(self):
        for bad in ('127.0.0.1', '224.0.0.1', '::1', 'example.com', '169.254.0.1'):
            with self.assertRaises(ValueError): validate_setting('BindAddress', bad)
        self.assertEqual(validate_setting('BindAddress','0.0.0.0'),'0.0.0.0')

    def test_archive_traversal_and_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('../escape', '/absolute', 'C:/escape', 'a/../../escape', 'a\\..\\..\\escape'):
                with self.assertRaises(ValueError): common.safe_path(root,name)
            archive = root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z: z.writestr('../escape','bad')
            with self.assertRaises(ValueError): common.extract(archive,root/'out')
            with zipfile.ZipFile(archive,'w') as z:
                link=zipfile.ZipInfo('link');link.external_attr=0o120777<<16;z.writestr(link,'outside')
            with self.assertRaises(ValueError): common.extract(archive,root/'out')

    def test_corrupt_cached_download_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'archive.zip').write_bytes(b'keep')
            with patch.object(common.urllib.request,'urlopen') as network:
                with self.assertRaises(ValueError): common.download(dict(file='archive.zip',sha256='0'*64,url='https://example.com'),root)
                network.assert_not_called()
            self.assertEqual((root/'archive.zip').read_bytes(),b'keep')

    def test_existing_destination_never_downloads(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(installer,'download') as download:
            root=Path(temp);(root/'sentinel').write_bytes(b'keep')
            with self.assertRaises(ValueError): installer.assemble(root,root,dict(DEFAULTS))
            download.assert_not_called()
            self.assertEqual((root/'sentinel').read_bytes(),b'keep')

    def test_three_steamcmd_attempts_and_logging(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'_setup').mkdir()
            with patch.object(installer.subprocess,'run',return_value=subprocess.CompletedProcess([],1)) as run:
                with self.assertRaisesRegex(ValueError,'three attempts'): installer.install_valve(root,root/'steamcmd')
                self.assertEqual(run.call_count,3)
                command=run.call_args.args[0]
                self.assertIn('anonymous',command);self.assertIn('steam_legacy',command)
                self.assertLess(command.index('+force_install_dir'),command.index('+login'))
            self.assertEqual(len(list((root/'_setup').glob('steamcmd-attempt-*.log'))),3)

    def test_missing_linux_library_is_fatal(self):
        with patch.object(installer.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'libc.so => not found','')):
            with self.assertRaisesRegex(ValueError,'32-bit'): installer.check_libraries(Path('/tmp'),['test.so'])

    def test_component_manifest_and_local_content_integrity(self):
        entries=installer.components()
        self.assertEqual(entries['rehlds']['version'],'3.15.0.896')
        self.assertNotIn('statsme',entries)
        self.assertIn('cstrike',entries)
        for entry in entries.values():
            self.assertRegex(entry['sha256'],r'^[0-9a-f]{64}$');self.assertTrue(entry['url'].startswith('https://'))
        manifest=common.read_json(installer.ROOT/'content/pack.json')
        for entry in manifest['localFiles']:
            self.assertEqual(hashlib.sha256((installer.ROOT/'content'/entry['source']).read_bytes()).hexdigest(),entry['sha256'])

    def test_preflight_rejects_wrong_os_and_root(self):
        with patch.object(installer.sys,'platform','win32'):
            with self.assertRaisesRegex(ValueError,'Linux Mint'): installer.preflight()
        with patch.object(installer.sys,'platform','linux'), patch.object(installer.platform,'machine',return_value='x86_64'), patch.object(installer.os,'geteuid',return_value=0,create=True):
            with self.assertRaisesRegex(ValueError,'regular user'): installer.preflight()

    def test_preflight_accepts_mint_22_and_point_releases(self):
        for version in ('22','22.1','22.3'):
            with patch.object(installer.sys,'platform','linux'), patch.object(installer.platform,'machine',return_value='x86_64'), patch.object(installer.os,'geteuid',return_value=1000,create=True), patch.object(installer.Path,'read_text',return_value=f'ID=linuxmint\nVERSION_ID="{version}"\n'), patch.object(installer.Path,'exists',return_value=True), patch.object(installer.shutil,'which',return_value='/bin/fixture'):
                installer.preflight()


if __name__=='__main__': unittest.main()
