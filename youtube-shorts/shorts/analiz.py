"""Kanal analizi: yüklenen videoların izlenme/beğeni/yorum sayılarını toplar, RAPOR.md üretir
ve en iyi çalışan başlıkları sonraki metinlere örnek olarak verir."""
from datetime import datetime, timedelta, timezone


def istatistik_guncelle(kayit, youtube):
    """kayit içindeki video_id'li girişlere güncel sayıları yazar; güncellenen video sayısını döndürür."""
    kimlikler = [k["video_id"] for k in kayit if k.get("video_id")]
    bilgiler = {}
    for i in range(0, len(kimlikler), 50):  # API tek istekte en fazla 50 video kabul eder
        yanit = youtube.videos().list(part="statistics,status", id=",".join(kimlikler[i:i + 50])).execute()
        for video in yanit.get("items", []):
            sayilar = video.get("statistics", {})
            bilgiler[video["id"]] = {
                "izlenme": int(sayilar.get("viewCount", 0)),
                "begeni": int(sayilar.get("likeCount", 0)),
                "yorum": int(sayilar.get("commentCount", 0)),
                "gizlilik": video.get("status", {}).get("privacyStatus"),
            }
    olcum = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for k in kayit:
        if k.get("video_id") in bilgiler:
            k.update(bilgiler[k["video_id"]], olcum=olcum)
    return len(bilgiler)


def puan(k):
    """Etkileşim ağırlıklı başarı puanı: beğeni, yorum ve (Analytics varsa) kazandırılan abone izlenmeden
    daha değerli sayılır."""
    return k.get("izlenme", 0) + 20 * k.get("begeni", 0) + 40 * k.get("yorum", 0) + 60 * k.get("abone_kazanc", 0)


def en_iyi_basliklar(kayit, adet=5, en_az_izlenme=50):
    """Herkese açık ve yeterince izlenmiş videolardan en iyi başlıklar (modele örnek olarak verilir)."""
    olculen = [k for k in kayit if k.get("gizlilik") == "public" and k.get("izlenme", 0) >= en_az_izlenme]
    return [k["baslik"] for k in sorted(olculen, key=puan, reverse=True)[:adet]]


def _durum(k):
    durum = k.get("durum") or "yüklenmedi"
    return "yüklenmedi" if durum == "yüklendi" else durum.replace("|", "/")[:60]


def bekleyenler(kayit):
    """Yüklenmiş ama hâlâ özel duran videolar: Studio'dan herkese açılmayı bekliyor."""
    return [k for k in kayit if k.get("video_id") and k.get("gizlilik", "private") == "private"]


def haftalik_ozet(kayit, simdi=None, durum=None):
    """Son 7 günün Telegram özeti; o hafta video yoksa None."""
    from . import konu

    simdi = simdi or datetime.now(timezone.utc)
    hafta = [k for k in kayit if datetime.fromisoformat(k["tarih"]) >= simdi - timedelta(days=7)]
    if not hafta:
        return None
    yuklenen = [k for k in hafta if k.get("video_id")]
    satirlar = [
        "📊 Haftalık özet",
        f"Üretilen: {len(hafta)}, yüklenen: {len(yuklenen)}",
        f"Bu haftanın videoları: {sum(k.get('izlenme', 0) for k in yuklenen)} izlenme, "
        f"{sum(k.get('begeni', 0) for k in yuklenen)} beğeni",
    ]
    if yuklenen:
        en_iyi = max(yuklenen, key=puan)
        satirlar.append(f"En iyi: {en_iyi['baslik']} ({en_iyi.get('izlenme', 0)} izlenme)")
    ozet = konu.tur_ozeti(kayit)
    if ozet:
        ad, _, ortalama = ozet[0]
        satirlar.append(f"En çok izlenen tür: {konu.TUR_ADI.get(ad, ad)} (ortalama {ortalama})")
    bekleyen = len(bekleyenler(kayit))
    if bekleyen:
        satirlar.append(f"Herkese açılmayı bekleyen: {bekleyen} video")
    gecmis = (durum or {}).get("gecmis") or []
    if gecmis:
        once = next((g for g in gecmis if g["tarih"] >= (simdi - timedelta(days=7)).date().isoformat()), gecmis[0])
        satirlar.append(f"Kanal: {gecmis[-1]['abone']} abone ({gecmis[-1]['abone'] - once['abone']:+d} bu hafta)")
    return "\n".join(satirlar)


def rapor(kayit, adet=30, durum=None):
    from . import konu, plan

    yuklenen = [k for k in kayit if k.get("video_id")]
    satirlar = [
        "# Kanal raporu",
        "",
        f"Son güncelleme: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} (UTC)",
        "",
        *(plan.plan_bolumu(durum, kayit) if durum else []),
        "## Videolar",
        "",
        f"- Üretilen video: {len(kayit)}",
        f"- YouTube'a yüklenen: {len(yuklenen)}",
        f"- Toplam izlenme: {sum(k.get('izlenme', 0) for k in yuklenen)}",
        f"- Toplam beğeni: {sum(k.get('begeni', 0) for k in yuklenen)}",
        "",
    ]
    en_iyiler = sorted(yuklenen, key=puan, reverse=True)[:5]
    if en_iyiler:
        satirlar += ["## En iyi 5", ""]
        satirlar += [f"{i}. {k['baslik']} — {k.get('izlenme', 0)} izlenme, {k.get('begeni', 0)} beğeni"
                     for i, k in enumerate(en_iyiler, 1)]
        satirlar.append("")
    ozet = konu.tur_ozeti(kayit)
    if ozet:
        satirlar += ["## Türlere göre (herkese açık videolar)", "", "| Tür | Video | Ortalama izlenme |", "|---|---|---|"]
        satirlar += [f"| {konu.TUR_ADI.get(ad, ad)} | {sayi} | {ortalama} |" for ad, sayi, ortalama in ozet]
        satirlar += ["", "Konu seçimi bu tabloya göre ağırlık verir: çok izlenen türler öne alınır.", ""]
    bekleyen = bekleyenler(kayit)
    if bekleyen:
        satirlar += ["## Herkese açılmayı bekleyenler", "",
                     "Bu videolar özel yüklendi; YouTube Studio'dan kontrol edip herkese açın.", ""]
        satirlar += [f"- [{k['baslik']}](https://studio.youtube.com/video/{k['video_id']}/edit) — {k['tarih'][:10]}"
                     for k in reversed(bekleyen[-10:])]
        satirlar.append("")
    satirlar += ["## Son videolar", "", "| Tarih | Konu | Başlık | İzlenme | Beğeni | Yorum | Durum |",
                 "|---|---|---|---|---|---|---|"]
    for k in reversed(kayit[-adet:]):
        baslik = k["baslik"].replace("|", "/")
        if k.get("video_id"):
            baslik = f"[{baslik}](https://youtube.com/shorts/{k['video_id']})"
        satirlar.append(
            f"| {k['tarih'][:10]} | {k['konu']} | {baslik} | {k.get('izlenme', '-')} | {k.get('begeni', '-')} "
            f"| {k.get('yorum', '-')} | {k.get('gizlilik') or ('-' if k.get('video_id') else _durum(k))} |"
        )
    return "\n".join(satirlar) + "\n"
