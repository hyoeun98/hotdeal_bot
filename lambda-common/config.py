# lambda-common/config.py

SITES_CONFIG = {
    "QUASAR_ZONE": {
        "url": "https://quasarzone.com/bbs/qb_saleinfo",
        # Selectors for scanner (get_item_links)
        "scanner_item_link_selector_template": "#frmSearch > div > div.list-board-wrap > div.market-type-list.market-info-type-list.relative > table > tbody > tr:nth-child({}) > td:nth-child(2) > div > div.market-info-list-cont > p > a",
        "scanner_item_link_range": range(1, 31),
        # Selectors for crawler (crawling)
        "crawler_item_name_selector": "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div:nth-child(1) > h1", # Needs adjustment for splitting
        "crawler_created_at_selector": "#content > div > div.sub-content-wrap > div.left-con-wrap > div.common-view-wrap.market-info-view-wrap > div > dl > dt > div.util-area > p > span",
        "crawler_content_selector": "#new_contents",
        "crawler_comment_selector": "#content > div.sub-content-wrap > div.left-con-wrap > div.reply-wrap > div.reply-area > div.reply-list", # For multiple comments
        "crawler_category_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dt/div[3]/div/div[1]", # XPath
        "crawler_shopping_mall_link_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[1]/td", # XPath
        "crawler_shopping_mall_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[2]/td", # XPath
        "crawler_price_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[3]/td", # XPath
        "crawler_delivery_selector": "/html/body/div[2]/div/div/div/div[1]/div[1]/div[4]/div/dl/dd/table/tbody/tr[4]/td" # XPath
    },
    "ARCA_LIVE": {
        "url": "https://arca.live/b/hotdeal",
        # Scanner selectors
        "scanner_item_link_selector_template": "/html/body/div[2]/div[3]/article/div/div[6]/div[2]/div[{}]/div/a", # XPath
        "scanner_item_link_range": range(2, 27),
        # Crawler selectors
        "crawler_table_selector": "table", # For rows
        "crawler_content_selector": "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-body > div.fr-view.article-content",
        "crawler_comment_box_selector": "#comment > div.list-area",
        "crawler_comment_text_selector": ".text", # Relative to comment_box
        "crawler_created_at_selector": "body > div.root-container > div.content-wrapper.clearfix > article > div > div.article-wrapper > div.article-head > div.info-row > div.article-info.article-info-section > span:nth-child(12) > span.body > time",
        "crawler_category_selector": "/html/body/div[2]/div[3]/article/div/div[2]/div[2]/div[1]/div[2]/span" # XPath
    },
    "RULI_WEB": {
        "url": "https://bbs.ruliweb.com/market/board/1020?view=default",
        # Scanner selectors
        "scanner_item_link_selector_template": "#board_list > div > div.board_main.theme_default.theme_white.theme_white > table > tbody > tr:nth-child({}) > td.subject > div > a.deco",
        "scanner_item_link_range": range(8, 36),
        # Crawler selectors
        "crawler_item_name_selector": "#board_read > div > div.board_main > div.board_main_top > div.user_view > div:nth-child(1) > div > div > h4 > span > span.subject_inner_text",
        "crawler_created_at_selector": "#board_read > div > div.board_main > div.board_main_top > div.user_view > div.row.user_view_target > div.col.user_info_wrapper > div > p:nth-child(6) > span",
        "crawler_content_selector": "article", # Tag name
        "crawler_comment_selector": ".comment", # Class name, for multiple
        "crawler_shopping_mall_link_selector": "#board_read > div > div.board_main > div.board_main_view > div.row.relative > div > div.source_url.box_line_with_shadow > a",
        "crawler_category_selector": "/html/body/div[4]/div[2]/div[2]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]/div/div/h4/span/span[1]" # XPath
    },
    "FM_KOREA": {
        "url": "https://www.fmkorea.com/hotdeal",
        # Scanner selectors
        "scanner_item_link_selector_template": "#bd_1196365581_0 > div > div.fm_best_widget._bd_pc > ul > li:nth-child({}) > div > h3 > a",
        "scanner_item_link_range": range(1, 21),
        # Crawler selectors
        "crawler_details_container_selector": ".xe_content", # This class is used for multiple fields
        "crawler_created_at_selector": "#bd_capture > div.rd_hd.clear > div.board.clear > div.top_area.ngeb > span",
        "crawler_category_selector": "/html/body/div[1]/div/div/div/div[3]/div/div[2]/div[2]/div/div[1]/span/a" # XPath
        # Note: FM_KOREA crawler logic for details (shopping_mall_link, shopping_mall, item_name, price, delivery, content)
        # uses a list of elements with class "xe_content". This will need special handling in the refactored code.
    },
    "PPOM_PPU": {
        "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu",
        # Scanner selectors (uses requests+bs4, not selenium)
        "scanner_item_link_container_selector": ".baseList-thumb", # Class for items
        "scanner_item_link_attribute": "href",
        "scanner_item_link_limit": 20,
        # Crawler selectors
        "crawler_item_name_selector": "#topTitle > h1",
        "crawler_content_selector": "/html/body/div[1]/div[2]/div[3]/div/table[3]/tbody/tr[1]/td/table/tbody/tr/td", # XPath
        "crawler_comment_selector": "#quote", # ID
        "crawler_created_at_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[2]", # XPath, needs .lstrip("등록일 ")
        "crawler_shopping_mall_link_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/div/ul/li[4]/a", # XPath
        "crawler_shopping_mall_selector": "/html/body/div[1]/div[2]/div[3]/div/div[3]/h1/span" # XPath
    }
}

# Global constants from the scanner that might be useful if not site-specific
# QUEUE_URL = os.environ["QUEUE_URL"] # Should remain in main lambda files
# REGION = os.environ.get("REGION", "ap-northeast-2") # Should remain in main lambda files
# DB_HOST = os.environ["DB_HOST"] # Etc. these are environment specific
# DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
# SNS_ARN = os.environ["SNS_ARN"]

# Note: Some logic like splitting text (e.g., Quasar Zone item_name) or joining base URLs (e.g., Ppomppu scanner)
# will still need to be handled in the respective class methods, but the selectors themselves will come from this config.
# The FM_KOREA crawler's way of getting multiple details from elements of the same class is a special case.
# The PPOM_PPU scanner uses BeautifulSoup instead of Selenium for getting item links, this distinction is important.
