
# legacy/scanner.py
# 이 파일은 여러 커뮤니티 사이트의 핫딜 게시판을 주기적으로 스캔하여 새로운 게시물 링크를 수집하고,
# 이를 데이터베이스와 비교하여 중복되지 않은 링크만 Kafka 토픽으로 발행하는 레거시 스캐너 로직을 포함합니다.

from selenium import webdriver # Selenium WebDriver 자동화 라이브러리
from webdriver_manager.chrome import ChromeDriverManager # ChromeDriver 관리 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver import Keys, ActionChains # 키보드 입력 및 액션 체인 (현재 코드에서는 직접 사용되지 않음)
from selenium.webdriver.common.by import By # Selenium 요소 검색 전략
from selenium.webdriver.chrome.service import Service # ChromeDriver 서비스 (현재 코드에서는 직접 사용되지 않음)
from bs4 import BeautifulSoup as bs # HTML/XML 파싱 라이브러리
from selenium.webdriver.chrome.options import Options # Chrome WebDriver 옵션 설정
from kafka import KafkaConsumer, KafkaProducer # Apache Kafka 메시지 큐 연동 라이브러리
from collections import deque # 양방향 큐 (현재 코드에서는 직접 사용되지 않음)
import json # JSON 데이터 직렬화/역직렬화
from enum import Enum # 열거형 (현재 코드에서는 직접 사용되지 않음)
from slack_sdk import WebClient # Slack API와 상호작용하기 위한 SDK
from slack_sdk.errors import SlackApiError # Slack API 오류 처리
from selenium.webdriver.remote.errorhandler import WebDriverException # WebDriver 관련 예외 처리
import requests # HTTP 요청 라이브러리 (뽐뿌 스캔 시 사용될 수 있으나, 현재는 Selenium 위주)
# from bs4 import BeautifulSoup # 중복 임포트 (위에서 bs로 이미 임포트됨)
from selenium_stealth import stealth # Selenium이 자동화 도구로 감지되는 것을 방지하는 라이브러리
import logging # 로깅 라이브러리
import re # 정규 표현식 (RULI_WEB 크롤링 로직 등에서 사용)
import random # 랜덤 숫자 생성 (현재 코드에서는 직접 사용되지 않음)
import time # 시간 관련 함수 (예: sleep, 실행 시간 측정)
import concurrent.futures # 동시성 처리 (현재 코드에서는 직접 사용되지 않음)
from datetime import datetime # 날짜 및 시간 처리
import psycopg2 # PostgreSQL 데이터베이스 어댑터
from psycopg2 import sql # SQL 쿼리 안전하게 구성
from dotenv import load_dotenv # .env 파일에서 환경 변수 로드
import os # 운영 체제 기능 접근 (환경 변수 등)
import base64 # Base64 인코딩/디코딩 (스크린샷 저장 시 사용)
# import requests # 중복 임포트

load_dotenv() # .env 파일에서 환경 변수 로드

# 스캔 대상 사이트 URL 상수 정의
ARCA_LIVE_LINK = "https://arca.live/b/hotdeal"
RULI_WEB_LINK = "https://bbs.ruliweb.com/market/board/1020?view=default"
PPOM_PPU_LINK = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
QUASAR_ZONE_LINK = "https://quasarzone.com/bbs/qb_saleinfo"
FM_KOREA_LINK = "https://www.fmkorea.com/hotdeal"

# 데이터베이스 연결 정보 및 기타 설정값 환경 변수에서 로드
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL") # Slack 웹훅 URL (현재 코드에서는 직접 사용되지 않음)
SLACK_TOKEN = os.environ.get("SLACK_TOKEN") # Slack API 토큰 (파일 업로드 시 사용)
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID") # Slack 채널 ID (파일 업로드 대상)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK") # Discord 웹훅 URL (현재 코드에서는 직접 사용되지 않음)

def set_driver():
    """
    Selenium WebDriver를 설정하고 초기화합니다. (legacy/crawler.py의 것과 동일)
    Headless 모드로 실행되며, 웹사이트의 감지를 피하기 위해 여러 옵션과 selenium-stealth가 적용됩니다.
    :return: 설정된 Selenium WebDriver 객체
    """
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--blink-settings=imagesEnabled=false')
    chrome_options.add_argument('--block-new-web-contents')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--disable-extensions")
    driver = webdriver.Chrome(options = chrome_options)
    stealth(driver,
        languages=['en-US','en'],
        vendor='Google Inc.',
        platform='Win32',
        webgl_vendor='Intel Inc.',
        renderer='Intel Iris OpenGL Engine',
        fix_hairline=True)
    driver.implicitly_wait(10) # 요소가 나타날 때까지 최대 10초 대기
    return driver

def save_full_screenshot(driver, screenshot_filename: str):
    """
    Selenium WebDriver를 사용하여 현재 페이지의 전체 스크린샷을 저장합니다.
    CDP(Chrome DevTools Protocol)를 사용하여 뷰포트를 넘어서는 전체 페이지를 캡처합니다.
    :param driver: Selenium WebDriver 객체
    :param screenshot_filename: 저장할 스크린샷 파일의 경로 및 이름
    """
    try:
        # 페이지 레이아웃 메트릭을 가져와 전체 페이지 크기 계산
        page_rect = driver.execute_cdp_cmd('Page.getLayoutMetrics', {})
        # 스크린샷 캡처 설정: 뷰포트 너머까지 캡처, 표면에서 캡처, 클리핑 영역 설정
        screenshot_config = {'captureBeyondViewport': True,
                                'fromSurface': True,
                                'clip': {'width': page_rect['cssContentSize']['width'],
                                        'height': page_rect['cssContentSize']['height'], # 이전 contentSize에서 cssContentSize로 변경되었을 수 있음
                                        'x': 0,
                                        'y': 0,
                                        'scale': 1}, # 페이지 배율
                                }
        # 페이지 스크린샷을 Base64 인코딩된 PNG 데이터로 가져옴
        base_64_png = driver.execute_cdp_cmd('Page.captureScreenshot', screenshot_config)
        # Base64 데이터를 디코딩하여 파일에 바이너리 쓰기 모드로 저장
        with open(screenshot_filename, "wb") as fh:
            fh.write(base64.urlsafe_b64decode(base_64_png['data']))
    except Exception as e:
        # 스크린샷 저장 실패 시 로그 기록 (표준 driver.save_screenshot은 주석 처리됨)
        logging.info(f"screenshot fail for {screenshot_filename}: {e}")
        # driver.save_screenshot(screenshot_filename) # 대체 스크린샷 방법 (뷰포트만 캡처 가능성)
        
def error_logging(class_name: str, driver, e: Exception, error_type: str, item_link: str, **kwargs):
    """
    오류 발생 시 로깅, 스크린샷 저장, Slack 알림 및 DB 기록을 수행합니다.
    :param class_name: 오류가 발생한 클래스의 이름 (사이트 식별용)
    :param driver: 현재 사용 중인 Selenium WebDriver 객체
    :param e: 발생한 예외 객체
    :param error_type: 오류 유형을 설명하는 문자열
    :param item_link: 오류 발생 당시 처리 중이던 아이템 링크 (없을 경우 "N/A" 등)
    :param kwargs: 추가적인 오류 정보를 담은 키워드 인자
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')  # 현재 시간을 '년월일_시분초' 형식으로 포맷팅
    error_log = {"error_log": str(e), "time": timestamp, "error_type": error_type, "item_link": item_link} # 기본 오류 정보
    screenshot_filename = f'error_screenshot/{class_name}_{timestamp}.png' # 스크린샷 파일명
    
    if kwargs: # 추가 정보가 있으면 error_log에 추가
        for k, v_arg in kwargs.items(): # kwargs.items()로 수정
            error_log[k] = v_arg
    logging.info(error_log) # 콘솔/파일에 오류 로그 기록
    
    try:
        save_full_screenshot(driver, screenshot_filename) # 전체 페이지 스크린샷 저장
        # 스크린샷 파일이 존재하면 Slack으로 업로드
        if os.path.exists(screenshot_filename):
            with open(screenshot_filename, 'rb') as file:
                response = client.files_upload_v2( # Slack 파일 업로드 API v2 사용
                    channel=SLACK_CHANNEL_ID, # 업로드할 채널 ID
                    file=file, # 파일 객체
                    filename=os.path.basename(screenshot_filename),  # 파일 이름
                    initial_comment=str(error_log)  # 업로드 시 함께 보낼 메시지 (오류 정보)
                )
            logging.info(f"File uploaded successfully to Slack: {response['file']['permalink']}")
        else:
            logging.warning(f"Screenshot file not found: {screenshot_filename}")
    except SlackApiError as slack_e: # Slack API 오류
        logging.info(f"Error uploading file to Slack: {slack_e.response['error']}")
    except Exception as general_e: # 기타 스크린샷 또는 Slack 관련 오류
        logging.error(f"General error during screenshot/Slack process: {general_e}")

    try:
        # 데이터베이스에 오류 정보 기록 (클래스 이름, 오류 로그 문자열, 타임스탬프, 아이템 링크)
        cursor.execute(error_insert_query, (class_name, str(error_log), timestamp, item_link))
        logging.info(f"Table error insert complete for {class_name}, item {item_link}")
        connection.commit() # 변경사항 커밋
    except Exception as db_e: # DB 오류
        logging.info(f"DB error during error_logging for {class_name}: {db_e}")
        logging.info(f"Table error insert fail for {class_name}, item {item_link}")
        connection.rollback() # 롤백
        
class PathFinder:
    """WebDriver 인스턴스를 관리하는 간단한 클래스입니다."""
    def __init__(self):
        """PathFinder 생성자입니다. WebDriver를 초기화합니다."""
        self.driver = set_driver() # WebDriver 인스턴스 생성
    
class PAGES:
    """
    각 사이트별 스캐너 클래스의 기본이 되는 부모 클래스입니다.
    WebDriver 인스턴스를 공유하고, 새로운 핫딜 페이지를 Kafka로 발행하는 공통 기능을 제공합니다.
    """
    def __init__(self, pathfinder: PathFinder):
        """
        PAGES 클래스 생성자입니다.
        :param pathfinder: PathFinder 인스턴스 (WebDriver를 제공)
        """
        self.refresh_delay = 30 # sec, 사이트 스캔 후 대기 시간
        self.driver = pathfinder.driver # PathFinder로부터 WebDriver 인스턴스 받기
            
    def pub_hot_deal_page(self, item_link: str):
        """
        주어진 아이템 링크가 DB에 이미 존재하는지 확인하고,
        존재하지 않으면 DB에 기록하고 Kafka 토픽('test')으로 발행합니다.
        :param item_link: 발행할 아이템 링크 URL
        """
        exists = False # 기본적으로 존재하지 않는 것으로 초기화
        try:
            # 'pages' 테이블에서 해당 item_link가 이미 있는지 확인
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pages WHERE item_link = %s)", (item_link,))
            exists_result = cursor.fetchone()
            if exists_result:
                exists = exists_result[0] # 쿼리 결과 (True/False)
        except Exception as e:
            # DB 조회 오류 시 로그 기록 (오류가 나도 일단 발행 시도는 할 수 있도록 exists는 False 유지)
            logging.error(f"Error checking item_link existence in DB for {item_link}: {e}")
            
        if not exists: # DB에 링크가 존재하지 않는 경우
            try:
                # 'pages' 테이블에 현재 클래스 이름(사이트 식별자)과 아이템 링크 기록
                logging.info(f"New item found for {self.__class__.__name__}: {item_link}. Inserting to DB and publishing to Kafka.")
                cursor.execute(page_insert_query, (self.__class__.__name__, item_link))
                connection.commit() # DB 변경사항 커밋
            except Exception as e:
                # DB 삽입 오류 시 로그 기록 및 롤백
                logging.error(f"Error inserting item_link to DB for {self.__class__.__name__} - {item_link}: {e}")
                connection.rollback()
                # DB 삽입 실패 시 Kafka 발행도 하지 않도록 여기서 중단할 수 있으나, 현재 로직은 발행 시도
            
            try:
                # Kafka 'test' 토픽으로 메시지 발행
                # 메시지 키: 현재 클래스 이름(사이트 식별자), 메시지 값: 아이템 링크
                producer.send(topic = 'test', key = self.__class__.__name__, value=item_link)
                producer.flush() # 프로듀서 버퍼 비우기 (즉시 전송)
                logging.info(f"Published to Kafka: {self.__class__.__name__} - {item_link}")
            except Exception as e:
                logging.error(f"Error publishing to Kafka for {self.__class__.__name__} - {item_link}: {e}")
        else:
            logging.info(f"Item link already exists, skipping: {item_link}")
            
class ARCA_LIVE(PAGES):
    """아카라이브 핫딜 채널 스캐너 및 크롤러 클래스입니다."""
    # 주석: shopping_mall_link, shopping_mall, item_name, price, delivery, content, comment 필드를 크롤링 대상으로 함 (crawling 메소드 기준)
    def __init__(self, pathfinder: PathFinder):
        """ARCA_LIVE 클래스 생성자입니다."""
        self.site_name = ARCA_LIVE_LINK # 사이트 URL 설정
        super().__init__(pathfinder) # 부모 클래스 초기화
        
    def get_item_links(self):
        """아카라이브 핫딜 채널에서 게시물 링크를 수집하여 Kafka로 발행합니다."""
        get_item_driver = self.driver # 부모로부터 받은 드라이버 사용
        get_item_driver.get(self.site_name) # 사이트 접속
        # XPath 선택자를 사용하여 특정 범위의 게시물 링크를 반복적으로 가져옴
        for i in range(2, 46): # 예: 2번째부터 45번째 게시물까지 (XPath 인덱스는 1부터 시작할 수 있으므로 확인 필요)
            item_link = "N/A" # 오류 로깅을 위해 초기화
            try:
                # XPath 선택자 동적 생성 (i 값을 사용하여 각 게시물 선택)
                find_xpath_selector = f"/html/body/div[2]/div[3]/article/div/div[6]/div[2]/div[{i}]/div/a"
                item = get_item_driver.find_element(By.XPATH, find_xpath_selector) # XPath로 요소 찾기
                item_link = item.get_attribute("href") # 'href' 속성(링크) 추출
                self.pub_hot_deal_page(item_link) # Kafka로 발행 (DB 중복 체크 포함)
            except Exception as e:
                # 링크 수집 중 오류 발생 시 로깅 (스크린샷, Slack 알림 등 포함)
                error_logging(self.__class__.__name__, self.driver, e, f"fail get item links with selector {find_xpath_selector}", item_link)
                break # 한 번 오류 발생 시 해당 사이트 스캔 중단
                
    @staticmethod
    def crawling(driver, item_link: str) -> dict:
        """
        주어진 아이템 링크로부터 상세 정보를 크롤링합니다. (이 메소드는 scanner의 주 기능이 아닐 수 있으며, crawler.py의 잔재일 수 있습니다)
        :param driver: Selenium WebDriver 객체
        :param item_link: 크롤링할 아이템 링크 URL
        :return: 크롤링된 데이터를 담은 딕셔너리
        """
        driver.get(item_link) # 해당 아이템 링크로 이동
        # 모든 필드를 "err"로 초기화 (오류 발생 대비)
        created_at, shopping_mall_link, shopping_mall, price, item_name, delivery, content, comment_texts = \
            "err", "err", "err", "err", "err", "err", "err", []
        try: 
            # 아카라이브 게시물 구조에 맞춰 데이터 추출
            table = driver.find_element(By.TAG_NAME, "table") # 상세 정보 테이블
            rows = table.find_elements(By.TAG_NAME, "tr") # 테이블 행
            details_texts = [row.text for row in rows] # 각 행의 텍스트
            # 행 텍스트에서 각 정보 추출 (예: "쇼핑몰 링크: 링크주소" -> "링크주소")
            if len(details_texts) >= 5: # 최소 5줄 정보가 있는지 확인
                shopping_mall_link = "".join(details_texts[0].split()[1:])
                shopping_mall = "".join(details_texts[1].split()[1:])
                item_name = "".join(details_texts[2].split()[1:])
                price = "".join(details_texts[3].split()[1:])
                delivery = "".join(details_texts[4].split()[1:])
            
            content_element = driver.find_element(By.CSS_SELECTOR, "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-body > div.fr-view.article-content")
            content = content_element.text # 본문 내용
            
            comment_box = driver.find_element(By.CSS_SELECTOR, "#comment > div.list-area") # 댓글 영역
            comments = comment_box.find_elements(By.CLASS_NAME, "text") # 댓글 요소들
            comment_texts = [c.text for c in comments] # 댓글 텍스트 목록
            
            created_at_element = driver.find_element(By.CSS_SELECTOR, "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-head > div.info-row > div.article-info.article-info-section > span:nth-child(12) > span.body > time")
            created_at = created_at_element.text # 작성 시간
        except Exception as e:
            # 크롤링 중 오류 발생 시 로깅 (현재 클래스명 "ARCA_LIVE", 드라이버, 예외, 오류 타입, 아이템 링크 전달)
            error_logging("ARCA_LIVE", driver, e, f"crawling error, {item_link}", item_link)
            
        finally: # 오류 발생 여부와 관계없이 최종 결과 반환
            result = {
                "created_at" : created_at, "item_link" : item_link,
                "shopping_mall_link" : shopping_mall_link, "shopping_mall" : shopping_mall,
                "price" : price, "item_name" : item_name, "delivery" : delivery,
                "content" : content, "comment": comment_texts # comment 필드 추가 (이전 코드에는 없었음)
            }
            return result

# 주석: RULI_WEB은 shopping_mall_link가 누락된 채로 게시글이 올라오는 경우가 있다고 명시되어 있음
class RULI_WEB(PAGES): # shopping_mall_link, item_name, content, comment 필드를 크롤링 대상으로 함 (crawling 메소드 기준)
    """루리웹 핫딜 게시판 스캐너 및 크롤러 클래스입니다."""
    def __init__(self, pathfinder: PathFinder):
        """RULI_WEB 클래스 생성자입니다."""
        self.site_name = RULI_WEB_LINK
        super().__init__(pathfinder)
    
    def get_item_links(self):
        """루리웹 핫딜 게시판에서 게시물 링크를 수집하여 Kafka로 발행합니다."""
        get_item_driver = self.driver
        get_item_driver.get(self.site_name)
        # 게시물 목록 전체를 나타내는 CSS 선택자
        find_css_selector_table = "#board_list > div > div.board_main.theme_default.theme_white.theme_white > table > tbody > tr"
        item_link = "N/A" # 오류 로깅용
        try:
            item_table_rows = get_item_driver.find_elements(By.CSS_SELECTOR, find_css_selector_table) # 모든 게시물 행 가져오기
            for item_row in item_table_rows: # 각 행에 대해 반복
                try:
                    # 'table_body blocktarget' 클래스를 가진 행이 실제 게시물로 추정
                    if item_row.get_attribute("class") == "table_body blocktarget":
                        # 해당 행 내부에서 제목 링크(a.deco)를 찾아 'href' 속성 추출
                        link_element = item_row.find_element(By.CSS_SELECTOR, "td.subject > div > a.deco")
                        item_link = link_element.get_attribute("href")
                        self.pub_hot_deal_page(item_link) # Kafka 발행
                    # else: 공지, BEST 핫딜 등은 건너뜀
                except Exception as inner_e: # 개별 행 처리 중 오류
                    # 현재 처리 중인 item_row의 HTML을 가져와서 로그에 포함시키면 디버깅에 도움될 수 있음
                    # error_logging 호출 시 item_link가 이전 값을 유지하거나 "N/A"일 수 있으므로 주의
                    error_logging(self.__class__.__name__, self.driver, inner_e, f"fail get item links from a row", item_link)
                    # continue # 한 행에서 오류 발생 시 다음 행으로 계속 진행
        except Exception as e: # 전체 테이블 검색 중 오류 (예: item_table_rows를 못 찾는 경우)
            error_logging(self.__class__.__name__, self.driver, e, f"fail get item links table with selector {find_css_selector_table}", item_link)
    
    @staticmethod
    def crawling(driver, item_link: str) -> dict:
        """루리웹 게시물 상세 정보를 크롤링합니다."""
        driver.get(item_link)
        created_at, shopping_mall_link, shopping_mall, price, item_name, delivery, content, comment_texts = \
            "err", "err", "err", "err", "err", "err", "err", []
        try:
            item_name_element = driver.find_element(By.CSS_SELECTOR, "#board_read > div > div.board_main > div.board_main_top > div.user_view > div:nth-child(1) > div > div > h4 > span > span.subject_inner_text")
            item_name = item_name_element.text # 아이템 이름
            # 아이템 이름에서 "[쇼핑몰명]" 형식으로 쇼핑몰 정보 추출 시도
            match = re.search(r"\[(.+?)\]", item_name) # 정규식 수정: 대괄호 안의 내용만 추출
            if match: shopping_mall = match.group(1) # 첫 번째 그룹 (대괄호 안 내용)
            
            created_at_element = driver.find_element(By.CSS_SELECTOR, "#board_read > div > div.board_main > div.board_main_top > div.user_view > div.row.user_view_target > div.col.user_info_wrapper > div > p:nth-child(6) > span")
            created_at = created_at_element.text # 작성 시간
            
            content_element = driver.find_element(By.TAG_NAME, "article") # 본문 내용 (article 태그 전체)
            content = content_element.text
            
            comment_elements = driver.find_elements(By.CLASS_NAME, "comment") # 댓글 요소들
            comment_texts = [c.text for c in comment_elements] # 댓글 텍스트 목록
            
            # 쇼핑몰 링크 추출 시도
            try:
                shopping_mall_link_element = driver.find_element(By.CSS_SELECTOR, "#board_read > div > div.board_main > div.board_main_view > div.row.relative > div > div.source_url.box_line_with_shadow > a")
                shopping_mall_link = shopping_mall_link_element.text # 링크 텍스트 (URL 자체가 아님, href를 가져와야 할 수 있음)
                # shopping_mall_link = shopping_mall_link_element.get_attribute("href") # 실제 URL을 가져오려면 이 코드 사용
            except Exception: # 쇼핑몰 링크 요소가 없는 경우
                # 본문 내용에서 URL 패턴으로 링크 추출 시도 (마지막 링크를 사용)
                url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+' # 좀 더 일반적인 URL 패턴
                found_links = re.findall(url_pattern, content)
                if found_links: shopping_mall_link = found_links[-1]
                    
        except Exception as e:
            error_logging("RULI_WEB", driver, e, f"crawling error, {item_link}", item_link)
            
        finally:
            result = {
                "created_at" : created_at, "item_link" : item_link,
                "shopping_mall_link" : shopping_mall_link, "shopping_mall" : shopping_mall,
                "price" : price, "item_name" : item_name, "delivery" : delivery,
                "content" : content, "comment": comment_texts # comment 필드 추가
            }
            return result
        
class FM_KOREA(PAGES): # shopping_mall_link, shopping_mall, item_name, price, delivery, content, comment 필드를 크롤링 대상으로 함
    """FM코리아 핫딜 게시판 스캐너 및 크롤러 클래스입니다."""
    def __init__(self, pathfinder: PathFinder):
        """FM_KOREA 클래스 생성자입니다."""
        self.site_name = FM_KOREA_LINK
        super().__init__(pathfinder)
    
    def get_item_links(self):
        """FM코리아 핫딜 게시판에서 게시물 링크를 수집하여 Kafka로 발행합니다."""
        get_item_driver = self.driver
        get_item_driver.get(self.site_name)
        item_link = "N/A"
        # CSS 선택자를 사용하여 특정 범위의 게시물 링크를 반복적으로 가져옴
        for i in range(1, 21): # 예: 1번째부터 20번째 게시물까지
            try:
                # CSS 선택자 동적 생성
                find_css_selector = f"#bd_1196365581_0 > div > div.fm_best_widget._bd_pc > ul > li:nth-child({i}) > div > h3 > a"
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector)
                item_link = item.get_attribute("href")
                self.pub_hot_deal_page(item_link)
            except Exception as e:
                error_logging(self.__class__.__name__, self.driver, e, f"fail get item links with selector {find_css_selector}", item_link)
                break 
    
    @staticmethod
    def crawling(driver, item_link: str) -> dict:
        """FM코리아 게시물 상세 정보를 크롤링합니다."""
        driver.get(item_link)
        created_at, shopping_mall_link, shopping_mall, price, item_name, delivery, content = \
            "err", "err", "err", "err", "err", "err", "err"
        comment_texts = []
        try:
            # FM코리아는 'xe_content' 클래스를 가진 여러 요소에 정보가 나뉘어 있음
            detail_elements = driver.find_elements(By.CLASS_NAME, "xe_content")
            # 각 정보 필드 추출 (요소 순서에 의존)
            if len(detail_elements) >= 6:
                shopping_mall_link = detail_elements[0].text
                shopping_mall = detail_elements[1].text
                item_name = detail_elements[2].text
                price = detail_elements[3].text
                delivery = detail_elements[4].text
                content = detail_elements[5].text
                if len(detail_elements) > 6: # 6번째 요소 이후는 댓글로 간주
                    comment_texts = [el.text for el in detail_elements[6:]]
            
            created_at_element = driver.find_element(By.CSS_SELECTOR, "#bd_capture > div.rd_hd.clear > div.board.clear > div.top_area.ngeb > span")
            created_at = created_at_element.text
        except Exception as e:
            error_logging("FM_KOREA", driver, e, f"crawling error, {item_link}", item_link)
            
        finally:
            result = {
                "created_at" : created_at, "item_link" : item_link,
                "shopping_mall_link" : shopping_mall_link, "shopping_mall" : shopping_mall,
                "price" : price, "item_name" : item_name, "delivery" : delivery,
                "content" : content, "comment": comment_texts # comment 필드 추가
            }
            return result
        
class QUASAR_ZONE(PAGES):
    """퀘이사존 핫딜 게시판 스캐너 및 크롤러 클래스입니다."""
    def __init__(self, pathfinder: PathFinder):
        """QUASAR_ZONE 클래스 생성자입니다."""
        self.site_name = QUASAR_ZONE_LINK
        super().__init__(pathfinder)
        
    def get_item_links(self):
        """퀘이사존 핫딜 게시판에서 게시물 링크를 수집하여 Kafka로 발행합니다."""
        get_item_driver = self.driver
        get_item_driver.get(self.site_name)
        item_link = "N/A"
        for i in range(1, 31): # 예: 1번째부터 30번째 게시물까지
            try:
                find_css_selector = f"#frmSearch > div > div.list-board-wrap > div.market-type-list.market-info-type-list.relative > table > tbody > tr:nth-child({i}) > td:nth-child(2) > div > div.market-info-list-cont > p > a"
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector)
                item_link = item.get_attribute("href")
                self.pub_hot_deal_page(item_link)
            except Exception as e:
                error_logging(self.__class__.__name__, self.driver, e, f"fail get item links with selector {find_css_selector}", item_link)
                break
                
    @staticmethod
    def crawling(driver, item_link: str) -> dict:
        """퀘이사존 게시물 상세 정보를 크롤링합니다."""
        driver.get(item_link)
        created_at, shopping_mall_link, shopping_mall, price, item_name, delivery, content = \
            "err", "err", "err", "err", "err", "err", "err"
        comment_texts = []
        try:
            item_name_full = driver.find_element(By.CSS_SELECTOR, "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div:nth-child(1) > h1").text
            item_name = " ".join(item_name_full.split()[2:]) # 앞의 태그 부분 제외
            
            table = driver.find_element(By.TAG_NAME, "table") # 상세 정보 테이블
            rows = table.find_elements(By.TAG_NAME, "tr") # 테이블 행
            
            created_at_element = driver.find_element(By.CSS_SELECTOR, "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div.util-area > p > span")
            created_at = created_at_element.text # 작성 시간
            
            content_element = driver.find_element(By.CSS_SELECTOR, "#new_contents")
            content = content_element.text # 본문 내용
            
            comment_elements = driver.find_elements(By.CSS_SELECTOR, "#content > div.sub-content-wrap > div.left-con-wrap > div.reply-wrap > div.reply-area > div.reply-list")
            comment_texts = [c.text for c in comment_elements] # 댓글 목록
            
            details_texts = [row.text for row in rows] # 테이블 각 행의 텍스트
            # 각 정보 추출 (순서에 의존)
            if len(details_texts) >= 4: # 최소 4줄 정보가 있는지 확인 (쇼핑몰 링크, 쇼핑몰, 가격, 배송비)
                shopping_mall_link = "".join(details_texts[0].split()[1:])
                shopping_mall = "".join(details_texts[1].split()[1:])
                price = "".join(details_texts[2].split()[1:])
                delivery = "".join(details_texts[3].split()[1:])
            
        except Exception as e:
            error_logging("QUASAR_ZONE", driver, e, f"crawling error, {item_link}", item_link)
            
        finally:
            result = {
                "created_at" : created_at, "item_link" : item_link,
                "shopping_mall_link" : shopping_mall_link, "shopping_mall" : shopping_mall,
                "price" : price, "item_name" : item_name, "delivery" : delivery,
                "content" : content, "comment": comment_texts # comment 필드 추가
            }
            return result

# 주석: PPOM_PPU는 shopping_mall이 태그되지 않은 채로 올라오는 경우가 있다고 명시됨
class PPOM_PPU(PAGES):
    """뽐뿌 핫딜 게시판 스캐너 및 크롤러 클래스입니다."""
    def __init__(self, pathfinder: PathFinder):
        """PPOM_PPU 클래스 생성자입니다."""
        self.site_name = PPOM_PPU_LINK
        super().__init__(pathfinder)
        
    def get_item_links(self):
        """뽐뿌 핫딜 게시판에서 게시물 링크를 수집하여 Kafka로 발행합니다."""
        # 뽐뿌는 Selenium 대신 requests와 BeautifulSoup을 사용할 수도 있으나, 여기서는 다른 사이트와 통일성을 위해 Selenium 사용
        # 만약 requests+bs4를 사용한다면, self.driver 대신 session 객체 사용 및 파싱 로직 변경 필요
        get_item_driver = self.driver
        get_item_driver.get(self.site_name)
        item_link = "N/A"
        # 뽐뿌 게시판 구조에 맞는 CSS 선택자 사용 (예시, 실제 구조에 따라 변경 필요)
        for i in range(8, 28): # 예시 범위, 실제 게시물 수에 따라 조정
            try:
                # CSS 선택자 (뽐뿌 구조에 맞게 수정 필요)
                # 예시: "#revolution_main_table > tbody > tr:nth-child(9) > td:nth-child(3) > table > tbody > tr > td:nth-child(2) > div > a:nth-child(2)" (제목 링크)
                find_css_selector = f"#revolution_main_table > tbody > tr:nth-child({i}) > td.baseList-space.title > div > div > a"
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector)
                item_link = item.get_attribute("href")
                self.pub_hot_deal_page(item_link)
            except Exception as e:
                error_logging(self.__class__.__name__, self.driver, e, f"fail get item links with selector {find_css_selector}", item_link)
                break # 오류 발생 시 해당 사이트 스캔 중단
          
    @staticmethod
    def crawling(driver, item_link: str) -> dict:
        """뽐뿌 게시물 상세 정보를 크롤링합니다."""
        driver.get(item_link)
        created_at, shopping_mall_link, shopping_mall, price, item_name, delivery, content, comment_text = \
            "err", "err", "err", "err", "err", "err", "err", "err" # comment는 단일 문자열로 초기화
        try:
            # 뽐뿌 게시물 상세 페이지 구조에 맞는 선택자 사용
            item_name_element = driver.find_element(By.CSS_SELECTOR, "#topTitle > h1")
            item_name = item_name_element.text
            
            content_element = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[3]/div/table[3]/tbody/tr[1]/td/table/tbody/tr/td")
            content = content_element.text
            
            # 뽐뿌는 댓글이 여러 영역에 나뉘어 있을 수 있으므로, 주 댓글 영역을 지정하거나 여러 영역을 합쳐야 할 수 있음
            # 여기서는 'quote' ID를 가진 요소의 전체 텍스트를 가져옴 (단일 댓글 또는 댓글 모음일 수 있음)
            comment_element = driver.find_element(By.ID, "quote")
            comment_text = comment_element.text # 댓글을 단일 문자열로 가져옴
            
            created_at_full = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[2]").text
            created_at = created_at_full.lstrip("등록일 ") # "등록일 " 문자열 제거
            
            try:
                shopping_mall_link_element = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[4]/a")
                shopping_mall_link = shopping_mall_link_element.text # 링크 텍스트 (URL 자체가 아닐 수 있음)
                # shopping_mall_link = shopping_mall_link_element.get_attribute("href") # 실제 URL을 가져오려면
            except Exception: # 쇼핑몰 링크가 없는 경우
                pass # "err" 유지
            
            try:
                shopping_mall_element = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[3]/div/div[3]/h1/span")
                shopping_mall = shopping_mall_element.text # 쇼핑몰 이름 (제목 옆 등에 있을 수 있음)
            except Exception: # 쇼핑몰 태그가 없는 경우
                # 아이템 이름에서 "[쇼핑몰명]" 형식으로 추출 시도
                match = re.search(r"\[(.+?)\]", item_name)
                if match: shopping_mall = match.group(1)
                    
            # 가격(price)과 배송비(delivery)는 뽐뿌 구조에 따라 별도 추출 로직 필요 (현재 "err"로 유지)
            
        except Exception as e:
            error_logging("PPOM_PPU", driver, e, f"crawling error, {item_link}", item_link)
            
        finally:
            result = {
                "created_at" : created_at, "item_link" : item_link,
                "shopping_mall_link" : shopping_mall_link, "shopping_mall" : shopping_mall,
                "price" : price, "item_name" : item_name, "delivery" : delivery,
                "content" : content, "comment": comment_text # 댓글을 단일 문자열로 전달
            }
            return result

# 스캔 대상 사이트 이름과 해당 클래스를 매핑하는 딕셔너리
SITES = {
    "ARCA_LIVE" : ARCA_LIVE,
    "PPOM_PPU" : PPOM_PPU,
    "FM_KOREA" : FM_KOREA,
    "QUASAR_ZONE" : QUASAR_ZONE,
    "RULI_WEB" : RULI_WEB,
}

def start_scanning():
    """
    스캐너의 메인 실행 함수입니다.
    PathFinder를 초기화하고, 각 사이트별 스캐너 인스턴스를 생성한 후,
    무한 루프를 돌며 주기적으로 각 사이트의 `get_item_links` 메소드를 호출하여 스캔 작업을 수행합니다.
    """
    pathfinder = PathFinder() # WebDriver를 포함하는 PathFinder 인스턴스 생성
    # 각 사이트별 스캐너 클래스 인스턴스화
    quasar_zone = QUASAR_ZONE(pathfinder)
    ppom_ppu = PPOM_PPU(pathfinder)
    fm_korea = FM_KOREA(pathfinder)
    ruli_web = RULI_WEB(pathfinder)
    arca_live = ARCA_LIVE(pathfinder)
    
    while True: # 무한 루프를 통해 주기적 스캔 수행
        try:
            # 각 사이트 스캔 시작 및 소요 시간 로깅
            current_scan_time = time.time()
            quasar_zone.get_item_links()
            logging.info(f" Quasar Zone scan finished in {time.time() - current_scan_time:.2f} seconds.")
            time.sleep(quasar_zone.refresh_delay) # 설정된 시간만큼 대기
            
            current_scan_time = time.time()
            ppom_ppu.get_item_links()
            logging.info(f" Ppomppu scan finished in {time.time() - current_scan_time:.2f} seconds.")
            time.sleep(ppom_ppu.refresh_delay)
            
            current_scan_time = time.time()
            fm_korea.get_item_links()
            logging.info(f" FM Korea scan finished in {time.time() - current_scan_time:.2f} seconds.")
            time.sleep(fm_korea.refresh_delay)
            
            current_scan_time = time.time()
            ruli_web.get_item_links()
            logging.info(f" Ruliweb scan finished in {time.time() - current_scan_time:.2f} seconds.")
            time.sleep(ruli_web.refresh_delay)
            
            current_scan_time = time.time()
            arca_live.get_item_links()
            logging.info(f" Arca Live scan finished in {time.time() - current_scan_time:.2f} seconds.")
            time.sleep(arca_live.refresh_delay)
            
        except WebDriverException as e: # WebDriver 관련 심각한 예외 발생 시
            logging.error(f"WebDriverException in main scanning loop: {e}")
            time.sleep(5) # 잠시 대기 후 재시도 (또는 드라이버 재시작 로직 추가 가능)
            
            # 오류 상황 로깅 및 Slack 알림
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_log_content = {"error_log": str(e), "time": timestamp, "error_type": "while_loop_webdriver_error"}
            screenshot_filename = f'error_screenshot/while_loop_error_{timestamp}.png'
            if pathfinder and pathfinder.driver: # 드라이버가 유효한 경우에만 스크린샷 시도
                save_full_screenshot(pathfinder.driver, screenshot_filename)
            logging.error(error_log_content)
            
            try:
                if os.path.exists(screenshot_filename):
                    with open(screenshot_filename, 'rb') as file:
                        response = client.files_upload_v2(
                            channel=SLACK_CHANNEL_ID,
                            file=file,
                            filename=os.path.basename(screenshot_filename),
                            initial_comment=str(error_log_content)
                        )
                    logging.info(f"Error screenshot uploaded to Slack: {response['file']['permalink']}")
            except Exception as slack_upload_e:
                logging.error(f"Error uploading error screenshot to Slack: {slack_upload_e}")
            
            # WebDriver 재시작 (선택적, 루프가 계속 돌면서 PathFinder가 새 드라이버를 만들도록 할 수도 있음)
            # pathfinder.driver.quit()
            # pathfinder = PathFinder() # 새 PathFinder 인스턴스 (새 드라이버)
            # Re-initialize site instances with new pathfinder if driver is recreated here
            # quasar_zone = QUASAR_ZONE(pathfinder) ... etc.

# 스크립트가 직접 실행될 때 실행되는 메인 블록
if __name__ == "__main__":
    # 로깅 설정: 'scanner.log' 파일에 INFO 레벨 이상의 로그를 기록
    # 형식: 시간 - 로그레벨 - 메시지
    logging.basicConfig(filename='scanner.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Start Scanning Process") # 스캐너 시작 로그
    
    # PostgreSQL 데이터베이스 연결
    connection = psycopg2.connect(
    dbname = DB_NAME,
    user = DB_USER,
    password = DB_PASSWORD,
    host = DB_HOST,
    port = DB_PORT
    )
    cursor = connection.cursor() # 데이터베이스 커서 생성

    # 새로운 페이지 링크를 'pages' 테이블에 삽입하기 위한 SQL 쿼리
    # site_name_idx는 pages 테이블의 외래 키 또는 사이트 식별자로 추정
    page_insert_query = sql.SQL("""
        INSERT INTO pages (site_name_idx, item_link)
        VALUES (%s, %s)
    """)

    # 오류 정보를 'error' 테이블에 삽입하기 위한 SQL 쿼리
    error_insert_query = sql.SQL("""
        INSERT INTO error (site_name_idx, error_log, timestamp, item_link)
        VALUES (%s, %s, %s, %s)
    """)

    # Slack 클라이언트 초기화 (오류 알림 시 파일 업로드 등에 사용)
    client = WebClient(token=SLACK_TOKEN)

    # Kafka Producer 설정: 메시지를 'test' 토픽으로 발행
    producer = KafkaProducer(
        acks=0, # 메시지 전송 성공 확인 수준 (0: 확인 안 함)
        compression_type='gzip', # 메시지 압축 타입
        bootstrap_servers=['localhost:29092'], # Kafka 브로커 주소 목록
        value_serializer=lambda x:json.dumps(x, default=str).encode('utf-8'), # 메시지 값을 JSON 문자열로 직렬화
        key_serializer=lambda x:json.dumps(x, default=str).encode('utf-8') # 메시지 키를 JSON 문자열로 직렬화
    )

    start_scanning() # 스캐닝 프로세스 시작