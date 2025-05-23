# 핫딜 알리미 (Hot Deal Notifier)

## 프로젝트 설명
이 프로젝트는 여러 한국 온라인 커뮤니티의 "핫딜" 게시판을 주기적으로 스캔하고, 새로운 할인 정보를 감지하여 사용자에게 알림을 제공하는 자동화 시스템입니다. AWS Lambda와 Docker를 기반으로 구축되어 서버리스 환경에서 효율적으로 실행됩니다.

## 주요 기능
*   **다중 웹사이트 스캔**: 다음 웹사이트들의 핫딜 게시판에서 새로운 게시글 링크를 수집합니다:
    *   퀘이사존 (Quasar Zone)
    *   아카라이브 (Arca Live)
    *   루리웹 (Ruli Web)
    *   에펨코리아 (FM Korea)
    *   뽐뿌 (Ppomppu)
*   **상세 정보 추출**: 수집된 게시글 링크로부터 상품명, 가격, 쇼핑몰 이름/링크, 배송비, 게시글 내용, 카테고리 등의 상세 정보를 추출합니다.
*   **데이터 중복 방지**: PostgreSQL 데이터베이스를 활용하여 이미 처리된 게시글 링크를 필터링하고, 새로운 정보만 처리합니다.
*   **클라우드 기반 아키텍처**:
    *   AWS Lambda: 스캐닝 및 크롤링 로직을 서버리스 함수로 실행합니다.
    *   AWS SNS (Simple Notification Service): 스캐너 Lambda 함수가 발견한 새로운 핫딜 링크를 게시(publish)하며, 이 메시지는 크롤러 Lambda 함수의 직접적인 트리거가 됩니다.
    *   AWS SQS (Simple Queue Service): 크롤러 Lambda 함수가 처리한 상세 정보를 수신하여 후속 처리를 위해 보관합니다.
*   **오류 알림 및 로깅**:
    *   오류 발생 시 Discord 웹훅을 통해 스크린샷과 페이지 HTML 소스를 포함한 알림을 전송합니다.
    *   (암시적으로) AWS CloudWatch를 통해 Lambda 함수의 로그가 기록됩니다.
*   **효율적인 웹 스크래핑**:
    *   Selenium 및 BeautifulSoup 라이브러리를 사용하여 동적 및 정적 웹 페이지 콘텐츠를 파싱합니다.
    *   `selenium-stealth` 및 `stealthenium` 라이브러리를 적용하여 웹사이트의 봇 탐지를 우회합니다.
*   **Docker 컨테이너화**: 각 Lambda 함수(스캐너, 크롤러)는 필요한 모든 종속성을 포함하는 Docker 이미지로 패키징되어 배포됩니다.

## 기술 스택
*   **프로그래밍 언어**: Python 3.x
*   **웹 스크래핑/파싱**: Selenium, BeautifulSoup4, requests
*   **봇 탐지 우회**: `selenium-stealth`, `stealthenium`
*   **클라우드 플랫폼**: AWS
    *   **컴퓨팅**: AWS Lambda
    *   **메시징**: AWS SNS (스캐너 -> 크롤러), AWS SQS (크롤러 -> 후속 처리)
    *   **데이터베이스**: PostgreSQL (AWS RDS 또는 Lightsail 등에서 호스팅 가능)
    *   **(암시적)**: IAM (권한 관리), CloudWatch (로깅)
*   **컨테이너화**: Docker
*   **기타 라이브러리**: `boto3` (AWS SDK), `psycopg2-binary` (PostgreSQL 어댑터)

## 아키텍처
본 시스템은 두 개의 주요 AWS Lambda 함수로 구성됩니다:

1.  **`lambda-selenium-docker-scanner` (핫딜 스캐너)**:
    *   주기적으로 (예: CloudWatch Events/EventBridge 스케줄에 따라) 실행됩니다.
    *   지정된 핫딜 웹사이트들의 목록 페이지를 스캔하여 새로운 게시글의 URL을 수집합니다.
    *   수집된 URL을 PostgreSQL 데이터베이스에 저장된 기존 링크들과 비교하여, 새로운 링크만 선별합니다.
    *   새로운 링크가 발견되면, 해당 링크 목록을 AWS SNS 토픽으로 발행(publish)합니다.
    *   오류 발생 시 (예: 웹사이트 구조 변경으로 인한 스크래핑 실패), Discord를 통해 스크린샷과 함께 알림을 보냅니다.

2.  **`lambda-selenium-docker-crawler` (핫딜 크롤러)**:
    *   `lambda-selenium-docker-scanner`에 의해 SNS 토픽으로 발행된 새로운 핫딜 링크 메시지를 **직접 이벤트 트리거로 수신**하여 실행됩니다. (즉, SNS 토픽이 이 Lambda 함수의 직접적인 이벤트 소스입니다.)
    *   전달받은 URL의 웹 페이지에 접속하여 Selenium을 사용해 상세 정보(상품명, 가격, 쇼핑몰 정보, 본문 내용 등)를 추출합니다.
    *   추출된 상세 정보는 JSON 형태로 구성되어, 추가적인 처리(예: 데이터베이스 저장, 알림 발송 등)를 위해 **별도의 AWS SQS 큐로 발행(publish)**합니다.

두 Lambda 함수 모두 Docker 컨테이너 이미지로 패키징되어 AWS Lambda 환경에 배포됩니다. 각 Dockerfile은 Chrome 웹 브라우저, ChromeDriver 및 필요한 Python 라이브러리 등 실행 환경을 정의합니다.

## Docker 이미지
프로젝트의 `lambda-selenium-docker-crawler` 및 `lambda-selenium-docker-scanner` 디렉토리에는 각각 `Dockerfile`이 포함되어 있습니다. 이 `Dockerfile`들은 각 Lambda 함수를 실행하는 데 필요한 환경(예: 특정 버전의 Chrome, ChromeDriver, Python 종속성)을 정의합니다.

AWS Lambda에서 컨테이너 이미지를 사용하려면:
1.  각 디렉토리에서 Docker 이미지를 빌드합니다. (예: `docker build -t <이미지_이름> .`)
2.  빌드된 이미지를 Amazon ECR (Elastic Container Registry)과 같은 컨테이너 레지스트리에 푸시합니다.
3.  AWS Lambda 함수를 생성할 때, "컨테이너 이미지" 옵션을 선택하고 ECR에 업로드된 이미지 URI를 지정합니다.
```
