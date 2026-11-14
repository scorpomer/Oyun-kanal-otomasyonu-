"""Kanal planı: gidişattan hedef tahmini, öncelikli tür ve yapılacaklar listesi (RAPOR.md'nin baş bölümü)."""
from datetime import date, datetime, timedelta

HEDEFLER = (100, 500, 1000, 5000, 10000, 50000, 100000)
# YouTube İş Ortağı Programı (Shorts yolu): 500 abone (alt kademe) / 1000 abone (reklam geliri)


def gunluk_abone_artisi(durum, gun=7):
    """Son gun günün ortalama günlük abone artışı. Analytics varsa net kazançtan, yoksa günlük ölçümlerden."""
    gunluk = durum.get("gunluk") or []
    if len(gunluk) >= 3:
        son = gunluk[-gun:]
        return sum(g["abone_kazanc"] - g["abone_kayip"] for g in son) / len(son)
    gecmis = durum.get("gecmis") or []
    if len(gecmis) < 2:
        return None
    ilk, son = gecmis[max(0, len(gecmis) - 1 - gun)], gecmis[-1]
    fark_gun = (date.fromisoformat(son["tarih"]) - date.fromisoformat(ilk["tarih"])).days
    return (son["abone"] - ilk["abone"]) / fark_gun if fark_gun > 0 else None


def gunluk_izlenme(durum, gun=7):
    gunluk = durum.get("gunluk") or []
    if len(gunluk) >= 3:
        son = gunluk[-gun:]
        return sum(g["izlenme"] for g in son) / len(son)
    gecmis = durum.get("gecmis") or []
    if len(gecmis) < 2:
        return None
    ilk, son = gecmis[max(0, len(gecmis) - 1 - gun)], gecmis[-1]
    fark_gun = (date.fromisoformat(son["tarih"]) - date.fromisoformat(ilk["tarih"])).days
    return (son["izlenme"] - ilk["izlenme"]) / fark_gun if fark_gun > 0 else None


def hedef_tahmini(abone, artis, bugun=None):
    """(sonraki hedef, kalan gün ya da None). Artış yoksa/negatifse gün tahmini yapılmaz."""
    bugun = bugun or date.today()
    hedef = next((h for h in HEDEFLER if h > abone), None)
    if hedef is None or not artis or artis <= 0:
        return hedef, None
    gun = int(-(-(hedef - abone) // artis))
    return hedef, (gun, bugun + timedelta(days=gun))


def yapilacaklar(durum, kayit, ortam=None):
    """Sistemin kendisinin yapamayıp kanal sahibinin yapması gerekenler + otomatik yapılanların durumu."""
    import os

    ortam = ortam if ortam is not None else os.environ
    liste = []
    yetki = durum.get("yetki", {})
    eksik = [ad for ad, alan in (("yorum yanıtlama", "yorum"), ("kanal açıklaması/kapak", "marka"),
                                 ("altyazı yükleme", "altyazi")) if yetki.get(alan) == "izin eksik"]
    if eksik:
        liste.append(f"**YouTube izni eksik** ({', '.join(eksik)}): bilgisayarında `python yetki_al.py "
                     "client_secret.json` çalıştırıp yeni `YT_REFRESH_TOKEN`'ı GitHub Secrets'a yaz.")
    if yetki.get("analitik") == "API kapalı":
        liste.append("**YouTube Analytics API kapalı:** Google Cloud Console > APIs & Services > Library > "
                     "\"YouTube Analytics API\" > Enable.")
    elif yetki.get("analitik") == "izin eksik":
        liste.append("**YouTube Analytics izni eksik:** `yetki_al.py` yeniden çalıştırılınca gelir.")
    bilgi = durum.get("bilgi", {})
    if bilgi and not bilgi.get("kapak_var") and yetki.get("marka") != "tamam":
        liste.append("Kanal kapak görseli yok; izin gelince sistem otomatik yükler.")
    liste.append("Profil fotoğrafı API ile değiştirilemez: depodaki `marka/profil.png` dosyasını "
                 "YouTube Studio > Özelleştirme > Marka bölümünden bir kez yükle (yüklediysen bu satırı yok say).")
    if not ortam.get("TELEGRAM_BOT_TOKEN"):
        liste.append("Telegram'dan yönetim ve bildirim kapalı: @BotFather ile bot açıp belirteci "
                     "`TELEGRAM_BOT_TOKEN` gizli ayarına yaz (README > Telegram).")
    return liste


def plan_bolumu(durum, kayit, bugun=None, ortam=None):
    """RAPOR.md'nin en üstüne konan 'Kanal durumu ve plan' bölümü (markdown satırları)."""
    from . import konu

    bugun = bugun or date.today()
    bilgi = durum.get("bilgi") or {}
    satirlar = []
    if bilgi:
        satirlar += [f"## Kanal: {bilgi.get('ad', '-')}", ""]
        abone = "gizli" if bilgi.get("abone_gizli") else bilgi.get("abone", 0)
        satirlar += [f"- Abone: **{abone}**", f"- Toplam izlenme: **{bilgi.get('izlenme', 0)}**",
                     f"- Video sayısı: {bilgi.get('video', 0)}"]
        if bilgi.get("ozel_ad"):
            satirlar.append(f"- Adres: https://youtube.com/{bilgi['ozel_ad']}")
        satirlar.append("")
    artis, izlenme = gunluk_abone_artisi(durum), gunluk_izlenme(durum)
    if bilgi:
        satirlar += ["## Gidişat ve hedef", ""]
        if artis is not None:
            satirlar.append(f"- Son 7 günde günlük ortalama: {artis:+.1f} abone"
                            + (f", {izlenme:.0f} izlenme" if izlenme is not None else ""))
        hedef, tahmin = hedef_tahmini(bilgi.get("abone", 0), artis, bugun)
        if hedef:
            if tahmin:
                gun, tarih = tahmin
                satirlar.append(f"- Sonraki hedef **{hedef} abone**: bu hızla yaklaşık {gun} gün "
                                f"({tarih.strftime('%d.%m.%Y')})")
            else:
                satirlar.append(f"- Sonraki hedef **{hedef} abone** (tahmin için birkaç günlük ölçüm gerekiyor)")
        satirlar.append("- Para kazanma eşiği: 500 abone (alt kademe), 1000 abone + 90 günde 10 milyon Shorts "
                        "izlenmesi (reklam geliri)")
        satirlar.append("")
        tablo = (durum.get("gunluk") or [])[-14:]
        if tablo:
            satirlar += ["| Gün | İzlenme | İzlenme (dk) | Abone + | Abone − |", "|---|---|---|---|---|"]
            satirlar += [f"| {g['tarih']} | {g['izlenme']} | {g['izlenme_dk']} | {g['abone_kazanc']} "
                         f"| {g['abone_kayip']} |" for g in reversed(tablo)]
            satirlar.append("")
        elif len(durum.get("gecmis") or []) >= 2:
            satirlar += ["| Gün | Abone | Toplam izlenme | Video |", "|---|---|---|---|"]
            satirlar += [f"| {g['tarih']} | {g['abone']} | {g['izlenme']} | {g['video']} |"
                         for g in reversed(durum["gecmis"][-14:])]
            satirlar.append("")
    ozet = konu.tur_ozeti(kayit)
    hafta = [k for k in kayit if k.get("tarih") and
             datetime.fromisoformat(k["tarih"]).date() >= bugun - timedelta(days=7)]
    satirlar += ["## Plan", ""]
    satirlar.append(f"- Bu hafta: {len(hafta)} video üretildi, "
                    f"{sum(1 for k in hafta if k.get('video_id'))} tanesi yüklendi (hedef: günde 2).")
    if ozet:
        en_iyi, en_kotu = ozet[0], ozet[-1]
        satirlar.append(f"- Öncelik: **{konu.TUR_ADI.get(en_iyi[0], en_iyi[0])}** (ortalama {en_iyi[2]} izlenme); "
                        "konu seçimi bu türü öne alıyor.")
        if len(ozet) > 1 and en_kotu[2] < en_iyi[2] / 4:
            satirlar.append(f"- Geri planda: {konu.TUR_ADI.get(en_kotu[0], en_kotu[0])} "
                            f"(ortalama {en_kotu[2]} izlenme).")
    oranli = [k for k in kayit if k.get("izlenme_orani") is not None]
    if oranli:
        ort = sum(k["izlenme_orani"] for k in oranli) / len(oranli)
        satirlar.append(f"- Ortalama izlenme oranı: %{ort:.0f}"
                        + (" — ilk 2 saniye ve kısa cümleler önemli; kanca güçlendirilmeli." if ort < 60 else "."))
        kazandiran = max(oranli, key=lambda k: k.get("abone_kazanc", 0))
        if kazandiran.get("abone_kazanc"):
            satirlar.append(f"- En çok abone getiren: {kazandiran['baslik']} (+{kazandiran['abone_kazanc']})")
    yorumlar = (durum.get("yorumlar") or {})
    if yorumlar.get("toplam_okunan") is not None:
        satirlar.append(f"- Yorumlar: son {yorumlar['toplam_okunan']} yorum okundu, toplam "
                        f"{len(yorumlar.get('yanitlanan', []))} yanıtlandı/işlendi, "
                        f"{len(yorumlar.get('bekletilen', []))} spam incelemeye alındı.")
    satirlar.append("")
    is_listesi = yapilacaklar(durum, kayit, ortam)
    if is_listesi:
        satirlar += ["## Senin yapman gerekenler", ""] + [f"- [ ] {i}" for i in is_listesi] + [""]
    son_yorum = (yorumlar.get("son") or [])[:5]
    if son_yorum:
        satirlar += ["## Son yorumlar", ""]
        satirlar += [f"- {y['tarih']}: “{y['metin'].replace(chr(10), ' ')[:120]}”" for y in son_yorum]
        satirlar.append("")
    return satirlar
