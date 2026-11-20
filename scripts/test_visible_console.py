"""Verify the panel opens an independent interactive server terminal."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import server_panel as panel


class VisibleConsoleTests(unittest.TestCase):
    def test_named_terminal_wraps_recorded_engine_without_exposing_libraries_to_gtk(self):
        with tempfile.TemporaryDirectory(prefix='CS16 server with spaces ') as temporary:
            root=Path(temporary);log=panel.new_log_file(root);engine=[str(root/'hlds_linux'),'-game','cstrike']
            with patch('shutil.which',side_effect=lambda name:'/usr/bin/'+name),patch.dict(panel.os.environ,{'DISPLAY':':0','LD_LIBRARY_PATH':'legacy-only'}),patch.object(panel.subprocess,'Popen',return_value=Mock()) as popen:
                panel.start_linux_console(engine,root,log)
            command=popen.call_args.args[0]
            self.assertIn('--window',command);self.assertIn('--wait',command)
            self.assertTrue(any(value.startswith('--title=Counter-Strike 1.6 Steam Server | ') and 'UDP ' in value for value in command))
            self.assertIn('--require-terminal',command);self.assertEqual(command[-3:],engine)
            self.assertNotIn('LD_LIBRARY_PATH',popen.call_args.kwargs['env'])
    def test_missing_desktop_rejected_instead_of_silent_background_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch('shutil.which',return_value='/usr/bin/gnome-terminal'),patch.dict(panel.os.environ,{},clear=True),patch.object(panel.subprocess,'Popen') as popen:
                with self.assertRaises(panel.PanelError):panel.start_linux_console(['fixture'],root,root/'log')
                popen.assert_not_called()


if __name__=='__main__':unittest.main()
