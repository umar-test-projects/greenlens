"""Use existing AWS CLI login credentials in memory for the paid Landsat build."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='default')
    parser.add_argument('--requester-pays', action='store_true', required=True,
                        help='Explicitly accept S3 request/data-transfer charges for Landsat')
    args = parser.parse_args()
    executable = shutil.which('aws')
    if not executable:
        candidate = Path(r'C:\Program Files\Amazon\AWSCLIV2\aws.exe')
        executable = str(candidate) if candidate.is_file() else None
    if not executable:
        raise SystemExit('AWS CLI v2 is required; install it and run aws login first.')
    # Never print, persist, or include credential values in command arguments.
    result = subprocess.run([executable, 'configure', 'export-credentials',
                             '--profile', args.profile, '--format', 'process'],
                            capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('Could not obtain existing CLI credentials. Refresh aws login and retry.')
    credentials = json.loads(result.stdout)
    environment = os.environ.copy()
    environment.update(AWS_ACCESS_KEY_ID=credentials['AccessKeyId'],
                       AWS_SECRET_ACCESS_KEY=credentials['SecretAccessKey'],
                       AWS_SESSION_TOKEN=credentials.get('SessionToken', ''),
                       AWS_DEFAULT_REGION='us-west-2', AWS_REGION='us-west-2')
    process = subprocess.run([sys.executable, str(Path(__file__).with_name('build_grid.py')),
                              '--requester-pays'], env=environment)
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
