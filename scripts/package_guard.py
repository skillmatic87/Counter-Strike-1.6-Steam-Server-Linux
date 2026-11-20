"""Coordinate updated launchers and explicit offline package migration."""
import functools,json,os
from pathlib import Path
import subprocess,sys

def claim(root):
    root=Path(root);path=root/'.package-operation.lock'
    if path.is_symlink():raise RuntimeError('Package lock must not be a symbolic link')
    stream=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            stream.seek(0);stream.write(b'0');stream.flush();stream.seek(0)
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        stream.close();raise RuntimeError('This package is busy. Stop its server/panel before migration or another start.')
    return stream

def state_lock(owner):return getattr(owner,'guard',None) or owner.lock

def release_if_stopped(owner):
    process=getattr(owner,'process',None)
    if process is None or process.poll() is not None:
        stream=getattr(owner,'_package_operation',None)
        if stream is not None:stream.close();owner._package_operation=None

def managed_start(root):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(owner,*args,**kwargs):
            with state_lock(owner):
                release_if_stopped(owner)
                if getattr(owner,'_package_operation',None) is not None:raise RuntimeError('Server already running')
                stream=claim(root() if callable(root) else root)
                try:result=function(owner,*args,**kwargs)
                except BaseException:
                    process=getattr(owner,'process',None)
                    if process is not None and process.poll() is None:owner._package_operation=stream
                    else:stream.close()
                    raise
                owner._package_operation=stream
                return result
        return wrapped
    return decorate

def managed_poll(function):
    @functools.wraps(function)
    def wrapped(owner,*args,**kwargs):
        with state_lock(owner):
            try:return function(owner,*args,**kwargs)
            finally:release_if_stopped(owner)
    return wrapped

def exclusive_command(root):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            with claim(root() if callable(root) else root):return function(*args,**kwargs)
        return wrapped
    return decorate

def refuse_legacy_processes(root):
    """Supplement the shared lock for pre-upgrade launchers; no secret arguments printed."""
    root=Path(root).resolve()
    if sys.platform=='linux':
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal() or int(entry.name)==os.getpid():continue
            try:
                comm=(entry/'comm').read_text().strip()
                arguments=(entry/'cmdline').read_bytes().split(b'\0')
                cwd=(entry/'cwd').resolve()
                panel=any(str(root/'scripts'/name).encode() in arguments for name in ('panel.py','server_panel.py','control.py'))
                engine=comm.casefold().startswith(('hlds','svends','wineconsole')) and cwd.is_relative_to(root)
                if panel or engine:raise RuntimeError('A legacy panel/server is active. Stop it before package migration.')
            except (PermissionError,FileNotFoundError,ProcessLookupError):continue
    elif os.name=='nt':
        script="$root="+"'"+str(root).replace("'","''")+"'"+"; @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne "+str(os.getpid())+" -and (($_.Name -match '^hlds|^svends') -and $_.ExecutablePath -like ($root+'\\*') -or ($_.Name -match '^python' -and $_.CommandLine -like ('*'+$root+'*') -and $_.CommandLine -match 'server_panel.py|panel.py|control.py')) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
        import base64
        result=subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],capture_output=True,text=True,check=True,timeout=15)
        if json.loads(result.stdout or '[]'):raise RuntimeError('A legacy panel/server is active. Stop it before package migration.')

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args();command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:parser.error('A server command is required')
    stream=claim(args.root)
    if os.name!='nt':
        os.set_inheritable(stream.fileno(),True)
        os.execvpe(command[0],command,os.environ)
    else:
        try:return subprocess.call(command)
        finally:stream.close()

if __name__=='__main__':sys.exit(main() or 0)
