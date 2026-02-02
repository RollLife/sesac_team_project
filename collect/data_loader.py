import json
import os

# 파일 경로 설정 (같은 폴더에 있다고 가정)
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'product_rules.json')

def load_product_rules():
    """JSON 파일을 읽어서 파이썬 딕셔너리로 변환"""
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✅ 설정 파일 로드 완료: {len(data['categories'])}개 카테고리")
            return data
    except FileNotFoundError:
        print(f"❌ 오류: '{JSON_FILE_PATH}' 파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ 오류: JSON 파일 형식이 잘못되었습니다. (콤마 확인 필요) \n{e}")
        return None

# 전역 변수로 로드 (다른 파일에서 import 해서 쓰기 위함)
rules_config = load_product_rules()

if rules_config:
    PREFIXES = rules_config['common_prefixes']
    REALISTIC_RULES = rules_config['categories']
else:
    # 비상용 빈 값 (에러 방지)
    PREFIXES = []
    REALISTIC_RULES = {}