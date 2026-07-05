"""
接力送 · 部署脚本
用法: python scripts/deploy.py "数据更新至MM/DD"

1. git add -A && git commit && git push (main + master)
2. 轮询 Pages 构建状态，最多等 120s
3. 构建卡住 (>30s 仍是 building 且无进展) 自动空 commit 重试
4. 最多重试 2 次
"""
import subprocess, sys, time, os

MAX_WAIT_SEC = 120
STUCK_THRESHOLD = 30
MAX_RETRIES = 2

REPO = 'hejaconceited2-lang/relay-delivery-dashboard'
GIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Windows TLS workaround
GIT_SSL = '-c http.sslVerify=false'

def run(cmd, cwd=None):
    """Run shell command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
        cwd=cwd or GIT_DIR
    )
    stdout = (result.stdout or '').strip()
    stderr = (result.stderr or '').strip()
    return result.returncode, stdout, stderr

def gh_api(path):
    """Call gh api, return JSON string or None."""
    code, out, err = run(f'gh api {path}')
    if code != 0:
        return None
    return out

def get_build_status():
    """Get latest Pages build status: built|building|errored|None."""
    import json
    raw = gh_api(f'repos/{REPO}/pages/builds/latest')
    if not raw:
        return None, None
    try:
        data = json.loads(raw)
        return data.get('status'), data.get('commit', '')
    except:
        return None, None

def deploy(commit_msg):
    # Step 1: Git push
    print('[1/3] Pushing code...')
    code, _, err = run(f'git {GIT_SSL} add -A')
    if code != 0:
        print(f'  git add failed: {err}')
        return False

    code, _, err = run(f'git {GIT_SSL} commit -m "{commit_msg}"')
    if code != 0 and 'nothing to commit' not in err:
        print(f'  git commit failed: {err}')
        return False

    code, _, err = run(f'git {GIT_SSL} push origin main:main')
    if code != 0:
        print(f'  push main failed: {err}')
        return False

    code, _, err = run(f'git {GIT_SSL} push origin main:master')
    if code != 0:
        print(f'  push master failed: {err}')
        return False

    print('  Push done.')

    # Step 2: Wait for Pages build
    print('[2/3] Waiting for Pages build...')
    waited = 0
    last_commit = None

    while waited < MAX_WAIT_SEC:
        time.sleep(5)
        waited += 5
        status, build_commit = get_build_status()

        if status is None:
            print(f'  [{waited}s] Cannot query status, retrying...')
            continue

        if status == 'built':
            print(f'  [{waited}s] Pages build SUCCESS')
            return True

        if status == 'errored':
            print(f'  [{waited}s] Pages build FAILED')
            error_info = gh_api(f'repos/{REPO}/pages/builds/latest')
            print(f'  Error: {error_info}')
            return False

        # Building - check if stuck
        if build_commit != last_commit:
            last_commit = build_commit
            stuck_time = 0
        else:
            stuck_time += 5

        if stuck_time >= STUCK_THRESHOLD:
            print(f'  [{waited}s] Build stuck (>30s no progress), retrying...')
            return 'stuck'

        if waited <= 15 or waited % 15 == 0:
            print(f'  [{waited}s] Building...')

    print(f'  [{waited}s] Build timeout, retrying...')
    return 'stuck'

def main():
    commit_msg = sys.argv[1] if len(sys.argv) > 1 else 'data update'

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            print(f'\n[Retry {attempt}/{MAX_RETRIES}]')
            run(f'git {GIT_SSL} commit --allow-empty -m "retry pages"')
            run(f'git {GIT_SSL} push origin main:main')
            run(f'git {GIT_SSL} push origin main:master')

        result = deploy(commit_msg)
        if result is True:
            print('\n[3/3] Deploy SUCCESS')
            return
        elif result is False:
            print('\nDeploy FAILED')
            sys.exit(1)

    print(f'\nDeploy FAILED after {MAX_RETRIES} retries, please check manually')
    sys.exit(1)

if __name__ == '__main__':
    main()
