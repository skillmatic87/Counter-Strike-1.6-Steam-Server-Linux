"""Cross-platform migration, address and launch-contract regression tests."""
from pathlib import Path
import contextlib,hashlib,json,os,subprocess,sys,tempfile,threading,unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import migrate_package as migration
import package_guard as guard
import server_addresses

def digest(value):return hashlib.sha256(value).hexdigest()

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Package migration with spaces ');self.root=Path(self.temp.name)
        self.source=self.root/'new';self.target=self.root/'old';self.source.mkdir();self.target.mkdir()
        self.old=b'old launcher with custom old-release content\r\n';self.new=b'new canonical launcher\n'
        (self.source/'start-server.sh').write_bytes(self.new);(self.target/'Start-Server.sh').write_bytes(self.old)
        self.manifest={'schema':1,'package':'fixture','files':[dict(path='start-server.sh',sha256=digest(self.new),previous=[dict(path='Start-Server.sh',sha256=digest(self.old))])]}
        (self.target/'settings.local.json').write_bytes(b'private sentinel')
    def tearDown(self):self.temp.cleanup()
    def test_case_spelling_content_preservation_and_idempotence(self):
        result=migration.apply(self.source,self.target,self.manifest)
        self.assertEqual(result['changed'],1)
        self.assertIn('start-server.sh',{p.name for p in self.target.iterdir()})
        self.assertNotIn('Start-Server.sh',{p.name for p in self.target.iterdir()})
        self.assertEqual((self.target/'start-server.sh').read_bytes(),self.new)
        self.assertEqual((self.target/'settings.local.json').read_bytes(),b'private sentinel')
        self.assertEqual((self.target/result['backup']/'0').read_bytes(),self.old)
        self.assertEqual(migration.apply(self.source,self.target,self.manifest)['changed'],0)
    def test_conflict_preflight_changes_no_files(self):
        (self.target/'Start-Server.sh').write_bytes(b'operator changed this launcher')
        with self.assertRaisesRegex(ValueError,'Locally modified'):migration.apply(self.source,self.target,self.manifest)
        self.assertFalse((self.target/migration.JOURNAL).exists());self.assertFalse((self.target/'.package-migration-backups').exists())
    def test_interruption_recovers_exact_original_spelling_and_bytes(self):
        with self.assertRaisesRegex(RuntimeError,'Injected'):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        self.assertTrue(migration.recover(self.target,self.manifest,self.source))
        self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old)
        self.assertNotIn('start-server.sh',{p.name for p in self.target.iterdir()})
        self.assertFalse((self.target/migration.JOURNAL).exists())
    def test_corrupt_backup_prevents_any_recovery_write(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        transaction=json.loads((self.target/migration.JOURNAL).read_text());(self.target/transaction['backup']/'0').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'):migration.recover(self.target,self.manifest,self.source)
        self.assertTrue((self.target/migration.JOURNAL).exists());self.assertFalse((self.target/'Start-Server.sh').exists())
    def test_manual_edits_after_interruption_are_not_overwritten(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        (self.target/'start-server.sh').write_bytes(b'later manual edit')
        with self.assertRaisesRegex(ValueError,'changed after interruption'):migration.recover(self.target,self.manifest,self.source)
        self.assertEqual((self.target/'start-server.sh').read_bytes(),b'later manual edit')
    def test_unmanaged_journal_path_cannot_restore_private_settings(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        path=self.target/migration.JOURNAL;value=json.loads(path.read_text());value['operations'][0]['path']='settings.local.json';path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'Unmanaged'):migration.recover(self.target,self.manifest,self.source)
        self.assertEqual((self.target/'settings.local.json').read_bytes(),b'private sentinel')
    def test_symlink_is_rejected_without_changing_referent(self):
        (self.target/'Start-Server.sh').unlink();other=self.root/'keep';other.write_bytes(self.old)
        try:(self.target/'Start-Server.sh').symlink_to(other)
        except OSError:self.skipTest('Host does not permit symlinks')
        with self.assertRaisesRegex(ValueError,'Linked'):migration.apply(self.source,self.target,self.manifest)
        self.assertEqual(other.read_bytes(),self.old)
    @unittest.skipIf(os.name=='nt','Two case-distinct names require a case-sensitive filesystem')
    def test_case_distinct_hardlinks_are_both_retired_and_backed_up(self):
        os.link(self.target/'Start-Server.sh',self.target/'start-server.sh')
        result=migration.apply(self.source,self.target,self.manifest)
        self.assertEqual((self.target/result['backup']/'0').read_bytes(),self.old)
        self.assertEqual((self.target/result['backup']/'1').read_bytes(),self.old)
        self.assertNotIn('Start-Server.sh',{p.name for p in self.target.iterdir()})
    def test_pending_zip_update_refuses_new_migration(self):
        (self.target/'.update-active.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'ZIP updater'):migration.apply(self.source,self.target,self.manifest)
        self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old)
    def test_partial_staging_file_recovery_is_retryable(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        (self.target/'.start-server.sh.migration-write').write_bytes(self.new[:4])
        original=migration.atomic
        with patch.object(migration,'atomic',side_effect=OSError('injected recovery failure')):
            with self.assertRaises(OSError):migration.recover(self.target,self.manifest,self.source)
        self.assertTrue((self.target/migration.JOURNAL).exists())
        self.assertTrue(migration.recover(self.target,self.manifest,self.source))
        self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old)
    def test_partial_old_spelling_staging_from_interrupted_recovery_is_removed(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        (self.target/'.Start-Server.sh.migration-write').write_bytes(self.old[:5])
        self.assertTrue(migration.recover(self.target,self.manifest,self.source))
        self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old)
        self.assertFalse((self.target/'.Start-Server.sh.migration-write').exists())
    def test_forged_expected_hash_cannot_authorize_deleting_a_manual_edit(self):
        with self.assertRaises(RuntimeError):migration.apply(self.source,self.target,self.manifest,fail_after=0)
        path=self.target/migration.JOURNAL;value=json.loads(path.read_text())
        (self.target/'start-server.sh').write_bytes(b'manual edit')
        value['operations'][0]['sha256']=digest(b'manual edit');path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):migration.recover(self.target,self.manifest,self.source)
        self.assertEqual((self.target/'start-server.sh').read_bytes(),b'manual edit')
    def test_linked_backup_parent_is_refused_before_removing_a_launcher(self):
        other=self.root/'outside';other.mkdir()
        try:(self.target/'.package-migration-backups').symlink_to(other,target_is_directory=True)
        except OSError:self.skipTest('Host does not permit directory symlinks')
        with self.assertRaisesRegex(ValueError,'backup directory'):migration.apply(self.source,self.target,self.manifest)
        self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old)
        self.assertEqual(list(other.iterdir()),[])
    @unittest.skipUnless(os.name=='nt','Windows junction/reparse test')
    def test_windows_backup_junction_is_refused_before_any_external_write(self):
        other=self.root/'external directory';other.mkdir();link=self.target/'.package-migration-backups'
        result=subprocess.run(['cmd.exe','/c','mklink','/J',str(link),str(other)],capture_output=True)
        if result.returncode:self.skipTest('Host does not permit creating directory junctions')
        try:
            with self.assertRaisesRegex(ValueError,'backup directory'):migration.apply(self.source,self.target,self.manifest)
            self.assertEqual((self.target/'Start-Server.sh').read_bytes(),self.old);self.assertEqual(list(other.iterdir()),[])
        finally:os.rmdir(link)

    def test_known_manifest_upgrade_recovery_and_unknown_manifest_refusal(self):
        path=self.source/'package-files.json'
        path.write_text(json.dumps(self.manifest)+'\n',encoding='utf-8')
        old_manifest=path.read_bytes()
        migration.apply(self.source,self.target,migration.load_source(self.source))
        second=b'second release launcher\n';(self.source/'start-server.sh').write_bytes(second)
        manifest=dict(schema=1,package='fixture',version='B',previous_manifests=[dict(path='package-files.json',sha256=digest(old_manifest))],files=[dict(path='start-server.sh',sha256=digest(second),previous=[dict(path='start-server.sh',sha256=digest(self.new))])])
        path.write_text(json.dumps(manifest)+'\n',encoding='utf-8');loaded=migration.load_source(self.source)
        with self.assertRaisesRegex(RuntimeError,'Injected'):migration.apply(self.source,self.target,loaded,fail_after=1)
        self.assertTrue(migration.recover(self.target,loaded,self.source))
        self.assertEqual((self.target/'package-files.json').read_bytes(),old_manifest)
        self.assertEqual((self.target/'start-server.sh').read_bytes(),self.new)
        migration.apply(self.source,self.target,loaded)
        self.assertEqual(migration.apply(self.source,self.target,loaded)['changed'],0)
        (self.target/'package-files.json').write_bytes(b'unknown operator manifest')
        with self.assertRaisesRegex(ValueError,'Locally modified'):migration.apply(self.source,self.target,loaded)
        self.assertEqual((self.target/'package-files.json').read_bytes(),b'unknown operator manifest')
    def test_manifest_history_and_self_entry_are_validated(self):
        for history in ({},[dict(path='settings.local.json',sha256='a'*64)],[dict(path='package-files.json',sha256='invalid')]):
            with self.subTest(history=history):
                value=dict(self.manifest,previous_manifests=history)
                (self.source/'package-files.json').write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'manifest history'):migration.load_source(self.source)
        value=dict(self.manifest,files=[dict(path='package-files.json',sha256='a'*64)])
        (self.source/'package-files.json').write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'self-entry'):migration.load_source(self.source)

class ContractTests(unittest.TestCase):
    def test_failed_start_keeps_lifetime_lock_for_a_still_live_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            class Owner:
                lock=threading.RLock();process=Mock()
                @guard.managed_start(temporary)
                def start(self):self.process.poll.return_value=None;raise RuntimeError('post-spawn failure')
                @guard.managed_poll
                def status(self):return self.process.poll() is None
            owner=Owner()
            with self.assertRaisesRegex(RuntimeError,'post-spawn'):owner.start()
            with self.assertRaises(RuntimeError):guard.claim(temporary)
            owner.process.poll.return_value=0;owner.status();guard.claim(temporary).close()
    def test_process_lifetime_lock_blocks_migration_until_child_ends(self):
        with tempfile.TemporaryDirectory() as temporary:
            class Owner:
                lock=threading.RLock();process=Mock()
                @guard.managed_start(temporary)
                def start(self):self.process.poll.return_value=None
                @guard.managed_poll
                def status(self):return self.process.poll() is None
            owner=Owner();owner.start()
            with self.assertRaisesRegex(RuntimeError,'busy'):guard.claim(temporary)
            owner.process.poll.return_value=0;self.assertFalse(owner.status())
            guard.claim(temporary).close()
    def test_game_addresses_filter_bind_loopback_and_inactive_interfaces(self):
        raw=[{'flags':['UP'],'addr_info':[{'family':'inet','local':x} for x in ('192.168.1.2','10.1.0.2','127.0.0.1','169.254.1.2','0.0.0.0')]},{'flags':[],'addr_info':[{'family':'inet','local':'10.2.0.2'}]}]
        with patch.object(server_addresses.sys,'platform','linux'),patch.object(server_addresses.subprocess,'run',return_value=Mock(stdout=json.dumps(raw))):
            rows=server_addresses.endpoints(27019);self.assertEqual(len(rows),2)
            self.assertEqual(server_addresses.endpoints(27019,'192.168.1.2'),[dict(address='192.168.1.2',port=27019,connect='connect 192.168.1.2:27019')])
            self.assertEqual(server_addresses.endpoints(27019,'127.0.0.1'),[])
    def test_windows_address_records_and_missing_network(self):
        with patch.object(server_addresses.sys,'platform','win32'),patch.object(server_addresses.subprocess,'run',return_value=Mock(stdout='[{"IPAddress":"192.168.1.3"}]')):
            self.assertEqual(server_addresses.endpoints(27015)[0]['connect'],'connect 192.168.1.3:27015')
        with patch.object(server_addresses.subprocess,'run',side_effect=FileNotFoundError()):self.assertEqual(server_addresses.endpoints(27015),[])

if __name__=='__main__':unittest.main(verbosity=2)
