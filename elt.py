import os
import pandas as pd
import mysql.connector

print("=== MEMULAI PIPELINE ELT (Extract, Load, Transform) ===")

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
# 2. EXTRACT: MEMBACA DATA CSV MENTAH
# ==========================================
file_csv = "data/transaksi_bank.csv"

if not os.path.exists(file_csv):
    raise FileNotFoundError(f"File tidak ditemukan: {file_csv}")

df_raw = pd.read_csv(file_csv)
print("Jumlah data mentah yang diekstrak:", len(df_raw))

# ==========================================
# 3. LOAD: MEMUAT DATA MENTAH LANGSUNG KE TABEL STAGING
# ==========================================
cursor.execute("DROP TABLE IF EXISTS stg_bank")
cursor.execute("""
    CREATE TABLE stg_bank (
        transaction_id VARCHAR(50),
        account_id VARCHAR(50),
        amount DECIMAL(15,2),
        transaction_date VARCHAR(50),
        transaction_type VARCHAR(50),
        channel VARCHAR(50),
        location VARCHAR(50),
        customer_age INT,
        occupation VARCHAR(50)
    )
""")
db.commit()

sql_staging = """
INSERT INTO stg_bank
(transaction_id, account_id, amount, transaction_date, transaction_type, channel, location, customer_age, occupation)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

data_staging = []
for r in df_raw.itertuples(index=False):
    data_staging.append((
        None if pd.isna(r.TransactionID) else str(r.TransactionID),
        None if pd.isna(r.AccountID) else str(r.AccountID),
        None if pd.isna(r.TransactionAmount) else float(r.TransactionAmount),
        None if pd.isna(r.TransactionDate) else str(r.TransactionDate),
        "Unknown" if pd.isna(r.TransactionType) else str(r.TransactionType),
        "Unknown" if pd.isna(r.Channel) else str(r.Channel),
        "Unknown" if pd.isna(r.Location) else str(r.Location),
        None if pd.isna(r.CustomerAge) else int(r.CustomerAge),
        "Unknown" if pd.isna(r.CustomerOccupation) else str(r.CustomerOccupation)
    ))

cursor.executemany(sql_staging, data_staging)
db.commit()
print("Data mentah berhasil dimuat (LOAD) ke tabel staging 'stg_bank'!")

# ==========================================
# 4. TRANSFORM (IN-DATABASE TRANSFORMATION VIA MYSQL)
# ==========================================
print("\n[TRANSFORM] Memproses transformasi dan skema dimensi langsung di dalam MySQL Engine...")

# A. Clear Tabel Target Dimensi & Fakta
tabel_target = ["daily_summary", "fact_transaction", "dim_date", "dim_type", "dim_channel", "dim_account"]
for nama in tabel_target:
    cursor.execute(f"TRUNCATE TABLE {nama}")
db.commit()

# B. Data Cleaning di Staging via SQL Query
cursor.execute("""
    DELETE FROM stg_bank 
    WHERE transaction_id IS NULL 
       OR account_id IS NULL 
       OR amount IS NULL 
       OR transaction_date IS NULL;
""")
db.commit()

# C. Populate Dimensi Channel via SQL
cursor.execute("""
    INSERT INTO dim_channel (channel)
    SELECT DISTINCT channel FROM stg_bank WHERE channel IS NOT NULL;
""")
db.commit()

# D. Populate Dimensi Type via SQL
cursor.execute("""
    INSERT INTO dim_type (transaction_type)
    SELECT DISTINCT transaction_type FROM stg_bank WHERE transaction_type IS NOT NULL;
""")
db.commit()

# E. Populate Dimensi Account (SCD Type 2) via SQL
cursor.execute("""
    INSERT INTO dim_account (account_id, customer_age, occupation, valid_from, valid_to, is_current)
    SELECT 
        account_id, 
        customer_age, 
        occupation, 
        MIN(STR_TO_DATE(transaction_date, '%Y-%m-%d')), 
        NULL, 
        1
    FROM stg_bank
    GROUP BY account_id, customer_age, occupation;
""")
db.commit()

# F. Populate Dimensi Date via SQL
cursor.execute("""
    INSERT INTO dim_date (date_sk, full_date, year_num, month_num, day_num)
    SELECT DISTINCT
        CAST(DATE_FORMAT(STR_TO_DATE(transaction_date, '%Y-%m-%d'), '%Y%m%d') AS UNSIGNED),
        STR_TO_DATE(transaction_date, '%Y-%m-%d'),
        YEAR(STR_TO_DATE(transaction_date, '%Y-%m-%d')),
        MONTH(STR_TO_DATE(transaction_date, '%Y-%m-%d')),
        DAY(STR_TO_DATE(transaction_date, '%Y-%m-%d'))
    FROM stg_bank;
""")
db.commit()

# G. Populate Fact Transaction via SQL JOIN
cursor.execute("""
    INSERT IGNORE INTO fact_transaction 
        (transaction_id, transaction_date, account_sk, channel_sk, type_sk, date_sk, amount)
    SELECT 
        s.transaction_id,
        STR_TO_DATE(s.transaction_date, '%Y-%m-%d'),
        a.account_sk,
        c.channel_sk,
        t.type_sk,
        CAST(DATE_FORMAT(STR_TO_DATE(s.transaction_date, '%Y-%m-%d'), '%Y%m%d') AS UNSIGNED),
        s.amount
    FROM stg_bank s
    JOIN dim_account a ON s.account_id = a.account_id AND a.is_current = 1
    JOIN dim_channel c ON s.channel = c.channel
    JOIN dim_type t ON s.transaction_type = t.transaction_type;
""")
db.commit()

# H. Membuat Agregasi Daily Summary via SQL Group By (Mengambil dari Tabel Fakta & Dimensi)
cursor.execute("""
    INSERT IGNORE INTO daily_summary 
        (transaction_date, transaction_type, channel, total_transaction, total_amount)
    SELECT 
        f.transaction_date,
        t.transaction_type,
        c.channel,
        COUNT(f.transaction_id) AS total_transaction,
        SUM(f.amount) AS total_amount
    FROM fact_transaction f
    JOIN dim_type t ON f.type_sk = t.type_sk
    JOIN dim_channel c ON f.channel_sk = c.channel_sk
    GROUP BY f.transaction_date, t.transaction_type, c.channel;
""")
db.commit()

# ==========================================
# 5. EKSPOR HASIL RINGKASAN
# ==========================================
import warnings

os.makedirs("outputs", exist_ok=True)

# Mematikan UserWarning dari Pandas DBAPI2
with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    df_summary = pd.read_sql("""
        SELECT transaction_date, transaction_type, channel, total_transaction, total_amount 
        FROM daily_summary
        ORDER BY transaction_date ASC
    """, db)

df_summary.to_csv("outputs/daily_summary.csv", index=False)

# Membaca jumlah record akhir untuk pelaporan
cursor.execute("SELECT COUNT(DISTINCT transaction_id) FROM stg_bank WHERE amount IS NOT NULL")
total_clean = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM fact_transaction")
total_fact = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM daily_summary")
total_summary = cursor.fetchone()[0]

print("\n========== HASIL ELT ==========")
print("Data mentah        :", len(df_raw))
print("Data setelah bersih:", total_clean)
print("Data staging       :", len(data_staging))
print("Data fact          :", total_fact)
print("Jumlah ringkasan   :", total_summary)
print("File hasil         : outputs/daily_summary.csv")
print("ELT SELESAI DENGAN SUKSES!")

cursor.close()
db.close()