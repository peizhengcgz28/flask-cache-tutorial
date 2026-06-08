import json
import datetime
from typing import Any
from functools import wraps

from flask import jsonify, Response


def timestamp() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def api_response(data: Any = None, message: str = "success", status: int = 200) -> tuple:
    body = {'success': status == 200, 'message': message, 'data': data, 'timestamp': timestamp()}
    return jsonify(body), status


def fix_json_response(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            response, status_code = result
            data = response.get_json() if hasattr(response, 'get_json') else response
            return Response(json.dumps(data, ensure_ascii=False),
                            status=status_code,
                            mimetype='application/json; charset=utf-8')
        return result
    return wrapper
