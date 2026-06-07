-- ============================================================
-- 01_create_staging.sql
-- Staging area: raw data lands here first, no constraints,
-- exactly mirrors the scraper CSV columns.
-- Run this once to set up the database and staging schema.
-- ============================================================

-- Create database (skip if already exists)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'EgyptianJobMarket')
    CREATE DATABASE EgyptianJobMarket;
GO

USE EgyptianJobMarket;
GO

-- Staging schema
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
    EXEC('CREATE SCHEMA stg');
GO

-- Drop and recreate staging table (safe to re-run)
DROP TABLE IF EXISTS stg.JobPostings;
GO

CREATE TABLE stg.JobPostings (
    stg_id            INT IDENTITY(1,1)   PRIMARY KEY,

    -- Raw columns exactly as they come from the scraper CSV
    job_title         NVARCHAR(500),
    company_name      NVARCHAR(500),
    location          NVARCHAR(500),
    job_type          NVARCHAR(200),
    experience_level  NVARCHAR(200),
    years_experience  NVARCHAR(100),
    skills            NVARCHAR(2000),      -- pipe-separated: "Power BI | SQL | Python"
    salary_raw        NVARCHAR(200),
    salary_min_egp    NVARCHAR(50),        -- stored as string; cast in ETL
    salary_max_egp    NVARCHAR(50),
    post_date_raw     NVARCHAR(100),       -- "6 days ago", "yesterday"
    job_url           NVARCHAR(1000),
    search_keyword    NVARCHAR(200),
    scraped_at        NVARCHAR(50),        -- "2026-06-07 08:00:00"

    -- ETL control columns
    load_date         DATETIME2           DEFAULT GETDATE(),
    is_processed      BIT                 DEFAULT 0,    -- flipped to 1 after DWH load
    error_message     NVARCHAR(1000)      NULL          -- populated if ETL fails this row
);
GO

-- Index to speed up "give me unprocessed rows" query in SSIS
CREATE INDEX IX_stg_JobPostings_Unprocessed
    ON stg.JobPostings (is_processed, load_date);
GO

PRINT 'Staging schema created successfully.';
GO
