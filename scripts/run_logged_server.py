#!/usr/bin/env python3
"""Interactive Linux console recorder shared by the panel and all launchers."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

ACTIVE = 'CS16_RECORDING_ACTIVE'
COMMAND = 'CS16_RECORDED_COMMAND'
CONTROL = 'CS16_RECORDER_CONTROL'
MARKER = '# cs16-console-recording-v1'


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def private_directory(path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f'Console directory is not a regular directory: {path}')
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)


def new_log_file(server):
    directory = server / 'logs'
    private_directory(directory)
    directory = directory / 'console'
    private_directory(directory)
    name = datetime.now(timezone.utc).strftime('cs16-console-%Y%m%d-%H%M%S-') + secrets.token_hex(4) + '.log'
    path = directory / name
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    return path


def append_record(log, message):
    if log.is_symlink() or not log.is_file():
        raise ValueError(f'Console log is not a regular file: {log}')
    descriptor = os.open(log, os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'ab') as output:
        output.write(message.encode('utf-8'))
        output.flush()
        os.fsync(output.fileno())


def replace_file(path, data, mode):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f'Recording helper destination is not a regular file: {path}')
    descriptor, temporary = tempfile.mkstemp(prefix='.cs16-recorder-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recording_preamble():
    return (MARKER + '\n'
        'if [[ "${CS16_RECORDING_ACTIVE:-}" != 1 ]]; then\n'
        '    exec python3 "$PWD/run_logged_server.py" '
        '--server "$PWD" -- bash "$PWD/${BASH_SOURCE[0]##*/}" "$@"\n'
        'fi\n')


def ensure_launcher_logging(server, launcher):
    """Back up and upgrade only the launcher/helper, never game configuration."""
    if launcher.parent != server or launcher.is_symlink() or not launcher.is_file():
        raise ValueError('The installed launcher must be a regular file inside the server folder.')
    original = launcher.read_bytes()
    text = original.decode('utf-8-sig')
    if len(re.findall(r'^\s*exec\s+\./hlds_linux\s+.*$', text, re.M)) != 1:
        raise ValueError('The installed launcher needs exactly one supported exec ./hlds_linux line.')
    # Insert before the legacy library export: Python must not load server libraries.
    insertion = re.search(r'^export LD_LIBRARY_PATH=.*$|^\s*exec\s+\./hlds_linux\s+.*$', text, re.M)
    if MARKER not in text:
        text = text[:insertion.start()] + recording_preamble() + text[insertion.start():]
    helper = server / 'run_logged_server.py'
    if helper.is_symlink() or (helper.exists() and not helper.is_file()):
        raise ValueError('The installed recording helper must be a regular file.')
    source = Path(__file__).read_bytes()
    updated = text.encode('utf-8')
    changes = [(launcher, updated, original, stat.S_IMODE(launcher.stat().st_mode))]
    old_helper = helper.read_bytes() if helper.exists() else None
    changes.append((helper, source, old_helper, 0o700))
    changes = [item for item in changes if item[1] != item[2]]
    if not changes:
        return
    directory = server / '_configurator'
    private_directory(directory)
    directory = directory / 'recording-backups'
    private_directory(directory)
    backup = directory / (datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(4))
    private_directory(backup)
    for target, data, old, mode in changes:
        if old is not None:
            replace_file(backup / target.name, old, mode)
    # Install the helper first. A killed migration leaves either the old launcher
    # or a launcher whose helper is already present; repeating this is safe.
    changes.sort(key=lambda item: item[0] == launcher)
    applied = []
    try:
        for target, data, old, mode in changes:
            replace_file(target, data, mode)
            applied.append((target, old, mode))
    except BaseException:
        for target, old, mode in reversed(applied):
            if old is None:
                target.unlink(missing_ok=True)
            else:
                replace_file(target, old, mode)
        raise


def show(message):
    # The outer terminal can disappear before the final status is printed.
    try:
        print(message, flush=True)
    except OSError:
        pass


def validate_terminal(log):
    try:
        if not os.isatty(0) or not os.isatty(1):
            raise ValueError('Open the server from a visible interactive terminal.')
        descriptor = os.open('/dev/tty', os.O_RDWR | getattr(os, 'O_NOCTTY', 0))
        try:
            if os.tcgetpgrp(descriptor) != os.getpgrp():
                raise ValueError('The server must run in the foreground of its terminal.')
        finally:
            os.close(descriptor)
    except (OSError, ValueError) as error:
        message = f'An interactive controlling terminal is required: {error}'
        append_record(log, f'\nCS16_SESSION_START time={stamp()}\nCS16_RECORDER_ERROR {message}\n'
                      f'CS16_SESSION_END time={stamp()} exit_code=1\n')
        raise ValueError(message) from error


def protect_child_parent(control):
    """Bind the exec'd server to its exact script parent, including startup races."""
    deadline = time.monotonic() + 5
    expected = None
    while time.monotonic() < deadline:
        descriptor = os.open(control, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as source:
            record = source.read(64)
        if record:
            if not re.fullmatch(rb'[1-9][0-9]*\n', record):
                raise ValueError('Invalid recorder parent identity.')
            expected = int(record)
            break
        time.sleep(0.01)
    if expected is None:
        raise ValueError('Timed out waiting for the recorder parent identity.')
    if sys.platform != 'linux':
        raise ValueError('The server parent-death protection requires Linux.')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    if os.getppid() != expected:
        raise ValueError('The recorder parent exited before the server could start.')
    Path(control).unlink()


def run_recorded(server, command, log=None):
    recorder = shutil.which('script')
    if not recorder:
        raise ValueError('Console recording requires util-linux: sudo apt install util-linux')
    if not command:
        raise ValueError('No server command supplied.')
    log = log or new_log_file(server)
    if log.parent != server / 'logs' / 'console' or log.is_symlink() or not log.is_file():
        raise ValueError('The console log must be a regular file in this server\'s logs/console folder.')
    append_record(log, f'\nCS16_SESSION_START time={stamp()}\n')
    show(f'Console recording: {log}')
    environment = os.environ.copy()
    environment['SHELL'] = '/bin/sh'
    environment[COMMAND] = json.dumps(command)
    control_fd, control_name = tempfile.mkstemp(prefix='.recorder-parent-', dir=log.parent)
    environment[CONTROL] = control_name
    # Keep arguments out of script's COMMAND header (they can contain passwords).
    child = 'exec ' + shlex.join([sys.executable, str(Path(__file__).resolve()), '--child'])
    arguments = [recorder, '-q', '-f', '-e', '-a', '-c', child, str(log)]
    received = []
    previous = {}
    process = None
    reaped = False
    deadline = None
    def recorder_signal(number):
        # util-linux 2.39's PTY loop blocks SIGHUP without consuming it.
        # Translate a lost outer terminal into its supported termination path.
        return signal.SIGTERM if number == getattr(signal, 'SIGHUP', None) else number
    def forward(number, frame):
        nonlocal deadline
        received.append(number)
        if deadline is None:
            deadline = time.monotonic() + 5
        if process is not None and process.poll() is None:
            process.send_signal(recorder_signal(number))
    try:
        for number in (signal.SIGTERM, signal.SIGINT, getattr(signal, 'SIGHUP', signal.SIGTERM)):
            if number not in previous:
                previous[number] = signal.signal(number, forward)
        # Inherit the visible terminal. No PIPEs or separate process group here.
        process = subprocess.Popen(arguments, cwd=server, env=environment)
        with os.fdopen(control_fd, 'wb') as identity:
            control_fd = None
            identity.write((str(process.pid) + '\n').encode('ascii'))
            identity.flush()
            os.fsync(identity.fileno())
        if received and process.poll() is None:
            process.send_signal(recorder_signal(received[-1]))
        while True:
            try:
                code = process.wait(timeout=0.25)
                reaped = True
                break
            except subprocess.TimeoutExpired:
                if deadline is not None and time.monotonic() >= deadline:
                    process.kill()
                    code = process.wait(timeout=3)
                    reaped = True
                    break
        status = 128 - code if code < 0 else code
        if received and status == 0:
            status = 128 + received[-1]
        append_record(log, f'\nCS16_SESSION_END time={stamp()} exit_code={status}' +
                      (f' signal={received[-1]}' if received else '') + '\n')
        show(f'Server stopped: exit_code={status}; log: {log}')
        return status
    except OSError as error:
        append_record(log, f'\nCS16_RECORDER_ERROR time={stamp()} {error}\n')
        raise
    finally:
        if control_fd is not None:
            os.close(control_fd)
        if process is not None and not reaped:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        Path(control_name).unlink(missing_ok=True)
        for number, handler in previous.items():
            signal.signal(number, handler)


def main():
    if sys.argv[1:] == ['--child']:
        command = json.loads(os.environ.pop(COMMAND))
        if not isinstance(command, list) or not command or not all(isinstance(a, str) for a in command):
            raise ValueError('Invalid recorded server command.')
        protect_child_parent(os.environ.pop(CONTROL))
        os.environ[ACTIVE] = '1'
        os.environ['LD_LIBRARY_PATH'] = str(Path.cwd()) + (
            ':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')
        os.execvpe(command[0], command, os.environ)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True, type=Path)
    parser.add_argument('--log-file', type=Path)
    parser.add_argument('--require-terminal', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--launcher', type=Path, help='Back up and enable recording for this installed launcher')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    server = args.server.expanduser().resolve()
    if not server.is_dir() or (server / '.install-incomplete').exists():
        raise ValueError('Server folder is missing or installation is incomplete.')
    log = args.log_file or new_log_file(server)
    validate_terminal(log)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.launcher:
        launcher = args.launcher.expanduser().resolve()
        ensure_launcher_logging(server, launcher)
        command = ['bash', str(launcher), *command]
    return run_recorded(server, command, log)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f'Server recording failed: {error}', file=sys.stderr)
        sys.exit(1)
