"""
MT5 Bot Kontrol Paneli + Yapay Zeka Sohbeti
Kurulum:  python panel.py --kur
Çalıştır: python panel.py
"""

import getpass
import importlib
import json
import os
import secrets
import sys
import time
from collections import defaultdict
from datetime import timedelta
from functools import wraps

import requests
from flask import Flask, Response, jsonify, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

DIZIN = os.path.dirname(os.path.abspath(__file__))
AYAR_DOSYA = os.path.join(DIZIN, "panel_ayar.json")
DURUM_DOSYA = os.path.join(DIZIN, "durum.json")
LOG_DOSYA = os.path.join(DIZIN, "bot.log")
DURAKLAT_DOSYA = os.path.join(DIZIN, "DURAKLAT")
KAPAT_DOSYA = os.path.join(DIZIN, "HEPSINI_KAPAT")

GUVENLI_AYARLAR = [
    "SYMBOLS", "TIMEFRAME", "RISK_PER_TRADE", "SL_ATR", "TAKE_PROFIT_R",
    "MAX_DAILY_LOSS", "MAX_OPEN_TRADES", "MAX_SPREAD_ATR", "EMA_FAST",
    "EMA_SLOW", "RSI_PERIOD", "RSI_OB", "RSI_OS", "ADX_MIN",
]


def ayar_oku() -> dict:
    if not os.path.exists(AYAR_DOSYA):
        return {}
    with open(AYAR_DOSYA, encoding="utf-8") as f:
        return json.load(f)


def kur() -> None:
    ayar = ayar_oku()
    print("=== Panel kurulumu ===")
    while True:
        s1 = getpass.getpass("Panel şifresi (en az 10 karakter, ekranda görünmez): ")
        if len(s1) < 10:
            print("Şifre çok kısa.")
            continue
        if s1 != getpass.getpass("Şifre tekrar: "):
            print("Şifreler eşleşmedi.")
            continue
        break
    port = input(f"Panel portu [{ayar.get('port', 8080)}]: ").strip()
    gemini = input("Gemini API anahtarı (yoksa boş bırakın, yerel yapay zeka kullanılır): ").strip()
    ayar.update(
        port=int(port) if port else ayar.get("port", 8080),
        sifre_hash=generate_password_hash(s1),
        gizli_anahtar=ayar.get("gizli_anahtar") or secrets.token_hex(32),
        ollama_model=ayar.get("ollama_model", "gemma3:1b"),
        gemini_model=ayar.get("gemini_model", "gemini-2.5-flash"),
    )
    if gemini:
        ayar["gemini_anahtar"] = gemini
    with open(AYAR_DOSYA, "w", encoding="utf-8") as f:
        json.dump(ayar, f, ensure_ascii=False, indent=2)
    print(f"Kaydedildi. Panel portu: {ayar['port']}")


AYAR = ayar_oku()
app = Flask(__name__)
app.secret_key = AYAR.get("gizli_anahtar") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

_giris_denemeleri = defaultdict(list)


def giris_gerekli(f):
    @wraps(f)
    def sar(*a, **k):
        if not session.get("ok"):
            return jsonify(hata="Oturum yok"), 401
        if request.method == "POST" and request.headers.get("X-Panel") != "1":
            return jsonify(hata="Geçersiz istek"), 403
        return f(*a, **k)
    return sar


def durum_oku() -> dict:
    d = {}
    if os.path.exists(DURUM_DOSYA):
        try:
            with open(DURUM_DOSYA, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
    yas = time.time() - d.get("zaman", 0)
    d["canli"] = yas < 180
    d["son_guncelleme_sn"] = int(yas) if d.get("zaman") else None
    d["duraklat_istendi"] = os.path.exists(DURAKLAT_DOSYA)
    d["kapat_bekliyor"] = os.path.exists(KAPAT_DOSYA)
    return d


def log_oku(n: int = 200) -> list:
    if not os.path.exists(LOG_DOSYA):
        return []
    with open(LOG_DOSYA, "rb") as f:
        f.seek(0, 2)
        boyut = f.tell()
        f.seek(max(0, boyut - 200_000))
        satirlar = f.read().decode("utf-8", errors="replace").splitlines()
    return satirlar[-n:]


def strateji_ayarlari() -> dict:
    try:
        if DIZIN not in sys.path:
            sys.path.insert(0, DIZIN)
        import config
        importlib.reload(config)
        return {k: getattr(config, k, None) for k in GUVENLI_AYARLAR}
    except Exception as e:
        return {"hata": str(e)}


def sistem_mesaji() -> str:
    durum = durum_oku()
    return (
        "Sen bu sunucuda çalışan MetaTrader 5 otomatik işlem botunun asistanısın. "
        "Kullanıcıyla her zaman Türkçe, kısa ve anlaşılır konuş; kullanıcı İngilizce bilmiyor. "
        "Yalnızca aşağıdaki verilere dayan, bilmediğin şeyi uydurma. Kâr garantisi verme. "
        "Kendin işlem açıp kapatamazsın; kullanıcı panelin 'Duraklat', 'Devam' ve "
        "'Tümünü kapat' düğmelerini kullanır.\n\n"
        "Botun stratejisi: kapanmış mumda EMA hızlı/yavaş kesişimi, RSI filtresi ve ADX trend gücü "
        "eşiği; stop ATR katı, kâr hedefi stopun katı; işlem başına sabit yüzde risk; günlük "
        "kayıp limiti dolunca o gün yeni işlem açılmaz.\n\n"
        f"STRATEJİ AYARLARI: {json.dumps(strateji_ayarlari(), ensure_ascii=False)}\n"
        f"ANLIK DURUM: {json.dumps(durum, ensure_ascii=False)}\n"
        "SON LOG SATIRLARI:\n" + "\n".join(log_oku(30))
    )


def ollama_sor(mesajlar: list) -> str:
    r = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": AYAR.get("ollama_model", "gemma3:1b"),
            "messages": [{"role": "system", "content": sistem_mesaji()}] + mesajlar,
            "stream": False,
            "keep_alive": "5m",
            "options": {"num_ctx": 4096},
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def gemini_sor(mesajlar: list) -> str:
    model = AYAR.get("gemini_model", "gemini-2.5-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": AYAR["gemini_anahtar"]},
        json={
            "systemInstruction": {"parts": [{"text": sistem_mesaji()}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in mesajlar
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


@app.get("/")
def ana_sayfa():
    if not session.get("ok"):
        return Response(GIRIS_HTML, mimetype="text/html")
    return Response(PANEL_HTML, mimetype="text/html")


@app.post("/giris")
def giris():
    ip = request.remote_addr
    simdi = time.time()
    _giris_denemeleri[ip] = [t for t in _giris_denemeleri[ip] if simdi - t < 900]
    if len(_giris_denemeleri[ip]) >= 5:
        return Response(GIRIS_HTML.replace("<!--HATA-->", "Çok fazla deneme. 15 dakika bekleyin."), mimetype="text/html", status=429)
    sifre = request.form.get("sifre", "")
    if AYAR.get("sifre_hash") and check_password_hash(AYAR["sifre_hash"], sifre):
        session.clear()
        session["ok"] = True
        session.permanent = True
        _giris_denemeleri.pop(ip, None)
        return redirect("/")
    _giris_denemeleri[ip].append(simdi)
    return Response(GIRIS_HTML.replace("<!--HATA-->", "Şifre yanlış."), mimetype="text/html", status=401)


@app.get("/cikis")
def cikis():
    session.clear()
    return redirect("/")


@app.get("/api/durum")
@giris_gerekli
def api_durum():
    return jsonify(durum_oku())


@app.get("/api/log")
@giris_gerekli
def api_log():
    return jsonify(satirlar=log_oku(300))


@app.post("/api/islem")
@giris_gerekli
def api_islem():
    islem = (request.get_json(silent=True) or {}).get("islem")
    if islem == "duraklat":
        open(DURAKLAT_DOSYA, "w").close()
    elif islem == "devam":
        if os.path.exists(DURAKLAT_DOSYA):
            os.remove(DURAKLAT_DOSYA)
    elif islem == "hepsini_kapat":
        open(KAPAT_DOSYA, "w").close()
    else:
        return jsonify(hata="Bilinmeyen işlem"), 400
    return jsonify(ok=True)


@app.post("/api/sohbet")
@giris_gerekli
def api_sohbet():
    gelen = (request.get_json(silent=True) or {}).get("mesajlar", [])
    mesajlar = [
        {"role": "assistant" if m.get("rol") == "asistan" else "user", "content": str(m.get("metin", ""))[:4000]}
        for m in gelen[-12:]
    ]
    if not mesajlar:
        return jsonify(hata="Mesaj boş"), 400
    try:
        if AYAR.get("gemini_anahtar"):
            return jsonify(yanit=gemini_sor(mesajlar), kaynak="Gemini")
        return jsonify(yanit=ollama_sor(mesajlar), kaynak="Yerel (" + AYAR.get("ollama_model", "gemma3:1b") + ")")
    except requests.ConnectionError:
        return jsonify(hata="Yapay zekaya bağlanılamadı. Yerel model için Ollama çalışıyor mu kontrol edin."), 502
    except Exception as e:
        return jsonify(hata=f"Yapay zeka hatası: {e}"), 502


GIRIS_HTML = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bot Paneli</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#0f1419;color:#e6e6e6;display:grid;place-items:center;min-height:100vh}
form{background:#1a2129;padding:28px;border-radius:12px;width:min(320px,90vw)}
h1{font-size:20px;margin:0 0 16px}
input,button{width:100%;box-sizing:border-box;padding:12px;border-radius:8px;border:1px solid #333;font-size:16px}
input{background:#0f1419;color:#e6e6e6;margin-bottom:12px}
button{background:#2f81f7;color:#fff;border:0;cursor:pointer}
.h{color:#f85149;min-height:20px;margin-bottom:8px}
</style></head><body>
<form method="post" action="/giris"><h1>MT5 Bot Paneli</h1>
<div class="h"><!--HATA--></div>
<input type="password" name="sifre" placeholder="Şifre" autofocus required>
<button>Giriş</button></form></body></html>"""

PANEL_HTML = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bot Paneli</title>
<style>
:root{--z:#0f1419;--k:#1a2129;--c:#2a333d;--y:#e6e6e6;--s:#8b949e;--m:#2f81f7;--g:#3fb950;--r:#f85149;--a:#d29922}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--z);color:var(--y)}
header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--k);border-bottom:1px solid var(--c)}
header b{font-size:17px}header a{color:var(--s);text-decoration:none}
nav{display:flex;gap:4px;padding:8px 16px;background:var(--k)}
nav button{flex:1;padding:10px;border:0;border-radius:8px;background:transparent;color:var(--s);font-size:15px;cursor:pointer}
nav button.on{background:var(--c);color:var(--y)}
main{padding:16px;max-width:900px;margin:0 auto}.gizli{display:none}
.kartlar{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kart{background:var(--k);border:1px solid var(--c);border-radius:10px;padding:12px}
.kart small{color:var(--s);display:block;margin-bottom:4px}.kart div{font-size:19px;font-weight:600}
.dugmeler{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
.dugmeler button{padding:10px 16px;border:0;border-radius:8px;font-size:15px;cursor:pointer;color:#fff}
.mavi{background:var(--m)}.sari{background:var(--a)}.kirmizi{background:var(--r)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px;border-bottom:1px solid var(--c);text-align:left}
th{color:var(--s);font-weight:500}.tablo{overflow-x:auto;background:var(--k);border-radius:10px;padding:4px 8px}
.yesil{color:var(--g)}.kirmizim{color:var(--r)}
#sohbet{display:flex;flex-direction:column;height:calc(100vh - 170px)}
#mesajlar{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-bottom:8px}
.m{max-width:85%;padding:10px 12px;border-radius:10px;white-space:pre-wrap;line-height:1.45}
.m.k{align-self:flex-end;background:var(--m);color:#fff}.m.a{align-self:flex-start;background:var(--k);border:1px solid var(--c)}
.m.a small{display:block;color:var(--s);margin-top:6px;font-size:12px}
#yaz{display:flex;gap:8px}#yaz textarea{flex:1;resize:none;height:52px;padding:10px;border-radius:8px;border:1px solid var(--c);background:var(--k);color:var(--y);font:inherit}
#yaz button{padding:0 18px;border:0;border-radius:8px;background:var(--m);color:#fff;font-size:15px}
pre{background:var(--k);padding:12px;border-radius:10px;font-size:12px;overflow:auto;max-height:70vh;white-space:pre-wrap}
.not{color:var(--s);font-size:13px}
</style></head><body>
<header><b>MT5 Bot Paneli</b><a href="/cikis">Çıkış</a></header>
<nav><button data-s="durum" class="on">Durum</button><button data-s="sohbet">Yapay Zeka</button><button data-s="log">Kayıtlar</button></nav>
<main>
<section id="s-durum">
<div class="kartlar">
<div class="kart"><small>Bot</small><div id="d-bot">—</div></div>
<div class="kart"><small>Hesap</small><div id="d-hesap">—</div></div>
<div class="kart"><small>Bakiye</small><div id="d-bakiye">—</div></div>
<div class="kart"><small>Varlık</small><div id="d-varlik">—</div></div>
<div class="kart"><small>Bugünkü değişim</small><div id="d-gun">—</div></div>
<div class="kart"><small>Son güncelleme</small><div id="d-zaman">—</div></div>
</div>
<div class="dugmeler">
<button class="sari" id="b-dur">Duraklat</button>
<button class="mavi" id="b-devam">Devam et</button>
<button class="kirmizi" id="b-kapat">Tüm pozisyonları kapat</button>
</div>
<p class="not">Duraklat: yeni işlem açılmaz, açık işlemler kendi stop ve hedefiyle devam eder.</p>
<div class="tablo"><table><thead><tr><th>Sembol</th><th>Yön</th><th>Lot</th><th>Giriş</th><th>Stop</th><th>Hedef</th><th>Kâr/Zarar</th></tr></thead><tbody id="d-poz"></tbody></table></div>
</section>
<section id="s-sohbet" class="gizli"><div id="sohbet">
<div id="mesajlar"><div class="m a">Merhaba. Botun durumu, işlemleri ve ayarları hakkında sorabilirsiniz. Ör: "Bot bugün neden işlem açmadı?"</div></div>
<div id="yaz"><textarea id="girdi" placeholder="Mesajınızı yazın..."></textarea><button id="gonder">Gönder</button></div>
</div></section>
<section id="s-log" class="gizli"><pre id="loglar">Yükleniyor...</pre></section>
</main>
<script>
const H={'Content-Type':'application/json','X-Panel':'1'};
const $=id=>document.getElementById(id);
const sayi=(v,p)=>v==null?'—':Number(v).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})+(p?' '+p:'');
async function al(u){const r=await fetch(u);if(r.status==401){location.reload();throw 0}return r.json()}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x==b));
 document.querySelectorAll('main section').forEach(s=>s.classList.toggle('gizli',s.id!='s-'+b.dataset.s));
 if(b.dataset.s=='log')loglar();});
async function durum(){try{
 const d=await al('/api/durum');
 let bot=!d.canli?'<span class="kirmizim">Çalışmıyor</span>':d.baglanti===false?'<span class="kirmizim">MT5 bağlantısı yok</span>':
  d.duraklatildi?'<span style="color:var(--a)">Duraklatıldı</span>':d.gunluk_limit_doldu?'<span style="color:var(--a)">Günlük limit doldu</span>':'<span class="yesil">Çalışıyor</span>';
 $('d-bot').innerHTML=bot;
 $('d-hesap').textContent=d.hesap?d.hesap+' ('+d.tur+')':'—';
 $('d-bakiye').textContent=sayi(d.bakiye,d.para);$('d-varlik').textContent=sayi(d.varlik,d.para);
 if(d.gun_baslangic&&d.varlik!=null){const f=d.varlik-d.gun_baslangic;$('d-gun').textContent=(f>=0?'+':'')+sayi(f,d.para);$('d-gun').className=f>=0?'yesil':'kirmizim'}
 $('d-zaman').textContent=d.son_guncelleme_sn==null?'—':d.son_guncelleme_sn+' sn önce';
 const tb=$('d-poz');tb.innerHTML='';
 (d.pozisyonlar||[]).forEach(p=>{const tr=document.createElement('tr');
  [p.sembol,p.yon,p.lot,p.giris,p.sl,p.tp,sayi(p.kar)].forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if(i==6)td.className=p.kar>=0?'yesil':'kirmizim';tr.appendChild(td)});tb.appendChild(tr)});
 if(!(d.pozisyonlar||[]).length)tb.innerHTML='<tr><td colspan="7" class="not">Açık pozisyon yok</td></tr>';
}catch(e){}}
async function islem(i,soru){if(soru&&!confirm(soru))return;
 const r=await fetch('/api/islem',{method:'POST',headers:H,body:JSON.stringify({islem:i})});
 alert(r.ok?'Komut gönderildi. Bot 30 saniye içinde uygular.':'Hata oluştu.');durum()}
$('b-dur').onclick=()=>islem('duraklat');$('b-devam').onclick=()=>islem('devam');
$('b-kapat').onclick=()=>islem('hepsini_kapat','Botun açtığı TÜM pozisyonlar piyasa fiyatından kapatılacak. Emin misiniz?');
async function loglar(){const d=await al('/api/log');$('loglar').textContent=d.satirlar.join('\\n')||'Kayıt yok';}
const gecmis=[];
function balon(metin,sinif,kaynak){const m=document.createElement('div');m.className='m '+sinif;m.textContent=metin;
 if(kaynak){const s=document.createElement('small');s.textContent=kaynak;m.appendChild(s)}
 $('mesajlar').appendChild(m);$('mesajlar').scrollTop=1e9;return m}
async function gonder(){const t=$('girdi').value.trim();if(!t)return;$('girdi').value='';
 balon(t,'k');gecmis.push({rol:'kullanici',metin:t});
 const bekle=balon('Düşünüyor... (yerel modelde 1-2 dakika sürebilir)','a');$('gonder').disabled=true;
 try{const r=await fetch('/api/sohbet',{method:'POST',headers:H,body:JSON.stringify({mesajlar:gecmis})});
  const d=await r.json();bekle.remove();
  if(d.yanit){balon(d.yanit,'a',d.kaynak);gecmis.push({rol:'asistan',metin:d.yanit})}else balon(d.hata||'Hata','a');
 }catch(e){bekle.remove();balon('Bağlantı hatası','a')}
 $('gonder').disabled=false}
$('gonder').onclick=gonder;
$('girdi').onkeydown=e=>{if(e.key=='Enter'&&!e.shiftKey){e.preventDefault();gonder()}};
durum();setInterval(durum,10000);
</script></body></html>"""


if __name__ == "__main__":
    if "--kur" in sys.argv:
        kur()
        sys.exit(0)
    if not AYAR.get("sifre_hash"):
        print("Önce şifre belirleyin:  python panel.py --kur")
        sys.exit(1)
    from waitress import serve
    print(f"Panel çalışıyor: http://0.0.0.0:{AYAR['port']}")
    serve(app, host="0.0.0.0", port=AYAR["port"], threads=6)
