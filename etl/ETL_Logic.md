# SSIS ETL Logic — Egyptian Job Market Pipeline

Three packages, run in this order:
1. `LoadStaging.dtsx` — CSV → stg.JobPostings
2. `LoadDimensions.dtsx` — stg → all dimension tables
3. `LoadFact.dtsx` — stg + dims → FactJobPosting + BridgeJobSkill

---

## Package 1 — LoadStaging.dtsx

**Purpose:** Land raw CSV data into staging. No transformation here — just get it in.

### Control Flow
```
[Foreach Loop Container]
    Iterates over all *.csv files in scraper/output/
    └── [Data Flow Task] Load CSV → stg.JobPostings
```

### Data Flow: CSV → Staging

```
[Flat File Source]
    File: current CSV from loop variable
    Format: Delimited, header row, utf-8-sig encoding
    Columns: all 14 scraper columns as DT_WSTR(500)
    │
    ▼
[Derived Column]
    Add: load_date = GETDATE()
    Add: is_processed = (DT_BOOL) FALSE
    Add: error_message = NULL
    │
    ▼
[Lookup — duplicate check]
    JOIN stg.JobPostings ON job_url = job_url AND is_processed = 0
    No match output → new rows only
    Match output → redirect to Ignore (already staged)
    │
    ▼
[OLE DB Destination]
    Table: stg.JobPostings
    FastLoad ON, batch size: 1000
```

### Key settings
- Foreach Loop: `*.csv` in scraper/output/, store full path in variable `User::FilePath`
- After successful load: move processed CSV to `scraper/output/archive/` using File System Task
- On package failure: send email via Send Mail Task (optional)

---

## Package 2 — LoadDimensions.dtsx

**Purpose:** Populate all 5 dimension tables from staging. Run only on unprocessed rows (`is_processed = 0`).

### Control Flow (sequential)
```
[Execute SQL Task] — get unprocessed row count → stop if 0
    │
    ▼
[Data Flow] Load DimCompany
    │
    ▼
[Data Flow] Load DimLocation
    │
    ▼
[Data Flow] Load DimJobCategory
    │
    ▼
[Data Flow] Load DimSkill
    │
    ▼
[Execute SQL Task] — DimDate already populated, nothing to do
```

---

### Data Flow: Load DimCompany

```
[OLE DB Source]
    SELECT DISTINCT company_name
    FROM stg.JobPostings
    WHERE is_processed = 0
      AND company_name IS NOT NULL
      AND company_name <> ''
    │
    ▼
[Lookup — DimCompany]
    JOIN dwh.DimCompany ON company_name = company_name
    No match → new companies only
    Match → ignore (already exists, SCD Type 1 = do nothing)
    │
    ▼
[Derived Column]
    first_seen_date = (DT_DBDATE) GETDATE()
    │
    ▼
[OLE DB Destination] → dwh.DimCompany
```

---

### Data Flow: Load DimLocation

```
[OLE DB Source]
    SELECT DISTINCT location
    FROM stg.JobPostings
    WHERE is_processed = 0
      AND location IS NOT NULL AND location <> ''
    │
    ▼
[Derived Column] — parse location string "Nasr City, Cairo, Egypt"
    location_raw = location
    city         = TRIM(TOKEN(location, ",", 1))   -- "Nasr City"
    governorate  = TRIM(TOKEN(location, ",", 2))   -- "Cairo"
    country      = "Egypt"
    │
    ▼
[Lookup — DimLocation]
    JOIN dwh.DimLocation ON location_raw = location_raw
    No match → insert new
    │
    ▼
[OLE DB Destination] → dwh.DimLocation
```

---

### Data Flow: Load DimJobCategory

```
[OLE DB Source]
    SELECT DISTINCT job_type, experience_level, years_experience
    FROM stg.JobPostings
    WHERE is_processed = 0
    │
    ▼
[Derived Column]
    -- Normalise nulls to empty string for the UNIQUE constraint
    job_type         = ISNULL(job_type, "")
    experience_level = ISNULL(experience_level, "")
    years_experience = ISNULL(years_experience, "")
    │
    ▼
[Lookup — DimJobCategory]
    JOIN on all three columns
    No match → insert
    │
    ▼
[OLE DB Destination] → dwh.DimJobCategory
```

---

### Data Flow: Load DimSkill

Skills arrive pipe-separated: `"Power BI | SQL | Python"`
SSIS can't split strings natively — use a Script Component.

```
[OLE DB Source]
    SELECT stg_id, skills
    FROM stg.JobPostings
    WHERE is_processed = 0
      AND skills IS NOT NULL AND skills <> ''
    │
    ▼
[Script Component — type: Transformation]
    Language: C#
    Input columns: skills (read-only)
    Output columns: skill_name (DT_WSTR 200)

    Script logic:
    ─────────────────────────────────────────
    string[] parts = Row.skills.Split('|');
    foreach (string part in parts)
    {
        string skill = part.Trim().TrimStart('·').Trim();
        if (!string.IsNullOrEmpty(skill))
        {
            Output0Buffer.AddRow();
            Output0Buffer.skillname = skill;
        }
    }
    ─────────────────────────────────────────
    │
    ▼
[Sort] — skill_name ASC (required before aggregate)
    │
    ▼
[Aggregate] — GROUP BY skill_name (deduplicate within batch)
    │
    ▼
[Lookup — DimSkill]
    JOIN dwh.DimSkill ON skill_name = skill_name
    No match → new skills only
    │
    ▼
[Derived Column]
    skill_category = "" -- leave blank, categorise manually later in PBI
    │
    ▼
[OLE DB Destination] → dwh.DimSkill
```

---

## Package 3 — LoadFact.dtsx

**Purpose:** Join staging to all dimension keys and insert into FactJobPosting + BridgeJobSkill.

### Control Flow
```
[Data Flow] Load FactJobPosting
    │
    ▼
[Data Flow] Load BridgeJobSkill
    │
    ▼
[Execute SQL Task] Mark rows as processed
    UPDATE stg.JobPostings SET is_processed = 1 WHERE is_processed = 0
```

---

### Data Flow: Load FactJobPosting

```
[OLE DB Source]
    SELECT
        s.stg_id,
        s.company_name,
        s.location,
        s.job_type,
        s.experience_level,
        s.years_experience,
        s.salary_min_egp,
        s.salary_max_egp,
        s.job_url,
        s.search_keyword,
        s.scraped_at
    FROM stg.JobPostings s
    WHERE s.is_processed = 0
    │
    ▼
[Lookup — DimCompany]  → get company_key
    │
    ▼
[Lookup — DimLocation] → get location_key
    │
    ▼
[Lookup — DimJobCategory] → get category_key
    │
    ▼
[Derived Column]
    -- Convert scraped_at string to date_key integer (YYYYMMDD)
    date_key = (DT_I4)(SUBSTRING(scraped_at,1,4)
               + SUBSTRING(scraped_at,6,2)
               + SUBSTRING(scraped_at,9,2))

    -- Cast salary strings to INT, default 0 if empty
    salary_min = (DT_I4)(salary_min_egp == "" ? "0" : salary_min_egp)
    salary_max = (DT_I4)(salary_max_egp == "" ? "0" : salary_max_egp)
    │
    ▼
[OLE DB Destination] → dwh.FactJobPosting
    Keep stg_id for traceability
```

---

### Data Flow: Load BridgeJobSkill

```
[OLE DB Source]
    -- Get posting_key + raw skills for all rows just inserted
    SELECT f.posting_key, s.skills
    FROM dwh.FactJobPosting f
    JOIN stg.JobPostings s ON f.stg_id = s.stg_id
    WHERE s.is_processed = 0
    │
    ▼
[Script Component] — same skill splitter as DimSkill load
    Output: posting_key, skill_name
    │
    ▼
[Lookup — DimSkill]
    JOIN on skill_name → get skill_key
    No match output → redirect to error log
    │
    ▼
[OLE DB Destination] → dwh.BridgeJobSkill
```

---

## Error Logging

Add this table to catch rows that fail any Lookup:

```sql
USE EgyptianJobMarket;
GO

CREATE TABLE stg.ErrorLog (
    error_id        INT IDENTITY(1,1) PRIMARY KEY,
    package_name    NVARCHAR(200),
    error_message   NVARCHAR(2000),
    raw_data        NVARCHAR(4000),
    logged_at       DATETIME2 DEFAULT GETDATE()
);
```

In every Lookup's **No Match** or **Error** output:
- Add a **Derived Column** to concatenate the failing row's key columns into `raw_data`
- Send to an **OLE DB Destination** → `stg.ErrorLog`

---

## Package Execution Order (SQL Agent Job)

```
Step 1: LoadStaging.dtsx
Step 2: LoadDimensions.dtsx   (only runs if Step 1 succeeds)
Step 3: LoadFact.dtsx          (only runs if Step 2 succeeds)
```

Set up as a **SQL Server Agent Job** scheduled every Sunday at 09:00 
(1 hour after the Python scheduler runs at 08:00).
