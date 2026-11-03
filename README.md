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

## Proses ETL & ELT

### 1. Pendekatan ETL (`etl.py`)
1. Extract: Membaca dataset CSV mentah.
2. Transform: Membersihkan data dan mengolah SCD Type 2 di memori Python (Pandas).
3. Load: Memasukkan data bersih ke MySQL.

### 2. Pendekatan ELT (`elt.py`)
1. Extract & Load: Membaca CSV mentah dan langsung memuatnya utuh ke tabel staging (`stg_bank`).
2. Transform: Pembersihan data, SCD Type 2, serta pembentukan tabel dimensi/fakta dilakukan langsung di dalam database MySQL (*In-Database SQL*).

### Perbandingan ETL vs ELT

| Fitur / Parameter | ETL (`etl.py`) | ELT (`elt.py`) |
| :--- | :--- | :--- |
| **Lokasi Transformasi** | Memori Python (Pandas) | Database Engine (MySQL) |
| **Karakteristik Load** | Data dibersihkan dulu, baru di-insert ke DB | Data mentah dimuat ke `stg_bank` dulu |
| **Keunggulan Utama** | Fleksibilitas data manipulation di Python | Memanfaatkan efisiensi indeks & query engine DB |
| **Penggunaan Resource** | Memakan memori RAM pada Application Server | Memakan beban komputasi pada Database Server |

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

| Metode | Waktu (detik) | Peningkatan (%) |
|---|---:|---:|
| Full Table Scan | 0.005492 | 0.00% |
| Indexing | 0.006043 | -10.04% |
| Partitioning | 0.005371 | 2.19% |
| Daily Summary | 0.002009 | **63.41%** |

## Cara Menjalankan
1. Jalankan MySQL XAMPP.
2. Import database.sql melalui phpMyAdmin.
3. Install library:

pip install -r requirements.txt

4. Menjalankan versi ETL (Pandas-centric)
python etl.py

5. Menjalankan versi ELT (In-Database Transformation)
python elt.py

6. Menjalankan Benchmark OLAP
python benchmark.py