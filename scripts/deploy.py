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
STUCK_THRESHOLD = 30  # 30s 无进展视为卡住
MAX_RETRIES = 2

REPO = 'hejaconceited2-lang/relay-delivery-dashboard'
GIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(cmd, cwd=None):
    """Run shell command, return (returncode, stdout)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or GIT_DIR,
        env={**os.environ, 'GIT_SSL_NO_VERIFY': 'true'}
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()

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
    print('[1/3] 推送代码...')
    code, _, err = run(f'git add -A')
    if code != 0:
        print(f'  git add 失败: {err}')
        return False

    code, _, err = run(f'git commit -m "{commit_msg}"')
    # commit 可能无变更 (nothing to commit)
    if code != 0 and 'nothing to commit' not in err:
        print(f'  git commit 失败: {err}')
        return False

    code, _, err = run(f'git push origin main:main')
    if code != 0:
        print(f'  push main 失败: {err}')
        return False

    code, _, err = run(f'git push origin main:master')
    if code != 0:
        print(f'  push master 失败: {err}')
        return False

    print('  推送完成.')

    # Step 2: Wait for Pages build
    print('[2/3] 等待 Pages 构建...')
    waited = 0
    last_commit = None

    while waited < MAX_WAIT_SEC:
        time.sleep(5)
        waited += 5
        status, build_commit = get_build_status()

        if status is None:
            print(f'  [{waited}s] 无法查询状态，继续等待...')
            continue

        if status == 'built':
            print(f'  [{waited}s] ✓ Pages 构建成功')
            return True

        if status == 'errored':
            print(f'  [{waited}s] ✗ Pages 构建失败')
            error_info = gh_api(f'repos/{REPO}/pages/builds/latest')
            print(f'  错误详情: {error_info}')
            return False

        # Building — check if stuck (same commit for too long)
        if build_commit != last_commit:
            last_commit = build_commit
            stuck_time = 0
        else:
            stuck_time += 5

        if stuck_time >= STUCK_THRESHOLD:
            print(f'  [{waited}s] 构建卡住 (>30s 无进展)，需要重试')
            return 'stuck'

        if waited <= 15 or waited % 15 == 0:
            print(f'  [{waited}s] 构建中...')

    print(f'  [{waited}s] 构建超时，需要重试')
    return 'stuck'

def main():
    commit_msg = sys.argv[1] if len(sys.argv) > 1 else '数据更新'

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            print(f'\n[重试 {attempt}/{MAX_RETRIES}]')
            # 空 commit 重触发
            run('git commit --allow-empty -m "retry pages"')
            run('git push origin main:main')
            run('git push origin main:master')

        result = deploy(commit_msg)
        if result is True:
            print('\n[3/3] ✓ 线上部署完成')
            return
        elif result is False:
            print(f'\n✗ 部署失败')
            sys.exit(1)
        # result == 'stuck' → retry

    print(f'\n✗ 重试 {MAX_RETRIES} 次后仍未成功，请手动检查')
    sys.exit(1)

if __name__ == '__main__':
    main()
