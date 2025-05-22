# lambda-common/webdriver_utils.py
# Selenium WebDriver 설정을 위한 유틸리티 함수를 포함합니다.
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth

# 참고: selenium_stealth로 표준화합니다. 기존 스캐너는 stealthenium을 사용했습니다.
# 만약 stealthenium이 매우 중요했다면 이 결정은 재검토가 필요할 수 있지만,
# 현재 크롤러에서 selenium_stealth가 사용되고 있습니다.

def set_driver():
    '''
    Selenium WebDriver를 설정하고 초기화합니다.
    웹 드라이버는 headless 모드로 실행되며, 웹사이트의 감지를 피하기 위해 여러 옵션이 적용됩니다.
    :return: 설정된 Selenium WebDriver 객체
    '''
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/opt/chrome/chrome" # AWS Lambda 환경의 Chrome 바이너리 경로
    
    # 자동화 탐지를 피하기 위한 옵션들
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) # "Chrome이 자동화된 테스트 소프트웨어에 의해 제어되고 있습니다." 메시지 숨김
    chrome_options.add_experimental_option('useAutomationExtension', False) # 자동화 확장 기능 사용 안 함
    
    chrome_options.add_argument("--headless") # UI 없이 백그라운드에서 실행 (Lambda 환경 필수)
    chrome_options.add_argument('--no-sandbox') # Chrome 샌드박스 비활성화 (Lambda에서 권장)
    chrome_options.add_argument("--single-process") # 단일 프로세스로 실행 (일부 환경에서 안정성 향상)
    chrome_options.add_argument("--disable-dev-shm-usage") # /dev/shm 파티션 사용 비활성화 (Lambda에서 메모리 부족 문제 방지)
    chrome_options.add_argument('--blink-settings=imagesEnabled=false') # 이미지 로딩 비활성화 (크롤링 속도 향상)
    chrome_options.add_argument('window-size=1392x1150') # 윈도우 크기 설정 (일부 웹사이트 레이아웃에 영향)
    chrome_options.add_argument("disable-gpu") # GPU 가속 비활성화 (headless 환경에서 불필요)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") # navigator.webdriver 플래그를 false로 설정하여 자동화 탐지 회피
    
    # 사용자 에이전트 설정 (일반적인 브라우저처럼 보이도록)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument('--incognito') # 시크릿 모드로 실행 (캐시나 쿠키 최소화)
    
    service = Service(executable_path="/opt/chromedriver") # AWS Lambda 환경의 ChromeDriver 경로
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # selenium-stealth 적용: 웹 드라이버가 자동화 도구로 감지되는 것을 방지
    stealth(driver,
        languages=["en-US", "en"], # 선호 언어 설정
        vendor="Google Inc.", # 브라우저 공급업체 설정
        platform="Win32", # 운영체제 플랫폼 설정
        webgl_vendor="Intel Inc.", # WebGL 벤더 설정
        renderer="Intel Iris OpenGL Engine", # WebGL 렌더러 설정
        fix_hairline=True, # 헤어라인 이슈 수정
    )
    
    driver.implicitly_wait(10) # 암시적 대기 시간 설정 (요소가 나타날 때까지 최대 10초 대기)
    return driver
