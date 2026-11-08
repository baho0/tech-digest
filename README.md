# Tech Digest

Her sabah o günün **gerçekten önemli** teknoloji gelişmelerini mail atan otomasyon.
"Claude Code'u daha iyi kullanmak için 10 teknik" tarzı listicle, rehber ve blogspam elenir;
lansmanlar, sürümler, aktif istismar edilen açıklar ve sektör hamleleri öne çıkar.

## Nasıl çalışır

```
collect (2 saatte bir)  →  SQLite  →  digest (07:00 İstanbul)
                                         cluster → classify → score → select → summarize → render → mail
```

- **Kaynaklar** (`config/sources.yaml`): Hacker News (puanı 80+), Lobsters, Techmeme, Ars Technica,
  The Register, OpenAI / DeepMind / Google AI / Hugging Face blogları, HF Daily Papers, CISA KEV,
  BleepingComputer, Krebs, Project Zero, SecurityWeek, LWN, Phoronix, ServeTheHome ve önemli
  projelerin GitHub sürümleri (yalnızca x.y.0, pre-release yok).
- **Cluster'lama:** aynı haber farklı kaynaklardan gelirse URL, CVE numarası veya başlık benzerliğiyle
  tek habere birleşir. Kaç kaynakta geçtiği en güçlü önem sinyalidir.
- **Puanlama** (`config/scoring.yaml`): kaynak kademesi + kaynak kapsamı + HN/Lobsters/HF etkileşimi
  + olay anahtar kelimeleri ("releases", "acquires", "CVE-", "actively exploited"…) − clickbait
  cezaları (listicle, "how to", "I tried", Ask HN, alışveriş, blog domainleri…) − konu dışı cezası,
  sonra tazeliğe göre azaltma. Her puanın gerekçesi kayıtlı.
- **Seçim:** önce "Today's headlines" (ilk 5), sonra kategori başına en fazla 5 haber
  (AI/ML, Security, Software & Infrastructure, Industry & Hardware). Eşiği geçemeyen gün
  kısa mail gelir, boşluk dolgu haberle doldurulmaz. Gönderilmiş haber bir daha gelmez.

## Komutlar

```bash
techdigest collect [-s "Hacker News"]   # kaynakları çek
techdigest preview [--collect]          # göndermeden HTML üret + puan dökümü (ayar için)
techdigest digest [--force]             # bugünün digest'ini gönder (gün başına bir kez)
techdigest send-test                    # SMTP ayarını dene
```

## Lokal geliştirme

```bash
uv sync
cp .env.example .env        # SMTP bilgilerini gir
uv run techdigest collect
uv run techdigest preview   # preview.html'i tarayıcıda aç
uv run pytest
```

## VPS kurulumu

Gereken: systemd'li bir Linux, `git`, [`uv`](https://docs.astral.sh/uv/).

```bash
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh   # uv yoksa
git clone <repo-url> tech-digest && cd tech-digest
sudo ./deploy/install.sh                            # /opt/tech-digest + systemd timer'ları
sudo -u techdigest nano /opt/tech-digest/.env       # SMTP bilgileri
cd /opt/tech-digest && sudo -u techdigest .venv/bin/techdigest send-test
```

Güncelleme: repoda `git pull`, ardından tekrar `sudo ./deploy/install.sh` (`.env` ve `data/` korunur).

İzleme:

```bash
systemctl list-timers 'techdigest-*'
journalctl -u techdigest-digest -n 50
journalctl -u techdigest-collect --since today
```

### Gmail SMTP

1. Google hesabında 2 adımlı doğrulamayı aç.
2. <https://myaccount.google.com/apppasswords> üzerinden bir App Password oluştur.
3. `.env`: `TD_SMTP_HOST=smtp.gmail.com`, `TD_SMTP_PORT=587`, `TD_SMTP_SECURITY=starttls`,
   `TD_SMTP_USER=adresin@gmail.com`, `TD_SMTP_PASSWORD=<app password>`.

### Kendi mail sunucuna geçiş

Kod değişmez, sadece `.env` değişir (`TD_SMTP_HOST`, port, `starttls`/`ssl`, kullanıcı/şifre).
Spam'e düşmemek için sunucuda SPF, DKIM, DMARC ve reverse DNS (PTR) kayıtlarını ayarla.

## Ayar (tuning)

İlk 1-2 hafta `techdigest preview` çıktısına bakıp `config/scoring.yaml`'daki ağırlıkları,
regex'leri, eşikleri ve `blocked_domains` listesini; `config/sources.yaml`'da kaynakları ve
kaynak ağırlıklarını (`weight`) ayarla. Kod değiştirmek gerekmez.

## Genişleme noktaları

| Ne | Nerede | Nasıl |
|---|---|---|
| Yeni kaynak | `src/techdigest/sources/` | `Source` alt sınıfı + `@register("tip")` + YAML satırı |
| LLM puanlama | `pipeline/score.py` | `Scorer` protokolünü uygula, `engine: llm \| hybrid` |
| LLM özet | `pipeline/summarize.py` | `Summarizer` protokolünü uygula, `summarizer: llm` |
| Başka teslimat kanalı | `delivery/` | `Notifier` protokolü (`send(Rendered)`) |
| Web arayüzü | `web/` | Aynı DB'yi okur: `digests` (günlük HTML), `clusters` (tüm adaylar + puan dökümü), `items` |
| Postgres | `.env` | `TD_DATABASE_URL=postgresql+psycopg://…` |
