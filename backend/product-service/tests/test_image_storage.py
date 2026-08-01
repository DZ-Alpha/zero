from unittest.mock import MagicMock, patch

from app.services import image_storage as st


def test_is_self_hosted_true_for_our_prefix():
    assert st.is_self_hosted("/b/product-images/abc.jpg") is True


def test_is_self_hosted_false_for_external_url():
    assert st.is_self_hosted("https://example.com/x.jpg") is False


def test_is_self_hosted_false_for_none():
    assert st.is_self_hosted(None) is False


def test_extension_for_content_type_maps_known_types():
    assert st.extension_for_content_type("image/jpeg") == "jpg"
    assert st.extension_for_content_type("image/png") == "png"
    assert st.extension_for_content_type("image/webp") == "webp"


def test_extension_for_content_type_ignores_charset_suffix():
    assert st.extension_for_content_type("image/jpeg; charset=binary") == "jpg"


def test_extension_for_content_type_unknown_returns_none():
    assert st.extension_for_content_type("image/gif") is None
    assert st.extension_for_content_type("text/html") is None


def test_build_object_key():
    assert st.build_object_key("jpg", key_uuid="1234") == "1234.jpg"


def test_public_path_for_key():
    # object_key는 버킷명 없이 {uuid}.{ext}; public 경로에서 /b/product-images/ 를 붙인다
    assert st.public_path_for_key("1234.jpg") == "/b/product-images/1234.jpg"


def test_store_external_image_returns_input_when_already_self_hosted():
    # 이미 우리 경로면 다운로드/업로드 없이 그대로 반환(멱등)
    assert st.store_external_image("/b/product-images/x.jpg") == "/b/product-images/x.jpg"


def test_store_external_image_returns_none_when_not_configured():
    with patch.object(st.settings, "minio_endpoint", ""):
        assert st.store_external_image("https://ext/x.jpg") is None


def test_store_external_image_happy_path_uploads_and_returns_path():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "image/jpeg"}
    fake_resp.content = b"\xff\xd8\xff" + b"0" * 100  # jpeg-ish bytes
    fake_client = MagicMock()
    fake_s3 = MagicMock()

    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", return_value=("image/jpeg", fake_resp.content)), \
         patch.object(st, "_s3_client", return_value=fake_s3), \
         patch.object(st.uuid, "uuid4", return_value="fixed-uuid"):
        result = st.store_external_image("https://ext/x.jpg")

    assert result == "/b/product-images/fixed-uuid.jpg"
    fake_s3.put_object.assert_called_once()
    kwargs = fake_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "product-images"
    assert kwargs["Key"] == "fixed-uuid.jpg"
    assert kwargs["ContentType"] == "image/jpeg"


def test_store_external_image_returns_none_on_unsupported_type():
    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", return_value=("image/gif", b"gif")):
        assert st.store_external_image("https://ext/x.gif") is None


def test_store_external_image_returns_none_on_download_failure():
    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", side_effect=RuntimeError("boom")):
        assert st.store_external_image("https://ext/x.jpg") is None
