"""
ETL script: load tuition_remission flat file into normalized tables
in a Microsoft Fabric SQL Warehouse.

Requested changes:
- Employment, Employment_Period, Tuition_Remission_Fact should accept NULL values,
  including NULL SPRIDEN_ID.
- Do NOT modify the logic for:
  Student, Academic_Program, Academic_Enrollment
  (i.e., do not insert Student with NULL SPRIDEN_ID; do not force placeholders)

Notes:
- Student upsert happens ONLY if spriden_id exists.
- Academic_Program upsert happens ONLY if major_code exists.
- Academic_Enrollment always inserted/cached as before.
- Fact is inserted for EVERY row (spriden_id may be NULL; major_code may be NULL).
- Employment + Employment_Period are inserted for EVERY row (spriden_id may be NULL).
"""

import pandas as pd
import pyodbc
from pyodbc import Error
import datetime
import math
from decimal import Decimal, InvalidOperation

# ============================
# Config
# ============================

INPUT_FILE = r"C:\Users\sswarna\Downloads\Cleaned_version_TR_1.xlsx"   # <-- CHANGE THIS
FILE_TYPE = "excel"  # "excel" or "csv"

COLUMN_MAP = {
    "SPRIDEN_ID": "SPRIDEN_ID",
    "EmplID": "EmplID",
    "Lastname": "Lastname",
    "Firstname": "Firstname",
    "MAJR_CODE": "MAJR_CODE",
    "MAJR_DESC": "MAJR_DESC",
    "COLL_DESC": "COLL_DESC",
    "RESD_CODE": "RESD_CODE",
    "LEVL_CODE": "LEVL_CODE",

    "ENROLLED_IND": "ENROLLED_IND",
    "Total_Enrolled_hours": "Total Enrolled hours",
    "OVERALL_LGPA_GPA_FIX": "OVERALL_LGPA_GPA FIX",
    "Graduation_Application_Y_N": "Graduation Application Y N",

    "EnrolledCourses": "Course5398-5399-6398-6399",

    "JobCode": "JobCode",
    "Title": "Title",
    "Percent_Time_Attribute": "Percent Time Attribute",
    "MinStart_Date_For_EMPLID": "MinStart Date For EMPLID",
    "Max_END_Date_For_EMPLID": "Max END Date For EMPLID",
    "BREAK_IN_APPT": "BREAK IN APPT",

    "CostCenter_Project_1": "CostCenter_Project_1",
    "CostCenter_Project_2": "CostCenter_Project_2",
    "CostCenter_Project_3": "CostCenter_Project_3",
}

SOURCE_DEFAULT = "Tuition Remission Flat File"

# ============================
# Fabric SQL Warehouse connection
# ============================

DRIVER_NAME = "ODBC Driver 18 for SQL Server"
SERVER_NAME = "2iqxzbiwdksehegp2v7t7k45f4-6dkhasazi3xuvaiyy4xgsixela.database.fabric.microsoft.com,1433"
DATABASE_NAME = "sql db-8ca89293-a413-43e1-b350-00b25b78e328"

DB_CONNECTION_STRING = (
    f"Driver={{{DRIVER_NAME}}};"
    f"Server={SERVER_NAME};"
    f"Database={DATABASE_NAME};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Authentication=ActiveDirectoryInteractive;"
    "Connect Timeout=30;"
)

# ============================
# Helpers
# ============================

def clean(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val
    if isinstance(val, str):
        s = val.strip()
        return s if s != "" else None
    return val

def normalize_id(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None

    if isinstance(val, str):
        s = val.strip()
        if s == "" or s.lower() == "nan":
            return None
        s = s.replace(",", "")
        if s.endswith(".0"):
            s = s[:-2]
        if "e+" in s.lower() or "e-" in s.lower():
            try:
                d = Decimal(s)
                s = str(int(d.to_integral_value()))
            except (InvalidOperation, ValueError):
                pass
        return s

    if isinstance(val, int):
        return str(val)

    if isinstance(val, (float, Decimal)):
        try:
            return str(int(round(float(val))))
        except Exception:
            return None

    s = str(val).strip()
    return s if s else None

# ============================
# Main
# ============================

def main():
    if FILE_TYPE.lower() == "csv":
        df = pd.read_csv(INPUT_FILE)
    else:
        df = pd.read_excel(INPUT_FILE)

    print("Columns in file:", df.columns.tolist())
    print(df.head(3))

    conn = pyodbc.connect(DB_CONNECTION_STRING, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("SELECT 1;")
    cursor.fetchone()
    print("✅ Connected to Fabric SQL Warehouse")
    print("✅ Query test passed")
    print("➡️ Starting inserts/updates...")

    employment_cache = {}
    employment_period_cache = {}
    enrollment_cache = {}

    # Student: UPDATE then INSERT (UNCHANGED behavior: only when SPRIDEN_ID exists)
    update_student_sql = """
        UPDATE dbo.Student
        SET Firstname = ?, Lastname = ?, RESD_CODE = ?, LEVL_CODE = ?, [Source] = ?
        WHERE SPRIDEN_ID = ?;
    """
    insert_student_sql = """
        INSERT INTO dbo.Student (SPRIDEN_ID, Firstname, [Source], Lastname, RESD_CODE, LEVL_CODE)
        VALUES (?, ?, ?, ?, ?, ?);
    """

    # Program: UPDATE then INSERT (UNCHANGED: only when MAJR_CODE exists)
    update_program_sql = """
        UPDATE dbo.Academic_Program
        SET MAJR_DESC = ?, COLL_DESC = ?
        WHERE MAJR_CODE = ?;
    """
    insert_program_sql = """
        INSERT INTO dbo.Academic_Program (MAJR_CODE, MAJR_DESC, COLL_DESC)
        VALUES (?, ?, ?);
    """

    # Employment / Period / Enrollment: INSERT and return IDs
    # (CHANGED behavior is in control flow: allow NULL spriden_id)
    insert_employment_sql = """
        INSERT INTO dbo.Employment
            (SPRIDEN_ID, EmplID, JobCode, Title, Percent_Time_Attribute,
             CostCenter_Project_1, CostCenter_Project_2, CostCenter_Project_3,
             BREAK_IN_APPT)
        OUTPUT INSERTED.Employment_ID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    insert_employment_period_sql = """
        INSERT INTO dbo.Employment_Period
            (Employment_ID, MinStart_Date, MaxEnd_Date)
        OUTPUT INSERTED.Employment_Period_ID
        VALUES (?, ?, ?);
    """

    # Academic_Enrollment (UNCHANGED)
    insert_enrollment_sql = """
        INSERT INTO dbo.Academic_Enrollment
            (ENROLLED_IND, Total_Enrolled_hours, OVERALL_LGPA_GPA_FIX,
             Graduation_Application_Y_N, EnrolledCourses)
        OUTPUT INSERTED.Enrollment_ID
        VALUES (?, ?, ?, ?, ?);
    """

    # Fact (CHANGED behavior: always insert, spriden_id may be NULL)
    insert_fact_sql = """
        INSERT INTO dbo.Tuition_Remission_Fact
            (SPRIDEN_ID, MAJR_CODE, Employment_Period_ID, Enrollment_ID)
        VALUES (?, ?, ?, ?);
    """

    processed_rows = 0
    student_upserts = 0
    student_skipped_null_spriden = 0
    program_upserts = 0
    program_skipped_null_major = 0
    fact_inserted = 0

    for idx, row in df.iterrows():
        # IDs
        spriden_id = normalize_id(row.get(COLUMN_MAP["SPRIDEN_ID"]))   # may be None
        emplid     = normalize_id(row.get(COLUMN_MAP["EmplID"]))
        major_code = normalize_id(row.get(COLUMN_MAP["MAJR_CODE"]))    # may be None

        # Student fields
        lastname   = clean(row.get(COLUMN_MAP["Lastname"]))
        firstname  = clean(row.get(COLUMN_MAP["Firstname"]))
        resd_code  = clean(row.get(COLUMN_MAP["RESD_CODE"]))
        levl_code  = clean(row.get(COLUMN_MAP["LEVL_CODE"]))

        # Program fields
        major_desc = clean(row.get(COLUMN_MAP["MAJR_DESC"]))
        coll_desc  = clean(row.get(COLUMN_MAP["COLL_DESC"]))

        # Enrollment fields
        enrolled_ind = clean(row.get(COLUMN_MAP["ENROLLED_IND"]))
        total_hrs    = clean(row.get(COLUMN_MAP["Total_Enrolled_hours"]))
        gpa          = clean(row.get(COLUMN_MAP["OVERALL_LGPA_GPA_FIX"]))
        grad_app     = clean(row.get(COLUMN_MAP["Graduation_Application_Y_N"]))
        enrolled_courses = clean(row.get(COLUMN_MAP["EnrolledCourses"]))

        # Employment fields
        jobcode   = clean(row.get(COLUMN_MAP["JobCode"]))
        title     = clean(row.get(COLUMN_MAP["Title"]))
        pct_time  = clean(row.get(COLUMN_MAP["Percent_Time_Attribute"]))
        min_start = clean(row.get(COLUMN_MAP["MinStart_Date_For_EMPLID"]))
        max_end   = clean(row.get(COLUMN_MAP["Max_END_Date_For_EMPLID"]))
        break_in  = clean(row.get(COLUMN_MAP["BREAK_IN_APPT"]))

        cc1 = clean(row.get(COLUMN_MAP["CostCenter_Project_1"]))
        cc2 = clean(row.get(COLUMN_MAP["CostCenter_Project_2"]))
        cc3 = clean(row.get(COLUMN_MAP["CostCenter_Project_3"]))

        # ---- Student upsert (UNCHANGED RULE: do NOT insert when SPRIDEN_ID is NULL) ----
        if spriden_id:
            cursor.execute(update_student_sql, (firstname, lastname, resd_code, levl_code, SOURCE_DEFAULT, spriden_id))
            if cursor.rowcount == 0:
                cursor.execute(insert_student_sql, (spriden_id, firstname, SOURCE_DEFAULT, lastname, resd_code, levl_code))
            student_upserts += 1
        else:
            student_skipped_null_spriden += 1

        # ---- Program upsert (UNCHANGED RULE: only when MAJR_CODE exists) ----
        if major_code:
            cursor.execute(update_program_sql, (major_desc, coll_desc, major_code))
            if cursor.rowcount == 0:
                cursor.execute(insert_program_sql, (major_code, major_desc, coll_desc))
            program_upserts += 1
        else:
            program_skipped_null_major += 1

        # ---- Employment (CHANGED: allow NULL spriden_id; still insert every row) ----
        # Important: if spriden_id is None, include idx so NULL-rows don't collapse in cache.
        if spriden_id is None:
            emp_key = ("ROW", idx)  # force unique per source row when missing spriden
        else:
            emp_key = (spriden_id, emplid, jobcode, title, pct_time, cc1, cc2, cc3, break_in)

        employment_id = employment_cache.get(emp_key)
        if employment_id is None:
            cursor.execute(
                insert_employment_sql,
                (spriden_id, emplid, jobcode, title, pct_time, cc1, cc2, cc3, break_in)
            )
            employment_id = cursor.fetchone()[0]
            employment_cache[emp_key] = employment_id

        # ---- Employment period (CHANGED: still insert even if dates are NULL) ----
        # Similar cache logic: if everything is NULL-y, include idx to avoid collapsing
        ep_key = (employment_id, min_start, max_end)
        if min_start is None and max_end is None:
            ep_key = ("ROW", idx, employment_id)

        employment_period_id = employment_period_cache.get(ep_key)
        if employment_period_id is None:
            cursor.execute(insert_employment_period_sql, (employment_id, min_start, max_end))
            employment_period_id = cursor.fetchone()[0]
            employment_period_cache[ep_key] = employment_period_id

        # ---- Enrollment (UNCHANGED) ----
        enroll_key = (enrolled_ind, total_hrs, gpa, grad_app, enrolled_courses)
        enrollment_id = enrollment_cache.get(enroll_key)
        if enrollment_id is None:
            cursor.execute(insert_enrollment_sql, (enrolled_ind, total_hrs, gpa, grad_app, enrolled_courses))
            enrollment_id = cursor.fetchone()[0]
            enrollment_cache[enroll_key] = enrollment_id

        # ---- Fact (CHANGED: always insert; spriden_id and major_code may be NULL) ----
        cursor.execute(insert_fact_sql, (spriden_id, major_code, employment_period_id, enrollment_id))
        fact_inserted += 1

        processed_rows += 1

        if (idx + 1) % 200 == 0:
            
            print(
                f"...processed {idx+1} rows | fact_inserted={fact_inserted} | "
                f"student_upserts={student_upserts} (skipped_null_spriden={student_skipped_null_spriden}) | "
                f"program_upserts={program_upserts} (skipped_null_major={program_skipped_null_major})"
            )

    print("✅ Finished.")
    print(f"✅ Total rows processed: {processed_rows}")
    print(f"✅ Fact inserted: {fact_inserted}")
    print(f"ℹ️ Student upserts: {student_upserts}")
    print(f"ℹ️ Student skipped (NULL SPRIDEN_ID): {student_skipped_null_spriden}")
    print(f"ℹ️ Program upserts (non-null major): {program_upserts}")
    print(f"ℹ️ Program skipped (NULL major): {program_skipped_null_major}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print("DB Error:", e)
    except Exception as ex:
        print("General Error:", ex)
