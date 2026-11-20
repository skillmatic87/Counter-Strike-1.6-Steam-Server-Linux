"""Explicit, journaled package-source update. Run from a separate new extraction."""
import argparse,hashlib,json,os,re,stat,sys,time,uuid
from pathlib import Path,PurePosixPath
from package_guard import claim,refuse_legacy_processes
ROOT=Path(__file__).resolve().parents[1]
JOURNAL='.package-migration-active.json'

def digest(data):return hashlib.sha256(data).hexdigest()
def path_in(root,relative):
    parts=PurePosixPath(relative).parts
    if not parts or any(x in ('','.','..') or ':' in x or '\\' in x for x in parts) or relative.startswith('/'):
        raise ValueError('Unsafe package path')
    path=root
    for part in parts:
        path=path/part
        if path.is_symlink() or (path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Linked/reparse package paths are not allowed')
    if path.exists() and not path.is_file():raise ValueError('Package destination is not a regular file')
    return path
def actual(root,relative):
    # Enumerate actual directory spellings: exists()/samefile() hide Windows aliases.
    current=root;parts=[]
    for part in PurePosixPath(relative).parts:
        if not current.is_dir():return None
        matches=[p for p in current.iterdir() if p.name==part]
        if not matches and os.name=='nt':matches=[p for p in current.iterdir() if p.name.casefold()==part.casefold()]
        if len(matches)>1:raise ValueError('Ambiguous case-sensitive Windows package path')
        if not matches:return None
        current=matches[0];parts.append(current.name)
    return '/'.join(parts)
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+path.name+'.migration-write')
    if temporary.exists() or temporary.is_symlink():raise ValueError('A temporary migration file already exists')
    try:
        with temporary.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        if os.name!='nt':
            descriptor=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
    finally:temporary.unlink(missing_ok=True)
def record(path,value):atomic(path,(json.dumps(value,indent=2)+'\n').encode())
def load_source(source):
    manifest=json.loads((source/'package-files.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!=1:raise ValueError('Unsupported package manifest')
    history=manifest.get('previous_manifests',[])
    if not isinstance(history,list) or any(not isinstance(x,dict) or x.get('path')!='package-files.json' or not isinstance(x.get('sha256'),str) or not re.fullmatch(r'[a-f0-9]{64}',x['sha256']) for x in history):raise ValueError('Invalid previous manifest history')
    for entry in manifest['files']:
        if entry['path']=='package-files.json':raise ValueError('The manifest self-entry must be synthesized')
        path=path_in(source,entry['path'])
        if digest(path.read_bytes())!=entry['sha256']:raise ValueError('Source package checksum mismatch: '+entry['path'])
    # The manifest itself is copied without requiring a self-referential hash.
    manifest['files'].append(dict(path='package-files.json',sha256=digest((source/'package-files.json').read_bytes()),previous=history,new=True))
    return manifest

def prepare(source,target,manifest):
    plan=[];known=set()
    for entry in manifest['files']:
        canonical=entry['path'];path_in(target,canonical)
        temporary=str(PurePosixPath(canonical).with_name('.'+PurePosixPath(canonical).name+'.migration-write'))
        if path_in(target,temporary).exists():raise ValueError('A temporary migration file already exists: '+temporary)
        candidates=[]
        for name in [canonical,*[x['path'] for x in entry.get('previous',[])]]:
            found=actual(target,name)
            if found is not None and found not in candidates:candidates.append(found)
        source_bytes=(source/canonical).read_bytes()
        allowed={entry['sha256'],*[x['sha256'] for x in entry.get('previous',[])]}
        allowed_normal={x.get('normalized_sha256') for x in entry.get('previous',[]) if x.get('normalized_sha256')}
        before=[]
        for name in candidates:
            if name in known:continue
            path=path_in(target,name);raw=path.read_bytes();sha=digest(raw)
            if sha not in allowed and digest(raw.replace(b'\r\n',b'\n')) not in allowed_normal:
                raise ValueError('Locally modified or unrecognized package file; no files changed: '+name)
            before.append(dict(path=name,sha256=sha,mode=stat.S_IMODE(path.stat().st_mode)));known.add(name)
        if len(before)==1 and before[0]['path']==canonical and before[0]['sha256']==entry['sha256']:continue
        if not before and not entry.get('new',False):
            # Missing optional old files are supplied by the new source package.
            pass
        plan.append(dict(path=canonical,temporary=temporary,sha256=entry['sha256'],before=before,mode=0o755 if canonical.endswith('.sh') else 0o644))
    return plan

def recover(target,manifest=None,source=None):
    journal=path_in(target,JOURNAL)
    if not journal.exists():return False
    transaction=json.loads(journal.read_text())
    source=source or ROOT;manifest=manifest or load_source(source)
    entries={x['path']:x for x in manifest['files']}
    allowed={x['path']:{x['path'],*[p['path'] for p in x.get('previous',[])]} for x in manifest['files']}
    if transaction.get('schema')!=1 or transaction.get('package')!=manifest['package']:raise ValueError('Wrong migration package/schema')
    if not re.fullmatch(r'\.package-migration-backups/[0-9]{8}-[0-9]{6}-[a-f0-9]{8}',transaction['backup']):raise ValueError('Unsafe backup identifier')
    backup=target/transaction['backup']
    for ancestor in (target/'.package-migration-backups',backup):
        if ancestor.is_symlink() or getattr(ancestor.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked backup directory')
    if json.loads(path_in(backup,'receipt.json').read_text())!=transaction:raise ValueError('Unmanaged or changed migration journal metadata')
    seen_paths=set();seen_originals=set();seen_objects=set();temporary_paths=set()
    # Validate every original and current byte before the first recovery write.
    for operation in transaction['operations']:
        if operation['path'] not in allowed:raise ValueError('Unmanaged recovery path')
        if operation['path'] in seen_paths:raise ValueError('Duplicate recovery operation')
        seen_paths.add(operation['path'])
        if operation['sha256']!=entries[operation['path']]['sha256']:raise ValueError('Unexpected new-file checksum in recovery journal')
        if operation['mode']!=(0o755 if operation['path'].endswith('.sh') else 0o644):raise ValueError('Invalid installed file mode')
        expected_temp=str(PurePosixPath(operation['path']).with_name('.'+PurePosixPath(operation['path']).name+'.migration-write'))
        if operation['temporary']!=expected_temp:raise ValueError('Unmanaged temporary path')
        original_data=[]
        for original in operation['before']:
            identity=original['path'].casefold() if os.name=='nt' else original['path']
            if identity in seen_originals:raise ValueError('Duplicate original recovery path')
            seen_originals.add(identity)
            if type(original['mode']) is not int or not 0<=original['mode']<=0o777:raise ValueError('Invalid original file mode')
            if original['path'] not in allowed[operation['path']] and not (os.name=='nt' and original['path'].casefold() in {x.casefold() for x in allowed[operation['path']]}):raise ValueError('Unmanaged original path')
            if not re.fullmatch('[0-9]+',original['object']):raise ValueError('Unsafe backup object')
            if original['object'] in seen_objects:raise ValueError('Duplicate backup object')
            seen_objects.add(original['object'])
            data=path_in(backup,original['object']).read_bytes()
            if digest(data)!=original['sha256']:raise ValueError('Migration backup checksum mismatch')
            entry=entries[operation['path']]
            known={entry['sha256'],*[x['sha256'] for x in entry.get('previous',[])]}
            normalized={x.get('normalized_sha256') for x in entry.get('previous',[]) if x.get('normalized_sha256')}
            if digest(data) not in known and digest(data.replace(b'\r\n',b'\n')) not in normalized:raise ValueError('Unrecognized original backup contents')
            original_data.append(data)
        for relative in {operation['path'],*[x['path'] for x in operation['before']]}:
            temp=str(PurePosixPath(relative).with_name('.'+PurePosixPath(relative).name+'.migration-write'))
            found=actual(target,temp)
            if found:
                temporary=path_in(target,found);raw=temporary.read_bytes()
                if not any(data.startswith(raw) for data in [(source/operation['path']).read_bytes(),*original_data]):raise ValueError('Unexpected temporary file contents')
                temporary_paths.add(found)
        expected={operation['sha256'],*[x['sha256'] for x in operation['before']]}
        for relative in {operation['path'],*[x['path'] for x in operation['before']]}:
            path=path_in(target,relative)
            if path.exists() and digest(path.read_bytes()) not in expected:raise ValueError('Files changed after interruption; recovery refused: '+relative)
        for original in operation['before']:
            data=path_in(backup,original['object']).read_bytes()
            if digest(data)!=original['sha256']:raise ValueError('Migration backup checksum mismatch')
    for relative in temporary_paths:path_in(target,relative).unlink(missing_ok=True)
    for operation in reversed(transaction['operations']):
        names={operation['path'],*[x['path'] for x in operation['before']]}
        for relative in names:path_in(target,relative).unlink(missing_ok=True)
        for original in operation['before']:
            path=path_in(target,original['path']);atomic(path,path_in(backup,original['object']).read_bytes());path.chmod(original['mode'])
    journal.unlink();return True

def apply(source,target,manifest,fail_after=None):
    if (target/JOURNAL).exists():raise RuntimeError('An interrupted migration exists. Run --recover first.')
    if (target/'.update-active.json').exists():raise RuntimeError('Recover the interrupted ZIP updater before migration.')
    operations=prepare(source,target,manifest)
    if not operations:return dict(changed=0,backup=None)
    parent=target/'.package-migration-backups'
    if parent.is_symlink() or (parent.exists() and (not parent.is_dir() or getattr(parent.lstat(),'st_file_attributes',0)&0x400)):raise ValueError('Linked or invalid migration backup directory')
    relative='.package-migration-backups/'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    backup=target/relative;backup.mkdir(parents=True,mode=0o700)
    counter=0
    for operation in operations:
        for original in operation['before']:
            original['object']=str(counter);counter+=1
            with (backup/original['object']).open('xb') as output:
                output.write(path_in(target,original['path']).read_bytes());output.flush();os.fsync(output.fileno())
    transaction=dict(schema=1,package=manifest['package'],backup=relative,operations=operations)
    record(backup/'receipt.json',transaction);record(target/JOURNAL,transaction)
    try:
        for index,operation in enumerate(operations):
            # Backup+journal make a temporary case-only rename recoverable on both filesystems.
            for original in operation['before']:path_in(target,original['path']).unlink(missing_ok=True)
            if fail_after==index:raise RuntimeError('Injected migration interruption')
            destination=path_in(target,operation['path']);atomic(destination,(source/operation['path']).read_bytes());destination.chmod(operation['mode'])
        (target/JOURNAL).unlink()
    except BaseException:
        # Leave the journal intact for explicit, validated and retryable recovery.
        raise
    return dict(changed=len(operations),backup=relative)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,required=True);group=parser.add_mutually_exclusive_group()
    for option in ('check','apply','recover'):group.add_argument('--'+option,action='store_true')
    args=parser.parse_args();requested=args.target.expanduser().absolute()
    for ancestor in [requested,*requested.parents]:
        if ancestor.is_symlink() or (ancestor.exists() and getattr(ancestor.lstat(),'st_file_attributes',0)&0x400):parser.error('Target and its ancestors must not be links or reparse points.')
    target=requested.resolve()
    if target==ROOT.resolve():parser.error('Extract the new package separately; --target must be the existing package folder.')
    if not target.is_dir() or (target/'.git').exists():parser.error('Target must be an extracted package, not a Git checkout.')
    manifest=load_source(ROOT)
    with claim(target):
        refuse_legacy_processes(target)
        # Also coordinate with older Linux CS15 ZIP updaters that predate this helper.
        legacy_lock=None
        try:
            if sys.platform=='linux':
                import fcntl
                legacy_lock=(target/'.update.lock').open('a')
                try:fcntl.flock(legacy_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:raise RuntimeError('The existing ZIP updater is active. Wait for it to finish.')
            if args.recover:print(json.dumps(dict(recovered=recover(target,manifest,ROOT))));return
            if args.apply:print(json.dumps(apply(ROOT,target,manifest)));return
            plan=prepare(ROOT,target,manifest);print(json.dumps(dict(package=manifest['package'],changes=[x['path'] for x in plan]),indent=2))
        finally:
            if legacy_lock:legacy_lock.close()

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:print('Migration stopped: '+str(error),file=sys.stderr);sys.exit(1)
