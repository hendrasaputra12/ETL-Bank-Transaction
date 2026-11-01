
import os
import pandas as pd
import mysql.connector

# ==========================================
# 1. KONEKSI DATABASE MYSQL XAMPP
# ==========================================

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="etl_bank"
)

cursor = db.cursor()

print("Berhasil terhubung ke database MySQL!")

# ==========================================
# 2. MEMBACA DATA CSV MENTAH
# ==========================================

file_csv = "data/transaksi_bank.csv"

if not os.path.exists(file_csv):
    raise FileNotFoundError(
        f"File tidak ditemukan: {file_csv}"
    )

df = pd.read_csv(file_csv)

# Menyesuaikan nama kolom CSV
df.columns = df.columns.str.strip()

df = df.rename(columns={
    "TransactionID": "transaction_id",
    "AccountID": "account_id",
    "TransactionAmount": "amount",
    "TransactionDate": "transaction_date",
    "TransactionType": "transaction_type",
    "Channel": "channel",
    "Location": "location",
    "CustomerAge": "customer_age",
    "CustomerOccupation": "occupation"
})

kolom_wajib = [
    "transaction_id", "account_id", "amount",
    "transaction_date", "transaction_type",
    "channel", "location", "customer_age",
    "occupation"
]

for kolom in kolom_wajib:
    if kolom not in df.columns:
        raise ValueError(
            f"Kolom {kolom} tidak ditemukan dalam CSV. "
            f"Kolom yang tersedia: {list(df.columns)}"
        )

print("Jumlah data mentah:", len(df))

# ==========================================
# 3. DATA CLEANING
# ==========================================

df["transaction_date"] = pd.to_datetime(
    df["transaction_date"], errors="coerce"
)

df["amount"] = pd.to_numeric(
    df["amount"], errors="coerce"
)

df = df.dropna(subset=[
    "transaction_id", "account_id",
    "amount", "transaction_date"
])

df = df.drop_duplicates(
    subset=["transaction_id"]
)

df["transaction_id"] = df["transaction_id"].astype(str)
df["account_id"] = df["account_id"].astype(str)

for kolom in ["transaction_type", "channel", "location",
              "occupation"]:
    df[kolom] = df[kolom].fillna("Unknown").astype(str)

df["customer_age"] = pd.to_numeric(
    df["customer_age"], errors="coerce"
)

df = df.sort_values("transaction_date").reset_index(drop=True)

print("Data setelah cleaning:", len(df))

# ==========================================
# 4. MEMBERSIHKAN TABEL LAMA
# ==========================================

tabel = [
    "daily_summary",
    "fact_transaction",
    "dim_date",
    "dim_type",
    "dim_channel",
    "dim_account",
    "stg_bank"
]

for nama in tabel:
    cursor.execute(f"TRUNCATE TABLE {nama}")

db.commit()

# ==========================================
# 5. LOAD DATA KE STAGING
# ==========================================

sql_staging = """
INSERT INTO stg_bank
(transaction_id, account_id, amount,
 transaction_date, transaction_type, channel, location)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

data_staging = []

for r in df.itertuples(index=False):
    data_staging.append((
        r.transaction_id,
        r.account_id,
        float(r.amount),
        r.transaction_date.date(),
        r.transaction_type,
        r.channel,
        r.location
    ))

cursor.executemany(sql_staging, data_staging)
db.commit()

print("Data berhasil masuk ke staging!")

# ==========================================
# 6. MEMBUAT DIMENSI CHANNEL
# ==========================================

for channel in df["channel"].unique():
    cursor.execute(
        "INSERT INTO dim_channel (channel) VALUES (%s)",
        (channel,)
    )

cursor.execute("SELECT channel_sk, channel FROM dim_channel")
channel_map = {nama: sk for sk, nama in cursor.fetchall()}

# ==========================================
# 7. MEMBUAT DIMENSI TRANSACTION TYPE
# ==========================================

for jenis in df["transaction_type"].unique():
    cursor.execute(
        "INSERT INTO dim_type (transaction_type) VALUES (%s)",
        (jenis,)
    )

cursor.execute(
    "SELECT type_sk, transaction_type FROM dim_type"
)
type_map = {nama: sk for sk, nama in cursor.fetchall()}

# ==========================================
# 8. MEMBUAT DIMENSI ACCOUNT (SCD TYPE 2)
# ==========================================

account_map = {}
account_terakhir = {}

for r in df.itertuples(index=False):

    account = r.account_id
    tanggal = r.transaction_date.date()

    umur = None if pd.isna(r.customer_age) else int(r.customer_age)
    pekerjaan = r.occupation

    data_baru = (umur, pekerjaan)

    if account not in account_terakhir:
        cursor.execute("""
            INSERT INTO dim_account
            (account_id, customer_age, occupation,
             valid_from, valid_to, is_current)
            VALUES (%s, %s, %s, %s, NULL, 1)
        """, (account, umur, pekerjaan, tanggal))

        account_sk = cursor.lastrowid

        account_terakhir[account] = {
            "data": data_baru,
            "sk": account_sk
        }

    elif account_terakhir[account]["data"] != data_baru:

        sk_lama = account_terakhir[account]["sk"]

        cursor.execute("""
            UPDATE dim_account
            SET valid_to = %s, is_current = 0
            WHERE account_sk = %s
        """, (tanggal, sk_lama))

        cursor.execute("""
            INSERT INTO dim_account
            (account_id, customer_age, occupation,
             valid_from, valid_to, is_current)
            VALUES (%s, %s, %s, %s, NULL, 1)
        """, (account, umur, pekerjaan, tanggal))

        account_sk = cursor.lastrowid

        account_terakhir[account] = {
            "data": data_baru,
            "sk": account_sk
        }

    account_map[r.transaction_id] = account_terakhir[account]["sk"]

# ==========================================
# 9. MEMBUAT DIMENSI DATE
# ==========================================

tanggal_unik = df["transaction_date"].dt.date.unique()

for tanggal in tanggal_unik:
    date_sk = int(tanggal.strftime("%Y%m%d"))

    cursor.execute("""
        INSERT INTO dim_date
        (date_sk, full_date, year_num, month_num, day_num)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        date_sk,
        tanggal,
        tanggal.year,
        tanggal.month,
        tanggal.day
    ))

# ==========================================
# 10. MEMBUAT FACT TRANSACTION
# ==========================================

sql_fact = """
INSERT INTO fact_transaction
(transaction_id, transaction_date, account_sk,
 channel_sk, type_sk, date_sk, amount)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

data_fact = []

for r in df.itertuples(index=False):

    tanggal = r.transaction_date.date()

    data_fact.append((
        r.transaction_id,
        tanggal,
        account_map[r.transaction_id],
        channel_map[r.channel],
        type_map[r.transaction_type],
        int(r.transaction_date.strftime("%Y%m%d")),
        float(r.amount)
    ))

cursor.executemany(sql_fact, data_fact)

# ==========================================
# 11. MEMBUAT RINGKASAN HARIAN
# ==========================================

sql_summary = """
INSERT INTO daily_summary
(transaction_date, transaction_type, channel,
 total_transaction, total_amount)
VALUES (%s, %s, %s, %s, %s)
"""

ringkasan = (
    df.groupby([
        df["transaction_date"].dt.date,
        "transaction_type",
        "channel"
    ])
    .agg(
        total_transaction=("transaction_id", "count"),
        total_amount=("amount", "sum")
    )
    .reset_index()
)

data_summary = []

for r in ringkasan.itertuples(index=False):
    data_summary.append((
        r.transaction_date,
        r.transaction_type,
        r.channel,
        int(r.total_transaction),
        float(r.total_amount)
    ))

cursor.executemany(sql_summary, data_summary)

# ==========================================
# 12. SIMPAN HASIL
# ==========================================

db.commit()

os.makedirs("outputs", exist_ok=True)

ringkasan.to_csv(
    "outputs/daily_summary.csv",
    index=False
)

print("\n========== HASIL ETL ==========")
print("Data mentah       :", len(pd.read_csv(file_csv)))
print("Data setelah bersih:", len(df))
print("Data staging      :", len(data_staging))
print("Data fact         :", len(data_fact))
print("Jumlah ringkasan  :", len(data_summary))
print("File hasil        : outputs/daily_summary.csv")
print("ETL SELESAI!")

cursor.close()
db.close()
