"""通用能力：图片上传等。"""
import os
import uuid

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
ALLOWED_DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB
MAX_DOC_SIZE = 20 * 1024 * 1024   # 20 MB


def _ok(data=None, message="success", http_status=status.HTTP_200_OK):
    return Response({"code": 0, "message": message, "data": data}, status=http_status)


def _err(message, http_status=status.HTTP_400_BAD_REQUEST, code=1):
    return Response({"code": code, "message": message, "data": None}, status=http_status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_image(request):
    """通用图片上传：表单字段 file；返回相对 URL 路径。

    - 保存到 media/uploads/yyyy-mm/<uuid>.<ext>
    - 仅接受图片类型；>8MB 直接拒绝
    """
    upload = request.FILES.get("file") or request.FILES.get("image")
    if not upload:
        return _err("未收到文件，请使用表单字段 file 或 image 上传")

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        return _err(f"暂不支持该图片格式：{ext or '未知'}")

    if upload.size > MAX_IMAGE_SIZE:
        return _err(f"图片过大，最大允许 {MAX_IMAGE_SIZE // 1024 // 1024} MB")

    today = timezone.now()
    relative_dir = f"uploads/{today:%Y-%m}"
    filename = f"{uuid.uuid4().hex}{ext}"
    relative_path = f"{relative_dir}/{filename}"

    save_root = settings.MEDIA_ROOT
    target_dir = os.path.join(save_root, relative_dir)
    os.makedirs(target_dir, exist_ok=True)

    full_path = os.path.join(save_root, relative_path)
    with open(full_path, "wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)

    url = f"{settings.MEDIA_URL}{relative_path}"
    return _ok(data={
        "url": url,
        "name": upload.name,
        "size": upload.size,
        "content_type": upload.content_type,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_file(request):
    """通用文件上传：图片或常见文档。"""
    upload = request.FILES.get("file") or request.FILES.get("image")
    if not upload:
        return _err("未收到文件")

    ext = os.path.splitext(upload.name)[1].lower()
    is_image = ext in ALLOWED_IMAGE_EXTS
    is_doc = ext in ALLOWED_DOC_EXTS
    if not (is_image or is_doc):
        return _err(f"暂不支持该文件类型：{ext or '未知'}")

    limit = MAX_IMAGE_SIZE if is_image else MAX_DOC_SIZE
    if upload.size > limit:
        return _err(f"文件过大，最大允许 {limit // 1024 // 1024} MB")

    today = timezone.now()
    sub = "images" if is_image else "files"
    relative_dir = f"uploads/{sub}/{today:%Y-%m}"
    filename = f"{uuid.uuid4().hex}{ext}"
    relative_path = f"{relative_dir}/{filename}"

    save_root = settings.MEDIA_ROOT
    target_dir = os.path.join(save_root, relative_dir)
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(save_root, relative_path)
    with open(full_path, "wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)

    url = f"{settings.MEDIA_URL}{relative_path}"
    return _ok(data={
        "url": url,
        "name": upload.name,
        "size": upload.size,
        "kind": "image" if is_image else "file",
        "content_type": upload.content_type,
    })