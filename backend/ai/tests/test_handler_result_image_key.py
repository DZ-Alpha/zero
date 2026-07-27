from app.handlers.base import HandlerResult


def test_image_key_defaults_none():
    r = HandlerResult(msg="hi")
    assert r.image_key is None


def test_image_key_accepted():
    r = HandlerResult(msg="hi", is_img=True, image_key="7/x.png")
    assert r.image_key == "7/x.png"
