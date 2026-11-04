"""Create server-local secrets once. Never run against the project data folder.

Run on the Oracle Linux VM, from this deployment directory. No values are printed.
"""
import os
from pathlib import Path
import secrets


def main():
    if os.name != 'posix':
        raise SystemExit('Run on the Linux server, not the Windows project checkout.')
    folder = Path(__file__).resolve().parent / '.runtime'
    os.umask(0o077)
    # Refuse reuse: do not rotate DB passwords or encryption keys accidentally.
    folder.mkdir(mode=0o700, exist_ok=False)
    password = secrets.token_hex(32)
    files = {
        'postgres.env': f'POSTGRES_DB=metabase\nPOSTGRES_USER=metabase\nPOSTGRES_PASSWORD={password}\n',
        'metabase.env': f'MB_DB_PASS={password}\nMB_ENCRYPTION_SECRET_KEY={secrets.token_hex(32)}\nMB_SESSION_SECRET_KEY={secrets.token_hex(32)}\n',
    }
    for name, content in files.items():
        with (folder/name).open('x', encoding='utf-8') as stream:
            stream.write(content)
        (folder/name).chmod(0o600)
    print('Server secrets created. Preserve .runtime securely alongside database backups.')


if __name__ == '__main__':
    main()
