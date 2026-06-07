-- ============================================================
-- 02_create_dimensions.sql
-- Dimension tables for the star schema.
-- All use surrogate integer PKs (not natural keys) so the
-- fact table stays narrow and joins stay fast.
-- ============================================================

USE EgyptianJobMarket;
GO

-- DWH schema
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dwh')
    EXEC('CREATE SCHEMA dwh');
GO

-- ── DimDate ──────────────────────────────────────────────────
-- Pre-populated calendar table (no joins to getdate() in queries)
DROP TABLE IF EXISTS dwh.DimDate;
GO

CREATE TABLE dwh.DimDate (
    date_key        INT             PRIMARY KEY,   -- YYYYMMDD e.g. 20260607
    full_date       DATE            NOT NULL,
    day_of_week     TINYINT         NOT NULL,      -- 1=Sun … 7=Sat
    day_name        NVARCHAR(20)    NOT NULL,
    day_of_month    TINYINT         NOT NULL,
    day_of_year     SMALLINT        NOT NULL,
    week_of_year    TINYINT         NOT NULL,
    month_num       TINYINT         NOT NULL,
    month_name      NVARCHAR(20)    NOT NULL,
    quarter_num     TINYINT         NOT NULL,
    year_num        SMALLINT        NOT NULL,
    is_weekend      BIT             NOT NULL
);
GO

-- Populate DimDate for 2024–2027 (covers project lifetime)
WITH dates AS (
    SELECT CAST('2024-01-01' AS DATE) AS d
    UNION ALL
    SELECT DATEADD(DAY, 1, d) FROM dates WHERE d < '2027-12-31'
)
INSERT INTO dwh.DimDate
SELECT
    CAST(FORMAT(d, 'yyyyMMdd') AS INT)  AS date_key,
    d                                   AS full_date,
    DATEPART(WEEKDAY, d)                AS day_of_week,
    DATENAME(WEEKDAY, d)                AS day_name,
    DAY(d)                              AS day_of_month,
    DATEPART(DAYOFYEAR, d)              AS day_of_year,
    DATEPART(WEEK, d)                   AS week_of_year,
    MONTH(d)                            AS month_num,
    DATENAME(MONTH, d)                  AS month_name,
    DATEPART(QUARTER, d)                AS quarter_num,
    YEAR(d)                             AS year_num,
    CASE WHEN DATEPART(WEEKDAY, d) IN (1,7) THEN 1 ELSE 0 END AS is_weekend
FROM dates
OPTION (MAXRECURSION 1500);
GO

-- ── DimCompany ───────────────────────────────────────────────
DROP TABLE IF EXISTS dwh.DimCompany;
GO

CREATE TABLE dwh.DimCompany (
    company_key     INT IDENTITY(1,1)   PRIMARY KEY,
    company_name    NVARCHAR(500)       NOT NULL,
    -- SCD Type 1: just overwrite if name changes
    first_seen_date DATE                NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    CONSTRAINT UQ_Company UNIQUE (company_name)
);
GO

-- ── DimLocation ──────────────────────────────────────────────
DROP TABLE IF EXISTS dwh.DimLocation;
GO

CREATE TABLE dwh.DimLocation (
    location_key    INT IDENTITY(1,1)   PRIMARY KEY,
    location_raw    NVARCHAR(500)       NOT NULL,  -- "Nasr City, Cairo, Egypt"
    city            NVARCHAR(200)       NULL,       -- parsed: "Nasr City"
    governorate     NVARCHAR(200)       NULL,       -- parsed: "Cairo"
    country         NVARCHAR(200)       NOT NULL DEFAULT 'Egypt',
    CONSTRAINT UQ_Location UNIQUE (location_raw)
);
GO

-- ── DimJobCategory ───────────────────────────────────────────
DROP TABLE IF EXISTS dwh.DimJobCategory;
GO

CREATE TABLE dwh.DimJobCategory (
    category_key        INT IDENTITY(1,1)   PRIMARY KEY,
    job_type            NVARCHAR(200)       NULL,   -- "Full Time", "Hybrid", etc.
    experience_level    NVARCHAR(200)       NULL,   -- "Entry Level", "Senior", etc.
    years_experience    NVARCHAR(100)       NULL,   -- "0 - 3 Yrs of Exp"
    CONSTRAINT UQ_JobCategory UNIQUE (job_type, experience_level, years_experience)
);
GO

-- ── DimSkill ─────────────────────────────────────────────────
-- One row per unique skill (Power BI, SQL, Python …)
-- Many-to-many with FactJobPosting via bridge table
DROP TABLE IF EXISTS dwh.DimSkill;
GO

CREATE TABLE dwh.DimSkill (
    skill_key       INT IDENTITY(1,1)   PRIMARY KEY,
    skill_name      NVARCHAR(200)       NOT NULL,
    skill_category  NVARCHAR(100)       NULL,   -- "Database", "Visualisation", "Programming" etc.
    CONSTRAINT UQ_Skill UNIQUE (skill_name)
);
GO

PRINT 'Dimension tables created successfully.';
GO
