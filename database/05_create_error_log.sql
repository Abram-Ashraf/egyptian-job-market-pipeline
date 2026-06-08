-- ============================================================
-- 05_create_error_log.sql
-- Error logging table — SSIS redirects bad rows here
-- instead of failing the whole package.
-- ============================================================

USE EgyptianJobMarket;
GO

DROP TABLE IF EXISTS stg.ErrorLog;
GO

CREATE TABLE stg.ErrorLog (
    error_id        INT IDENTITY(1,1)   PRIMARY KEY,
    package_name    NVARCHAR(200)       NOT NULL,
    error_message   NVARCHAR(2000)      NULL,
    raw_data        NVARCHAR(4000)      NULL,   -- the failing row serialised as text
    logged_at       DATETIME2           NOT NULL DEFAULT GETDATE()
);
GO

CREATE INDEX IX_ErrorLog_PackageName
    ON stg.ErrorLog (package_name, logged_at DESC);
GO

PRINT 'Error log table created successfully.';
GO
