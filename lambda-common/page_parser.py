# lambda-common/page_parser.py
class BasePageOperations:
    def __init__(self, site_name, config):
        self.site_name = site_name
        self.config = config # This will be SITES_CONFIG[site_name]
        self.item_link_list = []

    # Placeholder for common methods if they arise
    def _example_common_method(self):
        pass
