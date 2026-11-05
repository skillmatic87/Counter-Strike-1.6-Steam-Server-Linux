import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock, patch
import socket

import server_panel as module


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        fixture={
            'cstrike/server.cfg':'hostname "Fixture"\nsv_lan 0\nrcon_password "private-rcon"\n',
            'Start-CS16.sh':'exec ./hlds_linux -game cstrike -port 27987 +ip 0.0.0.0 +sv_lan 0 +maxplayers 32 +map de_dust2 "$@"\n',
            'hlds_linux':'fixture',
            module.ADMIN_USERS:'; retained comment\n"STEAM_0:1:42" "" "bcdefu" "ce" ; retained rights\n"legacy" "old-password" "abc" "a"\n',
            module.ADMIN_FILES[1]:'yb_quota 0\nyb_password "private-bot"\nyb_password_key "_ybpw"\n',
            module.ADMIN_AMXX:'amx_password_field "_pw"\n',
            'settings.local.json':'{"AdminSteamID":"STEAM_0:1:42","RankScore":"KillsMinusDeaths"}\n',
            'ADMIN.local.txt':'Administrator Steam ID: STEAM_0:1:42\nsetinfo _ybpw "private-bot"\nRCON password: private-rcon\n',
        }
        for name,text in fixture.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        self.query=patch.object(module,'query_info',side_effect=TimeoutError);self.query.start()
        self.panel=module.Panel(self.root)
        self.http=module.PanelHTTPServer(('127.0.0.1',0),self.panel)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.http.server_port)

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.query.stop();self.temp.cleanup()

    def request(self,path,body=None,token=True,headers=None):
        values={'X-CS16-Token':self.panel.token} if token else {}
        if body is not None:values['Content-Type']='application/json'
        values.update(headers or {})
        request=urllib.request.Request(self.url+path, data=json.dumps(body).encode() if body is not None else None,headers=values)
        with urllib.request.urlopen(request,timeout=4) as reply:return reply.read()

    def payload(self):
        info=self.panel.admin_info()
        return dict(generation=info['generation'], revision=info['revision'],accounts=[dict(id=a['id'],name=a['name'],password='') for a in info['accounts']],rconPassword='',ybPassword='')

    def test_page_bootstrap_and_origin_guards(self):
        self.assertIn(b'window.CS16Panel=',self.request('/',token=False))
        for args in (dict(token=False),dict(headers={'Origin':'http://evil.example'})):
            with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/info',**args)
            self.assertEqual(error.exception.code,403)

    def test_admin_metadata_excludes_secrets_and_protects_legacy_rules(self):
        raw=self.request('/api/admin');info=json.loads(raw)
        self.assertEqual([a['name'] for a in info['accounts']],['STEAM_0:1:42'])
        self.assertEqual(info['protectedRules'],1)
        for value in (b'private-rcon',b'private-bot',b'old-password'):self.assertNotIn(value,raw)

    def test_admin_save_and_private_backup_restore(self):
        original={name:(self.root/name).read_bytes() for name in module.ADMIN_FILES}
        payload=self.payload();payload['accounts'][0]['name']='STEAM_0:0:99';payload.update(rconPassword='new-rcon',ybPassword='new-bot')
        result=self.panel.save_admin(payload)
        users=(self.root/module.ADMIN_USERS).read_text()
        self.assertIn('"STEAM_0:0:99" "" "bcdefu" "ce" ; retained rights',users)
        self.assertIn('"legacy" "old-password"',users)
        self.assertEqual(json.loads((self.root/'settings.local.json').read_text())['AdminSteamID'],'STEAM_0:0:99')
        note=(self.root/'ADMIN.local.txt').read_text();self.assertIn('new-rcon',note);self.assertIn('new-bot',note)
        with self.assertRaises(module.PanelError):self.panel.fs('read',result['backup']+'/files/'+module.ADMIN_USERS,self.panel.generation)
        self.panel.restore_admin(dict(generation=self.panel.generation,backup=result['backup']))
        for name,data in original.items():self.assertEqual((self.root/name).read_bytes(),data)

    def test_add_and_remove_steam_administrator(self):
        payload=self.payload();payload['accounts'].append(dict(id=None,name='STEAM_0:0:100',password=''))
        self.panel.save_admin(payload)
        self.assertEqual(len(self.panel.admin_info()['accounts']),2)
        payload=self.payload();payload['accounts'].pop(0);self.panel.save_admin(payload)
        self.assertEqual([a['name'] for a in self.panel.admin_info()['accounts']],['STEAM_0:0:100'])

    def test_admin_invalid_auth_and_stale_revision(self):
        for value in ('Alice','STEAM_0:1:42\nquit','STEAM_ID_PENDING'):
            payload=self.payload();payload['accounts'][0]['name']=value
            with self.assertRaises(module.PanelError):self.panel.save_admin(payload)
        payload=self.payload();payload['accounts'][0]['password']='not-steam-auth'
        with self.assertRaises(module.PanelError):self.panel.save_admin(payload)
        payload=self.payload();payload['accounts']=[]
        with self.assertRaises(module.PanelError):self.panel.save_admin(payload)
        payload=self.payload();(self.root/'settings.local.json').write_text('{}')
        with self.assertRaises(module.PanelError) as error:self.panel.save_admin(payload)
        self.assertEqual(error.exception.status,409)

    def test_file_boundary_and_lease(self):
        for name in ('../outside','cstrike/../../outside',module.ADMIN_USERS):
            with self.assertRaises(module.PanelError):self.panel.fs('read',name,self.panel.generation)
        generation=self.panel.generation
        lease=self.panel.begin_edit(generation)['lease']
        payload=base64.b64encode(b'hostname "Changed"\n').decode()
        with self.assertRaises(module.PanelError):self.panel.fs('write','cstrike/server.cfg',generation,payload,'wrong')
        self.panel.fs('write','cstrike/server.cfg',generation,payload,lease)
        self.panel.end_edit(lease)
        self.assertIn('Changed',(self.root/'cstrike/server.cfg').read_text())

    def test_linux_arguments_and_wildcard_endpoint(self):
        command=self.panel.arguments();self.assertEqual(command[0],str(self.root/'hlds_linux'))
        self.assertNotIn('$@',command);self.assertEqual(self.panel.endpoint(),('127.0.0.1',27987))

    def test_incomplete_installation_rejected(self):
        (self.root/'.install-incomplete').touch()
        with self.assertRaises(module.PanelError):module.Panel(self.root)

    def test_running_server_cannot_be_edited(self):
        with patch.object(module,'query_info',return_value=dict(name='Running',map='de_dust2',players=1,maxPlayers=32)):
            with self.assertRaises(module.PanelError):self.panel.save_admin(self.payload())
            with self.assertRaises(module.PanelError):self.panel.fs('write','cstrike/server.cfg',self.panel.generation,'')

    def test_start_prepares_ranking_and_starts_linux_binary(self):
        process=Mock(pid=12345)
        with patch.object(module,'prepare_ranking') as prepare, patch.object(module,'check_bind') as bind, patch.object(module.subprocess,'Popen',return_value=process) as popen:
            result=self.panel.start()
            self.assertEqual(result['pid'],12345)
            prepare.assert_called_once_with(self.root)
            bind.assert_called_once_with('127.0.0.1',27987)
            self.assertEqual(popen.call_args.args[0][0],str(self.root/'hlds_linux'))
            self.assertEqual(popen.call_args.kwargs['cwd'],self.root)
        self.panel.process=None

    def test_stop_uses_goldsrc_challenge_and_quit(self):
        udp=Mock();udp.recv.side_effect=[b'\xff\xff\xff\xffchallenge rcon 12345\0',socket.timeout()]
        context=Mock();context.__enter__=Mock(return_value=udp);context.__exit__=Mock(return_value=False)
        with patch.object(self.panel,'status',side_effect=[{'running':True},{'running':False}]),patch.object(module.socket,'socket',return_value=context):
            self.assertEqual(self.panel.stop(),dict(stopped=True))
        self.assertEqual(udp.send.call_count,2)
        self.assertIn(b'rcon 12345 "private-rcon" quit',udp.send.call_args.args[0])


if __name__=='__main__':unittest.main()
