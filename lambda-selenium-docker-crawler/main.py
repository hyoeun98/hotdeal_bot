# lambda-selenium-docker-crawler/main.py
# 이 파일은 AWS Lambda 함수로 실행되어, SQS로부터 크롤링할 아이템 링크 목록을 받아 Selenium을 사용하여 웹 페이지 정보를 수집하고,
# 그 결과를 다시 SQS로 전송하는 크롤러의 메인 로직을 담고 있습니다.

import json # JSON 데이터 처리를 위한 모듈
# import logging # 로깅 모듈, 현재 직접 사용되지 않아 주석 처리
import requests # HTTP 요청을 보내기 위한 모듈
import time # 시간 관련 함수 사용 (주로 사이트별 클래스에서 사용)
import re # 정규 표현식 처리를 위한 모듈 (RULI_WEB, PPOM_PPU 등에서 사용)
# import boto3 # AWS SDK, 현재 aws_utils를 통해 간접 사용되므로 주석 처리
import ast # 문자열 형태의 Python 표현식을 안전하게 평가하기 위한 모듈 (핸들러에서 메시지 파싱 fallback으로 사용)
import os # 운영체제와 상호작용하기 위한 모듈 (환경 변수 등 접근)
# from bs4 import BeautifulSoup as bs # HTML/XML 파싱 모듈, 현재 크롤러에서 직접 사용되지 않아 주석 처리
# from selenium_stealth import stealth # Selenium Stealth, 현재 webdriver_utils를 통해 처리되어 주석 처리
from selenium.webdriver.common.by import By # Selenium에서 요소를 찾기 위한 By 객체 (사이트별 클래스에서 필요)
# from selenium import webdriver # Selenium WebDriver, 현재 webdriver_utils를 통해 처리되어 주석 처리
# from selenium.webdriver.chrome.service import Service # ChromeDriver 서비스, 현재 webdriver_utils를 통해 처리되어 주석 처리
from requests.adapters import HTTPAdapter # requests 라이브러리에서 재시도 등 고급 설정을 위한 어댑터
from urllib3.util.retry import Retry # HTTP 요청 재시도 로직을 위한 클래스

# 공통 모듈 임포트
from lambda_common.config import SITES_CONFIG # 각 사이트별 설정 (셀렉터 등)
from lambda_common.page_parser import BasePageOperations # 페이지 파싱 기본 작업을 위한 부모 클래스
from lambda_common.aws_utils import send_to_sqs # SQS 메시지 전송 유틸리티
from lambda_common.webdriver_utils import set_driver # Selenium WebDriver 설정 유틸리티

# 환경 변수에서 SQS 큐 URL과 AWS 리전 정보 가져오기
QUEUE_URL = os.environ["QUEUE_URL"] # 크롤링 결과를 보낼 SQS 큐 URL
REGION = os.environ.get("REGION", "ap-northeast-2") # AWS 리전 (기본값: ap-northeast-2)

# HTTP 요청을 위한 Session 설정 (재시도 로직 포함)
session = requests.Session() # requests 세션 객체 생성
retry = Retry(connect=2, backoff_factor=0.5) # 연결 재시도 2회, 재시도 간격 backoff_factor 적용
adapter = HTTPAdapter(max_retries=retry) # 최대 재시도 횟수를 설정한 어댑터 생성
session.mount('http://', adapter) # HTTP 스키마에 어댑터 마운트
session.mount('https://', adapter) # HTTPS 스키마에 어댑터 마운트

class PAGES(BasePageOperations):
    """각 웹사이트 페이지 처리를 위한 기본 클래스들의 부모 클래스입니다."""
    def __init__(self, site_name): 
        """
        PAGES 클래스 생성자입니다.
        :param site_name: 처리할 사이트의 이름 (SITES_CONFIG의 키와 일치)
        """
        super().__init__(site_name, SITES_CONFIG[site_name]) # 부모 클래스(BasePageOperations) 초기화
        self.refresh_delay = 30 # 페이지 새로고침 지연 시간 (현재 사용되지 않음)
        
class QUASAR_ZONE(PAGES):
    """퀘이사존 사이트 크롤링을 담당하는 클래스입니다."""
    def __init__(self):
        """QUASAR_ZONE 클래스 생성자입니다."""
        super().__init__("QUASAR_ZONE") # 부모 클래스에 사이트 이름 "QUASAR_ZONE" 전달하여 초기화

    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        """
        설정된 CSS 선택자 또는 XPath를 사용하여 웹 페이지에서 텍스트 필드를 추출합니다.
        :param driver: Selenium WebDriver 객체
        :param config_key: SITES_CONFIG에서 사용할 선택자 키
        :param by: Selenium By 객체 (기본값: By.CSS_SELECTOR)
        :return: 추출된 텍스트 또는 오류 시 "err"
        """
        try:
            return driver.find_element(by, self.config[config_key]).text
        except Exception as e:
            # print(f"Error extracting {config_key} for {self.site_name}: {e}") # 디버깅용 로그
            return "err"

    def _extract_item_name(self, driver):
        """
        퀘이사존 게시물 제목에서 실제 아이템 이름을 추출합니다. (앞부분 태그 등 제외)
        :param driver: Selenium WebDriver 객체
        :return: 추출된 아이템 이름 또는 오류 시 "err"
        """
        try:
            full_name = driver.find_element(By.CSS_SELECTOR, self.config['crawler_item_name_selector']).text
            return " ".join(full_name.split()[2:]) # 예: "[SSD] 삼성전자 PM9A1 M.2 NVMe (1TB)" -> "삼성전자 PM9A1 M.2 NVMe (1TB)"
        except Exception as e:
            # print(f"Error extracting item name for {self.site_name}: {e}")
            return "err"

    def _extract_comments(self, driver):
        """
        게시물에서 댓글 목록을 추출합니다.
        :param driver: Selenium WebDriver 객체
        :return: 댓글 텍스트 목록 또는 오류 시 빈 리스트
        """
        try:
            comment_elements = driver.find_elements(By.CSS_SELECTOR, self.config['crawler_comment_selector'])
            return [comment.text for comment in comment_elements] if comment_elements else []
        except Exception as e:
            # print(f"Error extracting comments for {self.site_name}: {e}")
            return [] 

    def crawling(self, driver, item_link_list):
        """
        주어진 아이템 링크 목록을 순회하며 각 페이지에서 정보를 크롤링하고 SQS로 전송합니다.
        :param driver: Selenium WebDriver 객체
        :param item_link_list: 크롤링할 아이템 링크 목록
        """
        for item_link in item_link_list:
            driver.get(item_link) # 해당 아이템 링크로 이동
            # 크롤링 데이터를 저장할 딕셔너리 초기화
            data = {
                "created_at": "err", "shopping_mall_link": "err",
                "shopping_mall": "err", "price": "err",
                "item_name": "err", "delivery": "err",
                "content": "err", "comment": [], 
                "category": "err",
                "item_link": item_link # 현재 아이템 링크 저장
            }
            try:
                # 각 필드 정보 추출
                data["item_name"] = self._extract_item_name(driver)
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector')
                data["content"] = self._extract_text_field(driver, 'crawler_content_selector')
                data["comment"] = self._extract_comments(driver)
                data["category"] = self._extract_text_field(driver, 'crawler_category_selector', by=By.XPATH)
                data["shopping_mall_link"] = self._extract_text_field(driver, 'crawler_shopping_mall_link_selector', by=By.XPATH)
                data["shopping_mall"] = self._extract_text_field(driver, 'crawler_shopping_mall_selector', by=By.XPATH)
                data["price"] = self._extract_text_field(driver, 'crawler_price_selector', by=By.XPATH)
                data["delivery"] = self._extract_text_field(driver, 'crawler_delivery_selector', by=By.XPATH)
            except Exception as e:
                # 크롤링 중 주요 오류 발생 시 로그 출력
                print(f"Major error processing item link {item_link} for {self.site_name}: {str(e)}")
            finally:
                # 최종 결과 데이터 구성 (오류 발생 시 기본값 사용)
                result = {
                    "created_at" : data.get("created_at", "err"), "item_link" : item_link,
                    "shopping_mall_link" : data.get("shopping_mall_link", "err"),
                    "shopping_mall" : data.get("shopping_mall", "err"), "price" : data.get("price", "err"),
                    "item_name" : data.get("item_name", "err"), "delivery" : data.get("delivery", "err"),
                    "content" : data.get("content", "err"), "category" : data.get("category", "err"),
                    "comment" : data.get("comment", []) 
                }
                # SQS 메시지 속성 설정
                message_attributes = {
                    "is_crawling": {'DataType': 'String', 'StringValue': "1"}, # 크롤링 작업임을 표시
                    "crawled_site": {'DataType': 'String', 'StringValue': self.site_name} # 크롤링된 사이트 이름
                }
                try:
                    # SQS로 결과 데이터 전송
                    send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e:
                    # SQS 전송 실패 시 로그 출력
                    print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")

class ARCA_LIVE(PAGES):
    """아카라이브 핫딜 채널 크롤링을 담당하는 클래스입니다."""
    def __init__(self):
        """ARCA_LIVE 클래스 생성자입니다."""
        super().__init__("ARCA_LIVE")

    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        """
        설정된 CSS 선택자 또는 XPath를 사용하여 웹 페이지에서 텍스트 필드를 추출합니다.
        :param driver: Selenium WebDriver 객체
        :param config_key: SITES_CONFIG에서 사용할 선택자 키
        :param by: Selenium By 객체 (기본값: By.CSS_SELECTOR)
        :return: 추출된 텍스트 또는 오류 시 "err"
        """
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"

    def _extract_arca_details(self, driver):
        """
        아카라이브 핫딜 게시물의 표 형식 상세 정보를 추출합니다.
        (쇼핑몰 링크, 쇼핑몰, 상품명, 가격, 배송)
        :param driver: Selenium WebDriver 객체
        :return: 상세 정보 딕셔너리 또는 오류 시 기본값 "err"
        """
        details = {"shopping_mall_link": "err", "shopping_mall": "err", "item_name": "err", "price": "err", "delivery": "err"}
        try:
            table = driver.find_element(By.TAG_NAME, self.config['crawler_table_selector']) # 표 요소 찾기
            rows = table.find_elements(By.TAG_NAME, "tr") # 표의 모든 행(row) 가져오기
            row_texts = [row.text for row in rows] # 각 행의 텍스트 추출
            if len(row_texts) >=5: # 최소 5줄의 정보가 있는지 확인
                details["shopping_mall_link"] = "".join(row_texts[0].split()[1:]) # "쇼핑몰 링크: 링크" -> "링크"
                details["shopping_mall"] = "".join(row_texts[1].split()[1:])
                details["item_name"] = "".join(row_texts[2].split()[1:])
                details["price"] = "".join(row_texts[3].split()[1:])
                details["delivery"] = "".join(row_texts[4].split()[1:])
        except Exception: pass # 오류 발생 시 무시하고 기본값 반환
        return details

    def _extract_comments(self, driver):
        """
        게시물에서 댓글 목록을 추출합니다.
        :param driver: Selenium WebDriver 객체
        :return: 댓글 텍스트 목록 또는 오류 시 빈 리스트
        """
        try:
            comment_box = driver.find_element(By.CSS_SELECTOR, self.config['crawler_comment_box_selector']) # 댓글 영역 요소
            comment_elements = comment_box.find_elements(By.CLASS_NAME, self.config['crawler_comment_text_selector']) # 댓글 텍스트 요소들
            return [comment.text for comment in comment_elements]
        except Exception: return []

    def crawling(self, driver, item_link_list):
        """
        주어진 아이템 링크 목록을 순회하며 각 페이지에서 정보를 크롤링하고 SQS로 전송합니다.
        :param driver: Selenium WebDriver 객체
        :param item_link_list: 크롤링할 아이템 링크 목록
        """
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err",
                    "item_name": "err", "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                arca_details = self._extract_arca_details(driver) # 표 정보 추출
                data.update(arca_details) # 추출된 상세 정보로 data 딕셔너리 업데이트
                data["content"] = self._extract_text_field(driver, 'crawler_content_selector')
                data["comment"] = self._extract_comments(driver)
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector')
                data["category"] = self._extract_text_field(driver, 'crawler_category_selector', by=By.XPATH)
            except Exception as e: print(f"Major error processing item link {item_link} for {self.site_name}: {str(e)}")
            finally:
                result = {key: data.get(key, "err" if key != "comment" else []) for key in data} # 댓글 외 필드는 오류 시 "err"
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")

class RULI_WEB(PAGES):
    """루리웹 핫딜 게시판 크롤링을 담당하는 클래스입니다."""
    def __init__(self): super().__init__("RULI_WEB") # 부모 클래스 초기화
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        """텍스트 필드 추출 (ARCA_LIVE와 동일)"""
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"
    def _extract_item_name(self, driver):
        """게시물 제목(아이템 이름) 추출"""
        try: return driver.find_element(By.CSS_SELECTOR, self.config['crawler_item_name_selector']).text
        except Exception: return "err"
    def _extract_shopping_mall(self, item_name_text):
        """
        아이템 이름 텍스트에서 쇼핑몰 정보([쇼핑몰명])를 추출합니다.
        :param item_name_text: 아이템 이름 텍스트
        :return: 추출된 쇼핑몰 이름 또는 오류 시 "err"
        """
        if item_name_text == "err": return "err"
        try: match = re.findall(r"\[.+\]", item_name_text); return match[0] if match else "err" # 정규식으로 "[...]" 부분 추출
        except Exception: return "err"
    def _extract_content(self, driver):
        """게시물 내용 추출 (태그 이름 사용)"""
        try: return driver.find_element(By.TAG_NAME, self.config['crawler_content_selector']).text 
        except Exception: return "err"
    def _extract_comments(self, driver):
        """댓글 목록 추출 (클래스 이름 사용)"""
        try: comment_elements = driver.find_elements(By.CLASS_NAME, self.config['crawler_comment_selector']); return [c.text for c in comment_elements] 
        except Exception: return []
    def crawling(self, driver, item_link_list):
        """루리웹 크롤링 로직"""
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", "item_name": "err", 
                    "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                data["item_name"] = self._extract_item_name(driver)
                data["shopping_mall"] = self._extract_shopping_mall(data["item_name"]) # 아이템 이름에서 쇼핑몰 추출
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector')
                data["content"] = self._extract_content(driver)
                data["comment"] = self._extract_comments(driver)
                data["shopping_mall_link"] = self._extract_text_field(driver, 'crawler_shopping_mall_link_selector')
                data["category"] = self._extract_text_field(driver, 'crawler_category_selector', by=By.XPATH)
            except Exception as e: print(f"Major error processing {item_link} for {self.site_name}: {e}")
            finally:
                result = {key: data.get(key, "err" if key != "comment" else []) for key in data}
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")

class FM_KOREA(PAGES):
    """FM코리아 핫딜 게시판 크롤링을 담당하는 클래스입니다."""
    def __init__(self): super().__init__("FM_KOREA")
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        """텍스트 필드 추출 (ARCA_LIVE와 동일)"""
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"
    def _extract_fm_korea_details(self, driver):
        """
        FM코리아 핫딜 게시물의 상세 정보를 추출합니다. 
        (쇼핑몰 링크, 쇼핑몰, 상품명, 가격, 배송비, 본문, 댓글)
        FM코리아는 'xe_content' 클래스를 가진 여러 요소에 정보가 나뉘어 있어 특별 처리가 필요합니다.
        :param driver: Selenium WebDriver 객체
        :return: 상세 정보 딕셔너리 또는 오류 시 기본값
        """
        details = {"shopping_mall_link": "err", "shopping_mall": "err", "item_name": "err", "price": "err",
                   "delivery": "err", "content": "err", "comment": []}
        try:
            # 'xe_content' 클래스를 가진 모든 요소를 가져옴
            elements = driver.find_elements(By.CLASS_NAME, self.config['crawler_details_container_selector']) 
            if len(elements) >= 6: # 최소 6개 요소가 있어야 주요 정보 추출 가능
                details["shopping_mall_link"], details["shopping_mall"], details["item_name"], \
                details["price"], details["delivery"], details["content"] = [el.text for el in elements[:6]] # 순서대로 할당
                if len(elements) > 6: details["comment"] = [el.text for el in elements[6:]] # 나머지는 댓글로 처리
        except Exception: pass
        return details
    def crawling(self, driver, item_link_list):
        """FM코리아 크롤링 로직"""
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", "item_name": "err",
                    "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                fm_details = self._extract_fm_korea_details(driver) # FM코리아용 상세 정보 추출
                data.update(fm_details)
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector')
                data["category"] = self._extract_text_field(driver, 'crawler_category_selector', by=By.XPATH)
            except Exception as e: print(f"Major error processing {item_link} for {self.site_name}: {e}")
            finally:
                result = {key: data.get(key, "err" if key != "comment" else []) for key in data}
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")
                
class PPOM_PPU(PAGES):
    """뽐뿌 게시판 크롤링을 담당하는 클래스입니다."""
    def __init__(self): super().__init__("PPOM_PPU")
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR, processing=None):
        """
        텍스트 필드를 추출하고, 선택적으로 후처리 함수를 적용합니다.
        :param driver: Selenium WebDriver 객체
        :param config_key: SITES_CONFIG에서 사용할 선택자 키
        :param by: Selenium By 객체 (기본값: By.CSS_SELECTOR)
        :param processing: 추출된 텍스트에 적용할 함수 (예: lambda x: x.strip())
        :return: 처리된 텍스트 또는 오류 시 "err"
        """
        try: text = driver.find_element(by, self.config[config_key]).text; return processing(text) if processing else text 
        except Exception: return "err"
    def _extract_shopping_mall(self, driver, current_item_name):
        """
        쇼핑몰 정보를 추출합니다. 먼저 XPath로 시도하고, 실패 시 아이템 이름에서 정규식으로 추출합니다.
        :param driver: Selenium WebDriver 객체
        :param current_item_name: 현재 아이템 이름
        :return: 쇼핑몰 이름 또는 오류 시 "err"
        """
        # XPath를 사용하여 쇼핑몰 정보 추출 시도
        shopping_mall = self._extract_text_field(driver, 'crawler_shopping_mall_selector', by=By.XPATH)
        # 아이템 이름이 있고, XPath 추출이 실패한 경우, 아이템 이름에서 추출 시도
        if current_item_name != "err" and shopping_mall == "err":
            try: match = re.match(r"\[.+\]", current_item_name); return match[0] if match else "err" # 제목 앞부분의 [...] 형식
            except Exception: return "err"
        return shopping_mall
    def crawling(self, driver, item_link_list):
        """뽐뿌 크롤링 로직"""
        for item_link in item_link_list:
            driver.get(item_link)
            # 뽐뿌는 category, comment 필드의 기본값이 다름
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", 
                    "item_name": "err", "delivery": "err", "content": "err", "comment": "err", "category": "None", "item_link": item_link}
            try:
                data["item_name"] = self._extract_text_field(driver, 'crawler_item_name_selector')
                data["content"] = self._extract_text_field(driver, 'crawler_content_selector', by=By.XPATH)
                data["comment"] = self._extract_text_field(driver, 'crawler_comment_selector', by=By.ID) 
                # '등록일 ' 문자열 제거 후처리
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector', by=By.XPATH, processing=lambda x: x.lstrip("등록일 "))
                data["shopping_mall_link"] = self._extract_text_field(driver, 'crawler_shopping_mall_link_selector', by=By.XPATH)
                data["shopping_mall"] = self._extract_shopping_mall(driver, data["item_name"]) # 뽐뿌용 쇼핑몰 추출
            except Exception as e: print(f"Major error processing {item_link} for {self.site_name}: {e}")
            finally:
                # 뽐뿌의 경우 comment는 "err", category는 "None"이 기본값
                result = {key: data.get(key, "err" if key not in ["comment", "category"] else ("err" if key == "comment" else "None")) for key in data}
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")
    
def handler(event, context):
    """
    AWS Lambda 핸들러 함수입니다.
    SQS 이벤트를 받아 해당 사이트의 크롤러를 실행하고 결과를 처리합니다.
    :param event: AWS Lambda 이벤트 객체 (SQS 메시지 포함)
    :param context: AWS Lambda 컨텍스트 객체
    :return: 처리 결과 HTTP 응답
    """
    driver = None # WebDriver 객체 초기화
    try:
        driver = set_driver() # WebDriver 설정 및 초기화
        
        sqs_record = event['Records'][0] # SQS 이벤트에서 첫 번째 레코드 가져오기
        
        # SQS 메시지 파싱 로직: SNS를 통해 전달된 경우와 직접 SQS로 전달된 경우를 모두 처리
        if 'Sns' in sqs_record: 
            # 표준 경로: SQS 메시지 본문에 SNS 알림이 포함된 경우 (실제 운영 환경)
            # SQS body는 SNS 알림 전체를 담고 있는 JSON 문자열임
            sns_message_payload = json.loads(sqs_record['body']) 
            message_attributes = sns_message_payload['MessageAttributes'] # SNS 메시지 속성
            item_link_list_str = sns_message_payload['Message'] # SNS 메시지 본문 (아이템 링크 목록 문자열)
            item_link_list = json.loads(item_link_list_str) # 아이템 링크 목록을 JSON 파싱하여 리스트로 변환
        elif 'messageAttributes' in sqs_record and 'body' in sqs_record: 
            # 직접 SQS 메시지 (SNS를 거치지 않음, 예: 테스트용)
            message_attributes = sqs_record['messageAttributes'] # SQS 메시지 속성 직접 사용
            item_link_list = json.loads(sqs_record['body']) # SQS 메시지 본문이 아이템 링크 목록
        else: 
            # 이전 테스트 구조 또는 예기치 않은 형식을 위한 Fallback 로직
            # SQS 메시지 본문을 JSON으로 파싱하여 내부에서 MessageAttributes와 Message 추출 시도
            message_body = json.loads(sqs_record['body']) 
            message_attributes = message_body.get('MessageAttributes', {})
            item_link_list = message_body.get('Message', [])

        scanned_site = message_attributes['scanned_site']['Value'] # 메시지 속성에서 스캔된 사이트 이름 가져오기
        
        # item_link_list가 리스트가 아닌 경우 처리 (예: 문자열로 잘못 들어온 경우)
        if not isinstance(item_link_list, list):
            print(f"Warning: item_link_list is not a list: {item_link_list}. Attempting ast.literal_eval.")
            try:
                # ast.literal_eval을 사용하여 안전하게 문자열을 Python 리터럴(리스트)로 변환 시도
                item_link_list = ast.literal_eval(str(item_link_list))
                if not isinstance(item_link_list, list): item_link_list = [item_link_list] # 그래도 리스트가 아니면 단일 아이템 리스트로 만듦
            except Exception as e_parse:
                # 변환 실패 시 오류 로그 출력 및 빈 리스트로 초기화
                print(f"Could not convert item_link_list to a list: {item_link_list}. Error: {e_parse}")
                item_link_list = []

        # 사이트 이름에 해당하는 크롤러 클래스를 동적으로 가져오기
        crawler_class = globals().get(scanned_site)
        if not crawler_class:
            # 해당 사이트의 크롤러 클래스가 없는 경우 오류 발생
            print(f"Error: No crawler class found for site: {scanned_site}")
            raise ValueError(f"No crawler class found for site: {scanned_site}")
            
        crawler = crawler_class() # 크롤러 클래스 인스턴스 생성
        print(f"Starting crawling for {scanned_site} with {len(item_link_list)} links.")
        crawler.crawling(driver, item_link_list) # 크롤링 실행
            
        # 성공 응답 반환
        return {
            'statusCode': 200,
            'body': json.dumps(f'Crawling completed successfully for {scanned_site}')
        }
        
    except Exception as e:
        # 핸들러 실행 중 오류 발생 시 오류 로그 및 스택 트레이스 출력
        print(f"Error in handler: {str(e)}")
        import traceback
        traceback.print_exc()
        # 실패 응답 반환
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error during crawling: {str(e)}')
        }
    finally:
        # WebDriver가 사용된 경우 항상 종료 (자원 해제)
        if driver:
            driver.quit()

# 로컬 테스트를 위한 코드 블록
if __name__ == '__main__':
    # SQS를 통해 SNS 메시지를 받는 상황을 모의(mock)하기 위한 테스트 데이터 생성
    # 1. SNS 메시지 내용 (실제 아이템 링크 목록)
    mock_sns_message_content_str = json.dumps([
        "https://quasarzone.com/bbs/qb_saleinfo/views/1529897",
        "https://quasarzone.com/bbs/qb_saleinfo/views/1529890" 
    ])
    # 2. SNS 알림 전체 구조 모의
    mock_sns_notification = {
        "Type" : "Notification", "MessageId" : "some-message-id",
        "TopicArn" : "arn:aws:sns:ap-northeast-2:123456789012:YourSNSTopic", # 예시 ARN
        "Subject" : "Test Subject", "Message" : mock_sns_message_content_str, # 실제 메시지(링크 목록 문자열) 삽입
        "Timestamp" : "2023-01-01T00:00:00.000Z", "SignatureVersion" : "1",
        "MessageAttributes" : { # 스캐너에서 전달되는 메시지 속성들
            "scanned_site": {"Type":"String","Value":"QUASAR_ZONE"}, # 스캔된 사이트
            "num_item_links": {"Type":"String","Value":"2"}, # 아이템 링크 수
            "is_scanning": {"Type":"String","Value":"1"} # 스캐닝 작업 여부
        }
    }
    # 3. SQS 레코드 모의 (SNS 알림을 body에 포함)
    # mock_sqs_record 정의에서 "Sns": sns_message_payload 부분은 실제 SQS-SNS 연동 구조와 다름.
    # 실제로는 SQS 레코드의 'body' 필드에 SNS 메시지(JSON 문자열)가 담겨서 옴.
    # 핸들러 로직은 이 점을 반영하여 sqs_record['body']를 json.loads() 하여 사용.
    mock_sqs_record_corrected = { # 수정된 SQS 레코드
        "messageId": "sqs-message-id", "receiptHandle": "sqs-receipt-handle",
        "body": json.dumps(mock_sns_notification), # SQS의 body는 SNS 알림(JSON 문자열)
        "attributes": {}, "messageAttributes": {}, "md5OfBody": "md5-of-body",
        "eventSource": "aws:sqs", "eventSourceARN": "arn:aws:sqs:ap-northeast-2:123456789012:YourSQSQueue",
        "awsRegion": "ap-northeast-2",
    }
    # 4. Lambda 이벤트 전체 구조 모의
    mock_sqs_event = {"Records": [mock_sqs_record_corrected]} 
    
    # 테스트를 위한 환경 변수 설정 (실제 Lambda 환경에서는 자동으로 설정됨)
    os.environ.setdefault("QUEUE_URL", "your-test-sqs-queue-url") # 테스트용 SQS URL
    os.environ.setdefault("REGION", "ap-northeast-2") # 테스트용 리전
    
    # 모의 이벤트로 핸들러 함수 직접 호출
    handler(mock_sqs_event, None)
