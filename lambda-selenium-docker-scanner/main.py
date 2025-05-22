# lambda-selenium-docker-scanner/main.py
# 이 파일은 AWS Lambda 함수로 실행되어, 여러 커뮤니티 사이트의 핫딜 게시판을 스캔하여 새로운 게시물 링크를 수집하고,
# 이를 데이터베이스와 비교하여 중복되지 않은 링크만 SNS 토픽으로 발행하는 스캐너의 메인 로직을 담고 있습니다.

import json # JSON 데이터 처리를 위한 모듈
# import logging # 로깅 모듈, 현재 직접 사용되지 않아 주석 처리
import requests # HTTP 요청을 보내기 위한 모듈
import time # 시간 관련 함수 사용 (실행 시간 측정 등)
# import boto3 # AWS SDK, 현재 aws_utils를 통해 간접 사용되므로 주석 처리
import os # 운영체제와 상호작용하기 위한 모듈 (환경 변수 등 접근)
from bs4 import BeautifulSoup as bs # HTML/XML 파싱을 위한 BeautifulSoup 라이브러리 (뽐뿌 스캔 시 사용)
from selenium.webdriver.common.by import By # Selenium에서 요소를 찾기 위한 By 객체 (사이트별 클래스에서 필요)
# from selenium.webdriver.chrome.service import Service # ChromeDriver 서비스, 현재 webdriver_utils를 통해 처리되어 주석 처리
from requests.adapters import HTTPAdapter # requests 라이브러리에서 재시도 등 고급 설정을 위한 어댑터
from urllib3.util.retry import Retry # HTTP 요청 재시도 로직을 위한 클래스
# from collections import defaultdict # 기본값을 가지는 딕셔너리, 현재 사용되지 않아 주석 처리
import psycopg2 # PostgreSQL 데이터베이스 어댑터
# from datetime import datetime # 날짜/시간 관련 모듈, 현재 직접 사용되지 않아 주석 처리

# 공통 모듈 임포트
from lambda_common.config import SITES_CONFIG # 각 사이트별 설정 (셀렉터, URL 등)
from lambda_common.page_parser import BasePageOperations # 페이지 파싱 기본 작업을 위한 부모 클래스
from lambda_common.error_utils import capture_and_send_screenshot # 오류 발생 시 스크린샷 전송 유틸리티
from lambda_common.aws_utils import publish_to_sns # SNS 메시지 발행 유틸리티
from lambda_common.webdriver_utils import set_driver # Selenium WebDriver 설정 유틸리티

# 환경 변수에서 주요 설정값 가져오기
REGION = os.environ.get("REGION", "ap-northeast-2") # AWS 리전 (기본값: ap-northeast-2)
DB_HOST = os.environ["DB_HOST"] # 데이터베이스 호스트 주소
DB_NAME = os.environ["DB_NAME"] # 데이터베이스 이름
DB_USER = os.environ["DB_USER"] # 데이터베이스 사용자 이름
DB_PASSWORD = os.environ["DB_PASSWORD"] # 데이터베이스 비밀번호
DB_PORT = os.environ["DB_PORT"] # 데이터베이스 포트
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"] # 오류 알림을 받을 Discord 웹훅 URL
SNS_ARN = os.environ["SNS_ARN"] # 스캔 결과를 발행할 SNS 토픽 ARN

# HTTP 요청을 위한 Session 설정 (재시도 로직 포함)
session = requests.Session() # requests 세션 객체 생성
retry = Retry(connect=2, backoff_factor=0.5) # 연결 재시도 2회, 재시도 간격 backoff_factor 적용
adapter = HTTPAdapter(max_retries=retry) # 최대 재시도 횟수를 설정한 어댑터 생성
session.mount('http://', adapter) # HTTP 스키마에 어댑터 마운트
session.mount('https://', adapter) # HTTPS 스키마에 어댑터 마운트

# item_link_dict = defaultdict(list) # 이전에 사용되었으나 현재는 사용되지 않는 것으로 보여 주석 처리

# 데이터베이스 연결 설정 딕셔너리
db_config = {
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST,
        "port": DB_PORT
    }

class PAGES(BasePageOperations):
    """각 웹사이트 페이지 스캔을 위한 기본 클래스들의 부모 클래스입니다."""
    def __init__(self, site_name):
        """
        PAGES 클래스 생성자입니다.
        :param site_name: 처리할 사이트의 이름 (SITES_CONFIG의 키와 일치)
        """
        super().__init__(site_name, SITES_CONFIG[site_name]) # 부모 클래스(BasePageOperations) 초기화
        
    def db_get_item_links(self):
        """
        데이터베이스에서 최근 3일 동안 저장된 해당 사이트의 아이템 링크를 조회합니다.
        이는 이미 처리된 링크를 다시 스캔하지 않기 위함입니다.
        :return: 데이터베이스에서 조회된 아이템 링크 리스트, 오류 발생 시 빈 리스트
        """
        try:
            conn = psycopg2.connect(**db_config) # 데이터베이스 연결
            cursor = conn.cursor() # 커서 생성
            table_name = f"{self.site_name.lower()}_item_links" # 사이트별 테이블 이름 동적 생성
            # 최근 3일 이내에 생성된 아이템 링크를 선택하는 SQL 쿼리
            cursor.execute(
                f"""
                SELECT item_link 
                FROM {table_name}
                WHERE created_at > NOW() - INTERVAL '3 days'; 
                """
            )
            rows = cursor.fetchall() # 모든 결과 가져오기
            db_item_links = [i[0] for i in rows] # 결과에서 링크만 추출하여 리스트로 만듦
            return db_item_links
        
        except Exception as e:
            # DB 조회 중 오류 발생 시 로그 출력 및 빈 리스트 반환
            print(f"Error getting item links from DB for {self.site_name}: {str(e)}")
            return [] 
        
class QUASAR_ZONE(PAGES):
    """퀘이사존 사이트 스캔을 담당하는 클래스입니다."""
    def __init__(self):
        """QUASAR_ZONE 클래스 생성자입니다."""
        super().__init__("QUASAR_ZONE") # 부모 클래스에 사이트 이름 "QUASAR_ZONE" 전달하여 초기화
        
    def get_item_links(self, driver):
        """
        퀘이사존 핫딜 게시판에서 새로운 아이템 링크를 수집하고 SNS로 발행합니다.
        :param driver: Selenium WebDriver 객체
        """
        get_item_driver = driver # 전달받은 드라이버 사용
        try:
            get_item_driver.get(self.config['url']) # 설정된 URL로 이동
        except Exception as e:
            # 페이지 접속 실패 시 오류 로그 출력 후 종료
            print(f"{self.config['url']} 접속 실패 {str(e)}") 
            return
        
        # 설정에서 아이템 링크 CSS 선택자 템플릿과 반복 범위 가져오기
        item_link_selector_template = self.config['scanner_item_link_selector_template']
        for i in self.config['scanner_item_link_range']: # 정해진 범위만큼 반복하여 링크 수집 시도
            try:
                find_css_selector = item_link_selector_template.format(i) # CSS 선택자 포맷팅
                item_link = "err" # 초기값 설정
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector) # 요소 찾기
                item_link = item.get_attribute("href") # 'href' 속성(링크) 추출
                # 유효한 링크이고, 중복되지 않은 경우 리스트에 추가
                if item_link and item_link != "err" and item_link not in self.item_link_list : 
                    self.item_link_list.append(item_link)
            except Exception as e:
                # 링크 수집 중 오류 발생 시 로그 출력, 스크린샷 전송 후 반복 중단
                print(f"fail get item links for {self.site_name} at index {i}: {item_link} {e}")
                capture_and_send_screenshot(get_item_driver, self.site_name, DISCORD_WEBHOOK) 
                break # 오류 발생 지점에서 더 이상 진행하지 않음
        
        db_item_links = self.db_get_item_links() # DB에서 최근 링크 가져오기
        # 현재 수집된 링크와 DB 링크를 비교하여 새로운 링크만 필터링
        _item_link_list = list(set(self.item_link_list) - set(db_item_links))
        print(f"For {self.site_name}, new item links found: {len(_item_link_list)}")

        if _item_link_list: # 새로운 링크가 있는 경우
            # SNS 메시지 속성 설정
            message_attributes = {
                "is_scanning": {'DataType': 'String', 'StringValue': "1"}, # 스캐닝 작업임을 표시
                "scanned_site": {'DataType': 'String', 'StringValue': self.site_name}, # 스캔된 사이트 이름
                "num_item_links": {'DataType': 'String', 'StringValue': str(len(_item_link_list))} # 새 링크 수
            }
            try:
                # SNS로 새 링크 목록 발행
                publish_to_sns(SNS_ARN, _item_link_list, message_attributes, REGION)
            except Exception as e:
                # SNS 발행 실패 시 로그 출력
                print(f"Failed to publish to SNS for {self.site_name}: {e}")
        else:
            # 새로운 링크가 없는 경우 로그 출력
            print(f"No new item links to publish for {self.site_name}")

class ARCA_LIVE(PAGES):
    """아카라이브 핫딜 채널 스캔을 담당하는 클래스입니다."""
    def __init__(self):
        """ARCA_LIVE 클래스 생성자입니다."""
        super().__init__("ARCA_LIVE")
        
    def get_item_links(self, driver):
        """
        아카라이브 핫딜 채널에서 새로운 아이템 링크를 수집하고 SNS로 발행합니다.
        (퀘이사존과 유사한 로직, XPath 사용)
        :param driver: Selenium WebDriver 객체
        """
        get_item_driver = driver
        try:
            get_item_driver.get(self.config['url'])
        except Exception as e:
            print(f"{self.config['url']} 접속 실패 {str(e)}")
            return
        
        item_link_selector_template = self.config['scanner_item_link_selector_template'] # XPath 선택자 템플릿
        for i in self.config['scanner_item_link_range']:
            try:
                find_xpath_selector = item_link_selector_template.format(i) # XPath 선택자 포맷팅
                item_link = "err"
                item = get_item_driver.find_element(By.XPATH, find_xpath_selector) # XPath로 요소 찾기
                item_link = item.get_attribute("href")
                if item_link and item_link != "err" and item_link not in self.item_link_list :
                    self.item_link_list.append(item_link)
            except Exception as e:
                print(f"fail get item links for {self.site_name} at index {i}: {item_link} {e}")
                capture_and_send_screenshot(get_item_driver, self.site_name, DISCORD_WEBHOOK)
                break
        
        db_item_links = self.db_get_item_links()
        _item_link_list = list(set(self.item_link_list) - set(db_item_links))
        print(f"For {self.site_name}, new item links found: {len(_item_link_list)}")
        if _item_link_list:
            message_attributes = {
                "is_scanning": {'DataType': 'String', 'StringValue': "1"},
                "scanned_site": {'DataType': 'String', 'StringValue': self.site_name},
                "num_item_links": {'DataType': 'String', 'StringValue': str(len(_item_link_list))}
            }
            try:
                publish_to_sns(SNS_ARN, _item_link_list, message_attributes, REGION)
            except Exception as e:
                print(f"Failed to publish to SNS for {self.site_name}: {e}")
        else:
            print(f"No new item links to publish for {self.site_name}")

class RULI_WEB(PAGES):
    """루리웹 핫딜 게시판 스캔을 담당하는 클래스입니다."""
    def __init__(self):
        """RULI_WEB 클래스 생성자입니다."""
        super().__init__("RULI_WEB")
        
    def get_item_links(self, driver):
        """
        루리웹 핫딜 게시판에서 새로운 아이템 링크를 수집하고 SNS로 발행합니다.
        (퀘이사존과 유사한 로직, CSS 선택자 사용)
        :param driver: Selenium WebDriver 객체
        """
        get_item_driver = driver
        try:
            get_item_driver.get(self.config['url'])
        except Exception as e:
            print(f"{self.config['url']} 접속 실패 {str(e)}")
            return
        
        item_link_selector_template = self.config['scanner_item_link_selector_template']
        for i in self.config['scanner_item_link_range']:
            try:
                find_css_selector = item_link_selector_template.format(i)
                item_link = "err"
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector)
                item_link = item.get_attribute("href")
                if item_link and item_link != "err" and item_link not in self.item_link_list :
                    self.item_link_list.append(item_link)
            except Exception as e:
                print(f"fail get item links for {self.site_name} at index {i}: {item_link} {e}")
                capture_and_send_screenshot(get_item_driver, self.site_name, DISCORD_WEBHOOK)
                break
        
        db_item_links = self.db_get_item_links()
        _item_link_list = list(set(self.item_link_list) - set(db_item_links))
        print(f"For {self.site_name}, new item links found: {len(_item_link_list)}")
        if _item_link_list:
            message_attributes = {
                "is_scanning": {'DataType': 'String', 'StringValue': "1"},
                "scanned_site": {'DataType': 'String', 'StringValue': self.site_name},
                "num_item_links": {'DataType': 'String', 'StringValue': str(len(_item_link_list))}
            }
            try:
                publish_to_sns(SNS_ARN, _item_link_list, message_attributes, REGION)
            except Exception as e:
                print(f"Failed to publish to SNS for {self.site_name}: {e}")
        else:
            print(f"No new item links to publish for {self.site_name}")
            
class FM_KOREA(PAGES):
    """FM코리아 핫딜 게시판 스캔을 담당하는 클래스입니다."""
    def __init__(self):
        """FM_KOREA 클래스 생성자입니다."""
        super().__init__("FM_KOREA")
        
    def get_item_links(self, driver):
        """
        FM코리아 핫딜 게시판에서 새로운 아이템 링크를 수집하고 SNS로 발행합니다.
        (퀘이사존과 유사한 로직, CSS 선택자 사용)
        :param driver: Selenium WebDriver 객체
        """
        get_item_driver = driver
        try:
            get_item_driver.get(self.config['url'])
        except Exception as e:
            print(f"{self.config['url']} 접속 실패 {str(e)}")
            return

        item_link_selector_template = self.config['scanner_item_link_selector_template']
        for i in self.config['scanner_item_link_range']:
            try:
                find_css_selector = item_link_selector_template.format(i)
                item_link = "err"
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector)
                item_link = item.get_attribute("href")
                if item_link and item_link != "err" and item_link not in self.item_link_list :
                    self.item_link_list.append(item_link)
            except Exception as e:
                print(f"fail get item links for {self.site_name} at index {i}: {item_link} {e}")
                capture_and_send_screenshot(get_item_driver, self.site_name, DISCORD_WEBHOOK)
                break
        
        db_item_links = self.db_get_item_links()
        _item_link_list = list(set(self.item_link_list) - set(db_item_links))
        print(f"For {self.site_name}, new item links found: {len(_item_link_list)}")
        if _item_link_list:
            message_attributes = {
                "is_scanning": {'DataType': 'String', 'StringValue': "1"},
                "scanned_site": {'DataType': 'String', 'StringValue': self.site_name},
                "num_item_links": {'DataType': 'String', 'StringValue': str(len(_item_link_list))}
            }
            try:
                publish_to_sns(SNS_ARN, _item_link_list, message_attributes, REGION)
            except Exception as e:
                print(f"Failed to publish to SNS for {self.site_name}: {e}")
        else:
            print(f"No new item links to publish for {self.site_name}")
                
class PPOM_PPU(PAGES):
    """뽐뿌 게시판 스캔을 담당하는 클래스입니다. (Selenium 대신 requests와 BeautifulSoup 사용)"""
    def __init__(self):
        """PPOM_PPU 클래스 생성자입니다."""
        super().__init__("PPOM_PPU")
        
    def get_item_links(self): 
        """
        뽐뿌 핫딜 게시판에서 새로운 아이템 링크를 수집하고 SNS로 발행합니다.
        이 메소드는 Selenium WebDriver를 사용하지 않고, requests와 BeautifulSoup을 사용합니다.
        """
        response = session.get(self.config['url']) # 설정된 URL로 HTTP GET 요청
        soup = bs(response.content, "html.parser") # 응답 내용을 BeautifulSoup으로 파싱
        # 설정된 CSS 클래스와 제한된 수만큼 아이템 컨테이너를 찾음
        for item in soup.find_all(class_=self.config['scanner_item_link_container_selector'])[:self.config['scanner_item_link_limit']]:
            try:
                base_url_ppomppu = "https://www.ppomppu.co.kr/zboard/" # 뽐뿌 상대 경로를 위한 기본 URL
                # 아이템의 'href' 속성(상대 경로)을 가져와 기본 URL과 결합
                item_link = base_url_ppomppu + item.attrs[self.config['scanner_item_link_attribute']]
                item_link = item_link.replace("&&", "&") # URL 내의 "&&"를 "&"로 수정 (뽐뿌 URL 특성)
                # 유효하고 중복되지 않은 링크를 리스트에 추가
                if item_link and item_link != "err" and item_link not in self.item_link_list :
                    self.item_link_list.append(item_link)
            except Exception as e:
                # 오류 발생 시, 어떤 아이템에서 오류가 났는지 확인하기 위한 정보 수집
                item_link_for_error = "undefined" 
                if 'item' in locals() and hasattr(item, 'attrs') and self.config.get('scanner_item_link_attribute') in item.attrs:
                    item_link_for_error = item.attrs[self.config['scanner_item_link_attribute']]
                print(f"fail get item links for {self.site_name} item '{item_link_for_error}' {e}")
                break # 오류 발생 시 중단
        
        # 이후 로직은 다른 Selenium 기반 스캐너와 동일 (DB 비교 및 SNS 발행)
        db_item_links = self.db_get_item_links()
        _item_link_list = list(set(self.item_link_list) - set(db_item_links))
        print(f"For {self.site_name}, new item links found: {len(_item_link_list)}")
        if _item_link_list:
            message_attributes = {
                "is_scanning": {'DataType': 'String', 'StringValue': "1"},
                "scanned_site": {'DataType': 'String', 'StringValue': self.site_name},
                "num_item_links": {'DataType': 'String', 'StringValue': str(len(_item_link_list))}
            }
            try:
                publish_to_sns(SNS_ARN, _item_link_list, message_attributes, REGION)
            except Exception as e:
                print(f"Failed to publish to SNS for {self.site_name}: {e}")
        else:
            print(f"No new item links to publish for {self.site_name}")

def handler(event=None, context=None):
    """
    AWS Lambda 핸들러 함수입니다.
    정의된 모든 사이트 스캐너를 순차적으로 실행합니다.
    :param event: AWS Lambda 이벤트 객체 (현재 스캐너에서는 직접 사용하지 않음)
    :param context: AWS Lambda 컨텍스트 객체 (현재 스캐너에서는 직접 사용하지 않음)
    :return: 처리 결과 HTTP 응답
    """
    driver = None # WebDriver 객체 초기화
    try:
        driver = set_driver() # WebDriver 설정 및 초기화
        # 스캔할 사이트 클래스 목록 정의
        sites_to_scan_classes = [QUASAR_ZONE, PPOM_PPU, FM_KOREA, RULI_WEB, ARCA_LIVE]
        
        # 각 사이트 클래스에 대해 스캔 작업 수행
        for site_class in sites_to_scan_classes:
            site_instance = site_class() # 사이트 클래스 인스턴스 생성
            current_time = time.time() # 스캔 시작 시간 기록
            print(f"Starting scan for {site_instance.site_name}...")
            try:
                # 뽐뿌(PPOM_PPU)는 WebDriver를 사용하지 않으므로 분기 처리
                if site_instance.site_name == "PPOM_PPU": 
                     site_instance.get_item_links() # WebDriver 없이 호출
                else:
                     site_instance.get_item_links(driver) # WebDriver 전달하여 호출
                # 스캔 완료 후 소요 시간 출력
                print(f"Scan for {site_instance.site_name} took {time.time() - current_time:.2f} seconds.")
            except Exception as e:
                # 특정 사이트 스캔 중 오류 발생 시 로그 출력 (핸들러는 계속 다른 사이트 스캔 시도)
                print(f"Error scanning {site_instance.site_name}: {e}")
    except Exception as e:
        # 핸들러 자체의 심각한 오류 발생 시 (예: WebDriver 초기화 실패) 로그 출력
        print(f"Critical error in handler: {e}")
    finally:
        # WebDriver가 사용된 경우 항상 종료 (자원 해제)
        if driver:
            driver.quit()
    
    # 모든 사이트 스캔 시도 후 성공 응답 반환
    return {
        "statusCode": 200, 
        "body": json.dumps({"message": "Scanner finished processing all specified sites."}),
    }

# 로컬 테스트를 위한 코드 블록
if __name__ == '__main__':
    # 핸들러 함수 직접 호출하여 로컬에서 스캐너 실행 테스트
    handler()
