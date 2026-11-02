
# ETL/ELT Pipeline Transaksi Bank

## Deskripsi
Project ini merupakan implementasi ETL Pipeline
menggunakan dataset transaksi bank berformat CSV,
Python, Pandas,dan MySQL. 

## Dataset
Nama: Bank Transaction Dataset for Fraud Detection

Sumber:
https://github.com/burra-ai-labs/Bank-Transaction-Dataset-for-Fraud-Detection

Jumlah data: 2.512 transaksi.

## Teknologi
- Python
- Pandas
- MySQL
- XAMPP
- VS Code
- Matplotlib

## Proses ETL
1. Extract: Membaca dataset CSV.
2. Transform: Membersihkan data.
3. Load: Memasukkan data ke MySQL.

## Star Schema
Tabel fakta:
- fact_transaction

Tabel dimensi:
- dim_account
- dim_channel
- dim_type
- dim_date

SCD Type 2 diterapkan pada dim_account.

## Optimasi OLAP
- Partitioning berdasarkan tanggal.
- Indexing.
- Daily Summary sebagai manual materialized view.

## Hasil ETL
- Data mentah: 2.512
- Data bersih: 2.512
- Data staging: 2.512
- Data fakta: 2.512
- Ringkasan: 1.044

## Hasil Benchmark

| Metode | Waktu (detik) | Peningkatan |
|---|---:|---:|
| Full Table Scan | 0.006015 | 0% |
| Indexing | 0.005614 | 6.67% |
| Partitioning | 0.006124 | -1.80% |
| Daily Summary | 0.002022 | 66.38% |

## Cara Menjalankan
1. Jalankan MySQL XAMPP.
2. Import database.sql melalui phpMyAdmin.
3. Install library:

pip install -r requirements.txt

4. Jalankan ETL:

python etl.py

5. Jalankan benchmark:

python benchmark.py
