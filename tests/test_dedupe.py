from techdigest.pipeline.dedupe import cluster_items

from .conftest import make_item


def test_same_url_merges_across_sources():
    items = [
        make_item("Asahi Linux progress", "https://lwn.net/Articles/1/", source="LWN"),
        make_item("Asahi Linux 7.3 progress report", "http://lwn.net/Articles/1?utm_source=hn", source="HN"),
    ]
    assert len(cluster_items(items)) == 1


def test_shared_cve_merges():
    items = [
        make_item("CISA: CVE-2026-19868 in SonicWall actively exploited", source="CISA KEV"),
        make_item("SonicWall warns of SSL-VPN flaw exploited in attacks", source="Bleeping",
                  excerpt="The flaw, tracked as CVE-2026-19868, lets attackers bypass MFA."),
    ]
    assert len(cluster_items(items)) == 1


def test_similar_titles_merge_but_different_stories_do_not():
    items = [
        make_item("OpenAI launches GPT-6 model with video understanding", source="A"),
        make_item("OpenAI launches GPT-6 model with native video understanding", source="B"),
        make_item("Google launches Gemini 4 model for developers", source="C"),
    ]
    sizes = sorted(len(c.items) for c in cluster_items(items))
    assert sizes == [1, 2]


def test_same_source_never_merges_by_title():
    items = [
        make_item("Deno 2.6.0 released today for everyone", source="GitHub Releases"),
        make_item("Deno 2.6.0 released today for everyone again", source="GitHub Releases"),
    ]
    assert len(cluster_items(items)) == 2
