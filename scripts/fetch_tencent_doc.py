"""
从腾讯文档拉取计薪表格
优先: 浏览器菜单导出 (需持久化登录态)
兜底: 提示手动下载
"""
import sys, os, time
from playwright.sync_api import sync_playwright

DOC_URL = "https://docs.qq.com/sheet/DUW9WanhjQXNTa0hk"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(BASE_DIR, "接力送真实人力计薪", "接力送计薪表格.xlsx")

def main():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    old_size = os.path.getsize(OUT_FILE) if os.path.exists(OUT_FILE) else 0
    downloaded = []

    with sync_playwright() as p:
        user_data = os.path.expanduser("~/.claude/tencent_browser")
        ctx = p.chromium.launch_persistent_context(
            user_data, headless=False, accept_downloads=True
        )
        page = ctx.new_page()

        page.on("download", lambda d: (d.save_as(OUT_FILE), downloaded.append(True)))

        print(f"打开: {DOC_URL}")
        page.goto(DOC_URL, timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)

        if "login" in page.url.lower():
            print("需要登录, 请在浏览器中扫码后按 Enter...")
            input()

        # 方法: 文件 → 下载 → Excel
        print("尝试菜单导出...")
        try:
            page.wait_for_selector('[class*="toolbar"]', timeout=10000)
            time.sleep(1)
            page.locator('text=文件').first.click(timeout=5000)
            time.sleep(0.5)
            page.locator('text=下载').first.hover(timeout=3000)
            time.sleep(0.3)
            page.locator('text=Excel').first.click(timeout=3000)
            time.sleep(8)
        except Exception as e:
            print(f"菜单导出失败: {e}")

        ctx.close()

    new_size = os.path.getsize(OUT_FILE) if os.path.exists(OUT_FILE) else 0
    if new_size > 500:
        changed = "已更新" if new_size != old_size else "未变化(可能腾讯文档无新数据)"
        print(f"完成: {new_size} bytes ({changed})")
        if new_size == old_size:
            print("提示: 如腾讯文档已更新但文件未变化, 请手动下载:")
            print(f"  1. 打开 {DOC_URL}")
            print(f"  2. 文件 → 下载 → Excel (.xlsx)")
            print(f"  3. 保存到: {OUT_FILE}")
    else:
        print("自动导出失败, 请手动下载:")
        print(f"  1. 打开 {DOC_URL}")
        print(f"  2. 文件 → 下载 → Excel (.xlsx)")
        print(f"  3. 保存到: {OUT_FILE}")


if __name__ == "__main__":
    main()
