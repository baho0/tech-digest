from techdigest.pipeline.normalize import canonical_url, domain, strip_html, truncate


def test_canonical_url_strips_tracking_and_noise():
    a = canonical_url("http://www.Example.com/news/story/?utm_source=x&id=5&ref=hn#comments")
    b = canonical_url("https://example.com/news/story?id=5")
    assert a == b == "https://example.com/news/story?id=5"


def test_canonical_url_amp_and_mobile():
    assert canonical_url("https://m.example.com/a/amp/") == canonical_url("https://example.com/a")


def test_domain():
    assert domain("https://www.theregister.com/x") == "theregister.com"


def test_strip_html_and_truncate():
    assert strip_html("<p>Hello&nbsp;<b>world</b></p>") == "Hello world"
    text = "First sentence here. Second sentence is much longer and goes on and on."
    assert truncate(text, 36) == "First sentence here."
    assert truncate("short", 40) == "short"
