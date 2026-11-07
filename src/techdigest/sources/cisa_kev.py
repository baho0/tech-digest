"""CISA Known Exploited Vulnerabilities catalog.

All vulnerabilities added on the same day become ONE story, so a busy day
does not flood the security section.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from ..models import RawItem
from .base import Source, register

CATALOG_PAGE = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"


@register("cisa_kev")
class CisaKevSource(Source):
    def fetch(self) -> list[RawItem]:
        data = self.get(self.config.url).json()
        cutoff = (datetime.now(UTC) - timedelta(days=int(self.opt("lookback_days", 3)))).date()
        by_day: dict[str, list[dict]] = defaultdict(list)
        for v in data.get("vulnerabilities", []):
            try:
                added = datetime.strptime(v["dateAdded"], "%Y-%m-%d").date()
            except (KeyError, ValueError):
                continue
            if added >= cutoff:
                by_day[v["dateAdded"]].append(v)

        items: list[RawItem] = []
        for day, vulns in sorted(by_day.items()):
            products = list(dict.fromkeys(f"{v['vendorProject']} {v['product']}" for v in vulns))
            ransomware = any(v.get("knownRansomwareCampaignUse") == "Known" for v in vulns)
            if len(vulns) == 1:
                v = vulns[0]
                title = f"CISA: {v['cveID']} in {products[0]} actively exploited — {v['vulnerabilityName']}"
            else:
                shown = ", ".join(products[:4]) + (f" +{len(products) - 4} more" if len(products) > 4 else "")
                title = f"CISA adds {len(vulns)} actively exploited vulnerabilities to KEV: {shown}"
            excerpt = "; ".join(f"{v['cveID']} ({v['vendorProject']} {v['product']})" for v in vulns)
            if ransomware:
                excerpt = "Known ransomware use. " + excerpt
            items.append(
                self.item(
                    guid=f"kev-{day}-{len(vulns)}",
                    title=title,
                    url=f"https://nvd.nist.gov/vuln/detail/{vulns[0]['cveID']}"
                    if len(vulns) == 1
                    else f"{CATALOG_PAGE}#kev-{day}",
                    excerpt=excerpt[:500],
                    published_at=datetime.strptime(day, "%Y-%m-%d").replace(hour=16, tzinfo=UTC),
                    metrics={"kev_count": float(len(vulns))},
                    extra={"cves": [v["cveID"] for v in vulns], "ransomware": ransomware},
                )
            )
        return items
