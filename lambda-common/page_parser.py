# lambda-common/page_parser.py
# 웹 페이지 파싱과 관련된 기본 작업을 정의하는 클래스입니다.
# 이 클래스는 다른 사이트별 파서 클래스들의 부모 클래스로 사용될 수 있습니다.
class BasePageOperations:
    def __init__(self, site_name, config):
        '''
        BasePageOperations 클래스의 생성자입니다.

        :param site_name: 사이트의 이름 (예: "QUASAR_ZONE")
        :param config: 해당 사이트의 설정값 (SITES_CONFIG[site_name])
        '''
        self.site_name = site_name # 사이트 이름 저장
        self.config = config # 사이트 설정 저장 (SITES_CONFIG[site_name]이 전달될 것으로 예상)
        self.item_link_list = [] # 아이템 링크를 저장할 리스트 초기화

    # 공통 메서드가 생길 경우를 위한 플레이스홀더
    # 예시: 모든 사이트 파서에서 공통으로 사용될 수 있는 유틸리티 함수 등
    def _example_common_method(self):
        '''공통 메서드 예시입니다. 실제 구현은 필요에 따라 추가됩니다.'''
        pass
