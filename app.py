from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import pandas as pd
import time
import os
import sqlite3
import io

app = Flask(__name__)

app.secret_key = "iett2026"
# ==============================
# DATABASE
# ==============================

DATABASE = os.path.join(
    os.path.dirname(__file__),
    "database",
    "iett.db"
)


def init_database():

    os.makedirs(
        os.path.dirname(DATABASE),
        exist_ok=True
    )

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    # Kullanıcı tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            role TEXT NOT NULL,

            status TEXT NOT NULL

        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        vehicle_type TEXT NOT NULL,
        fuel_type TEXT NOT NULL,
        model_year INTEGER,
        chassis_no TEXT,
        mileage INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'aktif'
    )
""")

    # -----------------------------------------------------
    # ARAÇLARA KAPI NO ALANI EKLE
    # -----------------------------------------------------

    cursor.execute("""
        PRAGMA table_info(vehicles)
    """)

    vehicle_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "door_number" not in vehicle_columns:

        cursor.execute("""
            ALTER TABLE vehicles
            ADD COLUMN door_number TEXT
        """)
        # =====================================================
    # GERÇEK ARAÇ VERİLERİNİ AKTAR
    # =====================================================

    # Daha önce eklediğimiz 5 yapay aracı kaldır
    cursor.execute("""
        DELETE FROM vehicles
        WHERE plate IN (?, ?, ?, ?, ?)
    """, (
        "34 DEF 456",
        "34 GHI 789",
        "34 GS 1905",
        "34 MNO 654",
        "34 PRS 987"
    ))

    # Gerçek sefer verilerini oku
    sefer_df = pd.read_csv(SEFER_CSV)
    print("SEFER SÜTUNLARI:", sefer_df.columns.tolist())

    # Benzersiz gerçek plakaları al
    real_plates = (
        sefer_df["Plaka"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
    )

    # Sentetik araç bilgileri
    vehicle_models = [
        ("Mercedes Conecto", "Standart Otobüs", "Dizel"),
        ("Otokar Kent LF", "Standart Otobüs", "Dizel"),
        ("Mercedes Capacity", "Körüklü Otobüs", "Dizel"),
        ("Otokar Kent LF Körüklü", "Körüklü Otobüs", "Dizel"),
        ("Karsan e-ATA", "Elektrikli Otobüs", "Elektrik")
    ]

    # Her gerçek aracı ekle
    for index, plate in enumerate(real_plates):

        vehicle_rows = sefer_df[
            sefer_df["Plaka"].astype(str).str.strip() == plate
        ]

        speeds = pd.to_numeric(
            vehicle_rows["Hiz"],
            errors="coerce"
        ).fillna(0)

        # Gerçek hız verisinden durum belirle
        if speeds.max() > 0:
            status = "aktif"
        else:
            status = "pasif"

        # Sentetik teknik bilgiler
        model, vehicle_type, fuel_type = vehicle_models[
            index % len(vehicle_models)
        ]

        model_year = 2018 + (index % 7)

        mileage = 80000 + ((index * 4731) % 320000)

        chassis_no = f"IETT{index + 1:06d}"

        cursor.execute("""
    INSERT INTO vehicles
    (
        plate,
        name,
        vehicle_type,
        fuel_type,
        model_year,
        chassis_no,
        mileage,
        status
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(plate) DO UPDATE SET
        name = excluded.name,
        vehicle_type = excluded.vehicle_type,
        fuel_type = excluded.fuel_type,
        model_year = excluded.model_year,
        chassis_no = excluded.chassis_no,
        mileage = excluded.mileage,
        status = excluded.status
""", (
    plate,
    model,
    vehicle_type,
    fuel_type,
    model_year,
    chassis_no,
    mileage,
    status
))
   
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stops (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        stop_code TEXT NOT NULL UNIQUE,

        stop_name TEXT NOT NULL,

        district TEXT NOT NULL,

        address TEXT,

        latitude REAL,

        longitude REAL,

        status TEXT NOT NULL

    )
""")

        # =====================================================
    # GERÇEK DURAK VERİLERİNİ AKTAR
    # =====================================================

    # Daha önce eklenmiş yapay durakları temizle
    cursor.execute("""
        DELETE FROM stops
    """)

    # Gerçek durak verilerini oku
    durak_df = pd.read_csv(DURAK_CSV)

    # Gerekli sütunları temizle
    durak_df["DURAKKODU"] = (
        durak_df["DURAKKODU"]
        .astype(str)
        .str.strip()
    )

    durak_df["DURAKADI"] = (
        durak_df["DURAKADI"]
        .astype(str)
        .str.strip()
    )

    durak_df["ILCEADI"] = (
        durak_df["ILCEADI"]
        .astype(str)
        .str.strip()
    )

    # Aynı durak farklı hatlarda tekrar ettiği için
    # DURAKKODU'na göre tekilleştir
    durak_df = durak_df.drop_duplicates(
        subset=["DURAKKODU"]
    )

    # Gerçek durakları ekle
    for _, row in durak_df.iterrows():

        stop_code = row["DURAKKODU"]
        stop_name = row["DURAKADI"]
        district = row["ILCEADI"]

        latitude = pd.to_numeric(
            row["YKOORDINATI"],
            errors="coerce"
        )

        longitude = pd.to_numeric(
            row["XKOORDINATI"],
            errors="coerce"
        )

        address = f"{district}, İstanbul"

        # CSV'de durak aktif/pasif bilgisi olmadığı için
        # varsayılan olarak aktif kabul ediyoruz
        status = "aktif"

        cursor.execute("""
            INSERT OR IGNORE INTO stops
            (
                stop_code,
                stop_name,
                district,
                address,
                latitude,
                longitude,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            stop_code,
            stop_name,
            district,
            address,
            latitude,
            longitude,
            status
        ))

    # Varsayılan admin hesabı
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role, status)
        VALUES (?, ?, ?, ?)
    """, (
        "mert",
        "1234",
        "admin",
        "aktif"
    ))

    # Varsayılan personel hesabı
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role, status)
        VALUES (?, ?, ?, ?)
    """, (
        "personel",
        "1234",
        "personel",
        "aktif"
    ))

        # =========================================================
    # SEFERLER TABLOSU
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        trip_number TEXT NOT NULL UNIQUE,

        line_number TEXT NOT NULL,

        route TEXT NOT NULL,

        vehicle_id INTEGER,

        start_stop_id INTEGER,

        end_stop_id INTEGER,

        start_time TEXT,

        end_time TEXT,

        status TEXT NOT NULL,

        FOREIGN KEY (vehicle_id)
            REFERENCES vehicles(id),

        FOREIGN KEY (start_stop_id)
            REFERENCES stops(id),

        FOREIGN KEY (end_stop_id)
            REFERENCES stops(id)
    )
""")

        # =====================================================
    # GERÇEK VERİLERDEN SEFERLERİ OLUŞTUR
    # =====================================================

    # Daha önce oluşturulmuş yapay seferleri temizle
    cursor.execute("""
        DELETE FROM trips
    """)

    # Gerçek verileri oku
    sefer_df = pd.read_csv(SEFER_CSV)
    guzergah_df = pd.read_csv(GUZERGAH_CSV)
    print("GÜZERGAH SÜTUNLARI:", guzergah_df.columns.tolist())

    # -----------------------------------------------------
    # GERÇEK ARAÇLARI AL
    # -----------------------------------------------------

    vehicle_rows = sefer_df[
        ["Plaka", "Saat", "Hiz"]
    ].dropna(subset=["Plaka"])

    vehicle_rows["Plaka"] = (
        vehicle_rows["Plaka"]
        .astype(str)
        .str.strip()
    )

    vehicle_rows["Saat"] = (
        vehicle_rows["Saat"]
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # GERÇEK HATLARI VE DURAKLARI AL
    # -----------------------------------------------------

    route_df = guzergah_df[
        [
            "HATKODU",
            "YON",
            "SIRANO",
            "DURAKKODU",
            "DURAKADI"
        ]
    ].copy()

    route_df["HATKODU"] = (
        route_df["HATKODU"]
        .astype(str)
        .str.strip()
    )

    route_df["YON"] = (
        route_df["YON"]
        .astype(str)
        .str.strip()
    )

    route_df["DURAKKODU"] = (
        route_df["DURAKKODU"]
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # HAT + YÖN BAZINDA GÜZERGAHLARI OLUŞTUR
    # -----------------------------------------------------

    route_groups = []

    for (line_number, direction), group in route_df.groupby(
        ["HATKODU", "YON"]
    ):

        group = group.sort_values("SIRANO")

        if len(group) < 2:
            continue

        start_code = str(
            group.iloc[0]["DURAKKODU"]
        ).strip()

        end_code = str(
            group.iloc[-1]["DURAKKODU"]
        ).strip()

        start_name = str(
            group.iloc[0]["DURAKADI"]
        ).strip()

        end_name = str(
            group.iloc[-1]["DURAKADI"]
        ).strip()

        route_groups.append({
            "line_number": line_number,
            "direction": direction,
            "start_code": start_code,
            "end_code": end_code,
            "start_name": start_name,
            "end_name": end_name
        })

    # -----------------------------------------------------
    # ARAÇLARI PLAKA -> DATABASE ID OLARAK AL
    # -----------------------------------------------------

    cursor.execute("""
        SELECT id, plate
        FROM vehicles
    """)

    vehicle_map = {
        str(row[1]).strip(): row[0]
        for row in cursor.fetchall()
    }

    # -----------------------------------------------------
    # DURAKLARI KOD -> DATABASE ID OLARAK AL
    # -----------------------------------------------------

    cursor.execute("""
        SELECT id, stop_code
        FROM stops
    """)

    stop_map = {
        str(row[1]).strip(): row[0]
        for row in cursor.fetchall()
    }

    # -----------------------------------------------------
    # SEFERLERİ OLUŞTUR
    # -----------------------------------------------------

    trip_counter = 1

    # Çok fazla kayıt oluşmaması için
    # ilk 500 gerçek hat/yön kombinasyonunu kullanıyoruz.
    for index, route_data in enumerate(route_groups):

        if not vehicle_rows.empty:

            vehicle_row = vehicle_rows.iloc[
                index % len(vehicle_rows)
            ]

            plate = str(
                vehicle_row["Plaka"]
            ).strip()

            start_time = str(
                vehicle_row["Saat"]
            ).strip()

            vehicle_id = vehicle_map.get(plate)

        else:

            continue

        start_stop_id = stop_map.get(
            route_data["start_code"]
        )

        end_stop_id = stop_map.get(
            route_data["end_code"]
        )

        # Araç veya durak database'de bulunmuyorsa
        # bu seferi oluşturma
        if vehicle_id is None:
            continue

        if start_stop_id is None:
            continue

        if end_stop_id is None:
            continue

        # CSV'de bitiş saati bulunmadığı için
        # kontrollü olarak yaklaşık 45 dakika ekliyoruz.
        try:

            start_dt = pd.to_datetime(
                start_time,
                format="%H:%M:%S"
            )

            end_dt = start_dt + pd.Timedelta(
                minutes=45
            )

            end_time = end_dt.strftime(
                "%H:%M:%S"
            )

        except Exception:

            end_time = start_time

        # Durum
        # Gerçek sefer CSV'sinde sefer durumu olmadığı için
        # kontrollü şekilde oluşturuyoruz.
        if index % 10 == 0:
            status = "iptal"
        elif index % 3 == 0:
            status = "tamamlandi"
        else:
            status = "aktif"

        trip_number = f"SEF-{trip_counter:05d}"

        route_name = (
            f"{route_data['start_name']} → "
            f"{route_data['end_name']}"
        )

        cursor.execute("""
            INSERT OR IGNORE INTO trips
            (
                trip_number,
                line_number,
                route,
                vehicle_id,
                start_stop_id,
                end_stop_id,
                start_time,
                end_time,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_number,
            route_data["line_number"],
            route_name,
            vehicle_id,
            start_stop_id,
            end_stop_id,
            start_time,
            end_time,
            status
        ))

        trip_counter += 1

    # =========================================================
# AI SEFER ÖNERİLERİ TABLOSU
# =========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_recommendations (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        line_number TEXT NOT NULL,

        vehicle_id INTEGER,

        day_type TEXT,

        start_time TEXT,

        end_time TEXT,

        expected_density TEXT,

        analysis_purpose TEXT,

        recommendation TEXT,

        extra_vehicle_count INTEGER DEFAULT 0,

        recommended_frequency TEXT,

        direction TEXT,

        confidence INTEGER DEFAULT 0,

        status TEXT DEFAULT 'olusturuldu',

        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (vehicle_id)
            REFERENCES vehicles(id)

    )
""")

    conn.commit()
    conn.close()

    



# =========================================================
# CSV DOSYA YOLLARI
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_DIR = os.path.join(
    BASE_DIR,
    "data",
    "csv"
)

SEFER_CSV = os.path.join(
    CSV_DIR,
    "sefer_gerceklesme.csv"
)

# =====================================================
# SEFER CSV CACHE
# =====================================================

SEFER_REPORT_CACHE = None


def get_sefer_report_df():

    global SEFER_REPORT_CACHE

    if SEFER_REPORT_CACHE is None:

        SEFER_REPORT_CACHE = pd.read_csv(
            SEFER_CSV,
            usecols=[
                "KapiNo",
                "Plaka",
                "Hiz"
            ]
        )

        SEFER_REPORT_CACHE["KapiNo"] = (
            SEFER_REPORT_CACHE["KapiNo"]
            .astype(str)
            .str.strip()
        )

        SEFER_REPORT_CACHE["Plaka"] = (
            SEFER_REPORT_CACHE["Plaka"]
            .astype(str)
            .str.strip()
        )

        SEFER_REPORT_CACHE["Hiz"] = pd.to_numeric(
            SEFER_REPORT_CACHE["Hiz"],
            errors="coerce"
        ).fillna(0)

    return SEFER_REPORT_CACHE

GUZERGAH_CSV = os.path.join(
    CSV_DIR,
    "iett_guzergah.csv"
)

ARAC_CSV = os.path.join(
    CSV_DIR,
    "arac_ozellik.csv"
)

DURAK_CSV = os.path.join(
    CSV_DIR,
    "durak_yogunluklari.csv"
)

# =========================================================
# DASHBOARD VERİLERİ
# =========================================================

def get_dashboard_data():

    # CSV dosyalarını oku
    sefer_df = pd.read_csv(SEFER_CSV)
    print("SEFER SÜTUNLARI:", sefer_df.columns.tolist())
    print("SEFER KAYIT SAYISI:", len(sefer_df))
    print(sefer_df.head(3).to_string())
    
    guzergah_df = pd.read_csv(GUZERGAH_CSV)
    arac_df = pd.read_csv(ARAC_CSV)
    print("ARAÇ SÜTUNLARI:", arac_df.columns.tolist())
    durak_df = pd.read_csv(DURAK_CSV)

        # =====================================================
    # KAPI NO → PLAKA → ARAÇ → HAT EŞLEŞME TESTİ
    # =====================================================

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            trips.line_number,
            vehicles.plate
        FROM trips
        INNER JOIN vehicles
            ON trips.vehicle_id = vehicles.id
        WHERE trips.line_number IS NOT NULL
        AND vehicles.plate IS NOT NULL
    """)

    trip_vehicle_rows = cursor.fetchall()

    conn.close()


    # Sefer Gerçekleşme verisinden KapıNo → Plaka
    kapi_plaka = (
        sefer_df[
            ["KapiNo", "Plaka"]
        ]
        .dropna()
        .astype(str)
    )

    kapi_plaka["KapiNo"] = (
        kapi_plaka["KapiNo"]
        .str.strip()
    )

    kapi_plaka["Plaka"] = (
        kapi_plaka["Plaka"]
        .str.strip()
    )


    # Gerçek verilerden KapıNo → Plaka → Hat
    kapi_hat_eslesmeleri = {}

    for line_number, plate in trip_vehicle_rows:

        plate = str(plate).strip()
        line_number = str(line_number).strip()

        matching_rows = kapi_plaka[
            kapi_plaka["Plaka"] == plate
        ]

        for _, row in matching_rows.iterrows():

            kapi_no = row["KapiNo"]

            if kapi_no not in kapi_hat_eslesmeleri:

                kapi_hat_eslesmeleri[kapi_no] = set()

            kapi_hat_eslesmeleri[kapi_no].add(
                line_number
            )


    print("========================================")
    print("KAPI NO → HAT GERÇEK EŞLEŞME TESTİ")
    print("========================================")

    print(
        "Toplam doğrulanmış Kapı No:",
        len(kapi_hat_eslesmeleri)
    )

    for kapi_no, lines_for_kapi in list(
        kapi_hat_eslesmeleri.items()
    )[:20]:

        print(
            "Kapı No:",
            kapi_no,
            "→ Hatlar:",
            sorted(lines_for_kapi)
        )

    print("========================================")

    # -----------------------------------------------------
    # TEMEL İSTATİSTİKLER
    # -----------------------------------------------------

    total_routes = guzergah_df["HATKODU"].nunique()

    # Durak veri setindeki toplam durak kaydı
    total_stops = len(durak_df)

    total_vehicles = sefer_df["Plaka"].nunique()
    total_trips = len(sefer_df)

    # -----------------------------------------------------
    # HAREKET HALİNDEKİ ARAÇLAR
    # -----------------------------------------------------

    moving_vehicles = sefer_df[
        pd.to_numeric(
            sefer_df["Hiz"],
            errors="coerce"
        ) > 0
    ]["Plaka"].nunique()

    # -----------------------------------------------------
    # YOĞUNLUK
    # -----------------------------------------------------

    average_density = round(
        pd.to_numeric(
            durak_df["YOGUNLUK_ENDEKSI"],
            errors="coerce"
        ).mean(),
        2
    )

    # -----------------------------------------------------
    # KRİTİK DURAKLAR
    # -----------------------------------------------------

    critical_stops = (
        durak_df["ONCELIK"]
        .astype(str)
        .str.strip()
        .eq("Kritik")
        .sum()
    )

    # -----------------------------------------------------
    # TOPLAM YAKIT
    # -----------------------------------------------------

    total_fuel = round(
        pd.to_numeric(
            arac_df["ToplamAkarYakit"],
            errors="coerce"
        ).sum(),
        2
    )

    # -----------------------------------------------------
    # DASHBOARD VERİLERİ
    # -----------------------------------------------------

        # -----------------------------------------------------
    # GRAFİK 1 - EN YOĞUN 10 HAT
    # -----------------------------------------------------

    route_counts = (
        guzergah_df["HATKODU"]
        .value_counts()
        .head(10)
    )

    chart_route_labels = route_counts.index.astype(str).tolist()

    chart_route_values = route_counts.values.tolist()


    # -----------------------------------------------------
    # GRAFİK 2 - DURAK YOĞUNLUK DAĞILIMI
    # -----------------------------------------------------

    priority_counts = (
        durak_df["ONCELIK"]
        .fillna("Bilinmiyor")
        .astype(str)
        .str.strip()
        .value_counts()
    )

    chart_priority_labels = priority_counts.index.tolist()

    chart_priority_values = priority_counts.values.tolist()

    return {
        "total_routes": total_routes,
        "total_stops": total_stops,
        "total_vehicles": total_vehicles,
        "moving_vehicles": moving_vehicles,
        "total_trips": total_trips,
        "average_density": average_density,
        "critical_stops": critical_stops,
        "total_fuel": total_fuel,
        "chart_route_labels": chart_route_labels,
        "chart_route_values": chart_route_values,
        "chart_priority_labels": chart_priority_labels,
        "chart_priority_values": chart_priority_values
    }

      

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

      
        username = request.form.get("username")
        password = request.form.get("password")

        # Veritabanına bağlan
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Kullanıcıyı kontrol et
        cursor.execute("""
            SELECT id, username, password, role, status
            FROM users
            WHERE username = ?
        """, (username,))

        user = cursor.fetchone()

        conn.close()

        # Kullanıcı bulunduysa kontrol et
        if user:

            user_id = user[0]
            db_username = user[1]
            db_password = user[2]
            db_role = user[3]
            db_status = user[4]

            # Şifre + rol + aktiflik kontrolü
            if (
                password == db_password
                and db_role == "admin"
                and db_status == "aktif"
            ):

                session["user_id"] = user_id
                session["role"] = db_role
                session["username"] = db_username

                    # Admin
                if db_role == "admin":
                    return redirect(url_for("admin_dashboard"))

        return render_template(
            "login.html",
            error="Kullanıcı adı veya şifre hatalı."
        )

    return render_template("login.html")


@app.route("/admin_dashboard")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    dashboard_data = get_dashboard_data()

    return render_template(
        "admin_dashboard.html",
        **dashboard_data
    )

# =====================================================
# ŞİFREMİ UNUTTUM
# =====================================================

@app.route("/sifremi-unuttum", methods=["GET", "POST"])
def sifremi_unuttum():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        new_password = request.form.get(
            "new_password",
            ""
        ).strip()

        confirm_password = request.form.get(
            "confirm_password",
            ""
        ).strip()


        # -------------------------------------------------
        # BOŞ ALAN KONTROLÜ
        # -------------------------------------------------

        if not username or not new_password or not confirm_password:

            return render_template(
                "forgot_password.html",
                error="Lütfen tüm alanları doldurun."
            )


        # -------------------------------------------------
        # ŞİFRE UZUNLUĞU
        # -------------------------------------------------

        if len(new_password) < 4:

            return render_template(
                "forgot_password.html",
                error="Yeni şifre en az 4 karakter olmalıdır.",
                username=username
            )


        # -------------------------------------------------
        # ŞİFRE TEKRARI
        # -------------------------------------------------

        if new_password != confirm_password:

            return render_template(
                "forgot_password.html",
                error="Yeni şifreler eşleşmiyor.",
                username=username
            )


        # -------------------------------------------------
        # VERİTABANI
        # -------------------------------------------------

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            AND role = 'admin'
            AND status = 'aktif'
            """,
            (username,)
        )


        user = cursor.fetchone()


        # -------------------------------------------------
        # KULLANICI KONTROLÜ
        # -------------------------------------------------

        if not user:

            conn.close()

            return render_template(
                "forgot_password.html",
                error="Aktif admin kullanıcısı bulunamadı.",
                username=username
            )


        # -------------------------------------------------
        # ŞİFREYİ GÜNCELLE
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                new_password,
                user[0]
            )
        )


        conn.commit()

        conn.close()


        # -------------------------------------------------
        # BAŞARILI
        # -------------------------------------------------

        return render_template(
            "forgot_password.html",
            success=(
                "Şifreniz başarıyla güncellendi. "
                "Yeni şifrenizle giriş yapabilirsiniz."
            )
        )


    return render_template(
        "forgot_password.html"
    )




# ---------------- KULLANICI YÖNETİMİ ----------------

@app.route("/kullanici_yonetimi")
def kullanici_yonetimi():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # -------------------------------------------------
    # SAYFALAMA + ARAMA
    # -------------------------------------------------

    page = request.args.get("page", 1, type=int)

    # Arama kutusundan gelen değer
    search = request.args.get("search", "").strip()

    per_page = 10

    if page < 1:
        page = 1

    # -------------------------------------------------
    # VERİTABANINA BAĞLAN
    # -------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # -------------------------------------------------
    # ARAMA VARSA
    # -------------------------------------------------

    if search:

        search_value = f"%{search}%"

        # Arama sonucundaki toplam kullanıcı
        cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE username LIKE ?
        """, (search_value,))

        total_users = cursor.fetchone()[0]

        # Arama sonucuna göre toplam sayfa
        total_pages = max(
            1,
            (total_users + per_page - 1) // per_page
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        # Arama sonucundaki kullanıcıları getir
        cursor.execute("""
            SELECT
                id,
                username,
                role,
                status
            FROM users
            WHERE username LIKE ?
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            search_value,
            per_page,
            offset
        ))

    # -------------------------------------------------
    # ARAMA YOKSA NORMAL LİSTE
    # -------------------------------------------------

    else:

        cursor.execute("""
            SELECT COUNT(*)
            FROM users
        """)

        total_users = cursor.fetchone()[0]

        total_pages = max(
            1,
            (total_users + per_page - 1) // per_page
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        cursor.execute("""
            SELECT
                id,
                username,
                role,
                status
            FROM users
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            per_page,
            offset
        ))

    users = cursor.fetchall()

    conn.close()

    # -------------------------------------------------
    # SAYFAYI GÖSTER
    # -------------------------------------------------

    return render_template(
        "kullanici_yonetimi.html",

        users=users,

        page=page,

        total_pages=total_pages,

        total_users=total_users,

        search=search
    )
# ---------------- KULLANICI EKLE ----------------

@app.route("/kullanici_ekle", methods=["POST"])
def kullanici_ekle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    username = request.form.get("username")
   
    password = request.form.get("password")
    role = request.form.get("role")
    status = request.form.get("status")

    # Boş alan kontrolü
    if not username or not password:
        return redirect(url_for("kullanici_yonetimi"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO users
            (username, password, role, status)
            VALUES (?, ?, ?, ?)
        """, (
            username,
            password,
            role,
            status
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        # Aynı kullanıcı adı varsa tekrar ekleme
        pass

    finally:

        conn.close()

    return redirect(url_for("kullanici_yonetimi"))

# ---------------- KULLANICI GETİR ----------------

@app.route("/kullanici_getir/<int:user_id>")
def kullanici_getir(user_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, password, role, status
        FROM users
        WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()

    conn.close()

    if not user:
        return redirect(url_for("kullanici_yonetimi"))

    return {
        "id": user[0],
        "username": user[1],
        "password": user[2],
        "role": user[3],
        "status": user[4]
    }

# ---------------- KULLANICI GÜNCELLE ----------------

@app.route("/kullanici_guncelle", methods=["POST"])
def kullanici_guncelle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    user_id = request.form.get("user_id")
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role")
    status = request.form.get("status")

    if not user_id or not username or not password:
        return redirect(url_for("kullanici_yonetimi"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            UPDATE users
            SET username = ?,
                password = ?,
                role = ?,
                status = ?
            WHERE id = ?
        """, (
            username,
            password,
            role,
            status,
            user_id
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        pass

    finally:
        conn.close()

    return redirect(url_for("kullanici_yonetimi"))


# ---------------- KULLANICI SİL ----------------

@app.route("/kullanici_sil/<int:user_id>", methods=["POST"])
def kullanici_sil(user_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM users
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("kullanici_yonetimi"))


# -----------------------------------------------------
# GERÇEK CSV'DEN KAPI NO EŞLEŞTİRME
# -----------------------------------------------------

def sync_vehicle_door_numbers():

    try:

        sefer_df = pd.read_csv(SEFER_CSV)

        if "KapiNo" not in sefer_df.columns:
            return

        if "Plaka" not in sefer_df.columns:
            return


        # Plaka - Kapı No eşleşmelerini al
        mapping_df = (
            sefer_df[["Plaka", "KapiNo"]]
            .dropna()
        )

        mapping_df["Plaka"] = (
            mapping_df["Plaka"]
            .astype(str)
            .str.strip()
        )

        mapping_df["KapiNo"] = (
            mapping_df["KapiNo"]
            .astype(str)
            .str.strip()
        )


        # Bir plakanın birden fazla Kapı No'su varsa
        # otomatik eşleştirme yapma.
        mapping_counts = (
            mapping_df
            .groupby("Plaka")["KapiNo"]
            .nunique()
        )

        valid_plates = mapping_counts[
            mapping_counts == 1
        ].index


        mapping_df = mapping_df[
            mapping_df["Plaka"].isin(valid_plates)
        ].drop_duplicates(
            subset=["Plaka"]
        )


        # Veritabanına bağlan
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()


        # Eşleşen araçların Kapı No'sunu güncelle
        for _, row in mapping_df.iterrows():

            cursor.execute("""
                UPDATE vehicles
                SET door_number = ?
                WHERE plate = ?
            """, (
                row["KapiNo"],
                row["Plaka"]
            ))


        conn.commit()
        conn.close()


    except Exception as e:

        print(
            "Kapı No eşleştirme hatası:",
            e
        )



# ---------------- ARAÇ YÖNETİMİ ----------------

@app.route("/arac_yonetimi")
def arac_yonetimi():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # -------------------------------------------------
    # SAYFALAMA + ARAMA
    # -------------------------------------------------

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()

    per_page = 10

    if page < 1:
        page = 1

    sync_vehicle_door_numbers()

    # -------------------------------------------------
    # VERİTABANINA BAĞLAN
    # -------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # -------------------------------------------------
    # ARAMA VARSA
    # -------------------------------------------------

    if search:

        search_value = f"%{search}%"

        cursor.execute("""
            SELECT COUNT(*)
            FROM vehicles
            WHERE door_number LIKE ?
        """, (search_value,))

        total_vehicles = cursor.fetchone()[0]

        total_pages = max(
            1,
            (total_vehicles + per_page - 1) // per_page
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        cursor.execute("""
            SELECT
                id,
                plate,
                name,
                vehicle_type,
                fuel_type,
                model_year,
                chassis_no,
                mileage,
                status,
                door_number
            FROM vehicles
            WHERE door_number LIKE ?
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            search_value,
            per_page,
            offset
        ))

    # -------------------------------------------------
    # ARAMA YOKSA NORMAL LİSTE
    # -------------------------------------------------

    else:

        cursor.execute("""
            SELECT COUNT(*)
            FROM vehicles
        """)

        total_vehicles = cursor.fetchone()[0]

        total_pages = max(
            1,
            (total_vehicles + per_page - 1) // per_page
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        cursor.execute("""
            SELECT
                id,
                plate,
                name,
                vehicle_type,
                fuel_type,
                model_year,
                chassis_no,
                mileage,
                status,
                door_number
            FROM vehicles
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            per_page,
            offset
        ))

    vehicles = cursor.fetchall()

    # -------------------------------------------------
    # AKTİF ARAÇ
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM vehicles
        WHERE status = 'aktif'
    """)

    active_vehicles = cursor.fetchone()[0]

    # -------------------------------------------------
    # BAKIMDAKİ ARAÇ
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM vehicles
        WHERE status = 'bakimda'
    """)

    maintenance_vehicles = cursor.fetchone()[0]

    # -------------------------------------------------
    # PASİF ARAÇ
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM vehicles
        WHERE status = 'pasif'
    """)

    passive_vehicles = cursor.fetchone()[0]

    conn.close()

    # -------------------------------------------------
    # SAYFAYI GÖSTER
    # -------------------------------------------------

    return render_template(
        "arac_yonetimi.html",

        vehicles=vehicles,

        total_vehicles=total_vehicles,

        active_vehicles=active_vehicles,

        maintenance_vehicles=maintenance_vehicles,

        passive_vehicles=passive_vehicles,

        page=page,

        total_pages=total_pages,

        search=search
    )

# ---------------- ARAÇ EKLE ----------------

@app.route("/arac_ekle", methods=["POST"])
def arac_ekle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    plate = request.form.get("plate")
    name = request.form.get("name")
    vehicle_type = request.form.get("vehicle_type")
    fuel_type = request.form.get("fuel_type")
    model_year = request.form.get("model_year")
    chassis_no = request.form.get("chassis_no")
    mileage = request.form.get("mileage")
    status = request.form.get("status")

    if not plate or not name:
        return redirect(url_for("arac_yonetimi"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO vehicles
            (
                plate,
                name,
                vehicle_type,
                fuel_type,
                model_year,
                chassis_no,
                mileage,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plate,
            name,
            vehicle_type,
            fuel_type,
            model_year,
            chassis_no,
            mileage,
            status
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        pass

    finally:

        conn.close()

    return redirect(url_for("arac_yonetimi"))

# ---------------- ARAÇ SİL ----------------

@app.route("/arac_sil/<int:vehicle_id>", methods=["POST"])
def arac_sil(vehicle_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM vehicles
        WHERE id = ?
    """, (vehicle_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("arac_yonetimi"))

# ---------------- ARAÇ GETİR ----------------

@app.route("/arac_getir/<int:vehicle_id>")
def arac_getir(vehicle_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            plate,
            name,
            vehicle_type,
            fuel_type,
            model_year,
            chassis_no,
            mileage,
            status,
            door_number
        FROM vehicles
        WHERE id = ?
    """, (vehicle_id,))

    vehicle = cursor.fetchone()

    conn.close()

    if not vehicle:
        return {"error": "Araç bulunamadı"}, 404

    return {
        "id": vehicle[0],
        "plate": vehicle[1],
        "name": vehicle[2],
        "vehicle_type": vehicle[3],
        "fuel_type": vehicle[4],
        "model_year": vehicle[5],
        "chassis_no": vehicle[6],
        "mileage": vehicle[7],
        "status": vehicle[8],
        "door_number": vehicle[9]
    }
# ---------------- ARAÇ GÜNCELLE ----------------

@app.route("/arac_guncelle", methods=["POST"])
def arac_guncelle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    vehicle_id = request.form.get("vehicle_id")
    door_number = request.form.get("door_number")
    name = request.form.get("name")
    vehicle_type = request.form.get("vehicle_type")
    fuel_type = request.form.get("fuel_type")
    model_year = request.form.get("model_year")
    chassis_no = request.form.get("chassis_no")
    mileage = request.form.get("mileage")
    status = request.form.get("status")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            UPDATE vehicles
            SET
                door_number = ?,
                name = ?,
                vehicle_type = ?,
                fuel_type = ?,
                model_year = ?,
                chassis_no = ?,
                mileage = ?,
                status = ?
            WHERE id = ?
        """, (
            door_number,
            name,
            vehicle_type,
            fuel_type,
            model_year,
            chassis_no,
            mileage,
            status,
            vehicle_id
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        pass

    finally:

        conn.close()

    return redirect(url_for("arac_yonetimi"))


# =========================================================
# DURAK YÖNETİMİ
# =========================================================

@app.route("/durak_yonetimi")
def durak_yonetimi():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # -------------------------------------------------
    # SAYFALAMA VE ARAMA
    # -------------------------------------------------

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()

    per_page = 10

    if page < 1:
        page = 1


    # -------------------------------------------------
    # VERİTABANINA BAĞLAN
    # -------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    # -------------------------------------------------
    # TÜRKÇE KARAKTER UYUMLU ARAMA
    # -------------------------------------------------

    def turkish_lower(value):

        if value is None:
            return ""

        return (
            str(value)
            .replace("İ", "i")
            .replace("I", "ı")
            .lower()
        )

    conn.create_function(
        "TURKISH_LOWER",
        1,
        turkish_lower
    )


    # -------------------------------------------------
    # TOPLAM DURAK SAYISI
    # -------------------------------------------------

    if search:

        search_pattern = f"%{turkish_lower(search)}%"

        cursor.execute("""
            SELECT COUNT(*)
            FROM stops
            WHERE
                TURKISH_LOWER(stop_code) LIKE ?
                OR TURKISH_LOWER(stop_name) LIKE ?
                OR TURKISH_LOWER(district) LIKE ?
                OR TURKISH_LOWER(address) LIKE ?
        """, (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern
        ))

    else:

        cursor.execute("""
            SELECT COUNT(*)
            FROM stops
        """)


    total_stops = cursor.fetchone()[0]


    # -------------------------------------------------
    # TOPLAM SAYFA
    # -------------------------------------------------

    total_pages = max(
        1,
        (total_stops + per_page - 1) // per_page
    )


    if page > total_pages:
        page = total_pages


    # -------------------------------------------------
    # SAYFALIK DURAKLARI GETİR
    # -------------------------------------------------

    offset = (page - 1) * per_page


    if search:

        cursor.execute("""
            SELECT
                id,
                stop_code,
                stop_name,
                district,
                address,
                latitude,
                longitude,
                status
            FROM stops
            WHERE
                TURKISH_LOWER(stop_code) LIKE ?
                OR TURKISH_LOWER(stop_name) LIKE ?
                OR TURKISH_LOWER(district) LIKE ?
                OR TURKISH_LOWER(address) LIKE ?
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            per_page,
            offset
        ))

    else:

        cursor.execute("""
            SELECT
                id,
                stop_code,
                stop_name,
                district,
                address,
                latitude,
                longitude,
                status
            FROM stops
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (
            per_page,
            offset
        ))


    stops = cursor.fetchall()


    # -------------------------------------------------
    # AKTİF DURAK
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'aktif'
    """)

    active_stops = cursor.fetchone()[0]


    # -------------------------------------------------
    # BAKIMDA OLAN DURAK
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'bakimda'
    """)

    maintenance_stops = cursor.fetchone()[0]


    # -------------------------------------------------
    # PASİF DURAK
    # -------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'pasif'
    """)

    passive_stops = cursor.fetchone()[0]


    # -------------------------------------------------
    # BAĞLANTIYI KAPAT
    # -------------------------------------------------

    conn.close()


    # -------------------------------------------------
    # SAYFAYI GÖSTER
    # -------------------------------------------------

    return render_template(
        "durak_yonetimi.html",

        stops=stops,

        total_stops=total_stops,

        active_stops=active_stops,

        maintenance_stops=maintenance_stops,

        passive_stops=passive_stops,

        page=page,

        total_pages=total_pages,

        search=search
    )
# =========================================================
# DURAK EKLE
# =========================================================

@app.route("/durak_ekle", methods=["POST"])
def durak_ekle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    stop_code = request.form.get("stop_code")
    stop_name = request.form.get("stop_name")
    district = request.form.get("district")
    address = request.form.get("address")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    status = request.form.get("status")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO stops (
            stop_code,
            stop_name,
            district,
            address,
            latitude,
            longitude,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        stop_code,
        stop_name,
        district,
        address,
        latitude,
        longitude,
        status
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("durak_yonetimi"))

# =========================================================
# DURAK DÜZENLE
# =========================================================

@app.route("/durak_duzenle/<int:stop_id>", methods=["POST"])
def durak_duzenle(stop_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    stop_code = request.form.get("stop_code")
    stop_name = request.form.get("stop_name")
    district = request.form.get("district")
    address = request.form.get("address")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    status = request.form.get("status")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE stops
        SET
            stop_code = ?,
            stop_name = ?,
            district = ?,
            address = ?,
            latitude = ?,
            longitude = ?,
            status = ?
        WHERE id = ?
    """, (
        stop_code,
        stop_name,
        district,
        address,
        latitude,
        longitude,
        status,
        stop_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("durak_yonetimi"))

# =========================================================
# DURAK SİL
# =========================================================

@app.route("/durak_sil/<int:stop_id>", methods=["POST"])
def durak_sil(stop_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM stops
        WHERE id = ?
    """, (stop_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("durak_yonetimi"))


# =========================================================
# SEFER YÖNETİMİ
# =========================================================

@app.route("/sefer_yonetimi")
def sefer_yonetimi():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # -----------------------------------------------------
    # ARAMA VE SAYFALAMA
    # -----------------------------------------------------

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()

    per_page = 10

    if page < 1:
        page = 1


    # -----------------------------------------------------
    # TÜRKÇE KARAKTER UYUMLU ARAMA
    # -----------------------------------------------------

    def turkish_lower(value):

        if value is None:
            return ""

        return (
            str(value)
            .replace("İ", "i")
            .replace("I", "ı")
            .lower()
        )

    conn.create_function(
        "TURKISH_LOWER",
        1,
        turkish_lower
    )


    # -----------------------------------------------------
    # TOPLAM SEFER SAYISI
    # -----------------------------------------------------

    if search:

        search_pattern = f"%{turkish_lower(search)}%"

        cursor.execute("""
            SELECT COUNT(*)
            FROM trips

            LEFT JOIN vehicles
                ON trips.vehicle_id = vehicles.id

            LEFT JOIN stops AS start_stop
                ON trips.start_stop_id = start_stop.id

            LEFT JOIN stops AS end_stop
                ON trips.end_stop_id = end_stop.id

            WHERE
                TURKISH_LOWER(trips.trip_number) LIKE ?
                OR TURKISH_LOWER(trips.line_number) LIKE ?
                OR TURKISH_LOWER(trips.route) LIKE ?
                OR TURKISH_LOWER(vehicles.door_number) LIKE ?
                OR TURKISH_LOWER(start_stop.stop_name) LIKE ?
                OR TURKISH_LOWER(end_stop.stop_name) LIKE ?
                OR TURKISH_LOWER(trips.status) LIKE ?
        """, (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern
        ))

    else:

        cursor.execute("""
            SELECT COUNT(*)
            FROM trips
        """)


    total_trips = cursor.fetchone()[0]


    # -----------------------------------------------------
    # TOPLAM SAYFA
    # -----------------------------------------------------

    total_pages = max(
        1,
        (total_trips + per_page - 1) // per_page
    )


    if page > total_pages:
        page = total_pages


    # -----------------------------------------------------
    # SEFERLERİ GETİR
    # -----------------------------------------------------

    offset = (page - 1) * per_page


    if search:

        cursor.execute("""
            SELECT
                trips.id,
                trips.trip_number,
                trips.line_number,
                trips.route,
                trips.vehicle_id,
                trips.start_stop_id,
                trips.end_stop_id,
                trips.start_time,
                trips.end_time,
                trips.status,

                vehicles.door_number,

                start_stop.stop_name,

                end_stop.stop_name

            FROM trips

            LEFT JOIN vehicles
                ON trips.vehicle_id = vehicles.id

            LEFT JOIN stops AS start_stop
                ON trips.start_stop_id = start_stop.id

            LEFT JOIN stops AS end_stop
                ON trips.end_stop_id = end_stop.id

            WHERE
                TURKISH_LOWER(trips.trip_number) LIKE ?
                OR TURKISH_LOWER(trips.line_number) LIKE ?
                OR TURKISH_LOWER(trips.route) LIKE ?
                OR TURKISH_LOWER(vehicles.door_number) LIKE ?
                OR TURKISH_LOWER(start_stop.stop_name) LIKE ?
                OR TURKISH_LOWER(end_stop.stop_name) LIKE ?
                OR TURKISH_LOWER(trips.status) LIKE ?

            ORDER BY trips.id DESC

            LIMIT ? OFFSET ?

        """, (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            per_page,
            offset
        ))

    else:

        cursor.execute("""
            SELECT
                trips.id,
                trips.trip_number,
                trips.line_number,
                trips.route,
                trips.vehicle_id,
                trips.start_stop_id,
                trips.end_stop_id,
                trips.start_time,
                trips.end_time,
                trips.status,

                vehicles.door_number,

                start_stop.stop_name,

                end_stop.stop_name

            FROM trips

            LEFT JOIN vehicles
                ON trips.vehicle_id = vehicles.id

            LEFT JOIN stops AS start_stop
                ON trips.start_stop_id = start_stop.id

            LEFT JOIN stops AS end_stop
                ON trips.end_stop_id = end_stop.id

            ORDER BY trips.id DESC

            LIMIT ? OFFSET ?

        """, (
            per_page,
            offset
        ))


    trips = cursor.fetchall()

    # -----------------------------------------------------
    # ARAÇLARI GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            plate,
            name
        FROM vehicles
        ORDER BY plate
    """)

    vehicles = cursor.fetchall()






    # -----------------------------------------------------
    # DURAKLARI GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            stop_code,
            stop_name
        FROM stops
        ORDER BY stop_name
    """)

    stops = cursor.fetchall()


    # -----------------------------------------------------
    # SEFER SAYILARI
    # -----------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
    """)

    total_trips_all = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'aktif'
    """)

    active_trips = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'tamamlandi'
    """)

    completed_trips = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'iptal'
    """)

    cancelled_trips = cursor.fetchone()[0]


    # -----------------------------------------------------
    # BAĞLANTIYI KAPAT
    # -----------------------------------------------------

    conn.close()


    # -----------------------------------------------------
    # SAYFAYI GÖSTER
    # -----------------------------------------------------

    return render_template(
        "sefer_yonetimi.html",

        trips=trips,

        vehicles=vehicles,

        stops=stops,

        total_trips=total_trips,

        active_trips=active_trips,

        completed_trips=completed_trips,

        cancelled_trips=cancelled_trips,

        page=page,

        total_pages=total_pages,

        search=search
    )

# =========================================================
# YENİ SEFER EKLE
# =========================================================

@app.route("/sefer_ekle", methods=["POST"])
def sefer_ekle():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    trip_number = request.form.get("trip_number")
    line_number = request.form.get("line_number")
    route = request.form.get("route")

    vehicle_id = request.form.get("vehicle_id")
    start_stop_id = request.form.get("start_stop_id")
    end_stop_id = request.form.get("end_stop_id")

    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")

    status = request.form.get("status")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO trips (
            trip_number,
            line_number,
            route,
            vehicle_id,
            start_stop_id,
            end_stop_id,
            start_time,
            end_time,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trip_number,
        line_number,
        route,
        vehicle_id,
        start_stop_id,
        end_stop_id,
        start_time,
        end_time,
        status
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("sefer_yonetimi"))

# =========================================================
# SEFER SİL
# =========================================================

@app.route("/sefer_sil/<int:trip_id>", methods=["POST"])
def sefer_sil(trip_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM trips
        WHERE id = ?
    """, (trip_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("sefer_yonetimi"))

# =========================================================
# SEFER DÜZENLE
# =========================================================

@app.route("/sefer_duzenle/<int:trip_id>", methods=["POST"])
def sefer_duzenle(trip_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    trip_number = request.form.get("trip_number")
    line_number = request.form.get("line_number")
    route = request.form.get("route")
    vehicle_id = request.form.get("vehicle_id")
    start_stop_id = request.form.get("start_stop_id")
    end_stop_id = request.form.get("end_stop_id")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    status = request.form.get("status")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE trips
        SET
            trip_number = ?,
            line_number = ?,
            route = ?,
            vehicle_id = ?,
            start_stop_id = ?,
            end_stop_id = ?,
            start_time = ?,
            end_time = ?,
            status = ?
        WHERE id = ?
    """, (
        trip_number,
        line_number,
        route,
        vehicle_id,
        start_stop_id,
        end_stop_id,
        start_time,
        end_time,
        status,
        trip_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("sefer_yonetimi"))

# =========================================================
# VERİ ANALİZİ
# =========================================================

@app.route("/veri_analizi")
def veri_analizi():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # =====================================================
    # FİLTRELER
    # =====================================================

    selected_line = request.args.get("line", "").strip()
    selected_vehicle = request.args.get("vehicle", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_start_hour = request.args.get("start_hour", "").strip()
    selected_end_hour = request.args.get("end_hour", "").strip()

    # =====================================================
    # TEMEL SEFER SORGUSU
    # =====================================================

    query = """
        SELECT
            trips.id,
            trips.trip_number,
            trips.line_number,
            trips.route,
            trips.vehicle_id,
            trips.start_stop_id,
            trips.end_stop_id,
            trips.start_time,
            trips.end_time,
            trips.status,
            vehicles.plate,
            vehicles.door_number
        FROM trips

        LEFT JOIN vehicles
            ON trips.vehicle_id = vehicles.id

        WHERE 1=1
    """

    params = []

    # Hat filtresi
    if selected_line:

        query += """
            AND trips.line_number = ?
        """

        params.append(selected_line)

    # Araç filtresi
    if selected_vehicle:

        query += """
            AND trips.vehicle_id = ?
        """

        params.append(selected_vehicle)

    # Durum filtresi
    if selected_status:

        query += """
            AND trips.status = ?
        """

        params.append(selected_status)

    query += """
        ORDER BY trips.id DESC
    """

    cursor.execute(query, params)

    trips = cursor.fetchall()

    # =====================================================
    # ÖZET SAYILARI
    # =====================================================

    total_trips = len(trips)

    active_trips = sum(
        1
        for trip in trips
        if trip[9] == "aktif"
    )

    completed_trips = sum(
        1
        for trip in trips
        if trip[9] == "tamamlandi"
    )

    cancelled_trips = sum(
        1
        for trip in trips
        if trip[9] == "iptal"
    )

    # =====================================================
    # CSV DOSYALARINI OKU
    # =====================================================

    try:

        sefer_df = pd.read_csv(SEFER_CSV)
        guzergah_df = pd.read_csv(GUZERGAH_CSV)
        durak_df = pd.read_csv(DURAK_CSV)

    except Exception as e:

        print("Veri Analizi CSV Hatası:", e)

        sefer_df = pd.DataFrame()
        guzergah_df = pd.DataFrame()
        durak_df = pd.DataFrame()

    # =====================================================
    # CSV VERİLERİNİ TEMİZLE
    # =====================================================

    if not guzergah_df.empty:

        guzergah_df["HATKODU"] = (
            guzergah_df["HATKODU"]
            .astype(str)
            .str.strip()
        )

        guzergah_df["DURAKADI"] = (
            guzergah_df["DURAKADI"]
            .astype(str)
            .str.strip()
        )

    if not durak_df.empty:

        durak_df["HATKODU"] = (
            durak_df["HATKODU"]
            .astype(str)
            .str.strip()
        )

        durak_df["DURAKADI"] = (
            durak_df["DURAKADI"]
            .astype(str)
            .str.strip()
        )

        durak_df["YOGUNLUK_ENDEKSI"] = pd.to_numeric(
            durak_df["YOGUNLUK_ENDEKSI"],
            errors="coerce"
        ).fillna(0)

    if not sefer_df.empty:

        sefer_df["KapiNo"] = (
            sefer_df["KapiNo"]
            .astype(str)
            .str.strip()
        )

        sefer_df["Plaka"] = (
            sefer_df["Plaka"]
            .astype(str)
            .str.strip()
        )

        sefer_df["Hiz"] = pd.to_numeric(
            sefer_df["Hiz"],
            errors="coerce"
        ).fillna(0)

        sefer_df["Saat"] = (
            sefer_df["Saat"]
            .astype(str)
            .str.strip()
        )

    # =====================================================
    # FİLTRELERİ CSV ANALİZ VERİSİNE BAĞLA
    # =====================================================

    # Filtrelenmiş seferlerden ilgili hat ve plakaları çıkar
    eligible_lines = set()
    eligible_plates = set()

    for trip in trips:

        # Hat
        if trip[2]:

            eligible_lines.add(
                str(trip[2]).strip()
            )

        # Plaka
        if trip[10]:

            eligible_plates.add(
                str(trip[10]).strip()
            )


    # =====================================================
    # CSV ANALİZ VERİSİ
    # =====================================================

    analysis_sefer_df = sefer_df.copy()


    if not analysis_sefer_df.empty:

                # -------------------------------------------------
        # HAT / DURUM FİLTRESİ
        # -------------------------------------------------

        if selected_line or selected_status:

            if eligible_plates:

                analysis_sefer_df = (
                    analysis_sefer_df[
                        analysis_sefer_df["Plaka"].isin(
                            eligible_plates
                        )
                    ]
                )

            else:

                analysis_sefer_df = (
                    analysis_sefer_df.iloc[0:0]
                )

        # -------------------------------------------------
        # SEÇİLİ ARAÇ (KAPI NO)
        # -------------------------------------------------

        if selected_vehicle:

            try:

                selected_vehicle_id = int(
                    selected_vehicle
                )

            except ValueError:

                selected_vehicle_id = None


            if selected_vehicle_id is not None:

                cursor.execute("""
                    SELECT
                        plate,
                        door_number
                    FROM vehicles
                    WHERE id = ?
                """, (
                    selected_vehicle_id,
                ))

                vehicle_row = cursor.fetchone()


                if vehicle_row:

                    selected_plate = str(
                        vehicle_row[0]
                    ).strip()

                    selected_door = str(
                        vehicle_row[1]
                    ).strip()


                    analysis_sefer_df = (
                        analysis_sefer_df[
                            (
                                analysis_sefer_df["Plaka"]
                                == selected_plate
                            )
                            |
                            (
                                analysis_sefer_df["KapiNo"]
                                == selected_door
                            )
                        ]
                    )


        # -------------------------------------------------
        # SAAT FİLTRESİ
        # -------------------------------------------------

        if (
            selected_start_hour
            or selected_end_hour
        ):

            time_values = pd.to_datetime(
                analysis_sefer_df["Saat"],
                format="%H:%M:%S",
                errors="coerce"
            )

            minutes = (
                time_values.dt.hour * 60
                + time_values.dt.minute
            )


            if selected_start_hour:

                start_parts = (
                    selected_start_hour
                    .split(":")
                )

                start_minutes = (
                    int(start_parts[0]) * 60
                    + int(start_parts[1])
                )

                analysis_sefer_df = (
                    analysis_sefer_df[
                        minutes >= start_minutes
                    ]
                )


            if selected_end_hour:

                # Saat filtresi tekrar hesaplanıyor
                time_values = pd.to_datetime(
                    analysis_sefer_df["Saat"],
                    format="%H:%M:%S",
                    errors="coerce"
                )

                minutes = (
                    time_values.dt.hour * 60
                    + time_values.dt.minute
                )

                end_parts = (
                    selected_end_hour
                    .split(":")
                )

                end_minutes = (
                    int(end_parts[0]) * 60
                    + int(end_parts[1])
                )

                analysis_sefer_df = (
                    analysis_sefer_df[
                        minutes <= end_minutes
                    ]
                )
        # =====================================================
    # GRAFİK 1
    # HAT YOĞUNLUĞU
    # =====================================================

    chart_route_df = guzergah_df.copy()

    if not chart_route_df.empty:

        # -------------------------------------------------
        # SEÇİLİ HAT
        # -------------------------------------------------

        if selected_line:

            chart_route_df["HATKODU"] = (
                chart_route_df["HATKODU"]
                .astype(str)
                .str.strip()
            )

            chart_route_df = chart_route_df[
                chart_route_df["HATKODU"] == str(selected_line).strip()
            ]

        # -------------------------------------------------
        # SEÇİLİ ARAÇ / DURUM
        # -------------------------------------------------

        elif selected_vehicle or selected_status:

            if eligible_lines:

                eligible_lines_normalized = {
                    str(line).strip()
                    for line in eligible_lines
                }

                chart_route_df["HATKODU"] = (
                    chart_route_df["HATKODU"]
                    .astype(str)
                    .str.strip()
                )

                chart_route_df = chart_route_df[
                    chart_route_df["HATKODU"].isin(
                        eligible_lines_normalized
                    )
                ]

            else:

                chart_route_df = chart_route_df.iloc[0:0]


    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    if not chart_route_df.empty:

        route_counts = (
            chart_route_df["HATKODU"]
            .value_counts()
            .head(10)
        )

        line_labels = (
            route_counts.index
            .astype(str)
            .tolist()
        )

        line_values = (
            route_counts.values
            .tolist()
        )

    else:

        line_labels = []
        line_values = []


    # =====================================================
    # GRAFİK 2
    # DURAK YOĞUNLUĞU
    # =====================================================

    chart_stop_df = durak_df.copy()

    if not chart_stop_df.empty:

        # -------------------------------------------------
        # SEÇİLİ HAT
        # -------------------------------------------------

        if selected_line:

            chart_stop_df["HATKODU"] = (
                chart_stop_df["HATKODU"]
                .astype(str)
                .str.strip()
            )

            chart_stop_df = chart_stop_df[
                chart_stop_df["HATKODU"] == str(selected_line).strip()
            ]

        # -------------------------------------------------
        # SEÇİLİ ARAÇ / DURUM
        # -------------------------------------------------

        elif selected_vehicle or selected_status:

            if eligible_lines:

                eligible_lines_normalized = {
                    str(line).strip()
                    for line in eligible_lines
                }

                chart_stop_df["HATKODU"] = (
                    chart_stop_df["HATKODU"]
                    .astype(str)
                    .str.strip()
                )

                chart_stop_df = chart_stop_df[
                    chart_stop_df["HATKODU"].isin(
                        eligible_lines_normalized
                    )
                ]

            else:

                chart_stop_df = chart_stop_df.iloc[0:0]


    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    if not chart_stop_df.empty:

        stop_counts = (
            chart_stop_df
            .groupby("DURAKADI")["YOGUNLUK_ENDEKSI"]
            .mean()
            .sort_values(ascending=False)
            .head(10)
        )

        stop_labels = (
            stop_counts.index
            .astype(str)
            .tolist()
        )

        stop_values = [
            round(float(value), 1)
            for value in stop_counts.values
        ]

    else:

        stop_labels = []
        stop_values = []
        
        

        # =====================================================
       # =====================================================
        # =====================================================
    # GRAFİK 3
    # HIZ DAĞILIMI
    # =====================================================

    speed_labels = [
        "0-10 km/s",
        "10-20 km/s",
        "20-30 km/s",
        "30-40 km/s",
        "40-50 km/s",
        "50+ km/s"
    ]

    speed_values = [0, 0, 0, 0, 0, 0]

    if not analysis_sefer_df.empty:

        speed_data = pd.to_numeric(
            analysis_sefer_df["Hiz"],
            errors="coerce"
        ).fillna(0)

        speed_values[0] = int(
            ((speed_data >= 0) & (speed_data < 10)).sum()
        )

        speed_values[1] = int(
            ((speed_data >= 10) & (speed_data < 20)).sum()
        )

        speed_values[2] = int(
            ((speed_data >= 20) & (speed_data < 30)).sum()
        )

        speed_values[3] = int(
            ((speed_data >= 30) & (speed_data < 40)).sum()
        )

        speed_values[4] = int(
            ((speed_data >= 40) & (speed_data < 50)).sum()
        )

        speed_values[5] = int(
            (speed_data >= 50).sum()
        )

    # HTML mevcut değişken isimlerini kullanmaya
    # devam etsin.
    vehicle_labels = speed_labels
    vehicle_values = speed_values

    # =====================================================
    # GRAFİK 4
    # SAATLİK ARAÇ HAREKETLİLİĞİ
    # =====================================================

    hour_counts = {
        f"{hour:02d}:00": 0
        for hour in range(24)
    }

    if not analysis_sefer_df.empty:

        for value in analysis_sefer_df["Saat"]:

            try:

                hour = int(
                    str(value)
                    .split(":")[0]
                )

                if 0 <= hour <= 23:

                    hour_counts[
                        f"{hour:02d}:00"
                    ] += 1

            except (
                ValueError,
                IndexError
            ):

                pass

    hour_labels = list(
        hour_counts.keys()
    )

    hour_values = list(
        hour_counts.values()
    )

    # =====================================================
    # ORTALAMA SEFER SÜRESİ
    # =====================================================

    trip_durations = []

    for trip in trips:

        start_time = trip[7]
        end_time = trip[8]

        if start_time and end_time:

            try:

                start_parts = start_time.split(":")
                end_parts = end_time.split(":")

                start_minutes = (
                    int(start_parts[0]) * 60
                    + int(start_parts[1])
                )

                end_minutes = (
                    int(end_parts[0]) * 60
                    + int(end_parts[1])
                )

                duration = (
                    end_minutes
                    - start_minutes
                )

                if duration < 0:

                    duration += 1440

                if duration > 0:

                    trip_durations.append(
                        duration
                    )

            except (
                ValueError,
                IndexError
            ):

                pass

    if trip_durations:

        average_duration = round(
            sum(trip_durations)
            / len(trip_durations),
            1
        )

    else:

        average_duration = 0

           # =====================================================
    # TABLO 1
    # HAT GÜZERGÂH ÖZETİ
    # =====================================================

    top_line_rows = []

    for index, line in enumerate(line_labels):

        top_line_rows.append({
            "line": str(line),
            "route_count": line_values[index]
        })

       # =====================================================
    # TABLO 2
    # SAATLİK HIZ PERFORMANSI
    # =====================================================

    vehicle_rows = []

    if not analysis_sefer_df.empty:

        hourly_data = []

        # 00:00 - 23:00 arasındaki her saat
        for hour in range(24):

            hour_text = f"{hour:02d}:00"

            hour_mask = (
                analysis_sefer_df["Saat"]
                .astype(str)
                .str.startswith(
                    f"{hour:02d}:"
                )
            )

            hour_df = analysis_sefer_df[
                hour_mask
            ]

            total_records = len(hour_df)

            if total_records == 0:
                continue

            speeds = pd.to_numeric(
                hour_df["Hiz"],
                errors="coerce"
            ).fillna(0)

            moving_records = int(
                (speeds > 0).sum()
            )

            moving_speeds = speeds[
                speeds > 0
            ]

            if len(moving_speeds) > 0:

                average_speed = round(
                    moving_speeds.mean(),
                    1
                )

            else:

                average_speed = 0

            vehicle_rows.append({

                # HTML'deki mevcut alanları
                # kullanıyoruz.
                "door_number":
                    hour_text,

                "records":
                    total_records,

                "moving":
                    moving_records,

                "average_speed":
                    average_speed

            })
    # =====================================================
    # FİLTRE SEÇENEKLERİ
    # =====================================================

    if not guzergah_df.empty:

        lines = sorted(
            guzergah_df["HATKODU"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

    else:

        lines = []

    cursor.execute("""
        SELECT
            id,
            door_number
        FROM vehicles
        ORDER BY door_number
    """)

    vehicles = cursor.fetchall()

    conn.close()

    # =====================================================
    # SAYFAYI GÖNDER
    # =====================================================

    return render_template(
        "veri_analizi.html",

        total_trips=total_trips,

        active_trips=active_trips,

        completed_trips=completed_trips,

        cancelled_trips=cancelled_trips,

        average_duration=
            average_duration,

        trips=trips,

        lines=lines,

        vehicles=vehicles,

        selected_line=
            selected_line,

        selected_vehicle=
            selected_vehicle,

        selected_status=
            selected_status,

        line_labels=
            line_labels,

        line_values=
            line_values,

        stop_labels=
            stop_labels,

        stop_values=
            stop_values,

        vehicle_labels=
            vehicle_labels,

        vehicle_values=
            vehicle_values,

        hour_labels=
            hour_labels,

        hour_values=
            hour_values,

        top_line_rows=
            top_line_rows,

        vehicle_rows=
            vehicle_rows
    )
# =========================================================
# AI SEFER ÖNERİSİ
# =========================================================

@app.route("/ai_sefer_onerisi")
def ai_sefer_onerisi():


    # Sadece admin erişebilir
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # Veritabanına bağlan
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # -----------------------------------------------------
    # HATLARI GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT DISTINCT line_number
        FROM trips
        WHERE line_number IS NOT NULL
        AND line_number != ''
        ORDER BY line_number
    """)

    lines = [row[0] for row in cursor.fetchall()]

    # -----------------------------------------------------
    # ARAÇLARI GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            plate,
            name
        FROM vehicles
        ORDER BY plate
    """)

    vehicles = cursor.fetchall()

    # -----------------------------------------------------
    # GERÇEK KAPI NO → HAT EŞLEŞMESİ
    # -----------------------------------------------------

    sefer_df = pd.read_csv(SEFER_CSV)

    # Gerekli sütunları temizle
    sefer_df["KapiNo"] = (
        sefer_df["KapiNo"]
        .astype(str)
        .str.strip()
    )

    sefer_df["Plaka"] = (
        sefer_df["Plaka"]
        .astype(str)
        .str.strip()
    )

    # Gerçek operasyon verisindeki
    # Kapı No → Hat eşleşmesini oluştur
    gate_numbers_by_line = {}

    # Burada henüz HAT bilgisi CSV'de olmadığı için
    # veritabanındaki araç-hat ilişkisini kullanacağız.
    for line in lines:

        line_trips = pd.DataFrame()

        conn_gate = sqlite3.connect(DATABASE)

        try:

            line_trips = pd.read_sql_query(
                """
                SELECT DISTINCT
                    v.plate
                FROM trips t
                INNER JOIN vehicles v
                    ON t.vehicle_id = v.id
                WHERE t.line_number = ?
                """,
                conn_gate,
                params=(line,)
            )

        finally:

            conn_gate.close()

        line_plates = set(
            line_trips["plate"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )

        # O hatta çalışan plakaların
        # gerçek CSV'deki Kapı No'larını bul
        line_gate_numbers = (
            sefer_df[
                sefer_df["Plaka"].isin(line_plates)
            ]["KapiNo"]
            .dropna()
            .loc[
                lambda x: x.ne("")
                & x.ne("nan")
            ]
            .drop_duplicates()
            .sort_values()
            .tolist()
        )

        gate_numbers_by_line[str(line)] = line_gate_numbers

    # -----------------------------------------------------
    # SON AI ÖNERİLERİNİ GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            ai_recommendations.id,
            ai_recommendations.line_number,
            ai_recommendations.day_type,
            ai_recommendations.start_time,
            ai_recommendations.end_time,
            ai_recommendations.expected_density,
            ai_recommendations.recommendation,
            ai_recommendations.extra_vehicle_count,
            ai_recommendations.recommended_frequency,
            ai_recommendations.direction,
            ai_recommendations.confidence,
            ai_recommendations.created_at,

            vehicles.plate

        FROM ai_recommendations

        LEFT JOIN vehicles
            ON ai_recommendations.vehicle_id = vehicles.id

        ORDER BY ai_recommendations.id DESC

        LIMIT 10
    """)

    recommendations = cursor.fetchall()

    # -----------------------------------------------------
    # SON OLUŞTURULAN AI ÖNERİSİ
    # -----------------------------------------------------

    latest_recommendation = recommendations[0] if recommendations else None

    # -----------------------------------------------------
    # TOPLAM ÖNERİ SAYISI
    # -----------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM ai_recommendations
    """)

    total_recommendations = cursor.fetchone()[0]

    # -----------------------------------------------------
    # ORTALAMA GÜVEN
    # -----------------------------------------------------

    cursor.execute("""
        SELECT AVG(confidence)
        FROM ai_recommendations
    """)

    average_confidence = cursor.fetchone()[0]

    if average_confidence is None:
        average_confidence = 0

    # -----------------------------------------------------
    # VERİTABANI BAĞLANTISINI KAPAT
    # -----------------------------------------------------

    conn.close()

    # -----------------------------------------------------
    # SAYFAYI GÖSTER
    # -----------------------------------------------------

    return render_template(
    "ai_oneri.html",

    lines=lines,

    vehicles=vehicles,

    gate_numbers_by_line=gate_numbers_by_line,

    recommendations=recommendations,

    latest_recommendation=latest_recommendation,

    total_recommendations=total_recommendations,

    average_confidence=round(average_confidence)
)

# =========================================================
# HAT → GERÇEK KAPI NO LARI
# =========================================================

@app.route("/api/ai_kapi_nolari/<line_number>")
def ai_kapi_nolari(line_number):

    if session.get("role") != "admin":
        return jsonify([])

    try:

        # Gerçek sefer CSV'sini oku
        sefer_df = pd.read_csv(SEFER_CSV)

        # Sütunları temizle
        sefer_df["Plaka"] = (
            sefer_df["Plaka"]
            .astype(str)
            .str.strip()
        )

        sefer_df["KapiNo"] = (
            sefer_df["KapiNo"]
            .astype(str)
            .str.strip()
        )

        # -------------------------------------------------
        # VERİTABANINDAN BU HATTA ÇALIŞAN PLAKALARI AL
        # -------------------------------------------------

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT
                v.plate
            FROM trips t
            INNER JOIN vehicles v
                ON t.vehicle_id = v.id
            WHERE t.line_number = ?
            AND t.line_number IS NOT NULL
            AND t.line_number != ''
            AND v.plate IS NOT NULL
            AND v.plate != ''
        """, (line_number,))

        rows = cursor.fetchall()

        conn.close()

        # Bu hatta çalışan gerçek plakalar
        line_plates = {
            str(row[0]).strip()
            for row in rows
        }

        # -------------------------------------------------
        # PLAKA → GERÇEK KAPI NO
        # -------------------------------------------------

        filtered = sefer_df[
            sefer_df["Plaka"].isin(line_plates)
        ]

        kapi_nolari = (
            filtered["KapiNo"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        kapi_nolari = sorted(
            kapi_nolari[
                (kapi_nolari != "") &
                (kapi_nolari.str.lower() != "nan")
            ].unique()
        )

        print("================================")
        print("AI KAPI NO API")
        print("SEÇİLEN HAT:", line_number)
        print("GERÇEK PLAKA SAYISI:", len(line_plates))
        print("GERÇEK KAPI NO SAYISI:", len(kapi_nolari))
        print("KAPI NOLAR:", kapi_nolari)
        print("================================")

        return jsonify(kapi_nolari)

    except Exception as e:

        print("KAPI NO HAT EŞLEŞME HATASI:", e)

        return jsonify([])


# =========================================================
# AI SEFER ÖNERİSİ OLUŞTUR
# =========================================================

@app.route("/ai_oneri_olustur", methods=["POST"])
def ai_oneri_olustur():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # -----------------------------------------------------
    # FORM VERİLERİNİ AL
    # -----------------------------------------------------

    line_number = request.form.get("line_number", "")
    vehicle_id = request.form.get("vehicle_id") or None
    kapi_no = request.form.get("kapi_no", "").strip()
    print("================================")
    print("FORMDAN GELEN KAPI NO:", repr(kapi_no))
    print("FORM VERİLERİ:", request.form.to_dict())
    print("================================")


    day_type = request.form.get("day_type", "")
    start_time = request.form.get("start_time", "")
    end_time = request.form.get("end_time", "")

    

    analysis_purpose = request.form.get(
        "analysis_purpose",
        ""
    )

        # -----------------------------------------------------
    # MEVCUT SEFER VERİLERİNİ ANALİZ ET
    # -----------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Saat aralığını güvenli şekilde oluştur
    # Normal aralık: 08:00 - 10:00
    # Gece yarısını geçen aralık: 22:00 - 02:00

    if start_time and end_time:

        if start_time <= end_time:

            time_condition = """
                AND start_time >= ?
                AND start_time <= ?
            """

            time_params = [
                start_time,
                end_time
            ]

        else:

            time_condition = """
                AND (
                    start_time >= ?
                    OR start_time <= ?
                )
            """

            time_params = [
                start_time,
                end_time
            ]

    else:

        time_condition = ""
        time_params = []


    # -----------------------------------------------------
    # TOPLAM SEFER SAYISI
    # -----------------------------------------------------

    query = f"""
        SELECT COUNT(*)
        FROM trips
        WHERE line_number = ?
        {time_condition}
    """

    cursor.execute(
        query,
        [line_number] + time_params
    )

    trip_count = cursor.fetchone()[0]


    # -----------------------------------------------------
    # AKTİF SEFER SAYISI
    # -----------------------------------------------------

    query = f"""
        SELECT COUNT(*)
        FROM trips
        WHERE line_number = ?
        {time_condition}
        AND status = 'aktif'
    """

    cursor.execute(
        query,
        [line_number] + time_params
    )

    active_trip_count = cursor.fetchone()[0]


    # -----------------------------------------------------
    # TAMAMLANAN SEFER SAYISI
    # -----------------------------------------------------

    query = f"""
        SELECT COUNT(*)
        FROM trips
        WHERE line_number = ?
        {time_condition}
        AND status = 'tamamlandi'
    """

    cursor.execute(
        query,
        [line_number] + time_params
    )

    completed_trip_count = cursor.fetchone()[0]


    # -----------------------------------------------------
    # İPTAL EDİLEN SEFER SAYISI
    # -----------------------------------------------------

    query = f"""
        SELECT COUNT(*)
        FROM trips
        WHERE line_number = ?
        {time_condition}
        AND status = 'iptal'
    """

    cursor.execute(
        query,
        [line_number] + time_params
    )

    cancelled_trip_count = cursor.fetchone()[0]


    conn.close()

        # -----------------------------------------------------
    # GERÇEK SEFER CSV VERİSİNİ ANALİZ ET
    # -----------------------------------------------------

    sefer_df = pd.read_csv(SEFER_CSV)

    # Saat bilgisini temizle
    sefer_df["Saat"] = (
        sefer_df["Saat"]
        .astype(str)
        .str.strip()
    )

    # Hız bilgisini sayısal hale getir
    sefer_df["Hiz"] = pd.to_numeric(
        sefer_df["Hiz"],
        errors="coerce"
    ).fillna(0)

    # CSV'deki saatleri datetime olarak çevir
    sefer_df["Saat_DT"] = pd.to_datetime(
        sefer_df["Saat"],
        format="%H:%M:%S",
        errors="coerce"
    )

        # -----------------------------------------------------
    # SEÇİLEN KAPI NO'YA GÖRE GERÇEK VERİYİ FİLTRELE
    # -----------------------------------------------------

    sefer_df["KapiNo"] = (
        sefer_df["KapiNo"]
        .astype(str)
        .str.strip()
    )

    if kapi_no:

        sefer_df = sefer_df[
            sefer_df["KapiNo"] == kapi_no
        ].copy()

        print("================================")
        print("AI KAPI NO FİLTRESİ")
        print("SEÇİLEN HAT:", line_number)
        print("SEÇİLEN KAPI NO:", kapi_no)
        print("KAPI NO GERÇEK KAYIT SAYISI:", len(sefer_df))
        print("================================")

    else:

        print("================================")
        print("UYARI: KAPI NO SEÇİLMEDİ")
        print("SEÇİLEN HAT:", line_number)
        print("================================")

    # -----------------------------------------------------
    # SEÇİLEN SAAT ARALIĞINA GÖRE GERÇEK CSV KAYITLARI
    # -----------------------------------------------------

    if start_time and end_time:

        csv_start = pd.to_datetime(
            start_time,
            format="%H:%M",
            errors="coerce"
        )

        csv_end = pd.to_datetime(
            end_time,
            format="%H:%M",
            errors="coerce"
        )

        csv_minutes = (
            sefer_df["Saat_DT"].dt.hour * 60
            + sefer_df["Saat_DT"].dt.minute
        )

        start_minutes = (
            csv_start.hour * 60
            + csv_start.minute
        )

        end_minutes = (
            csv_end.hour * 60
            + csv_end.minute
        )

        # Normal saat aralığı
        if start_minutes <= end_minutes:

            csv_filtered = sefer_df[
                (csv_minutes >= start_minutes)
                &
                (csv_minutes <= end_minutes)
            ]

        # Gece yarısını geçen aralık
        else:

            csv_filtered = sefer_df[
                (csv_minutes >= start_minutes)
                |
                (csv_minutes <= end_minutes)
            ]

    else:

        csv_filtered = sefer_df.copy()


    # -----------------------------------------------------
    # GERÇEK CSV KAYIT SAYISI
    # -----------------------------------------------------

    real_csv_record_count = len(
        csv_filtered
    )


    # -----------------------------------------------------
    # HAREKET EDEN GERÇEK ARAÇLAR
    # -----------------------------------------------------

    moving_csv_data = csv_filtered[
        csv_filtered["Hiz"] > 0
    ]

    real_moving_vehicle_count = (
        moving_csv_data["Plaka"]
        .dropna()
        .astype(str)
        .str.strip()
        .nunique()
    )


    # -----------------------------------------------------
    # ORTALAMA GERÇEK HIZ
    # -----------------------------------------------------

    if len(moving_csv_data) > 0:

        real_average_speed = round(
            moving_csv_data["Hiz"].mean(),
            1
        )

    else:

        real_average_speed = 0


    # -----------------------------------------------------
    # CSV'DEKİ TOPLAM FARKLI ARAÇ
    # -----------------------------------------------------

    real_vehicle_count = (
        csv_filtered["Plaka"]
        .dropna()
        .astype(str)
        .str.strip()
        .nunique()
    )

        # -----------------------------------------------------
    # OTOMATİK YOĞUNLUK HESABI
    # -----------------------------------------------------

    automatic_density = "dusuk"

    # Gerçek veri yoksa düşük kabul et
    if real_csv_record_count == 0:

        automatic_density = "dusuk"

    else:

        # -------------------------------------------------
        # 1. HAREKETLİ ARAÇ ORANI
        # -------------------------------------------------

        moving_ratio = (
            real_moving_vehicle_count / real_vehicle_count
            if real_vehicle_count > 0
            else 0
        )


        # -------------------------------------------------
        # 2. HIZ SKORU
        # Düşük ortalama hız = daha yüksek yoğunluk
        # -------------------------------------------------

        if real_average_speed < 10:

            speed_score = 100

        elif real_average_speed < 20:

            speed_score = 75

        elif real_average_speed < 30:

            speed_score = 50

        elif real_average_speed < 40:

            speed_score = 25

        else:

            speed_score = 0


        # -------------------------------------------------
        # 3. HAREKET ORANI SKORU
        # -------------------------------------------------

        if moving_ratio >= 0.50:

            movement_score = 100

        elif moving_ratio >= 0.35:

            movement_score = 75

        elif moving_ratio >= 0.20:

            movement_score = 50

        elif moving_ratio >= 0.10:

            movement_score = 25

        else:

            movement_score = 0


        # -------------------------------------------------
        # 4. GERÇEK VERİ MİKTARI
        # -------------------------------------------------

        if real_csv_record_count >= 5000:

            record_score = 100

        elif real_csv_record_count >= 2500:

            record_score = 75

        elif real_csv_record_count >= 1000:

            record_score = 50

        elif real_csv_record_count >= 500:

            record_score = 25

        else:

            record_score = 0


        # -------------------------------------------------
        # 5. GENEL YOĞUNLUK SKORU
        # -------------------------------------------------

        density_score = round(
            (speed_score * 0.40)
            + (movement_score * 0.40)
            + (record_score * 0.20)
        )


        # -------------------------------------------------
        # 6. YOĞUNLUK SEVİYESİ
        # -------------------------------------------------

        if density_score >= 75:

            automatic_density = "cok_yuksek"

        elif density_score >= 55:

            automatic_density = "yuksek"

        elif density_score >= 35:

            automatic_density = "orta"

        else:

            automatic_density = "dusuk"

        print("================================")
        print("CSV KAYIT:", real_csv_record_count)
        print("HAREKETLI ARAC:", real_moving_vehicle_count)
        print("TOPLAM ARAC:", real_vehicle_count)
        print("ORTALAMA HIZ:", real_average_speed)
        print("YOĞUNLUK SKORU:", density_score)
        print("OTOMATIK YOĞUNLUK:", automatic_density)
        print("================================")
        # -----------------------------------------------------
    # AI ÖNERİ MOTORU
    # GERÇEK VERİYE GÖRE OTOMATİK KARAR
    # -----------------------------------------------------

    extra_vehicle_count = 0
    recommended_frequency = "-"
    direction = "-"
    confidence = 70


    # -----------------------------------------------------
    # OTOMATİK YOĞUNLUĞU TEMEL AL
    # -----------------------------------------------------

    final_density = automatic_density


    # -----------------------------------------------------
    # YOĞUNLUĞA GÖRE ÖNERİ
    # -----------------------------------------------------

    if final_density == "dusuk":

        extra_vehicle_count = 0
        recommended_frequency = "15-20 dk"

    elif final_density == "orta":

        extra_vehicle_count = 1
        recommended_frequency = "10-15 dk"

    elif final_density == "yuksek":

        extra_vehicle_count = 2
        recommended_frequency = "7-10 dk"

    elif final_density == "cok_yuksek":

        extra_vehicle_count = 3
        recommended_frequency = "5-7 dk"


    # -----------------------------------------------------
    # VERİTABANI SEFER VERİLERİNE GÖRE GÜVEN
    # -----------------------------------------------------

    if trip_count > 0:
        confidence += 5

    if active_trip_count > 0:
        confidence += 3

    if completed_trip_count > 0:
        confidence += 2

    if cancelled_trip_count > 0:
        confidence += 2


    # -----------------------------------------------------
    # GÜVEN SINIRI
    # -----------------------------------------------------

    if confidence > 100:
        confidence = 100
           
        # =========================================================
    # VERİ ANALİZİ ÖZETİ
    # =========================================================

    data_summary = (
        f"{line_number} hattında "
        f"{start_time}-{end_time} saatleri arasında "
        f"{trip_count} sefer bulunmaktadır. "
        f"{active_trip_count} aktif, "
        f"{completed_trip_count} tamamlanan ve "
        f"{cancelled_trip_count} iptal sefer tespit edilmiştir."
    )


    # =========================================================
    # PROFESYONEL AI ÖNERİ METNİ
    # =========================================================

    # Otomatik hesaplanan yoğunluğu kullan
    final_density = automatic_density


    # Yoğunluk adını kullanıcıya düzgün göster
    density_names = {
        "dusuk": "düşük",
        "orta": "orta",
        "yuksek": "yüksek",
        "cok_yuksek": "çok yüksek"
    }

    density_text = density_names.get(
        final_density,
        "belirsiz"
    )


    # =========================================================
    # ANALİZ AMACINA GÖRE ÖNERİ
    # =========================================================

    if analysis_purpose == "ek_sefer":

        recommendation = (
            f"{line_number} hattının "
            f"{start_time}-{end_time} saatleri arasındaki "
            f"operasyonel verileri analiz edilmiştir. "

            f"Gerçek veri analizine göre yoğunluk seviyesi "
            f"{density_text} olarak belirlenmiştir. "

            f"Analiz kapsamında {real_csv_record_count:,} "
            f"araç hareket kaydı ve "
            f"{real_moving_vehicle_count:,} hareket halinde araç "
            f"tespit edilmiştir. "

            f"Ortalama araç hızı {real_average_speed} km/sa "
            f"olarak hesaplanmıştır. "

            f"Mevcut operasyonel kapasitenin desteklenmesi amacıyla "
            f"{extra_vehicle_count} ek aracın hatta dahil edilmesi "
            f"ve sefer sıklığının {recommended_frequency} "
            f"seviyesine çekilmesi önerilmektedir."
        )


    elif analysis_purpose == "arac_dagilimi":

        recommendation = (
            f"{line_number} hattının "
            f"{start_time}-{end_time} saatleri arasındaki "
            f"araç hareketliliği analiz edilmiştir. "

            f"Yoğunluk seviyesi {density_text} olarak "
            f"belirlenmiştir. "

            f"Gerçek veri setinde "
            f"{real_moving_vehicle_count:,} hareket halinde araç "
            f"tespit edilmiş ve ortalama hız "
            f"{real_average_speed} km/sa olarak hesaplanmıştır. "

            f"Operasyonel yoğunluğun dengelenmesi amacıyla "
            f"{extra_vehicle_count} ek aracın "
            f"{line_number} hattına yönlendirilmesi önerilmektedir."
        )


    elif analysis_purpose == "sefer_sikligi":

        recommendation = (
            f"{line_number} hattında "
            f"{start_time}-{end_time} saatleri arasındaki "
            f"veriler incelendiğinde yoğunluk seviyesi "
            f"{density_text} olarak belirlenmiştir. "

            f"Analiz edilen {real_csv_record_count:,} gerçek "
            f"araç hareket kaydı ve "
            f"{real_moving_vehicle_count:,} hareketli araç "
            f"verisi doğrultusunda, "

            f"sefer sıklığının {recommended_frequency} "
            f"seviyesine çekilmesi önerilmektedir."
        )


    elif analysis_purpose == "yogunluk":

        recommendation = (
            f"{line_number} hattının "
            f"{start_time}-{end_time} saatleri arasındaki "
            f"operasyonel yoğunluğu analiz edilmiştir. "

            f"Gerçek veri analizine göre yoğunluk seviyesi "
            f"{density_text} olarak belirlenmiştir. "

            f"Toplam {real_csv_record_count:,} araç hareket kaydı, "
            f"{real_moving_vehicle_count:,} hareketli araç ve "
            f"{real_average_speed} km/sa ortalama hız verisi "
            f"değerlendirilmiştir. "

            f"Mevcut yoğunluğa göre operasyonel kapasitenin "
            f"yeniden planlanması önerilmektedir."
        )


    else:

        recommendation = (
            f"{line_number} hattının "
            f"{start_time}-{end_time} saatleri arasındaki "
            f"operasyonel verileri analiz edilmiştir. "

            f"Yoğunluk seviyesi {density_text} olarak "
            f"belirlenmiştir. "

            f"Gerçek veri setindeki "
            f"{real_csv_record_count:,} kayıt ve "
            f"{real_moving_vehicle_count:,} hareketli araç "
            f"verisi dikkate alınarak sefer optimizasyonu "
            f"önerilmektedir."
        )


    # =========================================================
    # VERİTABANINA KAYDET
    # =========================================================

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ai_recommendations (

            line_number,
            vehicle_id,
            day_type,
            start_time,
            end_time,
            expected_density,
            analysis_purpose,
            recommendation,
            extra_vehicle_count,
            recommended_frequency,
            direction,
            confidence,
            status

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        line_number,
        vehicle_id,
        day_type,
        start_time,
        end_time,
        final_density,
        analysis_purpose,
        recommendation,
        extra_vehicle_count,
        recommended_frequency,
        direction,
        confidence,
        "olusturuldu"

    ))

    conn.commit()
    conn.close()


    # =========================================================
    # SONUCU AI PANELİNE GÖNDER
    # =========================================================

    return redirect(
        url_for("ai_sefer_onerisi")
    )

# ---------------- RAPORLAR ----------------

@app.route("/raporlar")
def raporlar():
    rapor_baslangic = time.perf_counter()

    if session.get("role") not in ["admin", "personel"]:
        return redirect(url_for("login"))

        # -----------------------------------------------------
    # RAPOR FİLTRELERİ
    # -----------------------------------------------------

    selected_line = request.args.get("line", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_start_time = request.args.get("start_time", "").strip()
    selected_end_time = request.args.get("end_time", "").strip()

    # -----------------------------------------------------
    # VERİTABANINA BAĞLAN
    # -----------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    # -----------------------------------------------------
    # GENEL SEFER SAYILARI
    # -----------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
    """)

    total_trips = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'aktif'
    """)

    active_trips = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'tamamlandi'
    """)

    completed_trips = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM trips
        WHERE status = 'iptal'
    """)

    cancelled_trips = cursor.fetchone()[0]


    # -----------------------------------------------------
    # HATLARI GETİR
    # -----------------------------------------------------

    cursor.execute("""
        SELECT DISTINCT line_number
        FROM trips
        WHERE line_number IS NOT NULL
        AND line_number != ''
        ORDER BY line_number
    """)

    lines = [row[0] for row in cursor.fetchall()]

        # -----------------------------------------------------
    # HAT BAZLI SEFER RAPORU
    # -----------------------------------------------------

        # -----------------------------------------------------
    # HAT BAZLI SEFER RAPORU
    # -----------------------------------------------------

        # -----------------------------------------------------
    # HAT BAZLI SEFER RAPORU
    # -----------------------------------------------------

    conditions = []
    params = []


    # Hat filtresi
    if selected_line:

        conditions.append("line_number = ?")
        params.append(selected_line)


    # Durum filtresi
    if selected_status:

        conditions.append("trips.status = ?")
        params.append(selected_status)

            # Başlangıç saati filtresi
    if selected_start_time:

        conditions.append("start_time >= ?")
        params.append(selected_start_time)

            # Bitiş saati filtresi
    if selected_end_time:

        conditions.append("start_time <= ?")
        params.append(selected_end_time)


    # WHERE oluştur
    where_clause = ""

    if conditions:

        where_clause = "WHERE " + " AND ".join(conditions)

        # -----------------------------------------------------
    # FİLTRELENMİŞ GENEL SEFER SAYILARI
    # -----------------------------------------------------

    cursor.execute(f"""
        SELECT
            COUNT(*),

            SUM(
                CASE
                    WHEN status = 'aktif'
                    THEN 1
                    ELSE 0
                END
            ),

            SUM(
                CASE
                    WHEN status = 'tamamlandi'
                    THEN 1
                    ELSE 0
                END
            ),

            SUM(
                CASE
                    WHEN status = 'iptal'
                    THEN 1
                    ELSE 0
                END
            )

        FROM trips

        {where_clause}

    """, params)

    report_summary = cursor.fetchone()

    total_trips = report_summary[0] or 0
    active_trips = report_summary[1] or 0
    completed_trips = report_summary[2] or 0
    cancelled_trips = report_summary[3] or 0                  

        # -----------------------------------------------------
    # HAT ANALİZ RAPORU - GERÇEK IETT VERİSİ
    # -----------------------------------------------------

    page = request.args.get("page", 1, type=int)

    per_page = 10

    if page < 1:
        page = 1


    # -----------------------------------------------------
    # DURAK YOĞUNLUK CSV'SİNİ OKU
    # -----------------------------------------------------

    trip_reports = []

    try:

        density_csv = os.path.join(
            CSV_DIR,
            "durak_yogunluklari.csv"
        )

        density_df = pd.read_csv(
            density_csv
        )
        print(
    "DEBUG HAT RAPORU:",
    round(time.perf_counter() - rapor_baslangic, 2),
    "saniye"
)


        # -------------------------------------------------
        # KOLONLARI TEMİZLE
        # -------------------------------------------------

        density_df["HATKODU"] = (
            density_df["HATKODU"]
            .astype(str)
            .str.strip()
        )

        density_df["DURAKKODU"] = (
            density_df["DURAKKODU"]
            .astype(str)
            .str.strip()
        )

        density_df["YOGUNLUK_ENDEKSI"] = pd.to_numeric(
            density_df["YOGUNLUK_ENDEKSI"],
            errors="coerce"
        ).fillna(0)


        # -------------------------------------------------
        # HAT FİLTRESİ
        # -------------------------------------------------

        if selected_line:

            density_df = density_df[
                density_df["HATKODU"]
                == str(selected_line).strip()
            ]


        # -------------------------------------------------
        # HAT BAZINDA RAPOR
        # -------------------------------------------------

        csv_line_reports = []

        for line, group in density_df.groupby("HATKODU"):

            # Farklı durak sayısı
            stop_count = (
                group["DURAKKODU"]
                .nunique()
            )


            # Ortalama yoğunluk
            average_density = round(
                group["YOGUNLUK_ENDEKSI"].mean(),
                1
            )


            # Kritik durak sayısı
            critical_count = 0

            if "ONCELIK" in group.columns:

                critical_count = int(
                    (
                        group["ONCELIK"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        == "kritik"
                    ).sum()
                )


            csv_line_reports.append(
                (
                    line,
                    stop_count,
                    average_density,
                    critical_count
                )
            )


        # -------------------------------------------------
        # YOĞUNLUĞA GÖRE SIRALA
        # -------------------------------------------------

        csv_line_reports.sort(
            key=lambda x: x[2],
            reverse=True
        )


        # -------------------------------------------------
        # TOPLAM HAT
        # -------------------------------------------------

        total_report_lines = len(
            csv_line_reports
        )


        # -------------------------------------------------
        # TOPLAM SAYFA
        # -------------------------------------------------

        total_pages = max(
            1,
            (
                total_report_lines
                + per_page
                - 1
            ) // per_page
        )


        if page > total_pages:

            page = total_pages


        # -------------------------------------------------
        # OFFSET
        # -------------------------------------------------

        offset = (
            page - 1
        ) * per_page


        # -------------------------------------------------
        # SAYFALANMIŞ HAT RAPORU
        # -------------------------------------------------

        trip_reports = csv_line_reports[
            offset:
            offset + per_page
        ]


    except Exception as csv_error:

        print(
            "Hat analiz CSV hatası:",
            csv_error
        )

        trip_reports = []

        total_report_lines = 0
        total_pages = 1
        page = 1
               # -----------------------------------------------------
    # HAT FİLTRESİNE GÖRE ARAÇLARI BELİRLE
    # -----------------------------------------------------

    # Filtrelenmiş seferlerde bulunan plakalar
    # Bu plakalar gerçek Kapı No'lara karşılık geliyor.
        eligible_plates = set()

    if selected_line or selected_status:

        cursor.execute(f"""
        SELECT DISTINCT vehicles.plate
        FROM trips
        INNER JOIN vehicles
            ON trips.vehicle_id = vehicles.id
        {where_clause}
    """, params)

        eligible_plates = {
            str(row[0]).strip()
            for row in cursor.fetchall()
            if row[0]
        }

    # -----------------------------------------------------
    # ARAÇ KULLANIM RAPORU - SAYFALAMA
    # -----------------------------------------------------

    vehicle_page = request.args.get(
        "vehicle_page",
        1,
        type=int
    )

    vehicle_per_page = 10

    if vehicle_page < 1:
        vehicle_page = 1


        # -----------------------------------------------------
    # GERÇEK CSV'DEN ARAÇ RAPORU
    # -----------------------------------------------------

    vehicle_reports = []

    csv_vehicle_reports = []

    try:

        report_csv_df = get_sefer_report_df().copy()

        # -----------------------------
        # KOLONLARI TEMİZLE
        # -----------------------------

        report_csv_df["KapiNo"] = (
            report_csv_df["KapiNo"]
            .astype(str)
            .str.strip()
        )

        report_csv_df["Plaka"] = (
            report_csv_df["Plaka"]
            .astype(str)
            .str.strip()
        )

        report_csv_df["Hiz"] = pd.to_numeric(
            report_csv_df["Hiz"],
            errors="coerce"
        ).fillna(0)

        # -------------------------------------------------
        # HAT / DURUM FİLTRESİ VARSA
        # SADECE O FİLTREYE BAĞLI ARAÇLAR
        # -------------------------------------------------

        if selected_line or selected_status:

            if eligible_plates:

                report_csv_df = report_csv_df[
                    report_csv_df["Plaka"].isin(
                        eligible_plates
                    )
                ]

            else:

                report_csv_df = (
                    report_csv_df.iloc[0:0]
                )


        # -------------------------------------------------
        # KAPI NO BAZINDA RAPOR
        # -------------------------------------------------

                

        cursor.execute("""
            SELECT door_number, name
            FROM vehicles
            WHERE door_number IS NOT NULL
        """)

        vehicle_name_map = {
            str(row[0]).strip(): row[1]
            for row in cursor.fetchall()
        }


            # -------------------------------------------------
        # KAPI NO BAZINDA HIZLI ARAÇ RAPORU
        # -------------------------------------------------

        vehicle_stats = (
            report_csv_df
            .assign(
                hareketli=(
                    report_csv_df["Hiz"] > 0
                ).astype(int)
            )
            .groupby("KapiNo")
            .agg(
                movement_count=("KapiNo", "size"),
                moving_count=("hareketli", "sum"),
                average_speed=("Hiz", "mean")
            )
            .reset_index()
        )


        for _, row in vehicle_stats.iterrows():

            kapi_no = row["KapiNo"]

            vehicle_name = vehicle_name_map.get(
                str(kapi_no).strip(),
                "Araç"
            )

            movement_count = int(
                row["movement_count"]
            )

            moving_count = int(
                row["moving_count"]
            )

            average_speed = round(
                row["average_speed"],
                1
            ) if pd.notna(row["average_speed"]) else 0


            csv_vehicle_reports.append((
                kapi_no,
                vehicle_name,
                movement_count,
                moving_count,
                average_speed
            ))
        # Kapı No'ya göre sırala
        csv_vehicle_reports.sort(
            key=lambda x: str(x[0])
        )


        # -------------------------------------------------
        # SAYFALAMA
        # -------------------------------------------------

        total_vehicle_reports = len(
            csv_vehicle_reports
        )

        vehicle_total_pages = max(
            1,
            (
                total_vehicle_reports
                + vehicle_per_page
                - 1
            ) // vehicle_per_page
        )


        if vehicle_page > vehicle_total_pages:
            vehicle_page = vehicle_total_pages


        vehicle_offset = (
            (vehicle_page - 1)
            * vehicle_per_page
        )


        vehicle_reports = csv_vehicle_reports[
            vehicle_offset:
            vehicle_offset + vehicle_per_page
        ]

    except Exception as csv_error:

        print(
            "ARAÇ RAPORU HATASI:",
            repr(csv_error)
        )

        raise


        

    
        print(
        "DEBUG ARAÇ RAPORU BİTTİ:",
        round(time.perf_counter() - rapor_baslangic, 2),
        "saniye"
    )

                # -----------------------------------------------------
    # DURAK RAPORU - SAYFALAMA
    # -----------------------------------------------------

    stop_page = request.args.get(
        "stop_page",
        1,
        type=int
    )

    stop_per_page = 10

    if stop_page < 1:
        stop_page = 1


    # -----------------------------------------------------
    # GERÇEK GÜZERGAH CSV'SİNİ OKU
    # -----------------------------------------------------

    print(
    "DEBUG GÜZERGAH CSV BAŞLANGIÇ:",
    round(time.perf_counter() - rapor_baslangic, 2),
    "saniye"
)

    route_stop_df = pd.read_csv(
        GUZERGAH_CSV
    )

    print(
    "DEBUG GÜZERGAH CSV BİTTİ:",
    round(time.perf_counter() - rapor_baslangic, 2),
    "saniye"
)


    # -----------------------------------------------------
    # CSV KOLONLARINI TEMİZLE
    # -----------------------------------------------------

    route_stop_df["HATKODU"] = (
        route_stop_df["HATKODU"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["DURAKKODU"] = (
        route_stop_df["DURAKKODU"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["DURAKADI"] = (
        route_stop_df["DURAKADI"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["ILCEADI"] = (
        route_stop_df["ILCEADI"]
        .astype(str)
        .str.strip()
    )


    # -----------------------------------------------------
    # SEÇİLİ HAT VARSA
    # SADECE O HATTIN DURAKLARINI GETİR
    # -----------------------------------------------------

    if selected_line:

        route_stop_df = route_stop_df[
            route_stop_df["HATKODU"]
            == selected_line
        ]


    # -----------------------------------------------------
    # DURAKLARI SIRALA
    # -----------------------------------------------------

    route_stop_df = route_stop_df.sort_values(
        ["HATKODU", "SIRANO"]
    )


    # Aynı durak farklı yönlerde tekrar edebilir.
    # Rapor tablosunda bir kez göster.
    route_stop_df = route_stop_df.drop_duplicates(
        subset=["DURAKKODU"]
    )


    # -----------------------------------------------------
    # TOPLAM DURAK SAYISI
    # -----------------------------------------------------

    total_stop_reports = len(
        route_stop_df
    )


    # -----------------------------------------------------
    # TOPLAM SAYFA
    # -----------------------------------------------------

    stop_total_pages = max(
        1,
        (
            total_stop_reports
            + stop_per_page
            - 1
        ) // stop_per_page
    )


    # Geçersiz sayfa gelirse son sayfaya dön
    if stop_page > stop_total_pages:

        stop_page = stop_total_pages


    # -----------------------------------------------------
    # OFFSET
    # -----------------------------------------------------

    stop_offset = (
        (stop_page - 1)
        * stop_per_page
    )


    # -----------------------------------------------------
    # SADECE İLGİLİ SAYFAYI AL
    # -----------------------------------------------------

    paged_stop_df = route_stop_df[
        stop_offset:
        stop_offset + stop_per_page
    ]


    # -----------------------------------------------------
    # STOP REPORTS OLUŞTUR
    # -----------------------------------------------------

    stop_reports = []


    for _, row in paged_stop_df.iterrows():

        stop_code = str(
            row["DURAKKODU"]
        ).strip()

        stop_name = str(
            row["DURAKADI"]
        ).strip()

        district = str(
            row["ILCEADI"]
        ).strip()


        stop_reports.append((
            stop_code,
            stop_name,
            district,
            f"{district}, İstanbul",
            "aktif"
        ))

    # -----------------------------------------------------
    # DURAK ÖZETİ
    # -----------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
    """)

    total_stops = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'aktif'
    """)

    active_stops = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'bakimda'
    """)

    maintenance_stops = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM stops
        WHERE status = 'pasif'
    """)

    passive_stops = cursor.fetchone()[0]


    # -----------------------------------------------------
    # BAĞLANTIYI KAPAT
    # -----------------------------------------------------

        # =====================================================
    # GERÇEK CSV VERİ ANALİZİ
    # =====================================================

    csv_record_count = 0
    csv_moving_vehicle_count = 0
    csv_total_vehicle_count = 0
    csv_average_speed = 0
    csv_density_score = 0
    csv_automatic_density = "belirsiz"

    csv_hour_labels = []
    csv_hour_counts = []


    try:
        print(
    "DEBUG GENEL CSV ANALİZİ BAŞLANGIÇ:",
    round(time.perf_counter() - rapor_baslangic, 2),
    "saniye"
)

        # -------------------------------------------------
        # CSV'Yİ OKU
        # -------------------------------------------------

        


        # -------------------------------------------------
        # TEMEL VERİLERİ TEMİZLE
        # -------------------------------------------------

        if "Plaka" in report_csv_df.columns:

            report_csv_df["Plaka"] = (
                report_csv_df["Plaka"]
                .astype(str)
                .str.strip()
            )


        if "Hiz" in report_csv_df.columns:

            report_csv_df["Hiz"] = pd.to_numeric(
                report_csv_df["Hiz"],
                errors="coerce"
            ).fillna(0)


        if "Saat" in report_csv_df.columns:

            report_csv_df["Saat"] = (
                report_csv_df["Saat"]
                .astype(str)
                .str.strip()
            )


        # -------------------------------------------------
        # TOPLAM CSV KAYDI
        # -------------------------------------------------

        csv_record_count = len(report_csv_df)


        # -------------------------------------------------
        # TOPLAM FARKLI ARAÇ
        # -------------------------------------------------

        if "Plaka" in report_csv_df.columns:

            csv_total_vehicle_count = (
                report_csv_df["Plaka"]
                .replace("", pd.NA)
                .dropna()
                .nunique()
            )


        # -------------------------------------------------
        # HAREKET HALİNDE ARAÇ
        # -------------------------------------------------

        if "Hiz" in report_csv_df.columns:

            moving_report_df = report_csv_df[
                report_csv_df["Hiz"] > 0
            ]

            if "Plaka" in moving_report_df.columns:

                csv_moving_vehicle_count = (
                    moving_report_df["Plaka"]
                    .replace("", pd.NA)
                    .dropna()
                    .nunique()
                )


        # -------------------------------------------------
        # ORTALAMA HIZ
        # -------------------------------------------------

        if "Hiz" in report_csv_df.columns:

            valid_speed_df = report_csv_df[
                report_csv_df["Hiz"] > 0
            ]

            if len(valid_speed_df) > 0:

                csv_average_speed = round(
                    valid_speed_df["Hiz"].mean(),
                    1
                )


        # -------------------------------------------------
        # YOĞUNLUK SKORU
        # -------------------------------------------------

        if csv_record_count > 0:

            moving_ratio = (
                csv_moving_vehicle_count
                / csv_total_vehicle_count
                if csv_total_vehicle_count > 0
                else 0
            )


            # Hız bazlı skor
            if csv_average_speed < 10:

                speed_score = 100

            elif csv_average_speed < 20:

                speed_score = 80

            elif csv_average_speed < 30:

                speed_score = 60

            elif csv_average_speed < 40:

                speed_score = 40

            else:

                speed_score = 20


            # Hareket oranı bazlı skor
            if moving_ratio > 0.30:

                movement_score = 100

            elif moving_ratio > 0.20:

                movement_score = 80

            elif moving_ratio > 0.10:

                movement_score = 60

            else:

                movement_score = 30


            csv_density_score = round(
                (speed_score + movement_score) / 2
            )


            # -------------------------------------------------
            # OTOMATİK YOĞUNLUK
            # -------------------------------------------------

            if csv_density_score >= 85:

                csv_automatic_density = "çok yüksek"

            elif csv_density_score >= 65:

                csv_automatic_density = "yüksek"

            elif csv_density_score >= 40:

                csv_automatic_density = "orta"

            else:

                csv_automatic_density = "düşük"


        # -------------------------------------------------
        # SAATLİK ARAÇ HAREKETLİLİĞİ
        # -------------------------------------------------

        if "Saat" in report_csv_df.columns:

            report_csv_df["Saat_DT"] = pd.to_datetime(
                report_csv_df["Saat"],
                format="%H:%M:%S",
                errors="coerce"
            )


            report_csv_df["Saat_Numara"] = (
                report_csv_df["Saat_DT"].dt.hour
            )


            hourly_data = (
                report_csv_df
                .dropna(subset=["Saat_Numara"])
                .groupby("Saat_Numara")
                .size()
            )


            for hour in range(24):

                csv_hour_labels.append(
                    f"{hour:02d}:00"
                )

                csv_hour_counts.append(
                    int(hourly_data.get(hour, 0))
                )


    except Exception as csv_error:

        print(
            "Rapor CSV analiz hatası:",
            csv_error
        )



    # -----------------------------------------------------
    # RAPORLAR SAYFASINI GÖSTER
    # -----------------------------------------------------

    return render_template(
        "raporlar.html",

        total_trips=total_trips,

        active_trips=active_trips,

        completed_trips=completed_trips,

        cancelled_trips=cancelled_trips,

        lines=lines,

        selected_line=selected_line,
selected_status=selected_status,
selected_start_time=selected_start_time,
selected_end_time=selected_end_time,

                trip_reports=trip_reports,
                page=page,
per_page=per_page,
total_pages=total_pages,
total_report_lines=total_report_lines,

        vehicle_reports=vehicle_reports,
        vehicle_page=vehicle_page,

vehicle_per_page=vehicle_per_page,

vehicle_total_pages=vehicle_total_pages,

total_vehicle_reports=total_vehicle_reports,

        stop_reports=stop_reports,
        stop_page=stop_page,

stop_per_page=stop_per_page,

stop_total_pages=stop_total_pages,

total_stop_reports=total_stop_reports,

        total_stops=total_stops,

        active_stops=active_stops,

        maintenance_stops=maintenance_stops,

        passive_stops=passive_stops,
            # CSV RAPOR VERİLERİ
    csv_record_count=csv_record_count,

    csv_moving_vehicle_count=csv_moving_vehicle_count,

    csv_total_vehicle_count=csv_total_vehicle_count,

    csv_average_speed=csv_average_speed,

    csv_density_score=csv_density_score,

    csv_automatic_density=csv_automatic_density,

    csv_hour_labels=csv_hour_labels,

    csv_hour_counts=csv_hour_counts,
    )

# =====================================================
# RAPORLAR - PDF
# =====================================================

@app.route("/raporlar/pdf")
def raporlar_pdf():

    if session.get("role") not in ["admin", "personel"]:
        return redirect(url_for("login"))

    # -------------------------------------------------
    # FİLTRELER
    # -------------------------------------------------

    selected_line = request.args.get("line", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_start_time = request.args.get("start_time", "").strip()
    selected_end_time = request.args.get("end_time", "").strip()


    # -------------------------------------------------
    # VERİTABANI
    # -------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    conditions = []
    params = []


    if selected_line:
        conditions.append("line_number = ?")
        params.append(selected_line)


    if selected_status:
        conditions.append("status = ?")
        params.append(selected_status)


    if selected_start_time:
        conditions.append("start_time >= ?")
        params.append(selected_start_time)


    if selected_end_time:
        conditions.append("start_time <= ?")
        params.append(selected_end_time)


    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)


    # -------------------------------------------------
    # SEFERLERİ GETİR
    # -------------------------------------------------

    cursor.execute(
        f"""
        SELECT
            id,
            line_number,
            vehicle_id,
            start_time,
            end_time,
            status
        FROM trips
        {where_clause}
        ORDER BY line_number, start_time
        """,
        params
    )

    trip_rows = cursor.fetchall()

        # -------------------------------------------------
    # FİLTRELENMİŞ ARAÇLARI GETİR
    # -------------------------------------------------

    vehicle_ids = list({
        row[2]
        for row in trip_rows
        if row[2] is not None
    })

    vehicle_rows = []

    if vehicle_ids:

        placeholders = ",".join(
            "?" for _ in vehicle_ids
        )

        cursor.execute(
            f"""
            SELECT
                id,
                door_number,
                name
            FROM vehicles
            WHERE id IN ({placeholders})
            ORDER BY door_number
            """,
            vehicle_ids
        )

        vehicle_rows = cursor.fetchall()

        
           # -------------------------------------------------
    # FİLTRELENMİŞ DURAKLARI GETİR
    # -------------------------------------------------

    route_stop_df = pd.read_csv(
        GUZERGAH_CSV
    )

    # Kolonları temizle
    route_stop_df["HATKODU"] = (
        route_stop_df["HATKODU"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["DURAKKODU"] = (
        route_stop_df["DURAKKODU"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["DURAKADI"] = (
        route_stop_df["DURAKADI"]
        .astype(str)
        .str.strip()
    )

    route_stop_df["ILCEADI"] = (
        route_stop_df["ILCEADI"]
        .astype(str)
        .str.strip()
    )


    # Seçili hat varsa sadece o hattın durakları
    if selected_line:

        route_stop_df = route_stop_df[
            route_stop_df["HATKODU"] == selected_line
        ]


    # Aynı durak farklı yönlerde tekrar edebilir
    route_stop_df = route_stop_df.drop_duplicates(
        subset=["DURAKKODU"]
    )


    # Durakları sırala
    route_stop_df = route_stop_df.sort_values(
        ["HATKODU", "SIRANO"]
    )


    # PDF'nin kullanacağı liste
    stop_rows = []

    for _, row in route_stop_df.iterrows():

        stop_rows.append([
            row["DURAKKODU"],
            row["DURAKADI"],
            row["ILCEADI"],
            f'{row["ILCEADI"]}, İstanbul',
            "aktif"
        ]) 
        

   


    # -------------------------------------------------
    # PDF
    # -------------------------------------------------

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        Image,
        Table as RLTable
    )

        # -------------------------------------------------
    # TÜRKÇE DESTEKLİ PDF FONTU
    # -------------------------------------------------

    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    font_bold_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]

    regular_font = None
    bold_font = None

    for path in font_paths:
        if os.path.exists(path):
            regular_font = path
            break

    for path in font_bold_paths:
        if os.path.exists(path):
            bold_font = path
            break

    if not regular_font or not bold_font:
        raise FileNotFoundError(
            "Türkçe destekli PDF fontu bulunamadı."
        )

    pdfmetrics.registerFont(
        TTFont("PDFTurkish", regular_font)
    )

    pdfmetrics.registerFont(
        TTFont("PDFTurkishBold", bold_font)
    )

        # -------------------------------------------------
    # KURUMSAL LOGOLAR
    # -------------------------------------------------

    combined_logo_path = os.path.join(
        os.path.dirname(__file__),
        "static",
        "img",
        "iett-ibb-logo1-1-17670.png"
    )

    output = io.BytesIO()


    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=18 * mm,
        bottomMargin=12 * mm
    )


    styles = getSampleStyleSheet()

    styles["Title"].fontName = "PDFTurkishBold"
    styles["Title"].fontSize = 18
    styles["Title"].leading = 22
    styles["Title"].alignment = TA_CENTER
    styles["Title"].textColor = colors.HexColor("#0b2d4f")

    styles["Normal"].fontName = "PDFTurkish"
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12

    styles["Heading2"].fontName = "PDFTurkishBold"
    styles["Heading2"].fontSize = 13
    styles["Heading2"].leading = 16
    styles["Heading2"].textColor = colors.HexColor("#0b2d4f")

    elements = []


            # -------------------------------------------------
    # KURUMSAL ÜST BİLGİ
    # -------------------------------------------------

    if os.path.exists(combined_logo_path):

        combined_logo = Image(
            combined_logo_path,
            width=58 * mm,
            height=22 * mm
        )

    else:

        combined_logo = Spacer(
            58 * mm,
            22 * mm
        )


    report_title = Paragraph(
        "İETT SEFER RAPORU",
        ParagraphStyle(
    "ReportTitleCentered",
    parent=styles["Title"],
    fontName="PDFTurkishBold",
    fontSize=20,
    leading=24,
    alignment=TA_CENTER,
    leftIndent=-15 * mm,
    textColor=colors.HexColor("#0b2d4f"),
    spaceAfter=2 * mm
)
    )


    header_table = RLTable(
    [[
        combined_logo,
        report_title
    ]],
    colWidths=[
        45 * mm,
        228 * mm
    ],
    rowHeights=[
        26 * mm
    ]
)
        
    header_table.setStyle(
        TableStyle([
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "ALIGN",
                (0, 0),
                (0, 0),
                "LEFT"
            ),

            (
                "ALIGN",
                (1, 0),
                (1, 0),
                "CENTER"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                0
            ),
        ])
    )

    elements.append(header_table)

    elements.append(
        Spacer(1, 4 * mm)
    )

    # -------------------------------------------------
    # FİLTRE BİLGİSİ
    # -------------------------------------------------

    filter_text = (
        f"Hat: {selected_line or 'Tümü'}"
        f" &nbsp;&nbsp;&nbsp; "
        f"Durum: {selected_status or 'Tümü'}"
        f" &nbsp;&nbsp;&nbsp; "
        f"Saat: {selected_start_time or '--:--'}"
        f" - {selected_end_time or '--:--'}"
    )


    elements.append(
        Paragraph(
            filter_text,
            styles["Normal"]
        )
    )


    elements.append(
        Spacer(1, 4 * mm)
    )


    # -------------------------------------------------
    # TOPLAM
    # -------------------------------------------------

    elements.append(
        Paragraph(
            f"Toplam sefer: {len(trip_rows)}",
            styles["Normal"]
        )
    )


    elements.append(
        Spacer(1, 5 * mm)
    )


    # -------------------------------------------------
    # TABLO
    # -------------------------------------------------

    table_data = [
        [
            "ID",
            "Hat",
            "Araç",
            "Başlangıç",
            "Bitiş",
            "Durum"
        ]
    ]


    for row in trip_rows:

        table_data.append([
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5]
        ])


    if len(table_data) == 1:

        table_data.append([
            "-",
            "Kayıt bulunamadı",
            "-",
            "-",
            "-",
            "-"
        ])


    report_table = Table(
        table_data,
        repeatRows=1
    )


    report_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0b2d4f")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "PDFTurkishBold"
            ),

            (
    "FONTNAME",
    (0, 1),
    (-1, -1),
    "PDFTurkish"
),

            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f4f7fa")
                ]
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            )

        ])
    )


    elements.append(
        report_table
    )

        # -------------------------------------------------
    # ARAÇ RAPORU PDF
    # -------------------------------------------------

    elements.append(
        Spacer(1, 8 * mm)
    )

    elements.append(
        Paragraph(
            "Araç Kullanım Raporu",
            styles["Heading2"]
        )
    )

    elements.append(
        Spacer(1, 3 * mm)
    )

    vehicle_table_data = [
        [
            "Kapı No",
            "Araç",
        ]
    ]

    for row in vehicle_rows:

        vehicle_table_data.append([
            row[0],
            row[1]
        ])

    if len(vehicle_table_data) == 1:

        vehicle_table_data.append([
            "-",
            "Araç bulunamadı"
        ])

    vehicle_table = Table(
        vehicle_table_data,
        repeatRows=1
    )

    vehicle_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0b2d4f")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "PDFTurkishBold"
            ),

            (
    "FONTNAME",
    (0, 1),
    (-1, -1),
    "PDFTurkish"
),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    elements.append(
        vehicle_table
    )

        # -------------------------------------------------
    # DURAK RAPORU PDF
    # -------------------------------------------------

    elements.append(
        Spacer(1, 8 * mm)
    )

    elements.append(
        Paragraph(
            "Durak Raporu",
            styles["Heading2"]
        )
    )

    elements.append(
        Spacer(1, 3 * mm)
    )

    stop_table_data = [
        [
            "Durak Kodu",
            "Durak Adı",
            "İlçe",
            "Adres",
            "Durum"
        ]
    ]

    for row in stop_rows:

        stop_table_data.append([
            row[0],
            row[1],
            row[2],
            row[3] or "-",
            row[4]
        ])

    if len(stop_table_data) == 1:

        stop_table_data.append([
            "-",
            "Durak bulunamadı",
            "-",
            "-",
            "-"
        ])

    stop_table = Table(
        stop_table_data,
        repeatRows=1
    )

    stop_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0b2d4f")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "PDFTurkishBold"
            ),

            (
    "FONTNAME",
    (0, 1),
    (-1, -1),
    "PDFTurkish"
),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    elements.append(
        stop_table
    )


    # -------------------------------------------------
    # PDF OLUŞTUR
    # -------------------------------------------------

    document.build(elements)

    output.seek(0)


    # -------------------------------------------------
    # İNDİR
    # -------------------------------------------------

    return send_file(
        output,
        as_attachment=True,
        download_name="sefer_raporu.pdf",
        mimetype="application/pdf"
    )

# =====================================================
# RAPORLAR - EXCEL
# =====================================================

@app.route("/raporlar/excel")
def raporlar_excel():

    if session.get("role") not in ["admin", "personel"]:
        return redirect(url_for("login"))


    # -------------------------------------------------
    # FİLTRELER
    # -------------------------------------------------

    selected_line = request.args.get(
        "line",
        ""
    ).strip()

    selected_status = request.args.get(
        "status",
        ""
    ).strip()

    selected_start_time = request.args.get(
        "start_time",
        ""
    ).strip()

    selected_end_time = request.args.get(
        "end_time",
        ""
    ).strip()


    # -------------------------------------------------
    # VERİTABANI
    # -------------------------------------------------

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()


    # -------------------------------------------------
    # SEFER FİLTRELERİ
    # -------------------------------------------------

    conditions = []
    params = []


    if selected_line:

        conditions.append(
            "line_number = ?"
        )

        params.append(
            selected_line
        )


    if selected_status:

        conditions.append(
            "status = ?"
        )

        params.append(
            selected_status
        )


    if selected_start_time:

        conditions.append(
            "start_time >= ?"
        )

        params.append(
            selected_start_time
        )


    if selected_end_time:

        conditions.append(
            "start_time <= ?"
        )

        params.append(
            selected_end_time
        )


    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )


    # -------------------------------------------------
    # SEFER RAPORU
    # -------------------------------------------------

    cursor.execute(
        f"""
        SELECT
            id,
            line_number,
            vehicle_id,
            start_time,
            end_time,
            status
        FROM trips
        {where_clause}
        ORDER BY line_number, start_time
        """,
        params
    )

    trip_rows = cursor.fetchall()


    # -------------------------------------------------
    # ARAÇ RAPORU
    # -------------------------------------------------
    # Sadece filtrelenmiş seferlerde kullanılan araçlar
    # -------------------------------------------------

    vehicle_ids = list({
        row[2]
        for row in trip_rows
        if row[2] is not None
    })


    vehicle_rows = []


    if vehicle_ids:

        placeholders = ",".join(
            "?" for _ in vehicle_ids
        )


        cursor.execute(
            f"""
            SELECT
                id,
                door_number,
                name
            FROM vehicles
            WHERE id IN ({placeholders})
            ORDER BY door_number
            """,
            vehicle_ids
        )

        vehicle_rows = cursor.fetchall()


    # -------------------------------------------------
    # GÜZERGAH CSV
    # -------------------------------------------------

    route_stop_df = pd.read_csv(
        GUZERGAH_CSV
    )


    # -------------------------------------------------
    # KOLONLARI TEMİZLE
    # -------------------------------------------------

    route_stop_df["HATKODU"] = (
        route_stop_df["HATKODU"]
        .astype(str)
        .str.strip()
    )


    route_stop_df["DURAKKODU"] = (
        route_stop_df["DURAKKODU"]
        .astype(str)
        .str.strip()
    )


    route_stop_df["DURAKADI"] = (
        route_stop_df["DURAKADI"]
        .astype(str)
        .str.strip()
    )


    route_stop_df["ILCEADI"] = (
        route_stop_df["ILCEADI"]
        .astype(str)
        .str.strip()
    )


    # -------------------------------------------------
    # SEÇİLİ HAT FİLTRESİ
    # -------------------------------------------------

    if selected_line:

        route_stop_df = route_stop_df[
            route_stop_df["HATKODU"]
            == selected_line
        ]


    # -------------------------------------------------
    # AYNI DURAKLARI TEKİLLEŞTİR
    # -------------------------------------------------

    route_stop_df = route_stop_df.drop_duplicates(
        subset=["DURAKKODU"]
    )


    # -------------------------------------------------
    # DURAK SIRALAMASI
    # -------------------------------------------------

    if "SIRANO" in route_stop_df.columns:

        route_stop_df = route_stop_df.sort_values(
            ["HATKODU", "SIRANO"]
        )

    else:

        route_stop_df = route_stop_df.sort_values(
            ["HATKODU", "DURAKKODU"]
        )


    # -------------------------------------------------
    # SEFER DATAFRAME
    # -------------------------------------------------

    trips_data = []


    for row in trip_rows:

        trips_data.append([
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5]
        ])


    trips_df = pd.DataFrame(
        trips_data,
        columns=[
            "ID",
            "Hat",
            "Araç",
            "Başlangıç",
            "Bitiş",
            "Durum"
        ]
    )


    # -------------------------------------------------
    # ARAÇ DATAFRAME
    # -------------------------------------------------

    vehicles_data = []


    for row in vehicle_rows:

        vehicles_data.append([
            row[1],
            row[2]
        ])


    vehicles_df = pd.DataFrame(
        vehicles_data,
        columns=[
            "Kapı No",
            "Araç"
        ]
    )


    # -------------------------------------------------
    # DURAK DATAFRAME
    # -------------------------------------------------

    stops_data = []


    for _, row in route_stop_df.iterrows():

        stops_data.append([
            row["DURAKKODU"],
            row["DURAKADI"],
            row["ILCEADI"],
            f'{row["ILCEADI"]}, İstanbul',
            "aktif"
        ])


    stops_df = pd.DataFrame(
        stops_data,
        columns=[
            "Durak Kodu",
            "Durak Adı",
            "İlçe",
            "Adres",
            "Durum"
        ]
    )


    # -------------------------------------------------
    # VERİTABANI KAPAT
    # -------------------------------------------------

    conn.close()


    # -------------------------------------------------
    # EXCEL DOSYASI
    # -------------------------------------------------

    output = io.BytesIO()


    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:


        # -------------------------------------------------
        # 1 - SEFER RAPORU
        # -------------------------------------------------

        trips_df.to_excel(
            writer,
            index=False,
            sheet_name="Sefer Raporu"
        )


        # -------------------------------------------------
        # 2 - ARAÇ RAPORU
        # -------------------------------------------------

        vehicles_df.to_excel(
            writer,
            index=False,
            sheet_name="Araç Raporu"
        )


        # -------------------------------------------------
        # 3 - DURAK RAPORU
        # -------------------------------------------------

        stops_df.to_excel(
            writer,
            index=False,
            sheet_name="Durak Raporu"
        )


        # -------------------------------------------------
        # EXCEL GÖRÜNÜM AYARLARI
        # -------------------------------------------------

        workbook = writer.book


        for sheet_name in [
            "Sefer Raporu",
            "Araç Raporu",
            "Durak Raporu"
        ]:

            worksheet = workbook[sheet_name]


            # Başlıkları kalın yap

            for cell in worksheet[1]:

                cell.font = cell.font.copy(
                    bold=True
                )


            # Filtre

            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )


            # İlk satırı sabitle

            worksheet.freeze_panes = "A2"


            # Kolon genişlikleri

            for column_cells in worksheet.columns:

                max_length = 0

                column_letter = (
                    column_cells[0].column_letter
                )


                for cell in column_cells:

                    try:

                        cell_length = len(
                            str(cell.value)
                        )

                        if cell_length > max_length:

                            max_length = cell_length

                    except Exception:

                        pass


                worksheet.column_dimensions[
                    column_letter
                ].width = min(
                    max_length + 3,
                    40
                )


    output.seek(0)


    # -------------------------------------------------
    # DOSYA ADI
    # -------------------------------------------------

    if selected_line:

        filename = (
            f"sefer_raporu_{selected_line}.xlsx"
        )

    else:

        filename = "sefer_raporu.xlsx"


    # -------------------------------------------------
    # EXCEL İNDİR
    # -------------------------------------------------

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

# =========================================================
# PROFİL
# =========================================================

@app.route("/profil", methods=["GET", "POST"])
def profil():

    # Sadece admin ve personel erişebilir
    if session.get("role") not in ["admin", "personel"]:
        return redirect(url_for("login"))

    # Mesaj değişkenleri
    password_error = None
    password_success = None

    # Kullanıcı ID
    user_id = session.get("user_id")

    # -----------------------------------------------------
    # POST İŞLEMLERİ
    # -----------------------------------------------------

    if request.method == "POST":

        # Formdan gelen bilgiler
        new_username = request.form.get("username", "").strip()

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # -------------------------------------------------
        # KULLANICI ADI GÜNCELLE
        # -------------------------------------------------

        if new_username:

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET username = ?
                WHERE id = ?
            """, (
                new_username,
                user_id
            ))

            conn.commit()
            conn.close()

            session["username"] = new_username

        # -------------------------------------------------
        # ŞİFRE DEĞİŞTİR
        # -------------------------------------------------

        if current_password or new_password or confirm_password:

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT password
                FROM users
                WHERE id = ?
            """, (user_id,))

            current_db_password = cursor.fetchone()

            if current_db_password:

                current_db_password = current_db_password[0]

                # Mevcut şifre yanlış
                if current_password != current_db_password:

                    password_error = "Mevcut şifrenizi hatalı girdiniz."

                # Yeni şifreler eşleşmiyor
                elif new_password != confirm_password:

                    password_error = "Yeni şifreler uyuşmuyor."

                # Yeni şifre boş
                elif not new_password:

                    password_error = "Yeni şifre boş bırakılamaz."

                # Her şey doğru
                else:

                    cursor.execute("""
                        UPDATE users
                        SET password = ?
                        WHERE id = ?
                    """, (
                        new_password,
                        user_id
                    ))

                    conn.commit()

                    password_success = "Şifreniz başarıyla güncellendi."

            conn.close()

    # -----------------------------------------------------
    # GÜNCEL KULLANICI BİLGİLERİNİ GETİR
    # -----------------------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, role, status
        FROM users
        WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()

    conn.close()

    # -----------------------------------------------------
    # PROFİL SAYFASINI GÖSTER
    # -----------------------------------------------------

    return render_template(
        "profil.html",
        user=user,
        password_error=password_error,
        password_success=password_success
    )

# ---------------- AYARLAR ---------------- #

@app.route("/ayarlar")
def ayarlar():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    return render_template("ayarlar.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":

    init_database()

    app.run(debug=True)