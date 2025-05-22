
# legacy/crawler.py
# 이 파일은 Kafka로부터 메시지를 소비하여 웹 페이지를 크롤링하고,
# 결과를 PostgreSQL 데이터베이스에 저장하며, 오류 발생 시 Slack 및 Discord로 알림을 보내고,
# 변환된 메시지를 다시 Kafka로 발행하는 레거시 크롤러 로직을 포함합니다.

from selenium import webdriver # Selenium WebDriver 자동화 라이브러리
from webdriver_manager.chrome import ChromeDriverManager # ChromeDriver를 쉽게 관리하기 위한 라이브러리 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver import Keys, ActionChains # 키보드 입력 및 액션 체인 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver.common.by import By # Selenium 요소 검색 전략 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver.chrome.service import Service # ChromeDriver 서비스 (현재 코드에서는 직접 사용되지 않음)
from bs4 import BeautifulSoup as bs # HTML/XML 파싱 라이브러리 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver.chrome.options import Options # Chrome WebDriver 옵션 설정
from kafka import KafkaConsumer, KafkaProducer # Apache Kafka 메시지 큐 연동 라이브러리
from collections import deque # 양방향 큐 자료구조 (현재 코드에서는 직접 사용되지 않음)
import json # JSON 데이터 직렬화/역직렬화
import re # 정규 표현식 (현재 코드에서는 직접 사용되지 않음)
from slack_sdk import WebClient # Slack API와 상호작용하기 위한 SDK
from slack_sdk.errors import SlackApiError # Slack API 오류 처리
from selenium_stealth import stealth # Selenium이 자동화 도구로 감지되는 것을 방지하는 라이브러리
import logging # 로깅 라이브러리
# import re # 중복 임포트 (위에서 이미 임포트됨)
import random # 랜덤 숫자 생성 (현재 코드에서는 직접 사용되지 않음)
import time # 시간 관련 함수 (예: sleep)
import concurrent.futures # 동시성 처리 (현재 코드에서는 직접 사용되지 않음)
from datetime import datetime # 날짜 및 시간 처리
import psycopg2 # PostgreSQL 데이터베이스 어댑터
from psycopg2 import sql # SQL 쿼리 안전하게 구성
from dotenv import load_dotenv # .env 파일에서 환경 변수 로드
import os # 운영 체제 기능 접근 (환경 변수 등)
import base64 # Base64 인코딩/디코딩 (현재 코드에서는 직접 사용되지 않음)
import requests # HTTP 요청 라이브러리
from scanner import PAGES, SITES, save_full_screenshot # 외부 'scanner' 모듈에서 클래스 및 함수 임포트 (PAGES, SITES는 크롤링 대상 사이트 정보 및 로직 포함 추정)

load_dotenv() # .env 파일에서 환경 변수 로드

# 주요 설정값 및 환경 변수
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL") # Slack 웹훅 URL (현재 코드에서는 직접 사용되지 않음)
SLACK_TOKEN = os.environ.get("SLACK_TOKEN") # Slack API 토큰 (파일 업로드 시 사용)
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID") # Slack 채널 ID (파일 업로드 대상)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK") # Discord 웹훅 URL (알림 전송 시 사용)
DB_NAME = os.environ.get("DB_NAME") # PostgreSQL 데이터베이스 이름
DB_USER = os.environ.get("DB_USER") # PostgreSQL 사용자 이름
DB_PASSWORD = os.environ.get("DB_PASSWORD") # PostgreSQL 비밀번호
DB_HOST = os.environ.get("DB_HOST") # PostgreSQL 호스트 주소
DB_PORT = os.environ.get("DB_PORT") # PostgreSQL 포트

def set_driver():
    """
    Selenium WebDriver를 설정하고 초기화합니다.
    Headless 모드로 실행되며, 웹사이트의 감지를 피하기 위해 여러 옵션과 selenium-stealth가 적용됩니다.
    :return: 설정된 Selenium WebDriver 객체
    """
    chrome_options = Options()
    # 자동화 탐지를 피하기 위한 실험적 옵션들
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) # "Chrome이 자동화된 테스트 소프트웨어에 의해 제어되고 있습니다." 메시지 숨김
    chrome_options.add_experimental_option('useAutomationExtension', False) # 자동화 확장 기능 사용 안 함

    # Headless 모드 및 기타 성능/안정성 관련 옵션
    chrome_options.add_argument("--headless") # UI 없이 백그라운드에서 실행
    chrome_options.add_argument('--blink-settings=imagesEnabled=false') # 이미지 로딩 비활성화 (크롤링 속도 향상)
    chrome_options.add_argument('--block-new-web-contents') # 새 웹 콘텐츠 차단 (팝업 등 방지)
    chrome_options.add_argument('--start-maximized') # 최대화된 창으로 시작 (일부 사이트 레이아웃에 필요할 수 있음)
    chrome_options.add_argument('--no-sandbox') # Chrome 샌드박스 비활성화 (Docker 등 특정 환경에서 필요)
    chrome_options.add_argument('--disable-gpu') # GPU 가속 비활성화 (headless 환경에서 불필요)
    # chrome_options.add_argument('--window-size=1920x1080') # 특정 창 크기 설정 (주석 처리됨)
    chrome_options.add_argument("--disable-extensions") # 확장 프로그램 비활성화
    driver = webdriver.Chrome(options = chrome_options) # 설정된 옵션으로 Chrome WebDriver 인스턴스 생성
    
    # selenium-stealth 적용: 웹 드라이버가 자동화 도구로 감지되는 것을 방지
    stealth(driver,
        languages=['en-US','en'], # 선호 언어 설정
        vendor='Google Inc.', # 브라우저 공급업체 설정
        platform='Win32', # 운영체제 플랫폼 설정 (Windows로 위장)
        webgl_vendor='Intel Inc.', # WebGL 벤더 설정
        renderer='Intel Iris OpenGL Engine', # WebGL 렌더러 설정
        fix_hairline=True, # 헤어라인 이슈 수정
    )
    driver.implicitly_wait(10) # 암시적 대기 시간 설정 (요소가 나타날 때까지 최대 10초 대기)
    return driver

class Crawler:
    """웹 크롤링 작업을 수행하는 메인 클래스입니다."""
    def __init__(self):
        """Crawler 클래스 생성자입니다. WebDriver를 초기화합니다."""
        self.driver = set_driver() # WebDriver 인스턴스 생성 및 할당
            
    def send_discord(self, **kwargs):
        """
        Discord 웹훅을 통해 간단한 메시지를 전송합니다.
        :param kwargs: page (사이트 이름), item_link (아이템 링크) 등을 포함하는 키워드 인자
        """
        # Discord로 보낼 데이터 구성
        data = {
            "content" :f"""page : {kwargs["page"]}
            item_link : {kwargs["item_link"]}
                        """
        }
        data = json.dumps(data) # 데이터를 JSON 문자열로 변환
        # Discord 웹훅 URL로 POST 요청 전송
        response = requests.post(DISCORD_WEBHOOK, data = data, headers={"Content-Type": "application/json"})

        # 응답 확인
        if response.status_code == 204: # 성공 (No Content)
            logging.info(f"Message insert, {kwargs['item_link']}")
        else: # 실패
            logging.error(f"Failed to send message: {response.status_code}, {response.text} {kwargs['item_link']}")
            
    def crawling_error_logging(self, e: Exception, error_type: str, item_link: str, **kwargs):
        """
        크롤링 중 발생한 오류를 로깅하고, 스크린샷을 찍어 Slack으로 전송하며, 데이터베이스에 오류 정보를 기록합니다.
        :param e: 발생한 예외 객체
        :param error_type: 오류 유형을 설명하는 문자열
        :param item_link: 오류가 발생한 아이템 링크
        :param kwargs: 추가적인 오류 정보를 담은 키워드 인자
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')  # 현재 시간을 '년월일_시분초' 형식으로 포맷팅
        error_log = {"error_log": str(e), "time": timestamp, "error_type": error_type} # 기본 오류 정보 구성
        screenshot_filename = f'error_screenshot/{self.__class__.__name__}_{timestamp}.png' # 스크린샷 파일명 생성
        
        # 전체 페이지 스크린샷 저장 (scanner 모듈의 함수 사용)
        save_full_screenshot(self.driver, screenshot_filename) 
        
        if kwargs: # 추가 정보가 있으면 error_log에 추가
            for k, v_arg in kwargs.items(): # kwargs.items()로 수정
                error_log[k] = v_arg
        
        try:
            # 스크린샷 파일이 존재하면 Slack으로 업로드
            if os.path.exists(screenshot_filename):
                with open(screenshot_filename, 'rb') as file: # 파일을 바이너리 읽기 모드로 열기
                    response = crawler_client.files_upload_v2( # Slack 파일 업로드 API v2 사용
                        channel=SLACK_CHANNEL_ID, # 업로드할 채널 ID
                        file=file, # 파일 객체
                        filename=os.path.basename(screenshot_filename),  # 파일 이름
                        initial_comment=str(error_log)  # 업로드 시 함께 보낼 메시지 (오류 정보)
                    )
                logging.info(f"File uploaded successfully: {response['file']['permalink']}")
        except SlackApiError as slack_e: # Slack API 오류 발생 시
            logging.error(f"Error uploading file to Slack: {slack_e.response['error']}")
        except Exception as general_e: # 기타 파일 처리 또는 Slack 연동 오류
             logging.error(f"General error during Slack upload: {general_e}")

        try:
            # 데이터베이스에 오류 정보 기록
            # self.__class__.__name__은 현재 클래스 이름 (Crawler)
            # str(error_log)는 오류 정보를 문자열로 변환
            crawler_cursor.execute(crawling_error_insert_query, (self.__class__.__name__, str(error_log), timestamp, item_link))
            crawler_connection.commit() # 변경사항 커밋
        except Exception as db_e:
            # DB 오류 발생 시 로그 출력 및 롤백
            logging.error(f"Error inserting error log to DB: {db_e}")
            crawler_connection.rollback()
    
    def consume_pages(self):
        """
        Kafka 컨슈머로부터 메시지(크롤링할 페이지 정보)를 지속적으로 수신하고 처리합니다.
        """
        for message in consumer: # Kafka 컨슈머가 수신하는 각 메시지에 대해 반복
            page = message.key # 메시지 키 (사이트 이름으로 사용)
            item_link = message.value # 메시지 값 (크롤링할 아이템 링크)
            logging.info(f"Received message: key={page}, value={item_link}")
            
            # self.send_discord(page = page, item_link = item_link) # Discord 알림 (주석 처리됨)
            
            if item_link is not None: # 아이템 링크가 있는 경우
                self.crawling(page, item_link) # 크롤링 수행
                time.sleep(1) # 다음 메시지 처리 전 1초 대기
            else:
                logging.info(f"Received None item_link for page: {page}")
            
    def crawling(self, page: str, item_link: str):
        """
        지정된 페이지(사이트)의 아이템 링크를 크롤링하고, 결과를 데이터베이스에 저장하며, Kafka로 발행합니다.
        :param page: 크롤링할 사이트의 이름 (SITES 딕셔너리의 키)
        :param item_link: 크롤링할 특정 아이템의 URL
        """
        # SITES 딕셔너리 (scanner 모듈에서 임포트)에 해당 페이지 정보가 없으면 오류 발생
        if page not in SITES:
            raise TypeError(f"Invalid page name : {page}")
        
        insert_table = page.lower() # 데이터베이스 테이블 이름 (사이트 이름을 소문자로 사용)
        # 동적으로 테이블 이름을 SQL 쿼리에 삽입 (SQL 인젝션 방지를 위해 psycopg2.sql 사용)
        crawling_result_insert_query = sql.SQL(f"""
            INSERT INTO {insert_table} (created_at, item_name, item_link, shopping_mall, shopping_mall_link, price, delivery)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """)
        
        result = {} # 크롤링 결과를 담을 딕셔너리 초기화
        value = None # DB에 삽입할 값 초기화
        try:
            # SITES[page]는 해당 사이트의 크롤링 로직을 담은 객체 또는 함수로 추정됨
            # .crawling(self.driver, item_link)를 호출하여 실제 크롤링 수행
            result = SITES[page].crawling(self.driver, item_link)
            result["site"] = page # 결과에 사이트 이름 추가
            # DB에 삽입할 튜플 생성
            value = (result.get("created_at"), result.get("item_name"), item_link, 
                     result.get("shopping_mall"), result.get("shopping_mall_link"), 
                     result.get("price"), result.get("delivery"))
        except Exception as e:
            # 크롤링 중 오류 발생 시 오류 로깅 및 WebDriver 재시작
            self.crawling_error_logging(e, f"fail crawling {item_link}", item_link)
            self.driver.close() # 현재 드라이버 종료
            self.driver = set_driver() # 새 드라이버 시작
            return # 오류 발생 시 이후 DB 저장 및 Kafka 발행 로직 중단
            
        try:
            # 크롤링 결과를 데이터베이스에 삽입
            if value: # value가 정상적으로 생성되었을 경우에만 실행
                crawler_cursor.execute(crawling_result_insert_query, value)
                crawler_connection.commit() # 변경사항 커밋
                logging.info(f"success insert {item_link}")
            else:
                logging.warning(f"Value for DB insert is None for item_link: {item_link}. Crawling might have failed silently or result was empty.")
        except Exception as e:
            # DB 삽입 중 오류 발생 시 롤백 및 오류 로깅
            crawler_connection.rollback()
            self.crawling_error_logging(e, f"fail insert {item_link}", item_link)
        
        # Slack 메시지 포맷 (주석 처리됨)
#         transformed_message = f'''
# # {result["item_name"]}
# - [원본 링크]({item_link})
# - [구매 링크]({result["shopping_mall_link"]})
# ```{content}```
# -# {result["created_at"]} {page}
# '''
        try:
            # 크롤링 결과를 'transformed_message' Kafka 토픽으로 발행
            # result["item_name"]이 "err"이면 메시지 키를 "fail", 아니면 "success"로 설정
            if result: # result 딕셔너리가 비어있지 않은 경우에만 전송
                producer.send(topic = 'transformed_message', value=result, key = "fail" if result.get("item_name") == "err" else "success")
            else:
                logging.warning(f"Result is empty for item_link: {item_link}. Skipping Kafka produce.")
        except Exception as e:
            # Kafka 발행 중 오류 발생 시 오류 로깅
            self.crawling_error_logging(e, f"fail publishing {item_link}", item_link)
        
if __name__ == "__main__":
    # 메인 실행 블록: 스크립트가 직접 실행될 때만 실행됨

    # PostgreSQL 데이터베이스 연결 설정
    crawler_connection = psycopg2.connect(
    dbname = DB_NAME,
    user = DB_USER,
    password = DB_PASSWORD,
    host = DB_HOST,
    port = DB_PORT
    )
    crawler_cursor = crawler_connection.cursor() # 데이터베이스 커서 생성
    
    # Slack 클라이언트 초기화 (파일 업로드 등에 사용)
    crawler_client = WebClient(token=SLACK_TOKEN)

    # 크롤링 오류 정보를 데이터베이스에 삽입하기 위한 SQL 쿼리
    # site_name_idx는 crawling_error 테이블의 외래 키 또는 사이트 식별자로 추정
    crawling_error_insert_query = sql.SQL("""
        INSERT INTO crawling_error (site_name_idx, error_log, timestamp, item_link)
        VALUES (%s, %s, %s, %s)
    """)

    # Kafka Consumer 설정
    consumer = KafkaConsumer(
        'test', # 구독할 Kafka 토픽 이름
        bootstrap_servers=['localhost:29092'], # Kafka 브로커 주소 목록
        auto_offset_reset='earliest', # 컨슈머 그룹이 처음 토픽을 구독할 때 오프셋 위치 ('earliest': 가장 오래된 메시지부터, 'latest': 가장 최신 메시지부터)
        enable_auto_commit=True, # 주기적으로 오프셋을 자동으로 커밋할지 여부
        group_id = "discord_bot", # 컨슈머 그룹 ID
        value_deserializer=lambda x: json.loads(x.decode('utf-8')), # 메시지 값을 JSON 문자열에서 Python 객체로 역직렬화
        key_deserializer=lambda x: json.loads(x.decode('utf-8')), # 메시지 키를 JSON 문자열에서 Python 객체로 역직렬화
    )
    
    # Kafka Producer 설정
    producer = KafkaProducer(
        acks=0, # 메시지 전송 성공 확인 수준 (0: 확인 안 함, 1: 리더만 확인, all: 모든 ISR 확인)
        compression_type='gzip', # 메시지 압축 타입 (None, gzip, snappy, lz4 등)
        bootstrap_servers=['localhost:29092'], # Kafka 브로커 주소 목록
        value_serializer=lambda x:json.dumps(x, default=str).encode('utf-8'), # Python 객체를 JSON 문자열로 직렬화하여 UTF-8로 인코딩
        key_serializer=lambda x:json.dumps(x, default=str).encode('utf-8') # 키도 동일하게 직렬화
    )
    
    # 로깅 설정: 'crawler.log' 파일에 INFO 레벨 이상의 로그를 기록
    logging.basicConfig(filename='crawler.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Start Crawling") # 크롤러 시작 로그 기록
    
    crawler = Crawler() # Crawler 인스턴스 생성
    crawler.consume_pages() # Kafka 메시지 소비 시작 -> 크롤링 로직 실행