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
    assert st.build_object_key("jpg", key_uuid="1234") == "product-images/1234.jpg"


def test_public_path_for_key():
    assert st.public_path_for_key("product-images/1234.jpg") == "/b/product-images/1234.jpg"
