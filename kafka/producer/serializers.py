"""Message serialization for Kafka"""
import json
from datetime import datetime
from typing import Any, Dict


def serialize_event(event_type: str, data: Dict[str, Any]) -> bytes:
    """
    이벤트 데이터를 JSON으로 직렬화

    Args:
        event_type: 이벤트 타입 (user_created, product_created, order_created)
        data: 이벤트 데이터 (dict)

    Returns:
        bytes: UTF-8로 인코딩된 JSON 바이트
    """
    # datetime 객체를 ISO 포맷 문자열로 변환
    def convert_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    # 데이터의 모든 필드를 순회하며 datetime 변환
    converted_data = {}
    for key, value in data.items():
        converted_data[key] = convert_datetime(value)

    # 메시지 구조
    message = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        event_type.split('_')[0]: converted_data  # user, product, order
    }

    # JSON으로 직렬화 후 UTF-8로 인코딩
    return json.dumps(message, ensure_ascii=False).encode('utf-8')
