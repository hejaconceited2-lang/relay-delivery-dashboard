"""
从腾讯文档拉取计薪表格（通过浏览器自动化）
首次运行会打开浏览器窗口，需要手动登录一次。
后续运行复用登录状态，自动下载。
"""
import sys, os, json, time
from playwright.sync_api import sync_playwright

DOC_URL = "https://docs.qq.com/sheet/DUW9WanhjQXNTa0hk?tab=849pll"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "接力送真实人力计薪")
OUT_FILE = os.path.join(OUT_DIR, "接力送计薪表格.xlsx")

def intercept_api(page, api_data):
    """拦截 XHR 响应, 捕获 sheet 数据"""
    def handle_response(response):
        url = response.url
        if "dop-api/sheet" in url and response.status == 200:
            try:
                data = response.json()
                api_data.append(data)
            except:
                pass
    page.on("response", handle_response)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        # 持久化浏览器上下文: 记住登录状态
        user_data_dir = os.path.join(os.path.expanduser("~"), ".claude", "tencent_browser")
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            accept_downloads=True,
        )
        page = context.new_page()

        # 下载监听
        got_download = []
        def on_download(download):
            download.save_as(OUT_FILE)
            got_download.append(True)
            print(f"已保存: {OUT_FILE} ({os.path.getsize(OUT_FILE)} bytes)")
        page.on("download", on_download)

        # 拦截 sheet API 数据 (备用方案)
        api_responses = []
        intercept_api(page, api_responses)

        print(f"打开: {DOC_URL}")
        page.goto(DOC_URL, timeout=60000, wait_until="domcontentloaded")

        # 等页面加载完成
        print("等待页面加载...")
        time.sleep(3)

        # 检查是否需要登录
        if "login" in page.url.lower():
            print("\n⚠ 需要登录! 请在浏览器中扫码/登录")
            print("登录完成后按 Enter 继续...")
            input()

        # 等待 sheet 完全渲染
        try:
            page.wait_for_selector('canvas', timeout=15000)
            print("Sheet 已渲染")
        except:
            pass

        time.sleep(2)

        # 方法1: 尝试通过 UI 导出
        print("尝试导出...")
        try:
            # 点击 "文件" 菜单
            file_menu = page.locator('text=文件').first
            if file_menu.is_visible():
                file_menu.click()
                time.sleep(0.5)
                # 悬停 "下载"
                download_menu = page.locator('text=下载').first
                if download_menu.is_visible():
                    download_menu.hover()
                    time.sleep(0.3)
                    # 点击 Excel
                    excel_btn = page.locator('text=Excel').first
                    if excel_btn.is_visible():
                        excel_btn.click()
                        print("已点击导出, 等待下载...")
                        time.sleep(5)
        except Exception as e:
            print(f"UI 导出失败: {e}")

        # 等待下载
        for _ in range(10):
            if os.path.exists(OUT_FILE) and os.path.getsize(OUT_FILE) > 500:
                break
            time.sleep(1)

        if os.path.exists(OUT_FILE) and os.path.getsize(OUT_FILE) > 500:
            print(f"成功! 文件: {OUT_FILE} ({os.path.getsize(OUT_FILE)} bytes)")
        else:
            print("自动导出未成功, 请手动操作:")
            print("1. 在浏览器中点击 文件 → 下载 → Excel (.xlsx)")
            print(f"2. 保存到: {OUT_FILE}")
            input("完成后按 Enter...")

        context.close()

if __name__ == "__main__":
    main()
