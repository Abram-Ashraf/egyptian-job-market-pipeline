-- ============================================================
-- 04_create_indexes.sql
-- Performance indexes for common Power BI query patterns.
-- Run after 03_create_fact.sql.
-- ============================================================

USE EgyptianJobMarket;
GO

-- Fact table: filter by date (most common slicer in PBI)
CREATE INDEX IX_Fact_DateKey
    ON dwh.FactJobPosting (date_key)
    INCLUDE (company_key, location_key, category_key, salary_avg_egp);
GO

-- Fact table: filter by company
CREATE INDEX IX_Fact_CompanyKey
    ON dwh.FactJobPosting (company_key);
GO

-- Fact table: filter by location
CREATE INDEX IX_Fact_LocationKey
    ON dwh.FactJobPosting (location_key);
GO

-- Bridge: look up all postings for a given skill
CREATE INDEX IX_Bridge_SkillKey
    ON dwh.BridgeJobSkill (skill_key)
    INCLUDE (posting_key);
GO

-- DimSkill: name lookups
CREATE INDEX IX_Skill_Name
    ON dwh.DimSkill (skill_name);
GO

-- DimLocation: city/governorate filters
CREATE INDEX IX_Location_City
    ON dwh.DimLocation (governorate, city);
GO

PRINT 'Indexes created successfully.';
GO
