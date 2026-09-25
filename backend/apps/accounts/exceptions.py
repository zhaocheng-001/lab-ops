from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """把 DRF 异常统一包装为 {code, message, data} 结构。"""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    message = "请求失败"
    if isinstance(detail, dict):
        if "detail" in detail:
            message = str(detail["detail"])
        else:
            parts = []
            for field, errors in detail.items():
                if isinstance(errors, (list, tuple)):
                    text = "；".join(str(e) for e in errors)
                else:
                    text = str(errors)
                parts.append(f"{field}: {text}" if field != "non_field_errors" else text)
            message = "；".join(parts) or message
    elif isinstance(detail, (list, tuple)):
        message = "；".join(str(e) for e in detail)

    response.data = {"code": response.status_code, "message": message, "data": detail}
    return response
