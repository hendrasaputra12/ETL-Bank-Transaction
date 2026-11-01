
CREATE DATABASE IF NOT EXISTS etl_bank;
USE etl_bank;

-- 1. TABEL STAGING
CREATE TABLE IF NOT EXISTS stg_bank (
    transaction_id VARCHAR(50),
    account_id VARCHAR(50),
    amount DECIMAL(15,2),
    transaction_date DATE,
    transaction_type VARCHAR(30),
    channel VARCHAR(30),
    location VARCHAR(100)
);

-- 2. DIMENSI ACCOUNT (SCD TYPE 2)
CREATE TABLE IF NOT EXISTS dim_account (
    account_sk INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(50),
    customer_age INT,
    occupation VARCHAR(100),
    valid_from DATE,
    valid_to DATE NULL,
    is_current TINYINT(1)
);

-- 3. DIMENSI CHANNEL
CREATE TABLE IF NOT EXISTS dim_channel (
    channel_sk INT AUTO_INCREMENT PRIMARY KEY,
    channel VARCHAR(30) UNIQUE
);

-- 4. DIMENSI TRANSACTION TYPE
CREATE TABLE IF NOT EXISTS dim_type (
    type_sk INT AUTO_INCREMENT PRIMARY KEY,
    transaction_type VARCHAR(30) UNIQUE
);

-- 5. DIMENSI DATE
CREATE TABLE IF NOT EXISTS dim_date (
    date_sk INT PRIMARY KEY,
    full_date DATE,
    year_num INT,
    month_num INT,
    day_num INT
);

-- 6. FACT TRANSACTION
CREATE TABLE IF NOT EXISTS fact_transaction (
    transaction_id VARCHAR(50),
    transaction_date DATE,
    account_sk INT,
    channel_sk INT,
    type_sk INT,
    date_sk INT,
    amount DECIMAL(15,2),

    PRIMARY KEY (transaction_id, transaction_date),
    INDEX idx_date (transaction_date)
)
PARTITION BY RANGE COLUMNS(transaction_date) (
    PARTITION p_before VALUES LESS THAN ('2023-01-01'),
    PARTITION p2023 VALUES LESS THAN ('2024-01-01'),
    PARTITION p2024 VALUES LESS THAN ('2025-01-01'),
    PARTITION p2025 VALUES LESS THAN ('2026-01-01'),
    PARTITION p_future VALUES LESS THAN (MAXVALUE)
);

-- 7. DAILY SUMMARY
CREATE TABLE IF NOT EXISTS daily_summary (
    transaction_date DATE,
    transaction_type VARCHAR(30),
    channel VARCHAR(30),
    total_transaction INT,
    total_amount DECIMAL(18,2),

    PRIMARY KEY (
        transaction_date,
        transaction_type,
        channel
    )
);
