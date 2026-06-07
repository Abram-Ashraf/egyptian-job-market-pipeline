-- ============================================================
-- 03_create_fact.sql
-- Fact table + bridge table for the skill many-to-many.
-- Run after 02_create_dimensions.sql.
-- ============================================================

USE EgyptianJobMarket;
GO

-- ── FactJobPosting ───────────────────────────────────────────
DROP TABLE IF EXISTS dwh.FactJobPosting;
GO

CREATE TABLE dwh.FactJobPosting (
    posting_key         INT IDENTITY(1,1)   PRIMARY KEY,

    -- Foreign keys to dimensions
    date_key            INT                 NOT NULL,
    company_key         INT                 NOT NULL,
    location_key        INT                 NOT NULL,
    category_key        INT                 NOT NULL,

    -- Degenerate dimensions (low cardinality, not worth a separate dim)
    search_keyword      NVARCHAR(200)       NULL,
    job_url             NVARCHAR(1000)      NULL,

    -- Measures
    salary_min_egp      INT                 NULL,
    salary_max_egp      INT                 NULL,
    salary_avg_egp      AS (               -- computed column — free in queries
        CASE
            WHEN salary_min_egp IS NOT NULL AND salary_max_egp IS NOT NULL
            THEN (salary_min_egp + salary_max_egp) / 2
        END
    ) PERSISTED,

    -- Audit
    scraped_at          DATETIME2           NULL,
    stg_id              INT                 NULL,   -- traceability back to staging

    -- Constraints
    CONSTRAINT FK_Fact_Date     FOREIGN KEY (date_key)     REFERENCES dwh.DimDate(date_key),
    CONSTRAINT FK_Fact_Company  FOREIGN KEY (company_key)  REFERENCES dwh.DimCompany(company_key),
    CONSTRAINT FK_Fact_Location FOREIGN KEY (location_key) REFERENCES dwh.DimLocation(location_key),
    CONSTRAINT FK_Fact_Category FOREIGN KEY (category_key) REFERENCES dwh.DimJobCategory(category_key)
);
GO

-- ── BridgeJobSkill ───────────────────────────────────────────
-- Resolves the many-to-many between job postings and skills
DROP TABLE IF EXISTS dwh.BridgeJobSkill;
GO

CREATE TABLE dwh.BridgeJobSkill (
    posting_key     INT     NOT NULL,
    skill_key       INT     NOT NULL,
    PRIMARY KEY (posting_key, skill_key),
    CONSTRAINT FK_Bridge_Posting FOREIGN KEY (posting_key) REFERENCES dwh.FactJobPosting(posting_key),
    CONSTRAINT FK_Bridge_Skill   FOREIGN KEY (skill_key)   REFERENCES dwh.DimSkill(skill_key)
);
GO

PRINT 'Fact and bridge tables created successfully.';
GO
