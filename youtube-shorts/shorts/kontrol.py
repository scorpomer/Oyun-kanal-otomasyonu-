"""Saatlik kontrol: Telegram komutlarını işler, zamanı gelen video üretimini başlatır, başarısız üretimi
bir kez yeniden dener. Yalnızca Python standart kütüphanesini kullanır (pip kurulumu gerekmez, iş saniyeler sürer).

Çalıştırma (kontrol.yml): python -m shorts.kontrol
Gerekli ortam: GITHUB_TOKEN + GITHUB_REPOSITORY (üretimi başlatmak için); isteğe bağlı TELEGRAM_BOT_TOKEN.
Durum depodaki kontrol.json'da, ayar değişiklikleri ayar.json'da tutulur; iş akışı ikisini depoya yazar.
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

from . import ayar, telegram

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DURUM = os.path.join(KOK, "kontrol.json")
KAYIT = os.path.join(KOK, "yapilanlar.json")
URETIM_IS_AKISI = "shorts.yml"
PENCERE = timedelta(hours=5)          # GitHub zamanlayıcısı gecikirse saat kaçırılmasın
YENIDEN_DENEME_SONRASI = timedelta(minutes=50)


def _oku(yol, varsayilan):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _yaz(yol, veri):
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
        f.write("\n")


def kayit_ve_kanal():
    veri = _oku(KAYIT, [])
    if isinstance(veri, list):
        return veri, {}
    return veri.get("videolar", []), veri.get("kanal", {})


# ---------------------------------------------------------------- GitHub

def _github(yol, govde=None, yontem=None):
    depo, belirtec = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (depo and belirtec):
        raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY yok")
    istek = urllib.request.Request(
        f"https://api.github.com/repos/{depo}/{yol}",
        data=json.dumps(govde).encode() if govde is not None else None,
        method=yontem or ("POST" if govde is not None else "GET"),
        headers={"Authorization": f"Bearer {belirtec}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "shorts-kontrol"})
    with urllib.request.urlopen(istek, timeout=30) as yanit:
        icerik = yanit.read()
    return json.loads(icerik) if icerik else {}


def uretimi_baslat(kuru=False):
    dal = os.getenv("GITHUB_REF_NAME") or "main"
    _github(f"actions/workflows/{URETIM_IS_AKISI}/dispatches",
            {"ref": dal, "inputs": {"kuru": "true" if kuru else "false"}})


def son_uretimler(adet=10):
    return _github(f"actions/workflows/{URETIM_IS_AKISI}/runs?per_page={adet}").get("workflow_runs", [])


def son_kalite_kosular(adet=10):
    return _github(f"actions/workflows/quality.yml/runs?per_page={adet}&branch=main").get("workflow_runs", [])


# ---------------------------------------------------------------- zamanlama

def zamani_gelenler(ayarlar, durum, simdi):
    """Bugün zamanı gelmiş ve henüz başlatılmamış saatler (en yenisi sonda). Duraklatma/bitiş/günlük sınır
    dikkate alınır."""
    z = ayarlar["zamanlama"]
    if not z.get("aktif", True):
        return []
    bugun = simdi.date()
    if z.get("bitis") and bugun > date.fromisoformat(z["bitis"]):
        return []
    tetik = durum.get("tetiklenen", {})
    bugunku = sum(1 for anahtar in tetik if anahtar.startswith(bugun.isoformat()))
    if bugunku >= int(z.get("gunluk_en_cok", 6)):
        return []
    gelen = []
    for saat in sorted(z.get("saatler") or []):
        try:
            sa, dk = (int(x) for x in saat.split(":"))
        except ValueError:
            continue
        an = simdi.replace(hour=sa, minute=dk, second=0, microsecond=0)
        anahtar = f"{bugun.isoformat()} {saat}"
        if an <= simdi < an + PENCERE and anahtar not in tetik:
            gelen.append(anahtar)
    return gelen


def bitis_kontrol(ayarlar, durum, simdi):
    """Bitiş tarihi geçtiyse otomatik üretimi kapatır; bir kez bildirim metni döndürür."""
    z = ayarlar["zamanlama"]
    if z.get("bitis") and simdi.date() > date.fromisoformat(z["bitis"]) and z.get("aktif", True):
        z["aktif"] = False
        return f"📅 Bitiş tarihi ({z['bitis']}) geldi: otomatik üretim durduruldu. Sürdürmek için /bitis yok ve /devam"
    return None


def yeniden_denenecekler(durum, kosular, simdi):
    """Başlatılmış ama başarısız biten (ve henüz yeniden denenmemiş) üretimler."""
    sonuc = []
    for anahtar, bilgi in durum.get("tetiklenen", {}).items():
        if bilgi.get("deneme", 1) >= 2 or bilgi.get("kuru"):
            continue
        zaman = datetime.fromisoformat(bilgi["zaman"])
        if simdi - zaman < YENIDEN_DENEME_SONRASI or simdi - zaman > timedelta(hours=6):
            continue
        sonra = [k for k in kosular if datetime.fromisoformat(k["created_at"].replace("Z", "+00:00")) >= zaman
                 - timedelta(minutes=2)]
        if sonra and all(k.get("status") == "completed" for k in sonra) and \
                not any(k.get("conclusion") == "success" for k in sonra):
            sonuc.append(anahtar)
    return sonuc


def _zaman(kosu, alan="created_at"):
    return datetime.fromisoformat(kosu[alan].replace("Z", "+00:00"))


def yeni_hatalar(durum, kosular, dal="main"):
    """Ana daldaki üretimlerden, daha önce bildirilmemiş başarısız olanlar. Görülen en büyük koşu numarası
    durumda tutulur; ilk çalıştırmada eski hatalar bildirilmez."""
    ilgili = [k for k in kosular if k.get("head_branch") == dal]
    if not ilgili:
        return []
    en_yeni = max(k["run_number"] for k in ilgili)
    onceki = durum.get("son_gorulen_kosu")
    bitenler = [k for k in ilgili if k.get("status") == "completed"]
    durum["son_gorulen_kosu"] = max([k["run_number"] for k in bitenler] + [onceki or 0]) if bitenler else onceki
    if onceki is None:
        durum["son_gorulen_kosu"] = max([k["run_number"] for k in bitenler], default=en_yeni)
        return []
    return [k for k in bitenler if k["run_number"] > onceki and k.get("conclusion") == "failure"]


def yeni_kalite_hatalari(durum, kosular, simdi):
    """Ana daldaki yeni kalite hatalarını bulur; ilk kontrolde yalnızca son iki saati değerlendirir."""
    ilgili = [k for k in kosular if k.get("head_branch") == "main"]
    bitenler = [k for k in ilgili if k.get("status") == "completed"]
    onceki = durum.get("son_gorulen_kalite_kosu")
    if onceki is None:
        hatalar = [k for k in bitenler if k.get("conclusion") == "failure" and
                   simdi - _zaman(k) <= timedelta(hours=2)]
    else:
        hatalar = [k for k in bitenler if k["run_number"] > onceki and k.get("conclusion") == "failure"]
    if bitenler:
        durum["son_gorulen_kalite_kosu"] = max(
            [k["run_number"] for k in bitenler] + [onceki or 0])
    return hatalar


def nobetci(ayarlar, durum, kosular, kayit, simdi, sinir=timedelta(hours=30)):
    """Sistem sessizce durmuş mu: otomatik üretim açıkken 30 saattir yeni video yoksa ve çalışan iş de yoksa
    True (en çok 12 saatte bir). Kontrol o zaman üretimi kendisi başlatır."""
    z = ayarlar["zamanlama"]
    if not z.get("aktif", True) or not z.get("saatler"):
        return False
    if z.get("bitis") and simdi.date() > date.fromisoformat(z["bitis"]):
        return False
    if any(k.get("status") != "completed" for k in kosular):
        return False
    son_kurtarma = durum.get("son_kurtarma")
    if son_kurtarma and simdi - datetime.fromisoformat(son_kurtarma) < timedelta(hours=12):
        return False
    tarihler = [datetime.fromisoformat(k["tarih"]) for k in kayit if k.get("tarih")]
    return bool(tarihler) and simdi - max(tarihler) > sinir


# ---------------------------------------------------------------- ana akış

def calistir(simdi=None):
    simdi = simdi or datetime.now(telegram.TR)
    ayarlar = ayar.oku()
    eski_ayar = json.dumps(ayarlar, sort_keys=True)
    durum = _oku(DURUM, {})
    eski_durum = json.dumps(durum, sort_keys=True)
    kayit, kanal_durumu = kayit_ve_kanal()
    bildirimler, eylemler = [], []

    # 1) Telegram komutları
    if telegram.belirtec():
        try:
            if not durum.get("komutlar_kayitli"):
                telegram.komutlari_kaydet()
                durum["komutlar_kayitli"] = True
            sahibi = telegram.sohbet_id(ayarlar)
            for g in telegram.guncellemeler(durum.get("telegram_offset", 0)):
                durum["telegram_offset"] = g["update_id"] + 1
                mesaj = g.get("message") or {}
                sohbet, metin = str((mesaj.get("chat") or {}).get("id", "")), mesaj.get("text") or ""
                if not sohbet or not metin:
                    continue
                if not sahibi and metin.split()[0].split("@")[0] == "/start":
                    # Sahip tanımlı değil: bota ilk /start yazan sohbet sahip olur ve ayar.json'a kaydedilir.
                    # TELEGRAM_CHAT_ID gizli ayarını elle eklemeye gerek kalmaz.
                    sahibi = sohbet
                    ayarlar["telegram"]["sohbet_id"] = sohbet
                    print("Telegram sahibi kaydedildi")
                    telegram.gonder("✅ Bu sohbet botun sahibi olarak kaydedildi; artık yalnızca seni dinliyorum.\n\n"
                                    + telegram.kurulum_metni(kanal_durumu) + "\n\n" + telegram._yardim(), sohbet)
                    continue
                if sohbet != sahibi:
                    # Yabancıya bilgi verme; yalnızca kurulum için sohbet kimliğini söyle
                    if metin.split()[0].split("@")[0] in ("/start", "/kimlik"):
                        telegram.gonder(f"Bu sohbetin kimliği: {sohbet}\nBotu yönetmek için bu sayıyı GitHub'da "
                                        "TELEGRAM_CHAT_ID gizli ayarına ya da ayar.json > telegram > sohbet_id "
                                        "alanına yaz.", sohbet)
                    continue
                yanit, eylem = telegram.komut_isle(metin, ayarlar, kayit, kanal_durumu, simdi.date())
                print(f"Telegram komutu: {metin[:40]!r}")
                telegram.gonder(yanit, sohbet)
                if eylem:
                    eylemler.append(eylem)
        except Exception as hata:
            print(f"Telegram okunamadı: {hata}")

    # 2) Bitiş tarihi
    mesaj = bitis_kontrol(ayarlar, durum, simdi)
    if mesaj:
        bildirimler.append(mesaj)

    # 3) Zamanı gelen üretim ve elle istenen üretim
    tetik = durum.setdefault("tetiklenen", {})
    gelenler = zamani_gelenler(ayarlar, durum, simdi)
    if len(gelenler) > 1:  # uzun kesintiden sonra birikenleri tek üretimde topla
        for anahtar in gelenler[:-1]:
            tetik[anahtar] = {"zaman": simdi.isoformat(timespec="seconds"), "atlandi": True, "deneme": 2}
        gelenler = gelenler[-1:]
    isler = [(a, False) for a in gelenler]
    for eylem in eylemler:
        isler.append((f"{simdi.date().isoformat()} elle {simdi.strftime('%H:%M:%S')} {eylem}", eylem == "deneme"))
    for anahtar, kuru in isler:
        try:
            uretimi_baslat(kuru)
            tetik[anahtar] = {"zaman": simdi.isoformat(timespec="seconds"), "deneme": 1, "kuru": kuru}
            print(f"Üretim başlatıldı: {anahtar}")
        except Exception as hata:
            print(f"Üretim başlatılamadı ({anahtar}): {hata}")
            bildirimler.append(f"⚠️ Video üretimi başlatılamadı: {hata}")

    # 4) Başarısız üretimi bir kez yeniden dene
    try:
        for kosu in yeni_kalite_hatalari(durum, son_kalite_kosular(), simdi):
            try:
                _github(f"actions/runs/{kosu['id']}/rerun-failed-jobs", yontem="POST")
                bildirimler.append(
                    f"🔁 Kalite kontrolleri #{kosu['run_number']} hata verdi; başarısız adımlar bir kez yeniden çalıştırıldı.\n"
                    f"{kosu.get('html_url', '')}")
            except Exception as hata:
                print(f"Kalite kontrolleri yeniden başlatılamadı (#{kosu['run_number']}): {hata}")
                bildirimler.append(f"⚠️ Kalite kontrolleri #{kosu['run_number']} yeniden başlatılamadı: {hata}")
    except Exception as hata:
        print(f"Kalite iş akışı geçmişi okunamadı: {hata}")

    try:
        kosular = son_uretimler()
        for anahtar in yeniden_denenecekler(durum, kosular, simdi):
            uretimi_baslat()
            tetik[anahtar].update(deneme=2, zaman=simdi.isoformat(timespec="seconds"))
            bildirimler.append(f"🔁 {anahtar} üretimi hata vermişti; bir kez yeniden deneniyor.")
        for k in yeni_hatalar(durum, kosular, os.getenv("GITHUB_REF_NAME") or "main"):
            bildirimler.append(f"⚠️ Video üretimi #{k['run_number']} hata verdi. Zamanlanmış üretimse bir kez "
                               f"kendiliğinden yeniden denenecek.\n{k.get('html_url', '')}")
        if not isler and nobetci(ayarlar, durum, kosular, kayit, simdi):
            uretimi_baslat()
            durum["son_kurtarma"] = simdi.isoformat(timespec="seconds")
            tetik[f"{simdi.date().isoformat()} kurtarma {simdi.strftime('%H:%M')}"] = {
                "zaman": simdi.isoformat(timespec="seconds"), "deneme": 1}
            bildirimler.append("🛟 30 saattir yeni video yoktu; üretimi kendim yeniden başlattım.")
    except Exception as hata:
        print(f"Üretim geçmişi okunamadı: {hata}")

    # Eski kayıtları temizle (30 gün)
    sinir = (simdi.date() - timedelta(days=30)).isoformat()
    durum["tetiklenen"] = {a: b for a, b in tetik.items() if a[:10] >= sinir}
    durum["son_kontrol"] = simdi.isoformat(timespec="seconds")

    for mesaj in bildirimler:
        telegram.gonder(mesaj, telegram.sohbet_id(ayarlar))
    if json.dumps(ayarlar, sort_keys=True) != eski_ayar:
        _yaz(ayar.DOSYA, ayarlar)
        print("ayar.json güncellendi")
    if json.dumps({k: v for k, v in durum.items() if k != "son_kontrol"}, sort_keys=True) != \
            json.dumps({k: v for k, v in json.loads(eski_durum).items() if k != "son_kontrol"}, sort_keys=True):
        _yaz(DURUM, durum)  # yalnızca gerçek değişiklikte yaz: her saat boş commit olmasın
    return durum


if __name__ == "__main__":
    calistir()
