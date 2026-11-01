
import time
import os
import pandas as pd
import mysql.connector
import matplotlib.pyplot as plt
from statistics import median

# Koneksi database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="etl_bank"
)

cursor = db.cursor()

os.makedirs("outputs", exist_ok=True)

# Membuat tabel pembanding tanpa partition
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

# Menentukan rentang tanggal
cursor.execute("""
SELECT MIN(transaction_date), MAX(transaction_date)
FROM fact_transaction
""")

start, finish = cursor.fetchone()

if start is None:
    raise ValueError("Tabel fact_transaction masih kosong!")

end = finish + pd.Timedelta(days=1)

# Query pengujian
queries = {
    "Full Table Scan": """
        SELECT transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_unpartitioned IGNORE INDEX(idx_date_unpartitioned)
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Indexing": """
        SELECT transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_unpartitioned FORCE INDEX(idx_date_unpartitioned)
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Partitioning": """
        SELECT transaction_date,
               COUNT(*) AS total_transaksi,
               SUM(amount) AS total_nominal
        FROM fact_transaction
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """,

    "Daily Summary": """
        SELECT transaction_date,
               SUM(total_transaction),
               SUM(total_amount)
        FROM daily_summary
        WHERE transaction_date >= %s
          AND transaction_date < %s
        GROUP BY transaction_date
    """
}

hasil = []

print("\n========== BENCHMARK OLAP ==========")

for nama, query in queries.items():

    waktu = []

    # Pemanasan query
    cursor.execute(query, (start, end))
    cursor.fetchall()

    # Pengujian 7 kali
    for i in range(7):
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

# Membuat DataFrame hasil
df_hasil = pd.DataFrame(hasil)

# Persentase peningkatan
baseline = df_hasil.loc[
    df_hasil["Metode"] == "Full Table Scan",
    "Waktu (detik)"
].iloc[0]

df_hasil["Peningkatan (%)"] = (
    (baseline - df_hasil["Waktu (detik)"]) / baseline
) * 100 if baseline > 0 else 0

# Simpan CSV
df_hasil.to_csv(
    "outputs/benchmark_results.csv",
    index=False
)

# Grafik
plt.figure(figsize=(10, 6))

plt.bar(
    df_hasil["Metode"],
    df_hasil["Waktu (detik)"]
)

plt.title("Perbandingan Performa OLAP")
plt.xlabel("Metode")
plt.ylabel("Waktu Eksekusi (detik)")
plt.xticks(rotation=15)
plt.tight_layout()

plt.savefig("outputs/benchmark_olap.png")
plt.close()

print("\n========== HASIL AKHIR ==========")
print(df_hasil.to_string(index=False))
print("\nFile hasil tersimpan di folder outputs!")

cursor.close()
db.close()
