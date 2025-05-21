import json
# import logging # Removed, not directly used
import requests
import time # Used by site classes, though not globally here
import re # Used by RULI_WEB, PPOM_PPU
# import boto3 # Removed, aws_utils handles boto3 client
import ast # Kept for fallback in handler's message parsing
import os
# from bs4 import BeautifulSoup as bs # Removed, not used in crawler
# from selenium_stealth import stealth # Removed, handled by webdriver_utils
from selenium.webdriver.common.by import By # Still needed by site classes
# from selenium import webdriver # Removed, handled by webdriver_utils
# from selenium.webdriver.chrome.service import Service # Removed, handled by webdriver_utils
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from lambda_common.config import SITES_CONFIG
from lambda_common.page_parser import BasePageOperations
from lambda_common.aws_utils import send_to_sqs
from lambda_common.webdriver_utils import set_driver 

QUEUE_URL = os.environ["QUEUE_URL"] 
REGION = os.environ.get("REGION", "ap-northeast-2")

session = requests.Session()
retry = Retry(connect=2, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

class PAGES(BasePageOperations):
    """각 Page들의 SuperClass"""
    def __init__(self, site_name): 
        super().__init__(site_name, SITES_CONFIG[site_name])
        self.refresh_delay = 30 
        
class QUASAR_ZONE(PAGES):
    def __init__(self):
        super().__init__("QUASAR_ZONE")

    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        try:
            return driver.find_element(by, self.config[config_key]).text
        except Exception as e:
            return "err"

    def _extract_item_name(self, driver):
        try:
            full_name = driver.find_element(By.CSS_SELECTOR, self.config['crawler_item_name_selector']).text
            return " ".join(full_name.split()[2:])
        except Exception as e:
            return "err"

    def _extract_comments(self, driver):
        try:
            comment_elements = driver.find_elements(By.CSS_SELECTOR, self.config['crawler_comment_selector'])
            return [comment.text for comment in comment_elements] if comment_elements else []
        except Exception as e:
            return [] 

    def crawling(self, driver, item_link_list):
        for item_link in item_link_list:
            driver.get(item_link)
            data = {
                "created_at": "err", "shopping_mall_link": "err",
                "shopping_mall": "err", "price": "err",
                "item_name": "err", "delivery": "err",
                "content": "err", "comment": [], 
                "category": "err",
                "item_link": item_link 
            }
            try:
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
                print(f"Major error processing item link {item_link} for {self.site_name}: {str(e)}")
            finally:
                result = {
                    "created_at" : data.get("created_at", "err"), "item_link" : item_link,
                    "shopping_mall_link" : data.get("shopping_mall_link", "err"),
                    "shopping_mall" : data.get("shopping_mall", "err"), "price" : data.get("price", "err"),
                    "item_name" : data.get("item_name", "err"), "delivery" : data.get("delivery", "err"),
                    "content" : data.get("content", "err"), "category" : data.get("category", "err"),
                    "comment" : data.get("comment", []) 
                }
                message_attributes = {
                    "is_crawling": {'DataType': 'String', 'StringValue': "1"},
                    "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}
                }
                try:
                    send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e:
                    print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")

class ARCA_LIVE(PAGES):
    def __init__(self):
        super().__init__("ARCA_LIVE")

    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"

    def _extract_arca_details(self, driver):
        details = {"shopping_mall_link": "err", "shopping_mall": "err", "item_name": "err", "price": "err", "delivery": "err"}
        try:
            table = driver.find_element(By.TAG_NAME, self.config['crawler_table_selector']) 
            rows = table.find_elements(By.TAG_NAME, "tr")
            row_texts = [row.text for row in rows]
            if len(row_texts) >=5: 
                details["shopping_mall_link"] = "".join(row_texts[0].split()[1:])
                details["shopping_mall"] = "".join(row_texts[1].split()[1:])
                details["item_name"] = "".join(row_texts[2].split()[1:])
                details["price"] = "".join(row_texts[3].split()[1:])
                details["delivery"] = "".join(row_texts[4].split()[1:])
        except Exception: pass 
        return details

    def _extract_comments(self, driver):
        try:
            comment_box = driver.find_element(By.CSS_SELECTOR, self.config['crawler_comment_box_selector'])
            comment_elements = comment_box.find_elements(By.CLASS_NAME, self.config['crawler_comment_text_selector']) 
            return [comment.text for comment in comment_elements]
        except Exception: return []

    def crawling(self, driver, item_link_list):
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err",
                    "item_name": "err", "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                arca_details = self._extract_arca_details(driver)
                data.update(arca_details) 
                data["content"] = self._extract_text_field(driver, 'crawler_content_selector')
                data["comment"] = self._extract_comments(driver)
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector')
                data["category"] = self._extract_text_field(driver, 'crawler_category_selector', by=By.XPATH)
            except Exception as e: print(f"Major error processing item link {item_link} for {self.site_name}: {str(e)}")
            finally:
                result = {key: data.get(key, "err" if key != "comment" else []) for key in data}
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")

class RULI_WEB(PAGES):
    def __init__(self): super().__init__("RULI_WEB")
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"
    def _extract_item_name(self, driver):
        try: return driver.find_element(By.CSS_SELECTOR, self.config['crawler_item_name_selector']).text
        except Exception: return "err"
    def _extract_shopping_mall(self, item_name_text):
        if item_name_text == "err": return "err"
        try: match = re.findall(r"\[.+\]", item_name_text); return match[0] if match else "err"
        except Exception: return "err"
    def _extract_content(self, driver):
        try: return driver.find_element(By.TAG_NAME, self.config['crawler_content_selector']).text # Uses By
        except Exception: return "err"
    def _extract_comments(self, driver):
        try: comment_elements = driver.find_elements(By.CLASS_NAME, self.config['crawler_comment_selector']); return [c.text for c in comment_elements] # Uses By
        except Exception: return []
    def crawling(self, driver, item_link_list):
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", "item_name": "err", 
                    "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                data["item_name"] = self._extract_item_name(driver)
                data["shopping_mall"] = self._extract_shopping_mall(data["item_name"]) 
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
    def __init__(self): super().__init__("FM_KOREA")
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR):
        try: return driver.find_element(by, self.config[config_key]).text
        except Exception: return "err"
    def _extract_fm_korea_details(self, driver):
        details = {"shopping_mall_link": "err", "shopping_mall": "err", "item_name": "err", "price": "err",
                   "delivery": "err", "content": "err", "comment": []}
        try:
            elements = driver.find_elements(By.CLASS_NAME, self.config['crawler_details_container_selector']) # Uses By
            if len(elements) >= 6:
                details["shopping_mall_link"], details["shopping_mall"], details["item_name"], \
                details["price"], details["delivery"], details["content"] = [el.text for el in elements[:6]]
                if len(elements) > 6: details["comment"] = [el.text for el in elements[6:]]
        except Exception: pass
        return details
    def crawling(self, driver, item_link_list):
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", "item_name": "err",
                    "delivery": "err", "content": "err", "comment": [], "category": "err", "item_link": item_link}
            try:
                fm_details = self._extract_fm_korea_details(driver)
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
    def __init__(self): super().__init__("PPOM_PPU")
    def _extract_text_field(self, driver, config_key, by=By.CSS_SELECTOR, processing=None):
        try: text = driver.find_element(by, self.config[config_key]).text; return processing(text) if processing else text # Uses By
        except Exception: return "err"
    def _extract_shopping_mall(self, driver, current_item_name):
        shopping_mall = self._extract_text_field(driver, 'crawler_shopping_mall_selector', by=By.XPATH)
        if current_item_name != "err" and shopping_mall == "err":
            try: match = re.match(r"\[.+\]", current_item_name); return match[0] if match else "err"
            except Exception: return "err"
        return shopping_mall
    def crawling(self, driver, item_link_list):
        for item_link in item_link_list:
            driver.get(item_link)
            data = {"created_at": "err", "shopping_mall_link": "err", "shopping_mall": "err", "price": "err", 
                    "item_name": "err", "delivery": "err", "content": "err", "comment": "err", "category": "None", "item_link": item_link}
            try:
                data["item_name"] = self._extract_text_field(driver, 'crawler_item_name_selector')
                data["content"] = self._extract_text_field(driver, 'crawler_content_selector', by=By.XPATH)
                data["comment"] = self._extract_text_field(driver, 'crawler_comment_selector', by=By.ID) 
                data["created_at"] = self._extract_text_field(driver, 'crawler_created_at_selector', by=By.XPATH, processing=lambda x: x.lstrip("등록일 "))
                data["shopping_mall_link"] = self._extract_text_field(driver, 'crawler_shopping_mall_link_selector', by=By.XPATH)
                data["shopping_mall"] = self._extract_shopping_mall(driver, data["item_name"])
            except Exception as e: print(f"Major error processing {item_link} for {self.site_name}: {e}")
            finally:
                result = {key: data.get(key, "err" if key not in ["comment", "category"] else ("err" if key == "comment" else "None")) for key in data}
                message_attributes = {"is_crawling": {'DataType': 'String', 'StringValue': "1"}, "crawled_site": {'DataType': 'String', 'StringValue': self.site_name}}
                try: send_to_sqs(QUEUE_URL, result, message_attributes, REGION)
                except Exception as e: print(f"Failed to send to SQS for {self.site_name} item {item_link}: {e}")
    
def handler(event, context):
    driver = None 
    try:
        driver = set_driver() 
        
        sqs_record = event['Records'][0]
        
        if 'Sns' in sqs_record: # Standard path: SQS message body contains SNS notification
            sns_message_payload = json.loads(sqs_record['body']) # The SQS body is the SNS notification as a JSON string
            message_attributes = sns_message_payload['MessageAttributes']
            item_link_list_str = sns_message_payload['Message']
            item_link_list = json.loads(item_link_list_str) 
        elif 'messageAttributes' in sqs_record and 'body' in sqs_record: # Direct SQS message (non-SNS, e.g. from test)
            message_attributes = sqs_record['messageAttributes'] # Message attributes are part of SQS record directly
            item_link_list = json.loads(sqs_record['body']) # Body is the list of links
        else: # Fallback for older test structure or unexpected format
            message_body = json.loads(sqs_record['body']) 
            message_attributes = message_body.get('MessageAttributes', {})
            item_link_list = message_body.get('Message', [])

        scanned_site = message_attributes['scanned_site']['Value']
        
        if not isinstance(item_link_list, list):
            print(f"Warning: item_link_list is not a list: {item_link_list}. Attempting ast.literal_eval.")
            try:
                item_link_list = ast.literal_eval(str(item_link_list))
                if not isinstance(item_link_list, list): item_link_list = [item_link_list]
            except Exception as e_parse:
                print(f"Could not convert item_link_list to a list: {item_link_list}. Error: {e_parse}")
                item_link_list = []

        crawler_class = globals().get(scanned_site)
        if not crawler_class:
            print(f"Error: No crawler class found for site: {scanned_site}")
            raise ValueError(f"No crawler class found for site: {scanned_site}")
            
        crawler = crawler_class()
        print(f"Starting crawling for {scanned_site} with {len(item_link_list)} links.")
        crawler.crawling(driver, item_link_list)
            
        return {
            'statusCode': 200,
            'body': json.dumps(f'Crawling completed successfully for {scanned_site}')
        }
        
    except Exception as e:
        print(f"Error in handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error during crawling: {str(e)}')
        }
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    mock_sns_message_content_str = json.dumps([
        "https://quasarzone.com/bbs/qb_saleinfo/views/1529897",
        "https://quasarzone.com/bbs/qb_saleinfo/views/1529890" 
    ])
    mock_sns_notification = {
        "Type" : "Notification", "MessageId" : "some-message-id",
        "TopicArn" : "arn:aws:sns:ap-northeast-2:123456789012:YourSNSTopic",
        "Subject" : "Test Subject", "Message" : mock_sns_message_content_str,
        "Timestamp" : "2023-01-01T00:00:00.000Z", "SignatureVersion" : "1",
        "MessageAttributes" : {
            "scanned_site": {"Type":"String","Value":"QUASAR_ZONE"},
            "num_item_links": {"Type":"String","Value":"2"},
            "is_scanning": {"Type":"String","Value":"1"}
        }
    }
    mock_sqs_record = {
        "messageId": "sqs-message-id", "receiptHandle": "sqs-receipt-handle",
        "body": json.dumps(mock_sns_notification), 
        "attributes": {}, "messageAttributes": {}, "md5OfBody": "md5-of-body",
        "eventSource": "aws:sqs", "eventSourceARN": "arn:aws:sqs:ap-northeast-2:123456789012:YourSQSQueue",
        "awsRegion": "ap-northeast-2",
        # Adding 'Sns' key for handler logic that checks for it (this is the more accurate structure for SNS->Lambda via SQS)
        "Sns": sns_message_payload # Re-using variable from handler, should be mock_sns_notification
    }
    # Correcting the mock_sqs_record to use mock_sns_notification for the 'Sns' key
    mock_sqs_record_corrected = {
        "messageId": "sqs-message-id", "receiptHandle": "sqs-receipt-handle",
        "body": json.dumps(mock_sns_notification), # SQS body is the SNS notification string
        "attributes": {}, "messageAttributes": {}, "md5OfBody": "md5-of-body",
        "eventSource": "aws:sqs", "eventSourceARN": "arn:aws:sqs:ap-northeast-2:123456789012:YourSQSQueue",
        "awsRegion": "ap-northeast-2",
        # The 'Sns' key is not typically part of an SQS record from an SNS trigger.
        # The SNS payload is *inside* the 'body' of the SQS record.
        # The handler logic was updated to reflect this: json.loads(sqs_record['body'])
        # then access ['MessageAttributes'] and ['Message'] from that loaded dict.
    }
    mock_sqs_event = {"Records": [mock_sqs_record_corrected]} # Use the corrected record
    
    os.environ.setdefault("QUEUE_URL", "your-test-sqs-queue-url") 
    os.environ.setdefault("REGION", "ap-northeast-2")
    handler(mock_sqs_event, None)
