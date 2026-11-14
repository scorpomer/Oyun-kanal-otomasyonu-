import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shorts import __main__ as ana  # noqa: E402
from shorts import birlestir, yedek  # noqa: E402
from shorts import analiz, ayar, gorsel, kanal, kaynak, konu, kontrol, metin, plan, ses, telegram, trend, video, yukle  # noqa: E402
from shorts.__main__ import aciklama_olustur, env_yukle, hassas_mi, yeni_trendler  # noqa: E402


class EnvYukleTesti(unittest.TestCase):
    def test_okur_ama_ortami_ezmez(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, ".env")
            with open(yol, "w", encoding="utf-8") as f:
                f.write("# yorum\nENV_TEST_A=\"x y\"\nENV_TEST_B=2\n")
            os.environ.pop("ENV_TEST_A", None)
            os.environ["ENV_TEST_B"] = "var"
            try:
                env_yukle(yol)
                self.assertEqual(os.environ["ENV_TEST_A"], "x y")
                self.assertEqual(os.environ["ENV_TEST_B"], "var")
            finally:
                os.environ.pop("ENV_TEST_A", None)
                os.environ.pop("ENV_TEST_B", None)

ORNEK_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>az aranan</title><ht:approx_traffic>200+</ht:approx_traffic></item>
<item><title>Galatasaray</title><ht:approx_traffic>50.000+</ht:approx_traffic>
 <ht:news_item><ht:news_item_title>Mac sonucu</ht:news_item_title>
 <ht:news_item_snippet>Ozet</ht:news_item_snippet><ht:news_item_url>https://ornek.com/a</ht:news_item_url>
 <ht:news_item_source>Ornek</ht:news_item_source></ht:news_item>
</item></channel></rss>"""


class TrendTest(unittest.TestCase):
    def test_coz_ve_sirala(self):
        t = trend.trendleri_coz(ORNEK_RSS)
        self.assertEqual([x["konu"] for x in t], ["Galatasaray", "az aranan"])
        self.assertEqual(t[0]["trafik"], 50000)
        self.assertEqual(t[0]["haberler"][0]["url"], "https://ornek.com/a")
        self.assertEqual(t[1]["haberler"], [])

    def test_trafik(self):
        self.assertEqual(trend.trafik_sayisi("1,000+"), 1000)
        self.assertEqual(trend.trafik_sayisi(""), 0)


class MetinTest(unittest.TestCase):
    def gecerli(self, **degisen):
        veri = {"uygun": True, "baslik": "Merak eden herkes", "aciklama": "a",
                "etiketler": ["#bir", "iki"], "metin": " ".join(["kelime"] * 120),
                "gorseller": ["city"]}
        veri.update(degisen)
        return veri

    def test_shorts_etiketi_eklenir(self):
        d = metin.metni_dogrula(self.gecerli())
        self.assertTrue(d["baslik"].endswith("#Shorts"))
        self.assertEqual(d["etiketler"], ["bir", "iki"])

    def test_cumle_listesi_birlestirilir(self):
        d = metin.metni_dogrula(self.gecerli(metin=None, cumleler=["kelime " * 10] * 6))
        self.assertEqual(len(d["metin"].split()), 60)

    def test_kisa_metin_bir_kez_uzatilir(self):
        import json
        cevaplar = [
            json.dumps({"uygun": True, "baslik": "B", "cumleler": ["kısa bir cümle"], "gorseller": []}),
            json.dumps({"cumleler": ["uzun cümle " * 6] * 10}),
        ]
        istemler = []
        asil = metin.yapay_zeka
        metin.yapay_zeka = lambda istem: (istemler.append(istem), cevaplar.pop(0))[1]
        try:
            d = metin.metin_yaz({"konu": "k", "haberler": []}, tarih="12.11.2026")
        finally:
            metin.yapay_zeka = asil
        self.assertEqual(len(d["metin"].split()), 120)
        self.assertIn("12.11.2026", istemler[0])
        self.assertIn("çok kısa (3 kelime)", istemler[1])

    def test_uygun_metin_olarak_gelirse(self):
        self.assertTrue(metin.metni_dogrula(self.gecerli(uygun="true"))["metin"])
        with self.assertRaises(ValueError):
            metin.metni_dogrula(self.gecerli(uygun="false"))

    def test_baslik_temizlenir(self):
        self.assertEqual(metin.baslik_temizle("🔥  Galatasaray'da   bomba! ⚽"), "Galatasaray'da bomba!")
        self.assertEqual(metin.baslik_temizle("İSTANBUL'DA IŞIL IŞIL GECE"), "İstanbul'da Işıl Işıl Gece")
        self.assertEqual(metin.baslik_temizle("TRT 1 Bugün"), "TRT 1 Bugün")  # kısaltmaya dokunma
        d = metin.metni_dogrula(self.gecerli(baslik="GALATASARAY DERBİYİ KAZANDI 🔥", etiketler=["Spor", "#spor", "maç"]))
        self.assertEqual(d["baslik"], "Galatasaray Derbiyi Kazandı #Shorts")
        self.assertEqual(d["etiketler"], ["Spor", "maç"])

    def test_uslup_ipucu_istemde(self):
        import json
        istemler = []
        asil = metin.yapay_zeka
        metin.yapay_zeka = lambda istem: (istemler.append(istem), json.dumps(
            {"uygun": True, "baslik": "Sarı uyarı", "cumleler": ["bugün için sarı kodlu uyarı var."] * 10}))[1]
        self.addCleanup(setattr, metin, "yapay_zeka", asil)
        metin.metin_yaz({"konu": "istanbul", "haberler": []}, kaynak="sarı kodlu uyarı", uslup="Kısa ve net anlat.")
        self.assertIn("ANLATIM İPUCU", istemler[0])
        self.assertIn("Kısa ve net anlat.", istemler[0])
        self.assertIn("en fazla 12 kelime", istemler[0])

    def test_soru_kapanisi_uydurma_sayilmaz(self):
        self.assertEqual(kaynak.desteklenmeyenler(
            "Sizce bu karar doğru mu? Yorumlarda buluşalım. Acaba ne olacak?", "bu karar doğru"), [])

    def test_uygun_degil(self):
        with self.assertRaises(ValueError):
            metin.metni_dogrula(self.gecerli(uygun=False, neden="kaza haberi"))

    def test_kisa_metin_reddedilir(self):
        with self.assertRaises(ValueError):
            metin.metni_dogrula(self.gecerli(metin="çok kısa"))


class SaglayiciTest(unittest.TestCase):
    def setUp(self):
        self.asil = metin.saglayicilar
        self.cagrilar = []
        metin._KAPALI.clear()

    def tearDown(self):
        metin.saglayicilar = self.asil

    def _sahte(self, ad, kod=None):
        import urllib.error

        def cagri(istem):
            self.cagrilar.append(ad)
            if kod:
                raise urllib.error.HTTPError("u", kod, "hata", None, None)
            return ad
        return (ad, cagri)

    def test_kota_dolunca_ayni_modeli_uc_kez_dener_sonra_yedege_gecer(self):
        metin.saglayicilar = lambda: [self._sahte("github", 429), self._sahte("gemini")]
        self.assertEqual(metin.yapay_zeka("x", bekleme=(0, 0)), "gemini")
        self.assertEqual(self.cagrilar, ["github"] * 3 + ["gemini"])

    def test_kalici_hatada_beklemeden_yedege_gecer(self):
        metin.saglayicilar = lambda: [self._sahte("github", 401), self._sahte("gemini")]
        self.assertEqual(metin.yapay_zeka("x", bekleme=(0, 0)), "gemini")
        self.assertEqual(self.cagrilar, ["github", "gemini"])

    def test_kalici_hata_veren_bir_daha_denenmez(self):
        metin.saglayicilar = lambda: [self._sahte("gemini", 402), self._sahte("ollama")]
        metin.yapay_zeka("x", bekleme=(0, 0))
        metin.yapay_zeka("y", bekleme=(0, 0))
        self.assertEqual(self.cagrilar, ["gemini", "ollama", "ollama"])

    def test_hepsi_basarisizsa_saglayici_hatasi(self):
        metin.saglayicilar = lambda: [self._sahte("github", 400)]
        with self.assertRaises(metin.SaglayiciHatasi):
            metin.yapay_zeka("x", bekleme=(0, 0))

    def test_bozuk_cevapta_yedege_gecer(self):
        def bozuk(istem):
            self.cagrilar.append("github")
            raise ValueError("JSON olmayan cevap")
        metin.saglayicilar = lambda: [("github", bozuk), self._sahte("gemini")]
        self.assertEqual(metin.yapay_zeka("x", bekleme=(0, 0)), "gemini")
        self.assertEqual(self.cagrilar, ["github", "gemini"])

    def test_post_yonlendirmede_govde_korunur(self):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Isleyici(BaseHTTPRequestHandler):
            def do_POST(self):
                govde = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/eski":
                    self.send_response(302)
                    self.send_header("Location", "/yeni")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"yol": self.path, "govde": govde.decode()}).encode())

            def log_message(self, *a):
                pass

        sunucu = HTTPServer(("127.0.0.1", 0), Isleyici)
        threading.Thread(target=sunucu.serve_forever, daemon=True).start()
        try:
            adres = f"http://127.0.0.1:{sunucu.server_port}/eski"
            cevap = metin._post_json(adres, b'{"a": 1}', {"Content-Type": "application/json"}, 5)
        finally:
            sunucu.shutdown()
        self.assertEqual(cevap, {"yol": "/yeni", "govde": '{"a": 1}'})

    def test_saglayici_sirasi(self):
        eski = {k: os.environ.get(k) for k in ("OLLAMA_URL", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")}
        try:
            os.environ.update(OLLAMA_URL="http://localhost:11434", GEMINI_API_KEY="g", ANTHROPIC_API_KEY="c")
            os.environ.pop("YAPAY_ZEKA", None)
            adlar = [ad for ad, _ in self.asil()]  # varsayılan: önce anahtarsız yerel model
            self.assertEqual([a.split(":")[0] for a in adlar], ["ollama", "gemini", "gemini", "claude"])
            os.environ["YAPAY_ZEKA"] = "bulut"
            adlar = [ad for ad, _ in self.asil()]
            os.environ.pop("YAPAY_ZEKA")
            self.assertEqual([a.split(":")[0] for a in adlar], ["gemini", "gemini", "claude", "ollama"])
            del os.environ["OLLAMA_URL"], os.environ["GEMINI_API_KEY"], os.environ["ANTHROPIC_API_KEY"]
            self.assertEqual(self.asil(), [])
        finally:
            for k, v in eski.items():
                if v is not None:
                    os.environ[k] = v

    def test_turkce_anahtarlar_sadelesir(self):
        v = metin.json_coz('{"Cümleler": ["a b"], "Başlık": "x"}')
        self.assertEqual(v, {"cumleler": ["a b"], "baslik": "x"})
        self.assertEqual(metin.seslendirme_metni(v), "a b")

    def test_json_citleri_temizlenir(self):
        self.assertEqual(metin.json_coz('```json\n{"uygun": true}\n```'), {"uygun": True})
        with self.assertRaises(ValueError):
            metin.json_coz("JSON yok")


class SesTest(unittest.TestCase):
    def test_ust_baslik_tum_video_boyunca(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "a.ass")
            ses.ass_yaz([(0, 1.0, "a"), (1.0, 2.5, "b")], yol, ust_baslik="Konu başlığı", acilis=False)
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
        self.assertIn("Dialogue: 1,0:00:00.00,0:00:02.50,Ust,,0,0,0,,Konu başlığı", icerik)

    def _ass(self, gruplar, **kw):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "a.ass")
            ses.ass_yaz(gruplar, yol, **kw)
            with open(yol, encoding="utf-8") as f:
                return f.read()

    def test_acilis_karti_sonra_ust_serit_ve_ilerleme_cubugu(self):
        icerik = self._ass([(0, 3.0, "a"), (3.0, 9.0, "b")], ust_baslik="Konu")
        self.assertIn("Dialogue: 3,0:00:00.00,0:00:02.00,Kart,", icerik)
        self.assertIn("Dialogue: 1,0:00:01.80,0:00:09.00,Ust,,0,0,0,,{\\fad(200,0)}Konu", icerik)
        self.assertIn("\\t(0,9000,\\fscx100)", icerik)  # çubuk video boyunca dolar

    def test_karaoke_okunan_kelime_vurgulanir(self):
        g = ses.gruplandir([(0.0, 0.4, "istanbul"), (0.5, 0.4, "ışıl"), (1.0, 0.5, "ışıl.")])
        satirlar = [s for s in self._ass(g).splitlines() if ",Ana," in s]
        self.assertEqual(len(satirlar), 3)  # her kelime için bir satır
        self.assertIn("0:00:00.00,0:00:00.50", satirlar[0])
        self.assertIn("{\\c&H00E5FF&}İSTANBUL{\\c&HFFFFFF&} IŞIL IŞIL", satirlar[0])  # Türkçe büyük harf, nokta yok
        self.assertIn("İSTANBUL {\\c&H00E5FF&}IŞIL{\\c&HFFFFFF&} IŞIL", satirlar[1])
        self.assertIn("\\fscx82", satirlar[0])
        self.assertNotIn("\\fscx82", satirlar[1])  # büyüme yalnız grubun girişinde

    def test_grup_cumle_sonunda_kesilir(self):
        k = [(i * 0.5, 0.5, w) for i, w in enumerate("Bir iki. Üç dört beş altı?".split())]
        self.assertEqual([g[2] for g in ses.gruplandir(k)], ["Bir iki.", "Üç dört beş", "altı?"])

    def test_noktalama_asil_metinden_geri_gelir(self):
        k = [(0, 1, "Galatasaray'da"), (1, 1, "bomba"), (2, 1, "bilinmeyen"), (3, 1, "Sizce")]
        sonuc = ses.noktalama_ekle(k, "Galatasaray'da bomba! Peki, sizce?")
        self.assertEqual([x[2] for x in sonuc], ["Galatasaray'da", "bomba!", "bilinmeyen", "sizce?"])

    def test_cumle_kelimelere_bolunur(self):
        k = ses.kelimelere_bol([(1.0, 2.0, "bir iki üç dört")])
        self.assertEqual(len(k), 4)
        self.assertAlmostEqual(k[2][0], 2.0)

    def test_gruplar_bosluk_birakmaz(self):
        k = [(0.0, 0.3, "a"), (0.3, 0.3, "b"), (0.6, 0.3, "c"), (1.5, 0.3, "d")]
        g = ses.gruplandir(k, boyut=3)
        self.assertEqual(g[0][:3], (0.0, 1.5, "a b c"))
        self.assertEqual(g[0][3], [(0.0, 0.3, "a"), (0.3, 0.6, "b"), (0.6, 1.5, "c")])
        self.assertEqual(g[1][2], "d")

    def test_ass_kacis(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "a.ass")
            ses.ass_yaz([(0, 1.234, "süslü {parantez}")], yol)
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
        self.assertIn("0:00:01.23", icerik)
        self.assertIn("SÜSLÜ", icerik)
        self.assertIn("(PARANTEZ)", icerik)
        self.assertNotIn("{PARANTEZ", icerik)


class KaynakTest(unittest.TestCase):
    KAYNAK = ("istanbul [AA] İstanbul'un da aralarında bulunduğu 11 il için sarı kodlu uyarı. "
              "[NTV] Meteoroloji'den aralarında İstanbul'un da olduğu 11 il için sarı kodlu uyarı")

    def test_uydurma_il_yakalanir(self):
        uydurma = ("Meteoroloji 11 il için uyarı yaptı. İstanbul'un yanı sıra Antalya, Adana ve İzmir de etkileniyor. "
                   "Uyarı 3 gün sürecek.")
        self.assertEqual(kaynak.desteklenmeyenler(uydurma, self.KAYNAK), ["Antalya", "Adana", "İzmir", "3"])

    def test_baslikta_buyuk_harf_sorun_degil_sayi_sorun(self):
        icerik = {"baslik": "Sarı Kod Uyarısının Detayları", "metin": "Meteoroloji 11 il için uyarı yaptı."}
        self.assertEqual(metin._uydurmalar(icerik, self.KAYNAK), [])
        icerik["baslik"] = "Sarı Kod 3 Gün Sürecek"
        self.assertEqual(metin._uydurmalar(icerik, self.KAYNAK), ["3"])

    def test_kaynaga_uygun_metin_temiz(self):
        temiz = "Sarı kod verildi. Meteoroloji'nin uyarısına göre İstanbul dahil 11 ilde dikkatli olun."
        self.assertEqual(kaynak.desteklenmeyenler(temiz, self.KAYNAK), [])

    def test_paragraflar(self):
        html = ("<html><script>var p='<p>gizli</p>';</script><p>Kısa</p>"
                "<p>Bu paragraf yeterince uzun bir haber cümlesidir, <b>kalın</b> kısmıyla.</p></html>")
        self.assertEqual(kaynak.paragraflari_cikar(html),
                         ["Bu paragraf yeterince uzun bir haber cümlesidir, kalın kısmıyla."])

    def _sahte_yz(self, cevaplar):
        import json
        asil = metin.yapay_zeka
        metin.yapay_zeka = lambda istem: json.dumps(cevaplar.pop(0))
        self.addCleanup(setattr, metin, "yapay_zeka", asil)

    def test_uydurma_bir_kez_duzelttirilir(self):
        temiz = ["İstanbul dahil 11 il için sarı kodlu uyarı verildi ve herkes dikkatli olmalı."] * 10
        self._sahte_yz([
            {"uygun": True, "baslik": "Sarı uyarı", "cumleler": ["Antalya da uyarı listesinde yer alıyor bugün."] * 10},
            {"baslik": "Sarı uyarı", "cumleler": temiz},
        ])
        d = metin.metin_yaz({"konu": "istanbul", "haberler": []}, tarih="12.11.2026", kaynak=self.KAYNAK)
        self.assertNotIn("Antalya", d["metin"])

    def test_basarili_basliklar_istemde(self):
        import json
        istemler = []
        asil = metin.yapay_zeka
        metin.yapay_zeka = lambda istem: (istemler.append(istem), json.dumps(
            {"uygun": True, "baslik": "Sarı uyarı", "cumleler": ["İstanbul dahil 11 il için sarı kodlu uyarı var."] * 10}))[1]
        self.addCleanup(setattr, metin, "yapay_zeka", asil)
        metin.metin_yaz({"konu": "istanbul", "haberler": []}, tarih="12.11.2026", kaynak=self.KAYNAK,
                        ornekler=["Çok izlenen başlık"])
        self.assertIn("- Çok izlenen başlık", istemler[0])

    def test_duzelmezse_konu_atlanir(self):
        kotu = ["Antalya da uyarı listesinde yer alıyor bugün."] * 10
        self._sahte_yz([{"uygun": True, "baslik": "B", "cumleler": kotu}, {"baslik": "B", "cumleler": kotu}])
        with self.assertRaises(ValueError):
            metin.metin_yaz({"konu": "istanbul", "haberler": []}, tarih="12.11.2026", kaynak=self.KAYNAK)


class GorselTest(unittest.TestCase):
    def test_openverse_buyuk_gorseli_secer(self):
        from shorts import video
        veri = {"results": [{"url": "http://k/kucuk.jpg", "width": 300, "height": 200},
                            {"url": "http://k/buyuk.jpg", "width": 1200, "height": 1600}]}
        self.assertEqual(video.openverse_sec(veri), "http://k/buyuk.jpg")
        self.assertIsNone(video.openverse_sec({"results": []}))

    def test_pexels_birden_cok_dikey_video(self):
        def v(kimlik, *boyutlar):
            return {"id": kimlik, "video_files": [{"width": g, "height": y, "link": f"{kimlik}-{g}"} for g, y in boyutlar]}
        veri = {"videos": [v(1, (720, 1280), (1080, 1920), (2160, 3840)), v(2, (1920, 1080)), v(3, (720, 1280)),
                           v(4, (1080, 1920))]}
        self.assertEqual(video.pexels_sec(veri, 2), [(1, "1-1080"), (3, "3-720")])  # yatay olan atlanır
        self.assertEqual(video.pexels_sec({"videos": []}), [])

    def test_sahne_plani(self):
        adet, tek = video.sahne_plani(56.0, 10)
        self.assertEqual(adet, 16)  # yaklaşık 3,5 saniyede bir sahne
        self.assertAlmostEqual(adet * tek - (adet - 1) * video.GECIS_SN, 56.0, delta=adet / video.FPS)
        self.assertAlmostEqual(tek * video.FPS, round(tek * video.FPS))  # kare sınırında
        self.assertEqual(video.sahne_plani(56.0, 2)[0], 6)  # klip en fazla üç kez
        self.assertEqual(video.sahne_plani(5.0, 4)[0], 4)
        self.assertEqual(video.sahne_plani(56.0, 0), (0, 0.0))


class KonuTest(unittest.TestCase):
    def aday(self, ad, trafik=1000, *basliklar):
        return {"konu": ad, "trafik": trafik, "haberler": [{"baslik": b} for b in basliklar]}

    def test_tur(self):
        self.assertEqual(konu.tur(self.aday("kim min jae", 1, "Süper Lig devi transfer için harekete geçti")), "spor")
        self.assertEqual(konu.tur(self.aday("tabii", 1, "Yeni dizi belli oldu")), "magazin")
        self.assertEqual(konu.tur(self.aday("outlook çöktü mü")), "teknoloji")
        self.assertEqual(konu.tur(self.aday("konya hava durumu")), "hava")
        self.assertEqual(konu.tur(self.aday("ekpss branş sıralaması")), "egitim")
        self.assertEqual(konu.tur(self.aday("emekli zammı")), "ekonomi")
        self.assertEqual(konu.tur(self.aday("ne zaman", 1, "Kiralık oyuncu geri dönüyor")), "magazin")  # zam/kira değil
        self.assertEqual(konu.tur(self.aday("bambaşka bir şey")), "diger")

    def test_izlenen_tur_one_gecer(self):
        adaylar = [self.aday("konya hava durumu", 20000), self.aday("outlook çöktü mü", 10000),
                   self.aday("galatasaray transfer", 2000), self.aday("yeni dizi fragmanı", 2000)]
        sira = [a["konu"] for a in konu.sirala(adaylar, [])]
        self.assertEqual(sira[:2], ["galatasaray transfer", "yeni dizi fragmanı"])
        self.assertEqual(sira[-1], "konya hava durumu")

    def test_agirlik_kanal_verisinden_ogrenir(self):
        def video_(ad, izlenme, gizlilik="public"):
            return {"tarih": "2026-11-12T06:00:00+00:00", "konu": ad, "baslik": ad, "video_id": "v",
                    "izlenme": izlenme, "gizlilik": gizlilik}
        self.assertEqual(konu.agirliklar([]), konu.ON)
        kayit = [video_("galatasaray transfer", 10), video_("fenerbahçe maçı", 20), video_("derbi", 5),
                 video_("emekli zammı", 900), video_("asgari ücret", 1100), video_("dolar", 5000, "private")]
        a = konu.agirliklar(kayit)
        self.assertLess(a["spor"], konu.ON["spor"])
        self.assertGreater(a["ekonomi"], konu.ON["ekonomi"])
        self.assertGreater(a["ekonomi"], a["spor"])  # kanal verisi başlangıç katsayısını tersine çevirebilir
        self.assertEqual(a["hava"], konu.ON["hava"])  # verisi olmayan tür değişmez
        self.assertEqual(konu.tur_ozeti(kayit)[0], ("ekonomi", 2, 1000))  # özel video sayılmaz

    def test_kayitli_tur_onceliklidir(self):
        self.assertEqual(konu.kayit_turu({"konu": "galatasaray", "baslik": "x", "tur": "magazin"}), "magazin")
        self.assertEqual(konu.kayit_turu({"konu": "galatasaray", "baslik": "x"}), "spor")

    def test_benzer_konu(self):
        self.assertTrue(konu.benzer_mi("arda okan kurtulan", "Galatasaray Arda Okan"))
        self.assertTrue(konu.benzer_mi("İstanbul", "istanbul "))
        self.assertFalse(konu.benzer_mi("galatasaray maçı", "galatasaray transfer"))
        self.assertFalse(konu.benzer_mi("halef final mi yapıyor", "halef yeni bölüm"))


class YukleTest(unittest.TestCase):
    class Hata(Exception):
        def __init__(self, kod):
            super().__init__(f"HTTP {kod}")
            self.resp = type("Yanit", (), {"status": kod})()

    class Istek:
        def __init__(self, olaylar):
            self.olaylar, self.cagri = list(olaylar), 0

        def next_chunk(self):
            self.cagri += 1
            olay = self.olaylar.pop(0)
            if isinstance(olay, Exception):
                raise olay
            return None, olay

    def test_gecici_hatada_kaldigi_yerden_surer(self):
        istek = self.Istek([None, self.Hata(503), ConnectionResetError("koptu"), {"id": "abc"}])
        self.assertEqual(yukle.parcali_yukle(istek, bekleme=(0, 0)), "abc")
        self.assertEqual(istek.cagri, 4)

    def test_kalici_hata_hemen_yukselir(self):
        istek = self.Istek([self.Hata(403), {"id": "abc"}])
        with self.assertRaises(self.Hata):
            yukle.parcali_yukle(istek, bekleme=(0, 0))
        self.assertEqual(istek.cagri, 1)

    def test_gizlilik_ayar_dosyasi_once_gelir(self):
        klasor = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, klasor, True)
        yol = os.path.join(klasor, "ayar.json")
        eski = os.environ.get("YT_GIZLILIK")
        self.addCleanup(lambda: os.environ.pop("YT_GIZLILIK", None) if eski is None
                        else os.environ.__setitem__("YT_GIZLILIK", eski))
        os.environ["YT_GIZLILIK"] = "private"
        self.assertEqual(yukle.gizlilik(yol), "private")  # dosya yok: ortam değişkeni
        with open(yol, "w", encoding="utf-8") as f:
            f.write('{"gizlilik": "Public"}')
        self.assertEqual(yukle.gizlilik(yol), "public")
        with open(yol, "w", encoding="utf-8") as f:
            f.write('{"gizlilik": "herkes"}')  # geçersiz değer yok sayılır
        self.assertEqual(yukle.gizlilik(yol), "private")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("bozuk")
        os.environ.pop("YT_GIZLILIK")
        self.assertEqual(yukle.gizlilik(yol), "private")

    def test_depodaki_ayar_otomatik_yayin(self):
        self.assertEqual(yukle.gizlilik(), "public")

    def test_tam_yanit_istenirse_doner(self):
        istek = self.Istek([{"id": "abc", "status": {"privacyStatus": "public"}}])
        self.assertEqual(yukle.parcali_yukle(istek, tam=True)["status"]["privacyStatus"], "public")

    def test_denemeler_bitince_yukselir(self):
        istek = self.Istek([self.Hata(500)] * 3)
        with self.assertRaises(self.Hata):
            yukle.parcali_yukle(istek, bekleme=(0, 0))
        self.assertEqual(istek.cagri, 3)


class AnalizTest(unittest.TestCase):
    class SahteYouTube:
        def __init__(self, ogeler):
            self.ogeler, self.istenen = ogeler, []

        def videos(self):
            return self

        def list(self, part, id):
            self.istenen.append(id)
            ogeler = [o for o in self.ogeler if o["id"] in id.split(",")]
            return type("Istek", (), {"execute": lambda s: {"items": ogeler}})()

    def kayit(self):
        return [
            {"tarih": "2026-11-12T06:00:00+00:00", "konu": "a", "baslik": "A başlık", "video_id": "v1"},
            {"tarih": "2026-11-12T15:00:00+00:00", "konu": "b", "baslik": "B | başlık", "video_id": "v2"},
            {"tarih": "2026-11-13T06:00:00+00:00", "konu": "c", "baslik": "C başlık", "video_id": None},
        ]

    def test_istatistikler_yazilir(self):
        yt = self.SahteYouTube([
            {"id": "v1", "statistics": {"viewCount": "120", "likeCount": "9"}, "status": {"privacyStatus": "public"}},
            {"id": "v2", "statistics": {"viewCount": "800"}, "status": {"privacyStatus": "private"}},
        ])
        k = self.kayit()
        self.assertEqual(analiz.istatistik_guncelle(k, yt), 2)
        self.assertEqual(yt.istenen, ["v1,v2"])
        self.assertEqual((k[0]["izlenme"], k[0]["begeni"], k[0]["yorum"]), (120, 9, 0))
        self.assertNotIn("izlenme", k[2])

    def test_en_iyi_basliklar_yalniz_herkese_acik(self):
        k = self.kayit()
        k[0].update(izlenme=120, begeni=9, gizlilik="public")
        k[1].update(izlenme=800, gizlilik="private")
        self.assertEqual(analiz.en_iyi_basliklar(k), ["A başlık"])

    def test_rapor(self):
        k = self.kayit()
        k[0].update(izlenme=120, begeni=9, yorum=1, gizlilik="public")
        r = analiz.rapor(k)
        self.assertIn("Toplam izlenme: 120", r)
        self.assertIn("[A başlık](https://youtube.com/shorts/v1)", r)
        self.assertIn("B / başlık", r)  # tablo bozulmasın
        self.assertIn("| yüklenmedi |", r)

    def test_rapor_tur_tablosu_ve_bekleyenler(self):
        k = self.kayit()
        k[0].update(konu="galatasaray transfer", izlenme=120, begeni=9, gizlilik="public")
        k[1].update(izlenme=3, gizlilik="private")
        k[2].update(durum="yükleme hatası: HttpError: kota | doldu")
        r = analiz.rapor(k)
        self.assertIn("| Spor | 1 | 120 |", r)
        self.assertIn("## Herkese açılmayı bekleyenler", r)
        self.assertIn("(https://studio.youtube.com/video/v2/edit)", r)
        self.assertNotIn("video/v1/edit", r)
        self.assertIn("| yükleme hatası: HttpError: kota / doldu |", r)

    def test_haftalik_ozet(self):
        k = self.kayit()
        k[0].update(konu="galatasaray transfer", izlenme=120, begeni=9, gizlilik="public")
        k[1].update(izlenme=3, gizlilik="private")
        simdi = datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)  # pazartesi sabahı
        ozet = analiz.haftalik_ozet(k, simdi)
        self.assertIn("Üretilen: 3, yüklenen: 2", ozet)
        self.assertIn("123 izlenme", ozet)
        self.assertIn("En iyi: A başlık (120 izlenme)", ozet)
        self.assertIn("En çok izlenen tür: Spor", ozet)
        self.assertIn("bekleyen: 1 video", ozet)
        self.assertIsNone(analiz.haftalik_ozet(k, simdi + timedelta(days=30)))

    def test_haftalik_ozet_yalniz_pazartesi_sabahi_bir_kez(self):
        gonderilen = []
        asil = ana.telegram_bildir
        ana.telegram_bildir = gonderilen.append
        self.addCleanup(setattr, ana, "telegram_bildir", asil)
        k = self.kayit()
        pazartesi = datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)
        self.assertTrue(ana.haftalik_ozet_gonder(k, pazartesi))
        self.assertFalse(ana.haftalik_ozet_gonder(k, pazartesi.replace(hour=15)))  # akşam çalıştırması
        self.assertFalse(ana.haftalik_ozet_gonder(k, pazartesi + timedelta(days=1)))  # salı
        k.append({"tarih": "2026-11-16T05:00:00+00:00", "konu": "d", "baslik": "D", "video_id": None})
        self.assertFalse(ana.haftalik_ozet_gonder(k, pazartesi))  # o gün zaten çalışmış
        self.assertEqual(len(gonderilen), 1)


class AnaTest(unittest.TestCase):
    def test_yakin_zamanda_yapilan_atlanir(self):
        simdi = datetime.now(timezone.utc)
        kayit = [{"konu": "Galatasaray ", "tarih": simdi.isoformat()},
                 {"konu": "eski", "tarih": (simdi - timedelta(days=30)).isoformat()}]
        t = [{"konu": "galatasaray"}, {"konu": "Eski"}, {"konu": "yeni"}]
        self.assertEqual([x["konu"] for x in yeni_trendler(t, kayit)], ["Eski", "yeni"])

    def test_benzer_konu_da_atlanir(self):
        kayit = [{"konu": "arda okan kurtulan", "tarih": datetime.now(timezone.utc).isoformat()}]
        t = [{"konu": "galatasaray arda okan"}, {"konu": "arda güler"}]
        self.assertEqual([x["konu"] for x in yeni_trendler(t, kayit)], ["arda güler"])

    def _yukleme(self, sahte_yukle, ayar="public"):
        klasor = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, klasor, True)
        asil_ayar = yukle.AYAR_DOSYASI
        yukle.AYAR_DOSYASI = os.path.join(klasor, "ayar.json")
        self.addCleanup(setattr, yukle, "AYAR_DOSYASI", asil_ayar)
        with open(yukle.AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump({"gizlilik": ayar}, f)
        eski = {a: os.environ.get(a) for a in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "KURU_CALISMA")}
        asil = yukle.youtube_yukle
        os.environ.update(YT_CLIENT_ID="a", YT_CLIENT_SECRET="b", YT_REFRESH_TOKEN="c")
        os.environ.pop("KURU_CALISMA", None)
        yukle.youtube_yukle = sahte_yukle

        def geri():
            yukle.youtube_yukle = asil
            for a, v in eski.items():
                os.environ.pop(a, None) if v is None else os.environ.__setitem__(a, v)
        self.addCleanup(geri)
        return ana.yuklemeyi_dene("v.mp4", {"baslik": "B", "etiketler": []}, "açıklama", "spor")

    def test_yukleme_hatasi_calistirmayi_cokertmez(self):
        def patla(*a, **kw):
            raise RuntimeError("kota doldu")
        kimlik, durum = self._yukleme(patla)
        self.assertIsNone(kimlik)
        self.assertEqual(durum, "yükleme hatası: RuntimeError: kota doldu")

    def test_yuklemede_kategori_ture_gore(self):
        gelen = {}
        kimlik, durum = self._yukleme(lambda *a, **kw: gelen.update(kw) or ("vid1", "private"), ayar="private")
        self.assertEqual((kimlik, durum, gelen["kategori"]), ("vid1", "yüklendi", "17"))

    def test_otomatik_yayinda_durum_yayinda(self):
        self.assertEqual(self._yukleme(lambda *a, **kw: ("vid1", "public")), ("vid1", "yayında"))

    def test_youtube_ozel_tutarsa_bildirilir(self):
        self.assertEqual(self._yukleme(lambda *a, **kw: ("vid1", "private")), ("vid1", "yüklendi (YouTube özel tuttu)"))

    def test_kuru_calisma_yuklemez(self):
        os.environ["KURU_CALISMA"] = "1"
        self.addCleanup(os.environ.pop, "KURU_CALISMA", None)
        self.assertEqual(ana.yuklemeyi_dene("v.mp4", {}, "", "spor"), (None, "kuru çalışma"))

    def test_hassas_konular_elenir(self):
        self.assertEqual(hassas_mi({"konu": "13 yargı paketi infaz düzenlemesi", "haberler": []}), "yargı")
        self.assertEqual(hassas_mi({"konu": "son depremler", "haberler": []}), "depremler")
        self.assertTrue(hassas_mi({"konu": "maç", "haberler": [{"baslik": "Meclis'te tartışma"}]}))
        self.assertTrue(hassas_mi({"konu": "tır", "haberler": [{"baslik": "Otoyolda kaza"}]}))
        self.assertIsNone(hassas_mi({"konu": "lodos", "haberler": [{"baslik": "İstanbul'da fırtına uyarısı"}]}))
        self.assertIsNone(hassas_mi({"konu": "ekpss branş sıralaması", "haberler": []}))
        self.assertEqual(hassas_mi({"konu": "regaip kandili ne zaman", "haberler": []}), "kandili")
        self.assertTrue(hassas_mi({"konu": "cuma", "haberler": [{"baslik": "Cuma namazı saat kaçta?"}]}))
        self.assertIsNone(hassas_mi({"konu": "galatasaray", "haberler": [{"baslik": "Galatasaray kazandı, dinlenme günü"}]}))

    def test_aciklamada_kaynak_ve_bildirim(self):
        a = aciklama_olustur(
            {"aciklama": "Kısa açıklama.", "etiketler": ["spor haberi"]},
            {"haberler": [{"baslik": "x", "kaynak": "Ornek", "url": "https://ornek.com"}]},
        )
        self.assertIn("Ornek: https://ornek.com", a)
        self.assertIn("yapay zekâ", a)
        self.assertTrue(a.endswith("#sporhaberi #Shorts"))

    def test_aciklama_kancayla_baslar(self):
        a = aciklama_olustur(
            {"aciklama": "Kısa açıklama.", "etiketler": list("abcdefg"), "metin": "Bomba patladı mı? İkinci cümle."},
            {"haberler": []},
        )
        self.assertTrue(a.startswith("Bomba patladı mı?\nKısa açıklama."))
        self.assertTrue(a.endswith("#a #b #c #d #e #Shorts"))


class UydurmaKontroluTest(unittest.TestCase):
    def test_cumle_icinde_buyuk_harfli_yaygin_kelime_uydurma_sayilmaz(self):
        self.assertEqual(kaynak.desteklenmeyenler("Peki, Sizce bu doğru mu? Ve Ahmet geldi.", "kaynak metin"),
                         ["Ahmet"])


class AyarTest(unittest.TestCase):
    def test_eksik_alan_varsayilandan_gelir(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "ayar.json")
            with open(yol, "w", encoding="utf-8") as f:
                json.dump({"gizlilik": "private", "ses": {"hiz": "+10%"}}, f)
            a = ayar.oku(yol)
            self.assertEqual(a["gizlilik"], "private")
            self.assertEqual(a["ses"], {"ad": "tr-TR-AhmetNeural", "hiz": "+10%", "perde": "+0Hz"})
            self.assertTrue(a["yorumlar"]["yanitla"])
            with open(yol, "w", encoding="utf-8") as f:
                f.write("bozuk")
            self.assertEqual(ayar.oku(yol), ayar.VARSAYILAN)

    def test_depodaki_ayar_gecerli(self):
        self.assertEqual(ayar.oku()["gizlilik"], "public")
        self.assertEqual(ayar.oku()["yapay_zeka"], "yerel")


class YeniSesTest(unittest.TestCase):
    def test_konusma_metni(self):
        self.assertEqual(ses.konusma_metni("Fiyat %15 arttı 🔥 #Shorts & 12 milyon €!"),
                         "Fiyat yüzde 15 arttı Shorts ve 12 milyon euro!")

    def test_sayi_vurgulari_birimle_birlesir(self):
        k = [(0, 0.3, "Kulüp"), (0.3, 0.3, "12"), (0.6, 0.3, "milyon"), (0.9, 0.3, "euro'luk"),
             (1.2, 0.3, "teklif"), (2.0, 0.3, "2026'da"), (5.0, 0.3, "29"), (5.3, 0.3, "yaşında.")]
        v = ses.vurgular(k)
        self.assertEqual([x[2] for x in v], ["12 milyon euro'luk", "29 yaşında"])  # 2026 çok yakın: atlandı
        self.assertAlmostEqual(v[0][1] - v[0][0], ses.ETIKET_SN)

    def test_srt_cumle_sonunda_birlesir(self):
        gruplar = [(0.0, 1.0, "Bir iki üç"), (1.0, 2.0, "dört beş."), (2.0, 3.5, "Altı?")]
        with tempfile.TemporaryDirectory() as d:
            yol = ses.srt_yaz(gruplar, os.path.join(d, "a.srt"))
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
        self.assertEqual(icerik, "1\n00:00:00,000 --> 00:00:02,000\nBir iki üç dört beş.\n\n"
                                 "2\n00:00:02,000 --> 00:00:03,500\nAltı?\n\n")

    def test_kelime_suresi_uzunlukla_orantili(self):
        k = ses.kelimelere_bol([(0.0, 3.0, "a uzunkelime")])
        self.assertLess(k[0][1], k[1][1])
        self.assertAlmostEqual(k[1][0] + k[1][1], 3.0)

    def test_edge_olmazsa_cevrimdisi_sese_gecer(self):
        asil_edge, asil_piper = ses._edge, ses._piper

        async def bozuk(metin_, yol):
            raise OSError("ağ yok")
        ses._edge = bozuk
        ses._piper = lambda metin_, yol: [(0.0, 1.0, metin_)]
        try:
            self.assertEqual(ses.seslendir("Merhaba.", "x.mp3"), [(0.0, 1.0, "Merhaba.")])
            self.assertEqual(ses.seslendir.motor, "piper")
        finally:
            ses._edge, ses._piper = asil_edge, asil_piper

    def test_ass_turkce_yazi_tipi_ve_etiket(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "a.ass")
            g = ses.gruplandir([(0, 0.4, "Tam"), (0.4, 0.4, "15"), (0.8, 0.4, "gol.")])
            ses.ass_yaz(g, yol)
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
        self.assertIn("Poppins ExtraBold", icerik)
        self.assertIn(",Etiket,", icerik)
        self.assertIn("}15 GOL", icerik)
        self.assertTrue(os.path.exists(os.path.join(ses.YAZITIPI, "Poppins-ExtraBold.ttf")))


def _commons_sayfa(baslik, g=1600, y=1200, mime="image/jpeg", sira=0):
    return {"title": f"File:{baslik}", "index": sira, "imageinfo": [{
        "mime": mime, "width": g, "height": y, "thumburl": f"https://upload.example/{sira}.jpg",
        "descriptionurl": "https://commons.example/x",
        "extmetadata": {"Artist": {"value": "<a href='x'>Ali Veli</a>"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}},
    }]}


class GorselTest(unittest.TestCase):
    def test_uygun_fotograflar_secilir(self):
        veri = {"query": {"pages": {
            "1": _commons_sayfa("Marco Asensio 2024.jpg", sira=0),
            "2": _commons_sayfa("Fenerbahçe logo.png", sira=1),
            "3": _commons_sayfa("Kucuk Asensio.jpg", g=400, y=300, sira=2),
            "4": _commons_sayfa("Asensio.svg", mime="image/svg+xml", sira=3),
            "5": _commons_sayfa("Random stadium.jpg", sira=4),
            "6": _commons_sayfa("Marco ASENSIO celebrating.jpg", sira=5),
        }}}
        secilen = gorsel.sonuclari_sec(veri, "marco asensio")
        self.assertEqual([s["baslik"] for s in secilen], ["Marco Asensio 2024.jpg", "Marco ASENSIO celebrating.jpg"])
        self.assertEqual(secilen[0]["yazar"], "Ali Veli")
        self.assertEqual(len(gorsel.sonuclari_sec(veri, "marco asensio", katı=False)), 3)

    def test_aksansiz_eslesme(self):
        veri = {"query": {"pages": {"1": _commons_sayfa("Brahim Diaz Real Madrid.jpg")}}}
        self.assertEqual(len(gorsel.sonuclari_sec(veri, "brahim díaz")), 1)

    def test_sorgular_ozel_adlari_ceker(self):
        t = {"konu": "asensio", "haberler": [{"baslik": "Marco Asensio için Fenerbahçe kararı"}]}
        s = gorsel.sorgular(t, {"gorseller": ["football"]})
        self.assertEqual(s[0], ("asensio", True))
        self.assertIn(("football", False), s)
        self.assertTrue(any(q.startswith("Fenerbahçe") for q, _ in s))

    def test_atif_metni(self):
        self.assertEqual(gorsel.atif_metni([]), "")
        m = gorsel.atif_metni([{"baslik": "A.jpg", "yazar": "Ali", "lisans": "CC BY 4.0"}])
        self.assertIn("A.jpg — Ali (CC BY 4.0)", m)

    def test_yatay_gorsel_bulanik_zemine_oturur(self):
        asil = video.boyut
        try:
            video.boyut = lambda yol: (1600, 900)
            self.assertIn("gblur", video.kare_suzgeci(".", "a.jpg", 1296, 2304))
            video.boyut = lambda yol: (1080, 1920)
            self.assertNotIn("gblur", video.kare_suzgeci(".", "a.jpg", 1296, 2304))
        finally:
            video.boyut = asil


class _Istek:
    def __init__(self, sonuc=None, hata=None, kayit=None, ad=None):
        self.sonuc, self.hata, self.kayit, self.ad = sonuc, hata, kayit, ad

    def execute(self):
        if self.kayit is not None:
            self.kayit.append(self.ad)
        if self.hata:
            raise self.hata
        return self.sonuc


class _YetkiHatasi(Exception):
    def __init__(self):
        super().__init__("insufficientPermissions: Request had insufficient authentication scopes.")
        self.resp = type("R", (), {"status": 403})()


class _SahteYouTube:
    def __init__(self, yorumlar=(), marka=None, yazma_hatasi=None):
        self.cagrilar, self.yanitlar, self.bekletilen, self.guncelleme = [], [], [], None
        self._yorumlar, self._hata = list(yorumlar), yazma_hatasi
        self._marka = marka if marka is not None else {"channel": {"description": "", "keywords": ""}}

    def channels(self):
        dis = self

        class C:
            def list(self, **kw):
                return _Istek({"items": [{"id": "UC1", "snippet": {"title": "Gündem Kanalı"},
                                          "statistics": {"subscriberCount": "120", "viewCount": "5000",
                                                         "videoCount": "20"},
                                          "brandingSettings": dis._marka}]})

            def update(self, part, body):
                dis.guncelleme = body
                return _Istek({}, dis._hata)
        return C()

    def commentThreads(self):
        dis = self

        class T:
            def list(self, **kw):
                return _Istek({"items": dis._yorumlar})
        return T()

    def comments(self):
        dis = self

        class Y:
            def insert(self, part, body):
                dis.yanitlar.append(body["snippet"])
                return _Istek({}, dis._hata)

            def setModerationStatus(self, id, moderationStatus):
                dis.bekletilen.append((id, moderationStatus))
                return _Istek({}, dis._hata)
        return Y()


def _yorum(kimlik, metin_, yazar="UCx", video_id="v1", yanitlar=()):
    return {"id": kimlik, "snippet": {"videoId": video_id, "topLevelComment": {"id": kimlik, "snippet": {
        "authorChannelId": {"value": yazar}, "textDisplay": metin_, "videoId": video_id,
        "publishedAt": "2026-11-14T10:00:00Z"}}},
        "replies": {"comments": [{"snippet": {"authorChannelId": {"value": a}}} for a in yanitlar]}}


class KanalTest(unittest.TestCase):
    def setUp(self):
        self.durum = kanal.bos_durum()
        self.durum["bilgi"] = {"kimlik": "UC1"}
        self.kayit = [{"video_id": "v1", "baslik": "Asensio kalıyor mu?", "ozet": "Asensio için teklif geldi."}]

    def test_yorum_turleri(self):
        self.assertEqual(kanal.yorum_turu("Bedava para kazan: www.ornek.com"), "spam")
        self.assertEqual(kanal.yorum_turu("Transfer ne zaman olacak?"), "soru")
        self.assertEqual(kanal.yorum_turu("Harika video 👏"), "olumlu")
        self.assertIsNone(kanal.yorum_turu("tamam"))

    def test_yorumlar_yonetilir(self):
        yt = _SahteYouTube([
            _yorum("c1", "Transfer ne zaman olacak?"),
            _yorum("c2", "Abone ol bana kanalıma gel www.spam.com"),
            _yorum("c3", "Kendi yorumum?", yazar="UC1"),
            _yorum("c4", "Zaten yanıtlanan?", yanitlar=("UC1",)),
            _yorum("c5", "ok"),
        ])
        istemler = []
        gunluk = kanal.yorumlari_yonet(yt, self.durum, self.kayit, {"yanitla": True},
                                       yanit_uret=lambda i: istemler.append(i) or "Takipte kalın, gelişmeleri paylaşacağız!")
        self.assertEqual(yt.yanitlar, [{"parentId": "c1", "textOriginal": "Takipte kalın, gelişmeleri paylaşacağız!"}])
        self.assertEqual(yt.bekletilen, [("c2", "heldForReview")])
        self.assertIn("Asensio için teklif geldi.", istemler[0])
        self.assertEqual(set(self.durum["yorumlar"]["yanitlanan"]), {"c1", "c4"})
        self.assertEqual(self.durum["yetki"]["yorum"], "tamam")
        self.assertEqual(len(gunluk), 2)
        # ikinci çalıştırma aynı yorumlara dokunmaz
        yt.yanitlar.clear()
        kanal.yorumlari_yonet(yt, self.durum, self.kayit, {}, yanit_uret=lambda i: "Teşekkürler!")
        self.assertEqual(yt.yanitlar, [])

    def test_uygunsuz_yanit_gonderilmez(self):
        yt = _SahteYouTube([_yorum("c1", "Bu ne?")])
        kanal.yorumlari_yonet(yt, self.durum, self.kayit, {}, yanit_uret=lambda i: "Detaylar http://x.com adresinde")
        self.assertEqual(yt.yanitlar, [])
        self.assertIn("c1", self.durum["yorumlar"]["yanitlanan"])

    def test_izin_eksikse_isaretlenir(self):
        yt = _SahteYouTube([_yorum("c1", "Ne zaman?"), _yorum("c2", "Peki ya sonra?")], yazma_hatasi=_YetkiHatasi())
        kanal.yorumlari_yonet(yt, self.durum, self.kayit, {}, yanit_uret=lambda i: "Takipte kalın!")
        self.assertEqual(self.durum["yetki"]["yorum"], "izin eksik")
        self.assertEqual(len(yt.yanitlar), 1)  # ilk hatada durur

    def test_marka_yalnizca_bos_alanlari_doldurur(self):
        self.durum["marka"]["kapak_denendi"] = "önceden"
        yt = _SahteYouTube(marka={"channel": {"description": "Benim açıklamam", "keywords": ""}})
        _, ham = kanal.kanal_bilgisi(yt)
        gunluk = kanal.marka_uygula(yt, ham, self.durum, ayar.VARSAYILAN["kanal"], ".")
        kanal_ = yt.guncelleme["brandingSettings"]["channel"]
        self.assertEqual(kanal_["description"], "Benim açıklamam")
        self.assertIn('gündem', kanal_["keywords"])
        self.assertEqual((kanal_["defaultLanguage"], kanal_["country"]), ("tr", "TR"))
        self.assertTrue(any("anahtar" in g for g in gunluk))
        # her şey doluysa güncelleme yapılmaz
        yt2 = _SahteYouTube(marka={"channel": {"description": "a", "keywords": "b", "defaultLanguage": "tr",
                                               "country": "TR"}, "image": {"bannerExternalUrl": "u"}})
        _, ham2 = kanal.kanal_bilgisi(yt2)
        self.assertEqual(kanal.marka_uygula(yt2, ham2, self.durum, ayar.VARSAYILAN["kanal"], "."), [])
        self.assertIsNone(yt2.guncelleme)

    def test_kanal_bilgisi_ve_gunluk_olcum(self):
        bilgi, _ = kanal.kanal_bilgisi(_SahteYouTube())
        self.assertEqual((bilgi["ad"], bilgi["abone"], bilgi["izlenme"]), ("Gündem Kanalı", 120, 5000))
        kanal.anlik_kaydet(self.durum, bilgi, date(2026, 11, 14))
        kanal.anlik_kaydet(self.durum, dict(bilgi, abone=125), date(2026, 11, 14))
        self.assertEqual(self.durum["gecmis"], [{"tarih": "2026-11-14", "abone": 125, "izlenme": 5000, "video": 20}])

    def test_hata_turu(self):
        self.assertEqual(kanal._hata_turu(_YetkiHatasi()), "yetki")
        kapali = Exception("accessNotConfigured: YouTube Analytics API has not been used in project")
        kapali.resp = type("R", (), {"status": 403})()
        self.assertEqual(kanal._hata_turu(kapali), "kapali")
        self.assertIsNone(kanal._hata_turu(ValueError("x")))

    def test_kanal_yonetimi_hatalarda_durmaz(self):
        class Bozuk:
            def reports(self):
                raise _YetkiHatasi()
        klasor = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, klasor, True)
        durum, gunluk = kanal.kanali_yonet(self.kayit, {}, ayar.VARSAYILAN, klasor, youtube=_SahteYouTube(),
                                           analitik=Bozuk(), yanit_uret=None)
        self.assertEqual(durum["bilgi"]["abone"], 120)
        self.assertEqual(durum["yetki"]["analitik"], "izin eksik")
        self.assertTrue(any("Analytics" in g for g in gunluk))


class PlanTest(unittest.TestCase):
    def test_hedef_tahmini(self):
        bugun = date(2026, 11, 14)
        self.assertEqual(plan.hedef_tahmini(120, 4, bugun), (500, (95, date(2027, 2, 17))))
        self.assertEqual(plan.hedef_tahmini(120, 0, bugun), (500, None))
        self.assertEqual(plan.hedef_tahmini(0, None, bugun), (100, None))

    def test_artis_olcumlerden_hesaplanir(self):
        d = {"gecmis": [{"tarih": "2026-11-10", "abone": 100, "izlenme": 1000},
                        {"tarih": "2026-11-14", "abone": 120, "izlenme": 3000}]}
        self.assertEqual(plan.gunluk_abone_artisi(d), 5)
        self.assertEqual(plan.gunluk_izlenme(d), 500)
        d["gunluk"] = [{"izlenme": 10, "abone_kazanc": 3, "abone_kayip": 1}] * 3
        self.assertEqual(plan.gunluk_abone_artisi(d), 2)

    def test_plan_bolumu(self):
        d = kanal.bos_durum()
        d["bilgi"] = {"ad": "Gündem", "abone": 120, "izlenme": 5000, "video": 20}
        d["gecmis"] = [{"tarih": "2026-11-10", "abone": 100, "izlenme": 1000, "video": 18},
                       {"tarih": "2026-11-14", "abone": 120, "izlenme": 5000, "video": 20}]
        d["yetki"] = {"yorum": "izin eksik", "analitik": "API kapalı"}
        metin_ = "\n".join(plan.plan_bolumu(d, [], date(2026, 11, 14), ortam={}))
        self.assertIn("## Kanal: Gündem", metin_)
        self.assertIn("Sonraki hedef **500 abone**: bu hızla yaklaşık 76 gün", metin_)
        self.assertIn("YouTube izni eksik", metin_)
        self.assertIn("YouTube Analytics API kapalı", metin_)
        self.assertIn("marka/profil.png", metin_)
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "marka", "profil.png")))


class KayitBicimiTest(unittest.TestCase):
    def test_eski_ve_yeni_bicim_okunur(self):
        asil = ana.KAYIT, ana.RAPOR
        with tempfile.TemporaryDirectory() as d:
            ana.KAYIT, ana.RAPOR = os.path.join(d, "k.json"), os.path.join(d, "r.md")
            try:
                with open(ana.KAYIT, "w", encoding="utf-8") as f:
                    json.dump([{"konu": "a", "tarih": "2026-11-14T00:00:00+00:00", "baslik": "A"}], f)
                self.assertEqual(ana.kaydi_oku()[0]["konu"], "a")
                self.assertEqual(ana.durumu_oku()["gecmis"], [])
                durum = ana.durumu_oku()
                durum["bilgi"] = {"ad": "Kanal", "abone": 3, "izlenme": 9, "video": 1}
                ana.kaydi_yaz(ana.kaydi_oku(), durum)
                self.assertEqual(ana.durumu_oku()["bilgi"]["abone"], 3)
                ana.kaydi_yaz(ana.kaydi_oku())  # durum verilmezse eskisi korunur
                self.assertEqual(ana.durumu_oku()["bilgi"]["ad"], "Kanal")
                with open(ana.RAPOR, encoding="utf-8") as f:
                    self.assertIn("## Kanal: Kanal", f.read())
            finally:
                ana.KAYIT, ana.RAPOR = asil

    def test_aciklamada_gorsel_atfi(self):
        icerik = {"metin": "Kanca.", "aciklama": "Açıklama", "etiketler": ["a"]}
        a = aciklama_olustur(icerik, {"haberler": []}, [{"baslik": "F.jpg", "yazar": "Ali", "lisans": "CC BY 4.0"}])
        self.assertIn("Görseller (Wikimedia Commons):\n- F.jpg — Ali (CC BY 4.0)", a)


class TelegramKomutTest(unittest.TestCase):
    def setUp(self):
        self.ayarlar = ayar.oku()
        self.kayit = [{"tarih": "2026-11-14T07:00:00+00:00", "baslik": "Asensio kalıyor mu?", "video_id": "v1",
                       "izlenme": 50, "begeni": 2, "durum": "yayında"}]
        self.kanal = {"bilgi": {"ad": "ScorpDas", "abone": 24, "izlenme": 7627, "video": 71}, "yetki": {}}

    def komut(self, metin_):
        return telegram.komut_isle(metin_, self.ayarlar, self.kayit, self.kanal, date(2026, 11, 14))

    def test_durum_ve_son(self):
        yanit, eylem = self.komut("/durum")
        self.assertIsNone(eylem)
        self.assertIn("ScorpDas: 24 abone", yanit)
        self.assertIn("Otomatik üretim: AÇIK", yanit)
        self.assertIn("https://youtube.com/shorts/v1", self.komut("/son")[0])

    def test_uretim_eylemleri(self):
        self.assertEqual(self.komut("/uret")[1], "uret")
        self.assertEqual(self.komut("/deneme@ScorpBot")[1], "deneme")

    def test_zamanlama_komutlari(self):
        self.komut("/duraklat")
        self.assertFalse(self.ayarlar["zamanlama"]["aktif"])
        self.komut("/devam")
        self.assertTrue(self.ayarlar["zamanlama"]["aktif"])
        self.komut("/saatler 8 12:30 20:00")
        self.assertEqual(self.ayarlar["zamanlama"]["saatler"], ["08:00", "12:30", "20:00"])
        self.assertIn("Biçim", self.komut("/saatler 25:00")[0])
        self.komut("/bitis 2027-01-31")
        self.assertEqual(self.ayarlar["zamanlama"]["bitis"], "2027-01-31")
        self.assertIn("geçmişte", self.komut("/bitis 2020-01-01")[0])
        self.komut("/bitis yok")
        self.assertIsNone(self.ayarlar["zamanlama"]["bitis"])

    def test_ayar_komutlari(self):
        self.komut("/gizlilik private")
        self.assertEqual(self.ayarlar["gizlilik"], "private")
        self.komut("/yorum kapat")
        self.assertFalse(self.ayarlar["yorumlar"]["yanitla"])
        self.komut("/ses emel")
        self.assertEqual(self.ayarlar["ses"]["ad"], "tr-TR-EmelNeural")
        self.assertIn("Bilinmeyen", self.komut("/xyz")[0])
        self.assertIn("/uret", self.komut("/yardim")[0])

    def test_rapor_tablosuz(self):
        r = self.komut("/rapor")[0]
        self.assertIn("ScorpDas", r)
        self.assertNotIn("|", r)


class KontrolTest(unittest.TestCase):
    def setUp(self):
        self.ayarlar = ayar.oku()
        self.simdi = datetime(2026, 11, 14, 9, 7, tzinfo=telegram.TR)

    def test_zamani_gelen_saat(self):
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, {}, self.simdi), ["2026-11-14 09:00"])
        d = {"tetiklenen": {"2026-11-14 09:00": {"zaman": "x"}}}
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, d, self.simdi), [])
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, {}, self.simdi.replace(hour=8)), [])
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, {}, self.simdi.replace(hour=15)), [])  # pencere 5 saat

    def test_duraklatma_bitis_ve_gunluk_sinir(self):
        self.ayarlar["zamanlama"]["aktif"] = False
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, {}, self.simdi), [])
        self.ayarlar["zamanlama"].update(aktif=True, bitis="2026-11-13")
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, {}, self.simdi), [])
        self.assertIn("Bitiş", kontrol.bitis_kontrol(self.ayarlar, {}, self.simdi))
        self.assertFalse(self.ayarlar["zamanlama"]["aktif"])
        self.ayarlar["zamanlama"].update(aktif=True, bitis=None, gunluk_en_cok=1)
        d = {"tetiklenen": {"2026-11-14 elle 08:00:00 uret": {"zaman": "x"}}}
        self.assertEqual(kontrol.zamani_gelenler(self.ayarlar, d, self.simdi), [])

    def test_basarisiz_uretim_bir_kez_yeniden_denenir(self):
        d = {"tetiklenen": {"2026-11-14 09:00": {"zaman": "2026-11-14T09:07:00+03:00", "deneme": 1}}}
        kosu = [{"created_at": "2026-11-14T06:07:30Z", "status": "completed", "conclusion": "failure"}]
        sonra = self.simdi + timedelta(hours=1)
        self.assertEqual(kontrol.yeniden_denenecekler(d, kosu, sonra), ["2026-11-14 09:00"])
        self.assertEqual(kontrol.yeniden_denenecekler(d, kosu, self.simdi + timedelta(minutes=20)), [])
        kosu[0]["conclusion"] = "success"
        self.assertEqual(kontrol.yeniden_denenecekler(d, kosu, sonra), [])
        kosu[0].update(status="in_progress", conclusion=None)
        self.assertEqual(kontrol.yeniden_denenecekler(d, kosu, sonra), [])

    def test_calistir_telegram_ve_uretim(self):
        with tempfile.TemporaryDirectory() as d:
            asil = (kontrol.DURUM, kontrol.KAYIT, ayar.DOSYA, telegram._api, kontrol._github)
            kontrol.DURUM, kontrol.KAYIT = os.path.join(d, "kontrol.json"), os.path.join(d, "k.json")
            ayar.DOSYA = os.path.join(d, "ayar.json")
            giden, github = [], []

            def sahte_api(yontem, veri=None, zaman_asimi=20):
                if yontem == "getUpdates":
                    return {"result": [
                        {"update_id": 5, "message": {"chat": {"id": 42}, "text": "/duraklat"}},
                        {"update_id": 6, "message": {"chat": {"id": 99}, "text": "/start"}},
                        {"update_id": 7, "message": {"chat": {"id": 99}, "text": "/uret"}},
                        {"update_id": 8, "message": {"chat": {"id": 42}, "text": "/uret"}},
                    ]}
                giden.append((yontem, veri))
                return {"ok": True}

            def sahte_github(yol, govde=None, yontem=None):
                github.append((yol, govde))
                return {"workflow_runs": []}
            telegram._api, kontrol._github = sahte_api, sahte_github
            eski = {k: os.environ.get(k) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
            os.environ.update(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="42")
            try:
                durum = kontrol.calistir(self.simdi)
            finally:
                kontrol.DURUM, kontrol.KAYIT, ayar.DOSYA, telegram._api, kontrol._github = asil
                for k, v in eski.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
            self.assertEqual(durum["telegram_offset"], 9)
            dispatch = [g for y, g in github if y.endswith("dispatches")]
            self.assertEqual(dispatch, [{"ref": "main", "inputs": {"kuru": "false"}}])  # yalnız sahibin /uret'i
            mesajlar = [v for y, v in giden if y == "sendMessage"]
            self.assertTrue(any(m["chat_id"] == "99" and "kimliği: 99" in m["text"] for m in mesajlar))
            self.assertFalse(any(m["chat_id"] == "99" and "üretimi" in m["text"] for m in mesajlar))
            with open(os.path.join(d, "ayar.json"), encoding="utf-8") as f:
                self.assertFalse(json.load(f)["zamanlama"]["aktif"])  # /duraklat kaydedildi
            # duraklatılmış olsa da /uret elle üretimi başlatır; zamanlanmış 09:00 başlatılmaz
            self.assertFalse(any(" 09:00" in a for a in durum["tetiklenen"]))


class KendiniOnarmaTest(unittest.TestCase):
    def test_kayitlar_birlesir(self):
        depodaki = {"videolar": [{"tarih": "2026-11-14T07:00:00+00:00", "konu": "a", "izlenme": 5, "olcum": "1"},
                                 {"tarih": "2026-11-14T10:00:00+00:00", "konu": "c"}],
                    "kanal": {"bilgi": {"olcum": "2026-11-14T10:00:00+00:00", "abone": 30}}}
        yeni = [{"tarih": "2026-11-14T07:00:00+00:00", "konu": "a", "izlenme": 9, "olcum": "2"},
                {"tarih": "2026-11-14T09:00:00+00:00", "konu": "b"}]  # eski biçim (liste)
        videolar, kanal_ = birlestir.birlestir(depodaki, yeni)
        self.assertEqual([v["konu"] for v in videolar], ["a", "b", "c"])
        self.assertEqual(videolar[0]["izlenme"], 9)
        self.assertEqual(kanal_["bilgi"]["abone"], 30)

    def test_art_arda_yukleme_engellenir(self):
        simdi = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
        os.environ.pop("KURU_CALISMA", None)
        yakin = [{"tarih": "2026-11-14T09:50:00+00:00", "video_id": "v"}]
        self.assertTrue(ana.yeni_yuklendi(yakin, simdi))
        self.assertFalse(ana.yeni_yuklendi([{"tarih": "2026-11-14T09:00:00+00:00", "video_id": "v"}], simdi))
        self.assertFalse(ana.yeni_yuklendi([{"tarih": "2026-11-14T09:50:00+00:00", "video_id": None}], simdi))

    def test_yeni_hatalar_bir_kez_bildirilir(self):
        kosular = [{"run_number": 40, "head_branch": "main", "status": "completed", "conclusion": "failure"},
                   {"run_number": 41, "head_branch": "eski-dal", "status": "completed", "conclusion": "failure"}]
        durum = {}
        self.assertEqual(kontrol.yeni_hatalar(durum, kosular), [])  # ilk çalıştırma: eski hatalar bildirilmez
        kosular.append({"run_number": 42, "head_branch": "main", "status": "completed", "conclusion": "failure"})
        self.assertEqual([k["run_number"] for k in kontrol.yeni_hatalar(durum, kosular)], [42])
        self.assertEqual(kontrol.yeni_hatalar(durum, kosular), [])

    def test_yeni_kalite_hatalari_yalnizca_yeni_ve_guncel_kosulari_secer(self):
        simdi = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
        eski = {"id": 1, "run_number": 10, "head_branch": "main", "status": "completed",
                "conclusion": "failure", "created_at": "2026-11-14T08:00:00Z"}
        yeni = {"id": 2, "run_number": 11, "head_branch": "main", "status": "completed",
                "conclusion": "failure", "created_at": "2026-11-14T11:30:00Z"}
        durum = {}
        self.assertEqual(kontrol.yeni_kalite_hatalari(durum, [eski], simdi), [])
        self.assertEqual(durum["son_gorulen_kalite_kosu"], 10)
        self.assertEqual(kontrol.yeni_kalite_hatalari(durum, [yeni, eski], simdi), [yeni])
        self.assertEqual(kontrol.yeni_kalite_hatalari(durum, [yeni, eski], simdi), [])

    def test_yeni_kalite_kosusu_devam_ediyorsa_izleme_numarasini_ilerletmez(self):
        devam = {"run_number": 12, "head_branch": "main", "status": "in_progress"}
        durum = {"son_gorulen_kalite_kosu": 11}
        self.assertEqual(kontrol.yeni_kalite_hatalari(durum, [devam], datetime.now(timezone.utc)), [])
        self.assertEqual(durum["son_gorulen_kalite_kosu"], 11)

    def test_nobetci_sessiz_durusu_yakalar(self):
        a = ayar.oku()
        simdi = datetime(2026, 11, 16, 12, 0, tzinfo=telegram.TR)
        eski = [{"tarih": "2026-11-14T10:00:00+00:00"}]
        self.assertTrue(kontrol.nobetci(a, {}, [], eski, simdi))
        self.assertFalse(kontrol.nobetci(a, {}, [{"status": "in_progress"}], eski, simdi))
        self.assertFalse(kontrol.nobetci(a, {"son_kurtarma": "2026-11-16T06:00:00+03:00"}, [], eski, simdi))
        self.assertFalse(kontrol.nobetci(a, {}, [], [{"tarih": "2026-11-16T05:00:00+00:00"}], simdi))
        a["zamanlama"]["aktif"] = False
        self.assertFalse(kontrol.nobetci(a, {}, [], eski, simdi))


class OtomatikKurulumTest(unittest.TestCase):
    def test_kurulum_metni(self):
        m = telegram.kurulum_metni({"yetki": {"yorum": "izin eksik", "analitik": "tamam"}},
                                   {"VAR_YOUTUBE": "true", "VAR_PEXELS": "false"})
        self.assertIn("✅ YouTube bağlantısı", m)
        self.assertIn("❌ Yorum yanıtlama izni", m)
        self.assertIn("✅ YouTube Analytics", m)
        self.assertIn("➖ Pexels", m)

    def test_ilk_start_yazan_sahip_olur(self):
        with tempfile.TemporaryDirectory() as d:
            asil = (kontrol.DURUM, kontrol.KAYIT, ayar.DOSYA, telegram._api, kontrol._github)
            kontrol.DURUM, kontrol.KAYIT = os.path.join(d, "kontrol.json"), os.path.join(d, "k.json")
            ayar.DOSYA = os.path.join(d, "ayar.json")
            giden = []

            def sahte_api(yontem, veri=None, zaman_asimi=20):
                if yontem == "getUpdates":
                    return {"result": [
                        {"update_id": 1, "message": {"chat": {"id": 7}, "text": "/durum"}},   # sahip yokken: yok sayılır
                        {"update_id": 2, "message": {"chat": {"id": 42}, "text": "/start"}},  # sahip olur
                        {"update_id": 3, "message": {"chat": {"id": 7}, "text": "/start"}},   # artık sahip olamaz
                        {"update_id": 4, "message": {"chat": {"id": 42}, "text": "/duraklat"}},
                    ]}
                giden.append((yontem, veri))
                return {"ok": True}
            telegram._api = sahte_api
            kontrol._github = lambda *a, **k: {"workflow_runs": []}
            eski = {k: os.environ.get(k) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
            os.environ["TELEGRAM_BOT_TOKEN"] = "t"
            os.environ.pop("TELEGRAM_CHAT_ID", None)
            try:
                kontrol.calistir(datetime(2026, 11, 14, 12, 7, tzinfo=telegram.TR))
                with open(ayar.DOSYA, encoding="utf-8") as f:
                    kayitli = json.load(f)
            finally:
                kontrol.DURUM, kontrol.KAYIT, ayar.DOSYA, telegram._api, kontrol._github = asil
                for k, v in eski.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
            self.assertEqual(kayitli["telegram"]["sohbet_id"], "42")
            self.assertFalse(kayitli["zamanlama"]["aktif"])  # sahibin komutu aynı turda işlendi
            mesajlar = [v for y, v in giden if y == "sendMessage"]
            self.assertTrue(any(m["chat_id"] == "42" and "sahibi olarak kaydedildi" in m["text"] for m in mesajlar))
            self.assertFalse(any(m["chat_id"] == "7" and "sahibi olarak" in m["text"] for m in mesajlar))


class YedekTest(unittest.TestCase):
    def test_arsiv_dosyalari_ve_ozeti_icerir(self):
        with tempfile.TemporaryDirectory() as d:
            kok = os.path.join(d, "depo")
            os.makedirs(os.path.join(kok, "marka"))
            for ad, icerik in (("yapilanlar.json", "{}"), ("ayar.json", "{}"), ("RAPOR.md", "# r"),
                               ("marka/profil.png", "png")):
                with open(os.path.join(kok, ad), "w", encoding="utf-8") as f:
                    f.write(icerik)
            hedef, adet = yedek.arsivle(os.path.join(d, "cikti"), kok=kok)
            self.assertEqual(adet, 4)
            import tarfile
            with tarfile.open(hedef) as tar:
                adlar = tar.getnames()
            self.assertIn("marka/profil.png", adlar)
            self.assertIn("manifest.json", adlar)

    def test_sir_iceren_dosyada_yedek_olusmaz(self):
        with tempfile.TemporaryDirectory() as d:
            kok = os.path.join(d, "depo")
            os.makedirs(kok)
            sahte = "1234567890:" + "A" * 35  # gerçek değil; yalnızca desen denemesi
            with open(os.path.join(kok, "ayar.json"), "w", encoding="utf-8") as f:
                f.write('{"belirtec": "%s"}' % sahte)
            cikti = os.path.join(d, "cikti")
            with self.assertRaises(yedek.SirBulundu):
                yedek.arsivle(cikti, kok=kok)
            self.assertFalse(os.path.exists(cikti))


if __name__ == "__main__":
    unittest.main()
