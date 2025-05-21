# lambda-common/error_utils.py
import requests
from datetime import datetime
import os

def capture_and_send_screenshot(driver, file_name_prefix, discord_webhook_url):
    '''화면 캡처 및 페이지 소스를 Discord로 전송'''
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 스크린샷 처리
    screenshot_file = f"/tmp/{file_name_prefix}_screenshot_{timestamp}.png"
    try:
        driver.save_screenshot(screenshot_file)
        with open(screenshot_file, "rb") as f:
            files = {"file": (screenshot_file, f, "image/png")}
            payload = {"content": f"Error screenshot: {file_name_prefix}"}
            response = requests.post(discord_webhook_url, data=payload, files=files)
        print(f"Screenshot Discord response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error saving/sending screenshot for {file_name_prefix}: {e}")
    finally:
        if os.path.exists(screenshot_file):
            try:
                os.remove(screenshot_file)
            except OSError as e:
                print(f"Error deleting screenshot file {screenshot_file}: {e}")

    # 페이지 소스 처리
    pagesource_file = f"/tmp/{file_name_prefix}_pagesource_{timestamp}.html"
    try:
        with open(pagesource_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        with open(pagesource_file, "rb") as f:
            files = {"file": (pagesource_file, f, "text/html")}
            payload = {"content": f"Error page source: {file_name_prefix}"}
            response = requests.post(discord_webhook_url, data=payload, files=files)
        print(f"Page source Discord response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error saving/sending page source for {file_name_prefix}: {e}")
    finally:
        if os.path.exists(pagesource_file):
            try:
                os.remove(pagesource_file)
            except OSError as e:
                print(f"Error deleting page source file {pagesource_file}: {e}")
