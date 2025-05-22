# lambda-common/error_utils.py
# 오류 발생 시 스크린샷과 페이지 소스를 Discord로 전송하는 유틸리티 함수들을 포함합니다.
import requests
from datetime import datetime
import os

def capture_and_send_screenshot(driver, file_name_prefix, discord_webhook_url):
    '''
    웹 드라이버를 사용하여 현재 화면을 캡처하고 페이지 소스를 가져와 Discord 웹훅으로 전송합니다.
    오류 분석 및 디버깅을 돕기 위한 함수입니다.

    :param driver: Selenium 웹 드라이버 객체
    :param file_name_prefix: 생성될 파일명의 접두사 (예: "quasar_zone_error")
    :param discord_webhook_url: Discord 웹훅 URL
    '''
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') # 현재 시간을 파일명에 포함하기 위한 타임스탬프
    
    # 스크린샷 처리: 현재 화면을 PNG 파일로 저장하고 Discord로 전송합니다.
    screenshot_file = f"/tmp/{file_name_prefix}_screenshot_{timestamp}.png" # 임시 저장될 스크린샷 파일 경로
    try:
        driver.save_screenshot(screenshot_file) # 웹 드라이버를 통해 스크린샷 저장
        with open(screenshot_file, "rb") as f: # 파일을 바이너리 읽기 모드로 열기
            files = {"file": (screenshot_file, f, "image/png")} # Discord로 전송할 파일 데이터 구성
            payload = {"content": f"오류 스크린샷: {file_name_prefix}"} # Discord 메시지 내용
            response = requests.post(discord_webhook_url, data=payload, files=files) # Discord 웹훅으로 POST 요청
        print(f"스크린샷 Discord 응답: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"{file_name_prefix} 스크린샷 저장/전송 오류: {e}")
    finally:
        # 임시 파일 정리
        if os.path.exists(screenshot_file): # 스크린샷 파일이 존재하면
            try:
                os.remove(screenshot_file) # 파일 삭제
            except OSError as e:
                print(f"스크린샷 파일 삭제 오류 {screenshot_file}: {e}")

    # 페이지 소스 처리: 현재 페이지의 HTML 소스를 파일로 저장하고 Discord로 전송합니다.
    pagesource_file = f"/tmp/{file_name_prefix}_pagesource_{timestamp}.html" # 임시 저장될 페이지 소스 파일 경로
    try:
        with open(pagesource_file, 'w', encoding='utf-8') as f: # 파일을 쓰기 모드(UTF-8 인코딩)로 열기
            f.write(driver.page_source) # 웹 드라이버를 통해 페이지 소스 저장
        with open(pagesource_file, "rb") as f: # 파일을 바이너리 읽기 모드로 열기
            files = {"file": (pagesource_file, f, "text/html")} # Discord로 전송할 파일 데이터 구성
            payload = {"content": f"오류 페이지 소스: {file_name_prefix}"} # Discord 메시지 내용
            response = requests.post(discord_webhook_url, data=payload, files=files) # Discord 웹훅으로 POST 요청
        print(f"페이지 소스 Discord 응답: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"{file_name_prefix} 페이지 소스 저장/전송 오류: {e}")
    finally:
        # 임시 파일 정리
        if os.path.exists(pagesource_file): # 페이지 소스 파일이 존재하면
            try:
                os.remove(pagesource_file) # 파일 삭제
            except OSError as e:
                print(f"페이지 소스 파일 삭제 오류 {pagesource_file}: {e}")
