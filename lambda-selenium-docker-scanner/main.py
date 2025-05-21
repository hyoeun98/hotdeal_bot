import json
# import logging # Removed, not directly used
import requests
import time
# import boto3 # Removed, aws_utils handles boto3 client
import os
from bs4 import BeautifulSoup as bs
from selenium.webdriver.common.by import By # Still needed by site classes
# from selenium.webdriver.chrome.service import Service # Removed, handled by webdriver_utils
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# from collections import defaultdict # Removed, item_link_dict seems unused
import psycopg2
# from datetime import datetime # Removed, not directly used here

from lambda_common.config import SITES_CONFIG
from lambda_common.page_parser import BasePageOperations
from lambda_common.error_utils import capture_and_send_screenshot
from lambda_common.aws_utils import publish_to_sns
from lambda_common.webdriver_utils import set_driver 

REGION = os.environ.get("REGION", "ap-northeast-2")
DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = os.environ["DB_PORT"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"] 
SNS_ARN = os.environ["SNS_ARN"] 

session = requests.Session()
retry = Retry(connect=2, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# item_link_dict = defaultdict(list) # Removed as it appeared unused
db_config = {
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST,
        "port": DB_PORT
    }

class PAGES(BasePageOperations):
    """각 Page들의 SuperClass"""
    def __init__(self, site_name):
        super().__init__(site_name, SITES_CONFIG[site_name])
        
    def db_get_item_links(self):
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            table_name = f"{self.site_name.lower()}_item_links" 
            cursor.execute(
                f"""
                SELECT item_link 
                FROM {table_name}
                WHERE created_at > NOW() - INTERVAL '3 days'; 
                """
            )
            rows = cursor.fetchall()
            db_item_links = [i[0] for i in rows]
            return db_item_links
        
        except Exception as e:
            print(f"Error getting item links from DB for {self.site_name}: {str(e)}")
            return [] 
        
class QUASAR_ZONE(PAGES):
    def __init__(self):
        super().__init__("QUASAR_ZONE") 
        
    def get_item_links(self, driver):
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
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector) # Uses By
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

class ARCA_LIVE(PAGES):
    def __init__(self):
        super().__init__("ARCA_LIVE")
        
    def get_item_links(self, driver):
        get_item_driver = driver
        try:
            get_item_driver.get(self.config['url'])
        except Exception as e:
            print(f"{self.config['url']} 접속 실패 {str(e)}")
            return
        
        item_link_selector_template = self.config['scanner_item_link_selector_template']
        for i in self.config['scanner_item_link_range']:
            try:
                find_xpath_selector = item_link_selector_template.format(i)
                item_link = "err"
                item = get_item_driver.find_element(By.XPATH, find_xpath_selector) # Uses By
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
    def __init__(self):
        super().__init__("RULI_WEB")
        
    def get_item_links(self, driver):
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
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector) # Uses By
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
    def __init__(self):
        super().__init__("FM_KOREA")
        
    def get_item_links(self, driver):
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
                item = get_item_driver.find_element(By.CSS_SELECTOR, find_css_selector) # Uses By
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
    def __init__(self):
        super().__init__("PPOM_PPU")
        
    def get_item_links(self): 
        response = session.get(self.config['url'])
        soup = bs(response.content, "html.parser")
        for item in soup.find_all(class_=self.config['scanner_item_link_container_selector'])[:self.config['scanner_item_link_limit']]:
            try:
                base_url_ppomppu = "https://www.ppomppu.co.kr/zboard/" 
                item_link = base_url_ppomppu + item.attrs[self.config['scanner_item_link_attribute']]
                item_link = item_link.replace("&&", "&") 
                if item_link and item_link != "err" and item_link not in self.item_link_list :
                    self.item_link_list.append(item_link)
            except Exception as e:
                item_link_for_error = "undefined" 
                if 'item' in locals() and hasattr(item, 'attrs') and self.config.get('scanner_item_link_attribute') in item.attrs:
                    item_link_for_error = item.attrs[self.config['scanner_item_link_attribute']]
                print(f"fail get item links for {self.site_name} item '{item_link_for_error}' {e}")
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

def handler(event=None, context=None):
    driver = None 
    try:
        driver = set_driver() 
        sites_to_scan_classes = [QUASAR_ZONE, PPOM_PPU, FM_KOREA, RULI_WEB, ARCA_LIVE]
        
        for site_class in sites_to_scan_classes:
            site_instance = site_class() 
            current_time = time.time()
            print(f"Starting scan for {site_instance.site_name}...")
            try:
                if site_instance.site_name == "PPOM_PPU": 
                     site_instance.get_item_links() 
                else:
                     site_instance.get_item_links(driver)
                print(f"Scan for {site_instance.site_name} took {time.time() - current_time:.2f} seconds.")
            except Exception as e:
                print(f"Error scanning {site_instance.site_name}: {e}")
    except Exception as e:
        print(f"Critical error in handler: {e}")
    finally:
        if driver:
            driver.quit()
    
    return {
        "statusCode": 200, 
        "body": json.dumps({"message": "Scanner finished processing all specified sites."}),
    }

if __name__ == '__main__':
    handler()
