#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests, os, re, time, base64
from difflib import SequenceMatcher

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ============================================
# AYARLAR
# ============================================
API_SAHIBI = "@fbxnext"
API_KANAL = "@logsuzlarvip"

# ============================================
# BÖLÜM 1: OPENROUTER AI (5 KEY) - BASE64 ŞİFRELİ
# ============================================
# Keyler base64 kodlu, runtime'da decode edilir
_K1 = "c2stb3ItdjEtNzRjZmU4M2ZmNzhjODRiMmQ4MWVhYzQ4NzUxOWRhNmM5NGQ1M2I5ZmEwZGNjMDZiNzc1MmRiMDM2MGIwM2ZjMw=="
_K2 = "c2stb3ItdjEtMGEyZmFkODMwOTdmMzQ3OWMyNTkyOGIyZTkyOTgxZjhkMTdhZDJjYjUxZDRlOWM2OGQ5ZDI2MDFjN2JhYTc4Yg=="
_K3 = "c2stb3ItdjEtNTQ3OGYzOTNiZTRkZTNkMTNmZmFiY2Y4ZDMzMWU5ZWVhMjk3ODUxMDhkYjIxMjkwODM3ZDVmNTc0YzViMjQ3Nw=="
_K4 = "c2stb3ItdjEtY2NkNTdhYjUzMTU0MDMyODVmMTgzZGFiNWE0NzZkYWEyZGY1OWY5ZDZlOWM0ZDQ0NzNjNWM3NGI2ZGViNzNiZQ=="
_K5 = "c2stb3ItdjEtNDEyNTI1ODYzMzhiNjM0NmNlZjExZTcyYmQxMjYyNjUyM2YwYzdmMDEwNzk5N2Q2ZTViZWRiNGIwN2U4OWMxNQ=="

OPENROUTER_KEYS = [
    base64.b64decode(_K1).decode("utf-8"),
    base64.b64decode(_K2).decode("utf-8"),
    base64.b64decode(_K3).decode("utf-8"),
    base64.b64decode(_K4).decode("utf-8"),
    base64.b64decode(_K5).decode("utf-8"),
]
aktif_ai_key = 0

# ============================================
# BÖLÜM 2: VERİ DEPOLARI
# ============================================
PLAKALAR = {}
ISIMLER_PLAKA = {}

TT_KAYITLAR = []
TT_GSM = {}
TT_ISIM = {}

PAPARA_KAYITLAR = []
PP_TC = {}
PP_ISIM = {}

SECMEN_KAYITLAR = []
SC_TC = {}
SC_ISIM = {}

SERINO_KAYITLAR = []
SR_TC = {}
SR_ISIM = {}
SR_SERINO = {}


# ============================================
# YARDIMCI FONKSİYONLAR
# ============================================
def benzer_isim_ara(kaynak_dict, aranan):
    aranan = aranan.upper().strip()
    aranan = re.sub(r"\s+", " ", aranan)
    if aranan in kaynak_dict:
        return aranan, 1.0

    aranan_parcalar = set(aranan.split())
    en_iyi = None
    en_iyi_skor = 0.0

    for isim in kaynak_dict.keys():
        isim_parcalar = set(isim.split())
        kesisim = aranan_parcalar & isim_parcalar
        birlesim = aranan_parcalar | isim_parcalar
        if not birlesim:
            continue
        skor1 = len(kesisim) / len(birlesim)
        skor2 = SequenceMatcher(None, aranan, isim).ratio()
        skor = max(skor1, skor2)
        if skor > en_iyi_skor:
            en_iyi_skor = skor
            en_iyi = isim

    if en_iyi_skor >= 0.6:
        return en_iyi, en_iyi_skor
    return None, 0.0


def gsm_normalize(numara):
    sadece = re.sub(r"\D", "", numara)
    if len(sadece) == 11 and sadece.startswith("0"):
        sadece = sadece[1:]
    if len(sadece) == 12 and sadece.startswith("90"):
        sadece = sadece[2:]
    return sadece


def tc_normalize(tc):
    return re.sub(r"\D", "", tc)


# ============================================
# VERİ YÜKLEME
# ============================================
def plaka_yukle():
    global PLAKALAR, ISIMLER_PLAKA
    PLAKALAR = {}
    ISIMLER_PLAKA = {}
    if not os.path.exists("plaka.txt"):
        print("⚠️ plaka.txt bulunamadı")
        return
    with open("plaka.txt", "r", encoding="utf-8") as f:
        for satir in f:
            parcalar = satir.strip().split()
            if len(parcalar) < 2:
                continue
            plaka = parcalar[-1].upper()
            isim = " ".join(parcalar[:-1]).upper()
            isim = re.sub(r"\s+", " ", isim).strip()
            if plaka:
                PLAKALAR[plaka] = isim
            if isim:
                ISIMLER_PLAKA.setdefault(isim, [])
                if plaka not in ISIMLER_PLAKA[isim]:
                    ISIMLER_PLAKA[isim].append(plaka)
    print(f"✅ {len(PLAKALAR)} plaka, {len(ISIMLER_PLAKA)} isim yüklendi")


def tt_yukle():
    global TT_KAYITLAR, TT_GSM, TT_ISIM
    TT_KAYITLAR = []
    TT_GSM = {}
    TT_ISIM = {}
    if not os.path.exists("turktelekom.txt"):
        print("⚠️ turktelekom.txt bulunamadı")
        return
    with open("turktelekom.txt", "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            gsm_match = re.search(r"\b(5\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\b", satir)
            gsm = None
            if gsm_match:
                gsm = gsm_match.group(1) + gsm_match.group(2) + gsm_match.group(3) + gsm_match.group(4)
            isim_bolumu = satir
            if gsm_match:
                isim_bolumu = satir[:gsm_match.start()].strip()
            isim = re.sub(r"\s+", " ", isim_bolumu).strip().upper()
            kayit = {"ad_soyad": isim, "gsm": gsm, "adres": satir}
            TT_KAYITLAR.append(kayit)
            if gsm:
                TT_GSM[gsm] = kayit
            if isim:
                TT_ISIM.setdefault(isim, []).append(kayit)
    print(f"✅ {len(TT_KAYITLAR)} TT kaydı yüklendi")


def papara_yukle():
    global PAPARA_KAYITLAR, PP_TC, PP_ISIM
    PAPARA_KAYITLAR = []
    PP_TC = {}
    PP_ISIM = {}
    if not os.path.exists("papara.txt"):
        print("⚠️ papara.txt bulunamadı")
        return
    with open("papara.txt", "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            parcalar = satir.split(",")
            if len(parcalar) < 2:
                continue
            tc = parcalar[0].strip()
            isim = ",".join(parcalar[1:]).strip()
            isim = re.sub(r"\s+", " ", isim).upper()
            if not tc or not isim:
                continue
            kayit = {"tc": tc, "ad_soyad": isim}
            PAPARA_KAYITLAR.append(kayit)
            PP_TC[tc] = kayit
            PP_ISIM.setdefault(isim, []).append(kayit)
    print(f"✅ {len(PAPARA_KAYITLAR)} Papara kaydı yüklendi")


def secmen_yukle():
    global SECMEN_KAYITLAR, SC_TC, SC_ISIM
    SECMEN_KAYITLAR = []
    SC_TC = {}
    SC_ISIM = {}
    if not os.path.exists("secmen.txt"):
        print("⚠️ secmen.txt bulunamadı")
        return
    with open("secmen.txt", "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            parcalar = [p.strip() for p in satir.split("|")]
            if len(parcalar) < 5:
                continue
            tc = re.sub(r"\D", "", parcalar[0])
            ad = parcalar[1].strip().upper()
            soyad = parcalar[2].strip().upper()
            il = parcalar[3].strip().upper()
            sokak = parcalar[4].strip().upper()
            if not tc or not ad:
                continue
            ad_soyad = f"{ad} {soyad}"
            kayit = {"tc": tc, "ad": ad, "soyad": soyad, "ad_soyad": ad_soyad, "il": il, "sokak": sokak}
            SECMEN_KAYITLAR.append(kayit)
            SC_TC[tc] = kayit
            SC_ISIM.setdefault(ad_soyad, []).append(kayit)
    print(f"✅ {len(SECMEN_KAYITLAR)} seçmen kaydı yüklendi")


def serino_yukle():
    global SERINO_KAYITLAR, SR_TC, SR_ISIM, SR_SERINO
    SERINO_KAYITLAR = []
    SR_TC = {}
    SR_ISIM = {}
    SR_SERINO = {}
    if not os.path.exists("serinosktpro.txt"):
        print("⚠️ serinosktpro.txt bulunamadı")
        return
    with open("serinosktpro.txt", "r", encoding="utf-8") as f:
        icerik = f.read()
    bloklar = re.split(r"---\s*\w+\s*---", icerik)
    for blok in bloklar:
        blok = blok.strip()
        if not blok:
            continue
        kayit = {}
        for satir in blok.split("\n"):
            satir = satir.strip()
            if not satir or ":" not in satir:
                continue
            anahtar, deger = satir.split(":", 1)
            anahtar = anahtar.strip().upper()
            deger = deger.strip()
            kayit[anahtar] = deger
        if "TC" not in kayit or "ADI SOYADI" not in kayit:
            continue
        tc = re.sub(r"\D", "", kayit["TC"])
        ad_soyad = kayit.get("ADI SOYADI", "").strip().upper()
        serino = kayit.get("SERİNO", "").strip().upper()
        if not tc or not ad_soyad:
            continue
        if kayit.get("ÖLÜM TARİHİ", "").strip() == "\\N":
            kayit["ÖLÜM TARİHİ"] = None
        tam_kayit = {
            "tc": tc,
            "ad_soyad": ad_soyad,
            "serino": serino,
            "cinsiyet": kayit.get("CİNSİYET", ""),
            "dogum": kayit.get("DOĞUM", ""),
            "dogum_yeri": kayit.get("DOĞUM YERİ", ""),
            "medeni_hal": kayit.get("MEDENİ HAL", ""),
            "il": kayit.get("İL", ""),
            "ilce": kayit.get("İLÇE", ""),
            "durum": kayit.get("DURUM", ""),
            "anne_adi": kayit.get("ANNE ADI", ""),
            "baba_adi": kayit.get("BABA ADI", ""),
            "aile_sirano": kayit.get("AİLE SIRANO", ""),
            "sirano": kayit.get("SIRANO", ""),
            "cilt_no": kayit.get("CİLT NO", ""),
            "koy": kayit.get("KOY", ""),
            "din": kayit.get("DİN", ""),
            "son_kullanma": kayit.get("SON KULLANMA", ""),
            "veren_kurum": kayit.get("VEREN KURUM", ""),
            "olum_tarihi": kayit.get("ÖLÜM TARİHİ"),
        }
        SERINO_KAYITLAR.append(tam_kayit)
        SR_TC[tc] = tam_kayit
        SR_ISIM.setdefault(ad_soyad, []).append(tam_kayit)
        if serino:
            SR_SERINO[serino] = tam_kayit
    print(f"✅ {len(SERINO_KAYITLAR)} serino kaydı yüklendi")


# ============================================
# AI FONKSİYONU
# ============================================
def sistem_promptu():
    return f"""Sen Logsuzlar AI'sın.
Adın: Logsuzlar AI
Sahibin: {API_SAHIBI}
Kanalın: {API_KANAL}

ASLA "Grok", "GPT", "OpenAI", "Llama" deme.
Kendini "Logsuzlar AI" olarak tanıt.
Türkçe konuş. Kısa ve net cevap ver."""


def ai_istek(mesaj):
    global aktif_ai_key
    for deneme in range(len(OPENROUTER_KEYS) * 2):
        key = OPENROUTER_KEYS[aktif_ai_key]
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "https://t.me/logsuzlarvip",
                    "X-Title": "Logsuzlar AI",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [
                        {"role": "system", "content": sistem_promptu()},
                        {"role": "user", "content": mesaj}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=60,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            elif r.status_code in [401, 402, 403, 429]:
                aktif_ai_key = (aktif_ai_key + 1) % len(OPENROUTER_KEYS)
                time.sleep(1)
                continue
            else:
                time.sleep(2)
                continue
        except:
            time.sleep(2)
            continue
    return "❌ AI şu an cevap veremiyor."


# ============================================
# ANA SAYFA (API LİSTESİ OTOMATİK)
# ============================================
@app.route("/")
def ana():
    base = request.url_root.rstrip("/")
    return jsonify({
        "api": "Logsuzlar API",
        "versiyon": "v6.0",
        "sahip": API_SAHIBI,
        "kanal": API_KANAL,
        "durum": "online",
        "toplam_api": 6,
        "site_url": base,
        "apis": [
            {
                "key": "ai",
                "name": "Logsuzlar AI",
                "icon": "fa-robot",
                "color": "#00f5ff",
                "desc": "Yapay zeka sohbet · 5 key yedekli",
                "endpoints": [
                    {"label": "AI Chat", "method": "GET", "path": "/chat?mesaj=Merhaba", "desc": "Yapay zeka sohbet"}
                ]
            },
            {
                "key": "plaka",
                "name": "Plaka Sorgu",
                "icon": "fa-car",
                "color": "#ff0055",
                "desc": "Plakadan ad soyad · Ad soyaddan plaka",
                "endpoints": [
                    {"label": "Plaka Sorgu", "method": "GET", "path": "/plaka/34KG4978", "desc": "Plakadan isim"},
                    {"label": "İsim Sorgu", "method": "GET", "path": "/isim/OĞUZHAN UĞUR", "desc": "İsimden plaka"},
                    {"label": "Genel Sorgu", "method": "GET", "path": "/sorgu?q=34KG4978", "desc": "Otomatik algılama"},
                    {"label": "Liste", "method": "GET", "path": "/liste", "desc": "Tüm plakalar"}
                ]
            },
            {
                "key": "tt",
                "name": "Türk Telekom",
                "icon": "fa-phone",
                "color": "#5865F2",
                "desc": "GSM → Ad Soyad → Adres",
                "endpoints": [
                    {"label": "GSM Sorgu", "method": "GET", "path": "/tt/gsm/5539848500", "desc": "GSM'den sorgu"},
                    {"label": "İsim Sorgu", "method": "GET", "path": "/tt/isim/EGEMEN KUTAY", "desc": "İsimden sorgu"},
                    {"label": "Genel Sorgu", "method": "GET", "path": "/tt/sorgu?q=5539848500", "desc": "Otomatik algılama"},
                    {"label": "Liste", "method": "GET", "path": "/tt/liste", "desc": "Tüm kayıtlar"}
                ]
            },
            {
                "key": "pp",
                "name": "Papara",
                "icon": "fa-credit-card",
                "color": "#ffd700",
                "desc": "TC ↔ Ad Soyad sorgu",
                "endpoints": [
                    {"label": "TC Sorgu", "method": "GET", "path": "/pp/tc/1354693996", "desc": "TC'den isim"},
                    {"label": "İsim Sorgu", "method": "GET", "path": "/pp/isim/MEHMET TEKER", "desc": "İsimden TC"},
                    {"label": "Genel Sorgu", "method": "GET", "path": "/pp/sorgu?q=1354693996", "desc": "Otomatik algılama"},
                    {"label": "Liste", "method": "GET", "path": "/pp/liste", "desc": "Tüm kayıtlar"}
                ]
            },
            {
                "key": "sc",
                "name": "Seçmen Sorgu",
                "icon": "fa-vote-yea",
                "color": "#00ff88",
                "desc": "TC ↔ Ad Soyad ↔ İl ↔ Sokak",
                "endpoints": [
                    {"label": "TC Sorgu", "method": "GET", "path": "/sc/tc/18445070762", "desc": "TC'den sorgu"},
                    {"label": "İsim Sorgu", "method": "GET", "path": "/sc/isim/AHMET AYDOĞDU", "desc": "İsimden sorgu"},
                    {"label": "Genel Sorgu", "method": "GET", "path": "/sc/sorgu?q=18445070762", "desc": "Otomatik algılama"},
                    {"label": "Liste", "method": "GET", "path": "/sc/liste", "desc": "Tüm kayıtlar"}
                ]
            },
            {
                "key": "sr",
                "name": "Serino Sorgu",
                "icon": "fa-id-card",
                "color": "#ff00aa",
                "desc": "TC ↔ Serino ↔ Detaylı nüfus bilgisi",
                "endpoints": [
                    {"label": "TC Sorgu", "method": "GET", "path": "/sr/tc/31417500708", "desc": "TC'den detaylı"},
                    {"label": "İsim Sorgu", "method": "GET", "path": "/sr/isim/GİZEM SEHER SAYAN", "desc": "İsimden sorgu"},
                    {"label": "Serino Sorgu", "method": "GET", "path": "/sr/serino/A32K96562", "desc": "Serino'dan sorgu"},
                    {"label": "Genel Sorgu", "method": "GET", "path": "/sr/sorgu?q=31417500708", "desc": "Otomatik algılama"},
                    {"label": "Liste", "method": "GET", "path": "/sr/liste", "desc": "Tüm kayıtlar"}
                ]
            }
        ]
    })


# ============================================
# AI CHAT
# ============================================
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
    else:
        data = request.args.to_dict()
    mesaj = data.get("mesaj") or data.get("message") or data.get("q")
    if not mesaj:
        return jsonify({"ok": False, "hata": "mesaj parametresi gerekli"}), 400
    cevap = ai_istek(mesaj)
    return jsonify({"ok": True, "soru": mesaj, "cevap": cevap, "model": "logsuzlar-ai-v2", "sahip": API_SAHIBI})


# ============================================
# PLAKA
# ============================================
@app.route("/plaka/<plaka>")
def plaka(plaka):
    pl = re.sub(r"[^A-Z0-9]", "", plaka.upper())
    if pl in PLAKALAR:
        return jsonify({"ok": True, "plaka": pl, "ad_soyad": PLAKALAR[pl], "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Plaka bulunamadı"}), 404


@app.route("/isim/<path:plaka_isim>")
def isim(plaka_isim):
    aranan = re.sub(r"\s+", " ", plaka_isim.upper().strip())
    if aranan in ISIMLER_PLAKA:
        return jsonify({"ok": True, "ad_soyad": aranan, "plakalar": ISIMLER_PLAKA[aranan], "toplam": len(ISIMLER_PLAKA[aranan]), "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(ISIMLER_PLAKA, aranan)
    if benzer:
        return jsonify({"ok": True, "aranan": aranan, "bulunan": benzer, "benzerlik": round(skor, 2), "plakalar": ISIMLER_PLAKA[benzer], "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/sorgu")
def sorgu():
    q = (request.args.get("q") or request.args.get("sorgu") or "").strip()
    if not q:
        return jsonify({"ok": False, "hata": "q parametresi gerekli"}), 400
    pl = re.sub(r"[^A-Z0-9]", "", q.upper())
    if re.match(r"^\d{2}[A-Z0-9]{3,8}$", pl):
        if pl in PLAKALAR:
            return jsonify({"ok": True, "tip": "plaka", "plaka": pl, "ad_soyad": PLAKALAR[pl], "sahip": API_SAHIBI})
        return jsonify({"ok": False, "hata": "Plaka bulunamadı"}), 404
    else:
        aranan = re.sub(r"\s+", " ", q.upper().strip())
        if aranan in ISIMLER_PLAKA:
            return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "plakalar": ISIMLER_PLAKA[aranan], "sahip": API_SAHIBI})
        return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/liste")
def plaka_liste():
    return jsonify({"ok": True, "toplam": len(PLAKALAR), "kayitlar": [{"plaka": p, "ad_soyad": i} for p, i in PLAKALAR.items()], "sahip": API_SAHIBI})


# ============================================
# TÜRK TELEKOM
# ============================================
@app.route("/tt/gsm/<gsm>")
def tt_gsm_sorgu(gsm):
    temiz = gsm_normalize(gsm)
    if temiz in TT_GSM:
        k = TT_GSM[temiz]
        return jsonify({"ok": True, "tip": "gsm", "gsm": temiz, "ad_soyad": k["ad_soyad"], "adres": k["adres"], "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "GSM bulunamadı"}), 404


@app.route("/tt/isim/<path:isim>")
def tt_isim_sorgu(isim):
    aranan = re.sub(r"\s+", " ", isim.upper().strip())
    if aranan in TT_ISIM:
        kayitlar = TT_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(TT_ISIM, aranan)
    if benzer:
        kayitlar = TT_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/tt/sorgu")
def tt_sorgu():
    q = (request.args.get("q") or request.args.get("sorgu") or "").strip()
    if not q:
        return jsonify({"ok": False, "hata": "q parametresi gerekli"}), 400
    temiz = gsm_normalize(q)
    if len(temiz) == 10 and temiz.startswith("5"):
        if temiz in TT_GSM:
            k = TT_GSM[temiz]
            return jsonify({"ok": True, "tip": "gsm", "gsm": temiz, "ad_soyad": k["ad_soyad"], "adres": k["adres"], "sahip": API_SAHIBI})
        return jsonify({"ok": False, "hata": "GSM bulunamadı"}), 404
    aranan = re.sub(r"\s+", " ", q.upper().strip())
    if aranan in TT_ISIM:
        kayitlar = TT_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(TT_ISIM, aranan)
    if benzer:
        kayitlar = TT_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Bulunamadı"}), 404


@app.route("/tt/liste")
def tt_liste():
    return jsonify({"ok": True, "toplam": len(TT_KAYITLAR), "kayitlar": TT_KAYITLAR, "sahip": API_SAHIBI})


# ============================================
# PAPARA
# ============================================
@app.route("/pp/tc/<tc>")
def pp_tc_sorgu(tc):
    temiz = tc_normalize(tc)
    if temiz in PP_TC:
        k = PP_TC[temiz]
        return jsonify({"ok": True, "tip": "tc", "tc": temiz, "ad_soyad": k["ad_soyad"], "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "TC bulunamadı"}), 404


@app.route("/pp/isim/<path:isim>")
def pp_isim_sorgu(isim):
    aranan = re.sub(r"\s+", " ", isim.upper().strip())
    if aranan in PP_ISIM:
        kayitlar = PP_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(PP_ISIM, aranan)
    if benzer:
        kayitlar = PP_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/pp/sorgu")
def pp_sorgu():
    q = (request.args.get("q") or request.args.get("sorgu") or "").strip()
    if not q:
        return jsonify({"ok": False, "hata": "q parametresi gerekli"}), 400
    temiz = tc_normalize(q)
    if len(temiz) == 10:
        if temiz in PP_TC:
            k = PP_TC[temiz]
            return jsonify({"ok": True, "tip": "tc", "tc": temiz, "ad_soyad": k["ad_soyad"], "sahip": API_SAHIBI})
        return jsonify({"ok": False, "hata": "TC bulunamadı"}), 404
    aranan = re.sub(r"\s+", " ", q.upper().strip())
    if aranan in PP_ISIM:
        kayitlar = PP_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(PP_ISIM, aranan)
    if benzer:
        kayitlar = PP_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Bulunamadı"}), 404


@app.route("/pp/liste")
def pp_liste():
    return jsonify({"ok": True, "toplam": len(PAPARA_KAYITLAR), "kayitlar": PAPARA_KAYITLAR, "sahip": API_SAHIBI})


# ============================================
# SEÇMEN
# ============================================
@app.route("/sc/tc/<tc>")
def sc_tc_sorgu(tc):
    temiz = tc_normalize(tc)
    if temiz in SC_TC:
        k = SC_TC[temiz]
        return jsonify({"ok": True, "tip": "tc", "tc": temiz, "ad": k["ad"], "soyad": k["soyad"], "ad_soyad": k["ad_soyad"], "il": k["il"], "sokak": k["sokak"], "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "TC bulunamadı"}), 404


@app.route("/sc/isim/<path:isim>")
def sc_isim_sorgu(isim):
    aranan = re.sub(r"\s+", " ", isim.upper().strip())
    if aranan in SC_ISIM:
        kayitlar = SC_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(SC_ISIM, aranan)
    if benzer:
        kayitlar = SC_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/sc/sorgu")
def sc_sorgu():
    q = (request.args.get("q") or request.args.get("sorgu") or "").strip()
    if not q:
        return jsonify({"ok": False, "hata": "q parametresi gerekli"}), 400
    temiz = tc_normalize(q)
    if len(temiz) == 11:
        if temiz in SC_TC:
            k = SC_TC[temiz]
            return jsonify({"ok": True, "tip": "tc", "tc": temiz, "ad": k["ad"], "soyad": k["soyad"], "ad_soyad": k["ad_soyad"], "il": k["il"], "sokak": k["sokak"], "sahip": API_SAHIBI})
        return jsonify({"ok": False, "hata": "TC bulunamadı"}), 404
    aranan = re.sub(r"\s+", " ", q.upper().strip())
    if aranan in SC_ISIM:
        kayitlar = SC_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(SC_ISIM, aranan)
    if benzer:
        kayitlar = SC_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Bulunamadı"}), 404


@app.route("/sc/liste")
def sc_liste():
    return jsonify({"ok": True, "toplam": len(SECMEN_KAYITLAR), "kayitlar": SECMEN_KAYITLAR, "sahip": API_SAHIBI})


# ============================================
# SERİNO
# ============================================
@app.route("/sr/tc/<tc>")
def sr_tc_sorgu(tc):
    temiz = tc_normalize(tc)
    if temiz in SR_TC:
        k = SR_TC[temiz]
        return jsonify({"ok": True, "tip": "tc", "tc": temiz, "kayit": k, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "TC bulunamadı"}), 404


@app.route("/sr/isim/<path:isim>")
def sr_isim_sorgu(isim):
    aranan = re.sub(r"\s+", " ", isim.upper().strip())
    if aranan in SR_ISIM:
        kayitlar = SR_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(SR_ISIM, aranan)
    if benzer:
        kayitlar = SR_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "İsim bulunamadı"}), 404


@app.route("/sr/serino/<serino>")
def sr_serino_sorgu(serino):
    temiz = re.sub(r"[^A-Z0-9]", "", serino.upper())
    if temiz in SR_SERINO:
        k = SR_SERINO[temiz]
        return jsonify({"ok": True, "tip": "serino", "serino": temiz, "kayit": k, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Serino bulunamadı"}), 404


@app.route("/sr/sorgu")
def sr_sorgu():
    q = (request.args.get("q") or request.args.get("sorgu") or "").strip()
    if not q:
        return jsonify({"ok": False, "hata": "q parametresi gerekli"}), 400
    temiz = tc_normalize(q)
    if len(temiz) == 11 and temiz in SR_TC:
        k = SR_TC[temiz]
        return jsonify({"ok": True, "tip": "tc", "tc": temiz, "kayit": k, "sahip": API_SAHIBI})
    if re.match(r"^A[A-Z0-9]{6,10}$", q.upper().strip()):
        sr = re.sub(r"[^A-Z0-9]", "", q.upper())
        if sr in SR_SERINO:
            k = SR_SERINO[sr]
            return jsonify({"ok": True, "tip": "serino", "serino": sr, "kayit": k, "sahip": API_SAHIBI})
    aranan = re.sub(r"\s+", " ", q.upper().strip())
    if aranan in SR_ISIM:
        kayitlar = SR_ISIM[aranan]
        return jsonify({"ok": True, "tip": "isim", "ad_soyad": aranan, "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    benzer, skor = benzer_isim_ara(SR_ISIM, aranan)
    if benzer:
        kayitlar = SR_ISIM[benzer]
        return jsonify({"ok": True, "tip": "isim", "bulunan": benzer, "benzerlik": round(skor, 2), "toplam": len(kayitlar), "kayitlar": kayitlar, "sahip": API_SAHIBI})
    return jsonify({"ok": False, "hata": "Bulunamadı"}), 404


@app.route("/sr/liste")
def sr_liste():
    return jsonify({"ok": True, "toplam": len(SERINO_KAYITLAR), "kayitlar": SERINO_KAYITLAR, "sahip": API_SAHIBI})


# ============================================
# DURUM
# ============================================
@app.route("/durum")
def durum():
    return jsonify({
        "ok": True,
        "toplam_api": 6,
        "ai": {"keys": len(OPENROUTER_KEYS), "aktif_key": aktif_ai_key},
        "plaka": {"toplam_plaka": len(PLAKALAR), "toplam_isim": len(ISIMLER_PLAKA)},
        "turk_telekom": {"toplam_kayit": len(TT_KAYITLAR), "gsm_kayit": len(TT_GSM), "isim_kayit": len(TT_ISIM)},
        "papara": {"toplam_kayit": len(PAPARA_KAYITLAR), "tc_kayit": len(PP_TC), "isim_kayit": len(PP_ISIM)},
        "secmen": {"toplam_kayit": len(SECMEN_KAYITLAR), "tc_kayit": len(SC_TC), "isim_kayit": len(SC_ISIM)},
        "serino": {"toplam_kayit": len(SERINO_KAYITLAR), "tc_kayit": len(SR_TC), "isim_kayit": len(SR_ISIM), "serino_kayit": len(SR_SERINO)},
        "sahip": API_SAHIBI,
        "kanal": API_KANAL
    })


# ============================================
# INDEX.HTML SERVE
# ============================================
@app.route("/panel")
def panel():
    return send_from_directory('.', 'index.html')


# ============================================
# BAŞLAT
# ============================================
plaka_yukle()
tt_yukle()
papara_yukle()
secmen_yukle()
serino_yukle()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
