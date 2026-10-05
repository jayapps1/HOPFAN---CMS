"""Verified local PostgreSQL backup and original-column preservation check.

Usage: python -m scripts.upgrade_guard backup
       python -m scripts.upgrade_guard verify backups/<name>_snapshot.json
Backups and fingerprint snapshots are ignored by Git. Credentials stay in the
child process environment, never command arguments or console output.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import os
import subprocess
import sys
from sqlalchemy import inspect,text
from src.config.database import engine

ROOT=Path(__file__).resolve().parents[1]
APPEND_ONLY={'permissions','roles','role_permissions','authorization_audit_logs','security_audit_logs'}


def hashes(connection,table,columns):
    quote=connection.dialect.identifier_preparer.quote
    selected=','.join(quote(c) for c in columns)
    return sorted(connection.execute(text('SELECT md5(row_to_json(t)::text) FROM (SELECT '+selected+' FROM public.'+quote(table)+') t')).scalars())


def snapshot():
    result={}
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        inspector=inspect(connection)
        for table in inspector.get_table_names(schema='public'):
            if table=='alembic_version': continue
            columns=[c['name'] for c in inspector.get_columns(table,schema='public')]
            result[table]=dict(columns=columns,hashes=hashes(connection,table,columns))
    return result


def backup():
    directory=ROOT/'backups';directory.mkdir(exist_ok=True)
    prefix=directory/('before_user_administration_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    archive=prefix.with_suffix('.dump')
    url=engine.url
    environment=dict(os.environ,PGPASSWORD=url.password or '')
    binary=Path(os.environ.get('PG_BIN',r'C:\Program Files\PostgreSQL\18\bin'))
    command=[str(binary/'pg_dump.exe'),'--host',url.host or 'localhost','--port',str(url.port or 5432),
        '--username',url.username or '', '--dbname',url.database or '', '--format=custom','--file',str(archive)]
    subprocess.run(command,env=environment,check=True,capture_output=True)
    subprocess.run([str(binary/'pg_restore.exe'),'--list',str(archive)],env=environment,check=True,capture_output=True)
    target=Path(str(prefix)+'_snapshot.json')
    target.write_text(json.dumps(snapshot(),indent=2),encoding='utf-8')
    print('Verified backup:',archive.relative_to(ROOT))
    print('Fingerprint snapshot:',target.relative_to(ROOT))


def verify(filename):
    path=Path(filename).resolve()
    if not path.is_relative_to((ROOT/'backups').resolve()):
        raise ValueError('Use a snapshot inside the project backups directory.')
    recorded=json.loads(path.read_text(encoding='utf-8'))
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        for table,expected in recorded.items():
            actual=hashes(connection,table,expected['columns'])
            if table in APPEND_ONLY:
                valid=set(expected['hashes']).issubset(actual)
            else:
                valid=actual==expected['hashes']
            if not valid: raise RuntimeError('Original records changed in '+table)
            print(table+': original '+str(len(expected['hashes']))+' rows preserved')


if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='backup': backup()
    elif len(sys.argv)==3 and sys.argv[1]=='verify': verify(sys.argv[2])
    else: raise SystemExit(__doc__)
