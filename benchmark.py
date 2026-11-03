import time
import os
import pandas as pd
import mysql.connector
import matplotlib.pyplot as plt
from statistics import median

# 1. Koneksi Database
db = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="etl_bank"
)

cursor = db.cursor()

os.makedirs("outputs", exist_ok=True)

# 2. Siapkan Tabel Unpartitioned
cursor.execute("DROP TABLE IF EXISTS fact_unpartitioned")
cursor.execute("""
CREATE TABLE fact_unpartitioned AS
SELECT * FROM fact_transaction
""")
cursor.execute("""
CREATE INDEX idx_date_unpartitioned
ON fact_unpartitioned(transaction_date)
""")
db.commit()

# 3. Ambil Rentang Tanggal
cursor.execute("""
SELECT MIN(transaction_date), MAX(transaction_date)
FROM fact_transaction
""")
start, finish = cursor.fetchone()

if start is None:
    raise ValueError("Tabel fact_transaction masih kosong!")

end = finish + pd.Timedelta(days=1)

# 4. Definisi Query Pengujian
queries = {
    "Full Table Scan": """
        SELECT SQL_NO_CACHE transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_unpartitioned IGNORE INDEX(idx_date_unpartitioned)
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Indexing": """
        SELECT SQL_NO_CACHE transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_unpartitioned FORCE INDEX(idx_date_unpartitioned)
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Partitioning": """
        SELECT SQL_NO_CACHE transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_transaction
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Daily Summary": """
        SELECT SQL_NO_CACHE transaction_date,
               SUM(total_transaction),
               SUM(total_amount)
        FROM daily_summary
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """
}

# 5. Fungsi Warm-up Buffer Global (Beban awal diratakan ke seluruh tabel)
def warm_up_buffer():
    cursor.execute("SELECT COUNT(*), SUM(amount) FROM fact_unpartitioned")
    cursor.fetchall()
    cursor.execute("SELECT COUNT(*), SUM(amount) FROM fact_transaction")
    cursor.fetchall()
    cursor.execute("SELECT COUNT(*), SUM(total_amount) FROM daily_summary")
    cursor.fetchall()

warm_up_buffer()

hasil = []

print("\n========== BENCHMARK OLAP ==========")

for nama, query in queries.items():
    waktu = []

    # Pengujian 10 kali
    for i in range(10):
        awal = time.perf_counter()
        cursor.execute(query, (start, end))
        cursor.fetchall()
        akhir = time.perf_counter()
        
        waktu.append(akhir - awal)

    rata = median(waktu)

    hasil.append({
        "Metode": nama,
        "Waktu (detik)": rata
    })

    print(f"{nama}: {rata:.6f} detik")

# 6. Pemrosesan Hasil
df_hasil = pd.DataFrame(hasil)

baseline = df_hasil.loc[
    df_hasil["Metode"] == "Full Table Scan",
    "Waktu (detik)"
].iloc[0]

df_hasil["Peningkatan (%)"] = (
    (baseline - df_hasil["Waktu (detik)"]) / baseline
) * 100 if baseline > 0 else 0

df_hasil.to_csv("outputs/benchmark_results.csv", index=False)

# 7. Visualisasi Grafik
plt.figure(figsize=(10, 6))
bars = plt.bar(
    df_hasil["Metode"],
    df_hasil["Waktu (detik)"],
    color=['#e74c3c', '#3498db', '#f1c40f', '#2ecc71']
)

plt.title("Perbandingan Performa OLAP Query")
plt.xlabel("Metode")
plt.ylabel("Waktu Eksekusi (detik)")
plt.xticks(rotation=0)

for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.6f}s', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig("outputs/benchmark_olap.png")
plt.close()

print("\n========== HASIL AKHIR ==========")
print(df_hasil.to_string(index=False))
print("\nFile hasil tersimpan di folder outputs!")

cursor.close()
db.close()