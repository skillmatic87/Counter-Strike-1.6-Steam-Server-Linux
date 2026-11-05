#!/usr/bin/env python3
"""Assemble a new native CS 1.6 Steam server from checksum-pinned archives."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
import tempfile
from project_version import VERSION


def atomic_write(path, data):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.cs16-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

ROOT = Path(__file__).resolve().parents[1]
def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_text(path, text, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='ascii', newline='\n')
    path.chmod(mode)


def safe_path(root, name):
    """Never permit absolute paths, traversal, drive names or symbolic links."""
    relative = PurePosixPath(name.replace('\\', '/'))
    if not relative.parts or relative.is_absolute() or any(
            p in ('.', '..') or ':' in p or any(ord(c) < 32 for c in p)
            for p in relative.parts):
        raise ValueError(f'Unsafe archive/content path: {name}')
    target = root.joinpath(*relative.parts)
    for parent in (target, *target.parents):
        if parent.is_symlink():
            raise ValueError(f'Links are not allowed: {parent}')
        if parent == root:
            break
    return target


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def verified_bytes(data, expected, label):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Checksum mismatch: {label}')
    return data


def download(entry, cache):
    target = safe_path(cache, entry['file'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_name(target.name + '.' + secrets.token_hex(6) + '.partial')
        print(f"Downloading {entry['file']}", flush=True)
        try:
            request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Counter-Strike-1.6-Steam-Server-Linux/' + VERSION})
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open('xb') as output:
                shutil.copyfileobj(response, output)
            if digest(temporary) != entry['sha256']:
                raise ValueError(f"Downloaded checksum mismatch: {entry['file']}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if not target.is_file() or digest(target) != entry['sha256']:
        raise ValueError(f'Cached checksum mismatch; move this file aside and retry: {target}')
    return target


def extract(archive_path, destination):
    """Extract regular files/directories only; keep executable bits, never ownership."""
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                target = safe_path(destination, member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError(f'Archive link rejected: {member.filename}')
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        with tarfile.open(archive_path) as archive:
            for member in archive:
                target = safe_path(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
                else:
                    raise ValueError(f'Archive link/device rejected: {member.name}')
