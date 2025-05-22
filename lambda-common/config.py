# lambda-common/config.py
# 각 사이트별 설정을 저장하는 딕셔너리
SITES_CONFIG = {
    "QUASAR_ZONE": { # 퀘이사존 설정
        "url": "https://quasarzone.com/bbs/qb_saleinfo", # 스캔할 URL
        # 스캐너(get_item_links)용 선택자
        "scanner_item_link_selector_template": "#frmSearch > div > div.list-board-wrap > div.market-type-list.market-info-type-list.relative > table > tbody > tr:nth-child({}) > td:nth-child(2) > div > div.market-info-list-cont > p > a", # 아이템 링크 선택자 템플릿
        "scanner_item_link_range": range(1, 31), # 아이템 링크 범위
        # 크롤러(crawling)용 선택자
        "crawler_item_name_selector": "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div:nth-child(1) > h1", # 아이템 이름 선택자 (분할 필요)
        "crawler_created_at_selector": "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div.util-area > p > span", # 작성 시간 선택자
        "crawler_content_selector": "#new_contents", # 내용 선택자
        "crawler_comment_selector": "#content > div.sub-content-wrap > div.left-con-wrap > div.reply-wrap > div.reply-area > div.reply-list", # 댓글 선택자 (여러 댓글용)
        "crawler_category_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dt/div[3]/div/div[1]", # 카테고리 선택자 (XPath)
        "crawler_shopping_mall_link_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[1]/td", # 쇼핑몰 링크 선택자 (XPath)
        "crawler_shopping_mall_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[2]/td", # 쇼핑몰 선택자 (XPath)
        "crawler_price_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[3]/td", # 가격 선택자 (XPath)
        "crawler_delivery_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[4]/td" # 배송비 선택자 (XPath)
    },
    "ARCA_LIVE": { # 아카라이브 설정
        "url": "https://arca.live/b/hotdeal", # 스캔할 URL
        # 스캐너 선택자
        "scanner_item_link_selector_template": "/html/body/div[2]/div[3]/article/div/div[6]/div[2]/div[{}]/div/a", # 아이템 링크 선택자 템플릿 (XPath)
        "scanner_item_link_range": range(2, 27), # 아이템 링크 범위
        # 크롤러 선택자
        "crawler_table_selector": "table", # 테이블 선택자 (행용)
        "crawler_content_selector": "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-body > div.fr-view.article-content", # 내용 선택자
        "crawler_comment_box_selector": "#comment > div.list-area", # 댓글 상자 선택자
        "crawler_comment_text_selector": ".text", # 댓글 텍스트 선택자 (comment_box 기준)
        "crawler_created_at_selector": "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-head > div.info-row > div.article-info.article-info-section > span:nth-child(12) > span.body > time", # 작성 시간 선택자
        "crawler_category_selector": "/html/body/div[2]/div[3]/article/div/div[2]/div[2]/div[1]/div[2]/span" # 카테고리 선택자 (XPath)
    },
    "RULI_WEB": { # 루리웹 설정
        "url": "https://bbs.ruliweb.com/market/board/1020?view=default", # 스캔할 URL
        # 스캐너 선택자
        "scanner_item_link_selector_template": "#board_list > div > div.board_main.theme_default.theme_white.theme_white > table > tbody > tr:nth-child({}) > td.subject > div > a.deco", # 아이템 링크 선택자 템플릿
        "scanner_item_link_range": range(8, 36), # 아이템 링크 범위
        # 크롤러 선택자
        "crawler_item_name_selector": "#board_read > div > div.board_main > div.board_main_top > div.user_view > div:nth-child(1) > div > div > h4 > span > span.subject_inner_text", # 아이템 이름 선택자
        "crawler_created_at_selector": "#board_read > div > div.board_main > div.board_main_top > div.user_view > div.row.user_view_target > div.col.user_info_wrapper > div > p:nth-child(6) > span", # 작성 시간 선택자
        "crawler_content_selector": "article", # 내용 선택자 (태그 이름)
        "crawler_comment_selector": ".comment", # 댓글 선택자 (클래스 이름, 여러 댓글용)
        "crawler_shopping_mall_link_selector": "#board_read > div > div.board_main > div.board_main_view > div.row.relative > div > div.source_url.box_line_with_shadow > a", # 쇼핑몰 링크 선택자
        "crawler_category_selector": "/html/body/div[4]/div[2]/div[2]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]/div/div/h4/span/span[1]" # 카테고리 선택자 (XPath)
    },
    "FM_KOREA": { # FM코리아 설정
        "url": "https://www.fmkorea.com/hotdeal", # 스캔할 URL
        # 스캐너 선택자
        "scanner_item_link_selector_template": "#bd_1196365581_0 > div > div.fm_best_widget._bd_pc > ul > li:nth-child({}) > div > h3 > a", # 아이템 링크 선택자 템플릿
        "scanner_item_link_range": range(1, 21), # 아이템 링크 범위
        # 크롤러 선택자
        "crawler_details_container_selector": ".xe_content", # 세부 정보 컨테이너 선택자 (여러 필드에 사용됨)
        "crawler_created_at_selector": "#bd_capture > div.rd_hd.clear > div.board.clear > div.top_area.ngeb > span", # 작성 시간 선택자
        "crawler_category_selector": "/html/body/div[1]/div/div/div/div[3]/div/div[2]/div[2]/div/div[1]/span/a" # 카테고리 선택자 (XPath)
        # 참고: FM_KOREA 크롤러 로직은 세부 정보(shopping_mall_link, shopping_mall, item_name, price, delivery, content)를
        # "xe_content" 클래스를 가진 요소 목록에서 가져옵니다. 리팩토링된 코드에서 특별한 처리가 필요합니다.
    },
    "PPOM_PPU": { # 뽐뿌 설정
        "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu", # 스캔할 URL
        # 스캐너 선택자 (selenium 대신 requests+bs4 사용)
        "scanner_item_link_container_selector": ".baseList-thumb", # 아이템 링크 컨테이너 선택자 (아이템용 클래스)
        "scanner_item_link_attribute": "href", # 아이템 링크 속성
        "scanner_item_link_limit": 20, # 아이템 링크 제한
        # 크롤러 선택자
        "crawler_item_name_selector": "#topTitle > h1", # 아이템 이름 선택자
        "crawler_content_selector": "/html/body/div[1]/div[2]/div[3]/div/table[3]/tbody/tr[1]/td/table/tbody/tr/td", # 내용 선택자 (XPath)
        "crawler_comment_selector": "#quote", # 댓글 선택자 (ID)
        "crawler_created_at_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[2]", # 작성 시간 선택자 (XPath, "등록일 " 제거 필요)
        "crawler_shopping_mall_link_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[4]/a", # 쇼핑몰 링크 선택자 (XPath)
        "crawler_shopping_mall_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/h1/span" # 쇼핑몰 선택자 (XPath)
    }
}

# 사이트별이 아닌 경우 스캐너의 전역 상수 (주요 람다 파일에 남아 있어야 함)
# QUEUE_URL = os.environ["QUEUE_URL"] # 기본 람다 파일에 있어야 합니다.
# REGION = os.environ.get("REGION", "ap-northeast-2") # 기본 람다 파일에 있어야 합니다.
# DB_HOST = os.environ["DB_HOST"] # 등등. 환경별 설정입니다.
# DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
# SNS_ARN = os.environ["SNS_ARN"]

# 참고: 텍스트 분할(예: Quasar Zone item_name) 또는 기본 URL 결합(예: Ppomppu 스캐너)과 같은 일부 로직은
# 각 클래스 메서드에서 계속 처리해야 하지만 선택자 자체는 이 구성에서 가져옵니다.
# FM_KOREA 크롤러가 동일한 클래스의 요소에서 여러 세부 정보를 가져오는 방식은 특수한 경우입니다.
# PPOM_PPU 스캐너는 아이템 링크를 가져오는 데 Selenium 대신 BeautifulSoup를 사용하며, 이 차이점은 중요합니다.
