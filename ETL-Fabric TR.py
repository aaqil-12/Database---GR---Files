"""
ETL script: load tuition_remission flat file into normalized tables
in a Microsoft Fabric SQL Warehouse.

Fixes included:
- Avoids hanging after "Query test passed" by NOT using multi-statement IF EXISTS batches
  (uses UPDATE then INSERT if rowcount == 0)
- Normalizes Excel float/scientific IDs for SPRIDEN_ID / EmplID / MAJR_CODE
- Matches UPDATED schema:
  Student has [Source]
  Employment has CostCenter_Project_1/2/3
  Academic_Enrollment has EnrolledCourses
  Tuition_Remission_Fact uses Load_Timestamp default (not inserted)

Requirements:
    pip install pandas pyodbc openpyxl
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

INPUT_FILE = r"C:\Users\sswarna\Downloads\Cleaned_version_TR_1.xlsx"  # <-- CHANGE THIS
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

    "EnrolledCourse_1": "EnrolledCourse_1",
    "EnrolledCourse_2": "EnrolledCourse_2",
    "EnrolledCourse_3": "EnrolledCourse_3",
    "EnrolledCourse_4": "EnrolledCourse_4",
    "EnrolledCourse_5": "EnrolledCourse_5",
    "EnrolledCourse_6": "EnrolledCourse_6",

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

# Timeout=120 is the command/query timeout for ODBC (seconds)
DB_CONNECTION_STRING = (
    f"Driver={{{DRIVER_NAME}}};"
    f"Server={SERVER_NAME};"
    f"Database={DATABASE_NAME};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Authentication=ActiveDirectoryInteractive;"
    "Connect Timeout=30;"
    "Timeout=120;"
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
    """Convert Excel float/scientific notation IDs to clean strings."""
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

def join_courses(*courses, sep="; "):
    parts = []
    for c in courses:
        c = clean(c)
        if c is None:
            continue
        parts.append(str(c))
    joined = sep.join(parts) if parts else None
    if joined is not None and len(joined) > 255:
        joined = joined[:255]
    return joined

def commit_every(conn, idx, n=1000):
    if (idx + 1) % n == 0:
        conn.commit()
        print(f"✅ committed at row {idx+1}")

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

    # conn = pyodbc.connect(DB_CONNECTION_STRING)
    # cursor = conn.cursor()

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

    # --- Single-statement SQL (NO IF EXISTS batches) ---

    update_student_sql = """
        UPDATE dbo.Student
        SET Firstname = ?, Lastname = ?, RESD_CODE = ?, LEVL_CODE = ?, [Source] = ?
        WHERE SPRIDEN_ID = ?;
    """
    insert_student_sql = """
        INSERT INTO dbo.Student (SPRIDEN_ID, Firstname, [Source], Lastname, RESD_CODE, LEVL_CODE)
        VALUES (?, ?, ?, ?, ?, ?);
    """

    update_program_sql = """
        UPDATE dbo.Academic_Program
        SET MAJR_DESC = ?, COLL_DESC = ?
        WHERE MAJR_CODE = ?;
    """
    insert_program_sql = """
        INSERT INTO dbo.Academic_Program (MAJR_CODE, MAJR_DESC, COLL_DESC)
        VALUES (?, ?, ?);
    """

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

    insert_enrollment_sql = """
        INSERT INTO dbo.Academic_Enrollment
            (ENROLLED_IND, Total_Enrolled_hours, OVERALL_LGPA_GPA_FIX,
             Graduation_Application_Y_N, EnrolledCourses)
        OUTPUT INSERTED.Enrollment_ID
        VALUES (?, ?, ?, ?, ?);
    """

    insert_fact_sql = """
        INSERT INTO dbo.Tuition_Remission_Fact
            (SPRIDEN_ID, MAJR_CODE, Employment_Period_ID, Enrollment_ID)
        VALUES (?, ?, ?, ?);
    """

    loaded = 0
    skipped = 0

    for idx, row in df.iterrows():
        spriden_id = normalize_id(row.get(COLUMN_MAP["SPRIDEN_ID"]))
        emplid     = normalize_id(row.get(COLUMN_MAP["EmplID"]))
        major_code = normalize_id(row.get(COLUMN_MAP["MAJR_CODE"]))

        if not spriden_id or not major_code:
            skipped += 1
            continue

        lastname   = clean(row.get(COLUMN_MAP["Lastname"]))
        firstname  = clean(row.get(COLUMN_MAP["Firstname"]))
        major_desc = clean(row.get(COLUMN_MAP["MAJR_DESC"]))
        coll_desc  = clean(row.get(COLUMN_MAP["COLL_DESC"]))
        resd_code  = clean(row.get(COLUMN_MAP["RESD_CODE"]))
        levl_code  = clean(row.get(COLUMN_MAP["LEVL_CODE"]))

        enrolled_ind = clean(row.get(COLUMN_MAP["ENROLLED_IND"]))
        total_hrs    = clean(row.get(COLUMN_MAP["Total_Enrolled_hours"]))
        gpa          = clean(row.get(COLUMN_MAP["OVERALL_LGPA_GPA_FIX"]))
        grad_app     = clean(row.get(COLUMN_MAP["Graduation_Application_Y_N"]))

        enrolled_courses = join_courses(
            row.get(COLUMN_MAP["EnrolledCourse_1"]),
            row.get(COLUMN_MAP["EnrolledCourse_2"]),
            row.get(COLUMN_MAP["EnrolledCourse_3"]),
            row.get(COLUMN_MAP["EnrolledCourse_4"]),
            row.get(COLUMN_MAP["EnrolledCourse_5"]),
            row.get(COLUMN_MAP["EnrolledCourse_6"]),
        )

        jobcode   = clean(row.get(COLUMN_MAP["JobCode"]))
        title     = clean(row.get(COLUMN_MAP["Title"]))
        pct_time  = clean(row.get(COLUMN_MAP["Percent_Time_Attribute"]))
        min_start = clean(row.get(COLUMN_MAP["MinStart_Date_For_EMPLID"]))
        max_end   = clean(row.get(COLUMN_MAP["Max_END_Date_For_EMPLID"]))
        break_in  = clean(row.get(COLUMN_MAP["BREAK_IN_APPT"]))

        cc1 = clean(row.get(COLUMN_MAP["CostCenter_Project_1"]))
        cc2 = clean(row.get(COLUMN_MAP["CostCenter_Project_2"]))
        cc3 = clean(row.get(COLUMN_MAP["CostCenter_Project_3"]))

        source_val = SOURCE_DEFAULT

        # Student: UPDATE then INSERT
        cursor.execute(update_student_sql, (firstname, lastname, resd_code, levl_code, source_val, spriden_id))
        if cursor.rowcount == 0:
            cursor.execute(insert_student_sql, (spriden_id, firstname, source_val, lastname, resd_code, levl_code))

        # Program: UPDATE then INSERT
        cursor.execute(update_program_sql, (major_desc, coll_desc, major_code))
        if cursor.rowcount == 0:
            cursor.execute(insert_program_sql, (major_code, major_desc, coll_desc))

        # Employment (cached)
        emp_key = (spriden_id, emplid, jobcode, title, pct_time, cc1, cc2, cc3, break_in)
        employment_id = employment_cache.get(emp_key)
        if employment_id is None:
            cursor.execute(insert_employment_sql, (spriden_id, emplid, jobcode, title, pct_time, cc1, cc2, cc3, break_in))
            employment_id = cursor.fetchone()[0]
            employment_cache[emp_key] = employment_id

        # Employment period (cached)
        ep_key = (employment_id, min_start, max_end)
        employment_period_id = employment_period_cache.get(ep_key)
        if employment_period_id is None:
            cursor.execute(insert_employment_period_sql, (employment_id, min_start, max_end))
            employment_period_id = cursor.fetchone()[0]
            employment_period_cache[ep_key] = employment_period_id

        # Enrollment (cached)
        enroll_key = (enrolled_ind, total_hrs, gpa, grad_app, enrolled_courses)
        enrollment_id = enrollment_cache.get(enroll_key)
        if enrollment_id is None:
            cursor.execute(insert_enrollment_sql, (enrolled_ind, total_hrs, gpa, grad_app, enrolled_courses))
            enrollment_id = cursor.fetchone()[0]
            enrollment_cache[enroll_key] = enrollment_id

        # Fact
        cursor.execute(insert_fact_sql, (spriden_id, major_code, employment_period_id, enrollment_id))

        loaded += 1

        # progress print
        if (idx + 1) % 50 == 0:
            print(f"...processed {idx+1} rows (loaded={loaded}, skipped={skipped})")

        commit_every(conn, idx, n=1000)

    conn.commit()
    print(f"✅ Done. Loaded rows: {loaded}, Skipped rows: {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print("DB Error:", e)
    except Exception as ex:
        print("General Error:", ex)
