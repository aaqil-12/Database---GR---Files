"""
ETL script: load tuition_remission flat file into normalized MySQL tables.

Requirements:
    pip install pandas mysql-connector-python openpyxl
"""

import pandas as pd
import mysql.connector
from mysql.connector import Error
import datetime

# ============================
# Config
# ============================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Dynamic63+99",
    "database": "tuition_remission",
}

INPUT_FILE = "/Users/aaqilsheriff/Downloads/8_9.xlsx"
FILE_TYPE = "excel"   # use "excel" for xlsx

# Map logical names -> actual Excel column headers
# RIGHT-HAND SIDE must match the Excel headers exactly
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

    # ---- Enrollment-related columns (EXCEL NAMES WITH SPACES) ----
    "ENROLLED_IND": "ENROLLED_IND",
    "Total_Enrolled_hours": "Total Enrolled hours",
    "OVERALL_LGPA_GPA_FIX": "OVERALL_LGPA_GPA FIX",
    "Graduation_Application_Y_N": "Graduation Application Y N",

    # Multiple enrolled course columns
    "EnrolledCourse_1": "EnrolledCourse_1",
    "EnrolledCourse_2": "EnrolledCourse_2",
    "EnrolledCourse_3": "EnrolledCourse_3",
    "EnrolledCourse_4": "EnrolledCourse_4",
    "EnrolledCourse_5": "EnrolledCourse_5",
    "EnrolledCourse_6": "EnrolledCourse_6",

    # ---- Employment-related columns ----
    "JobCode": "JobCode",
    "Title": "Title",
    "Percent_Time_Attribute": "Percent Time Attribute",
    "MinStart_Date_For_EMPLID": "MinStart Date For EMPLID",
    "Max_END_Date_For_EMPLID": "Max END Date For EMPLID",
    "BREAK_IN_APPT": "BREAK IN APPT",
    "CostCenter_Project": "CostCenter/Project",
}


def clean(val):
    """
    Normalize pandas values so MySQL accepts them as expected:
    - NaN -> None (NULL)
    - pandas Timestamp -> date
    """
    if pd.isna(val):
        return None

    # Convert pandas Timestamp (from Excel) to a plain date
    if isinstance(val, pd.Timestamp):
        return val.date()

    # If already a datetime/date, leave as is
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val

    return val


def main():
    # ----------------------------
    # 1. Read the input file
    # ----------------------------
    if FILE_TYPE.lower() == "csv":
        df = pd.read_csv(INPUT_FILE)
    else:
        df = pd.read_excel(INPUT_FILE)

    # Debug once to confirm column names
    print("Columns in file:", df.columns.tolist())
    print(df.head(3))

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Optional: disable FK checks during bulk load
    # cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    employment_cache = {}
    employment_period_cache = {}
    enrollment_cache = {}

    # ----------------------------
    # 3. SQL statements
    # ----------------------------

    insert_student_sql = """
        INSERT INTO Student (SPRIDEN_ID, Firstname, Lastname, RESD_CODE, LEVL_CODE)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            Firstname = VALUES(Firstname),
            Lastname  = VALUES(Lastname),
            RESD_CODE = VALUES(RESD_CODE),
            LEVL_CODE = VALUES(LEVL_CODE);
    """

    insert_program_sql = """
        INSERT INTO Academic_Program (MAJR_CODE, MAJR_DESC, COLL_DESC)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            MAJR_DESC = VALUES(MAJR_DESC),
            COLL_DESC = VALUES(COLL_DESC);
    """

    insert_employment_sql = """
        INSERT INTO Employment
            (SPRIDEN_ID, EmplID, JobCode, Title, Percent_Time_Attribute,
             CostCenter_Project, BREAK_IN_APPT)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    insert_employment_period_sql = """
        INSERT INTO Employment_Period
            (Employment_ID, MinStart_Date, MaxEnd_Date)
        VALUES (%s, %s, %s)
    """

    # ✅ Updated: now inserts 6 EnrolledCourse_* columns
    insert_enrollment_sql = """
        INSERT INTO Academic_Enrollment
            (ENROLLED_IND, Total_Enrolled_hours, OVERALL_LGPA_GPA_FIX,
             Graduation_Application_Y_N,
             EnrolledCourse_1, EnrolledCourse_2, EnrolledCourse_3,
             EnrolledCourse_4, EnrolledCourse_5, EnrolledCourse_6)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insert_fact_sql = """
        INSERT INTO Tuition_Remission_Fact
            (SPRIDEN_ID, MAJR_CODE, Employment_Period_ID, Enrollment_ID)
        VALUES (%s, %s, %s, %s)
    """

    # ----------------------------
    # 4. Iterate rows
    # ----------------------------
    for idx, row in df.iterrows():
        # Use COLUMN_MAP so you only fix names in one place
        spriden_id  = clean(row.get(COLUMN_MAP["SPRIDEN_ID"]))
        emplid      = clean(row.get(COLUMN_MAP["EmplID"]))
        lastname    = clean(row.get(COLUMN_MAP["Lastname"]))
        firstname   = clean(row.get(COLUMN_MAP["Firstname"]))
        major_code  = clean(row.get(COLUMN_MAP["MAJR_CODE"]))
        major_desc  = clean(row.get(COLUMN_MAP["MAJR_DESC"]))
        coll_desc   = clean(row.get(COLUMN_MAP["COLL_DESC"]))
        resd_code   = clean(row.get(COLUMN_MAP["RESD_CODE"]))
        levl_code   = clean(row.get(COLUMN_MAP["LEVL_CODE"]))

        enrolled_ind    = clean(row.get(COLUMN_MAP["ENROLLED_IND"]))
        total_hrs       = clean(row.get(COLUMN_MAP["Total_Enrolled_hours"]))
        gpa             = clean(row.get(COLUMN_MAP["OVERALL_LGPA_GPA_FIX"]))
        grad_app        = clean(row.get(COLUMN_MAP["Graduation_Application_Y_N"]))

        # ✅ New: six course columns
        enrolled_course_1 = clean(row.get(COLUMN_MAP["EnrolledCourse_1"]))
        enrolled_course_2 = clean(row.get(COLUMN_MAP["EnrolledCourse_2"]))
        enrolled_course_3 = clean(row.get(COLUMN_MAP["EnrolledCourse_3"]))
        enrolled_course_4 = clean(row.get(COLUMN_MAP["EnrolledCourse_4"]))
        enrolled_course_5 = clean(row.get(COLUMN_MAP["EnrolledCourse_5"]))
        enrolled_course_6 = clean(row.get(COLUMN_MAP["EnrolledCourse_6"]))

        jobcode     = clean(row.get(COLUMN_MAP["JobCode"]))
        title       = clean(row.get(COLUMN_MAP["Title"]))
        pct_time    = clean(row.get(COLUMN_MAP["Percent_Time_Attribute"]))
        min_start   = clean(row.get(COLUMN_MAP["MinStart_Date_For_EMPLID"]))
        max_end     = clean(row.get(COLUMN_MAP["Max_END_Date_For_EMPLID"]))
        break_in    = clean(row.get(COLUMN_MAP["BREAK_IN_APPT"]))
        cost_center = clean(row.get(COLUMN_MAP["CostCenter_Project"]))

        # ---- 4.1 Student ----
        if spriden_id:
            cursor.execute(
                insert_student_sql,
                (spriden_id, firstname, lastname, resd_code, levl_code)
            )

        # ---- 4.2 Academic_Program ----
        if major_code:
            cursor.execute(
                insert_program_sql,
                (major_code, major_desc, coll_desc)
            )

        # ---- 4.3 Employment ----
        emp_key = (
            spriden_id,
            emplid,
            jobcode,
            title,
            pct_time,
            cost_center,
            break_in,
        )

        employment_id = employment_cache.get(emp_key)
        if employment_id is None:
            cursor.execute(
                insert_employment_sql,
                (spriden_id, emplid, jobcode, title, pct_time, cost_center, break_in)
            )
            employment_id = cursor.lastrowid
            employment_cache[emp_key] = employment_id

        # ---- 4.4 Employment_Period ----
        ep_key = (employment_id, min_start, max_end)
        employment_period_id = employment_period_cache.get(ep_key)

        if employment_period_id is None:
            cursor.execute(
                insert_employment_period_sql,
                (employment_id, min_start, max_end)
            )
            employment_period_id = cursor.lastrowid
            employment_period_cache[ep_key] = employment_period_id

        # ---- 4.5 Academic_Enrollment ----
        enroll_key = (
            enrolled_ind,
            total_hrs,
            gpa,
            grad_app,
            enrolled_course_1,
            enrolled_course_2,
            enrolled_course_3,
            enrolled_course_4,
            enrolled_course_5,
            enrolled_course_6,
        )

        enrollment_id = enrollment_cache.get(enroll_key)
        if enrollment_id is None:
            cursor.execute(
                insert_enrollment_sql,
                (
                    enrolled_ind,
                    total_hrs,
                    gpa,
                    grad_app,
                    enrolled_course_1,
                    enrolled_course_2,
                    enrolled_course_3,
                    enrolled_course_4,
                    enrolled_course_5,
                    enrolled_course_6,
                )
            )
            enrollment_id = cursor.lastrowid
            enrollment_cache[enroll_key] = enrollment_id

        # ---- 4.6 Fact ----
        cursor.execute(
            insert_fact_sql,
            (spriden_id, major_code, employment_period_id, enrollment_id)
        )

        if (idx + 1) % 1000 == 0:
            print(f"Committed {idx+1} rows...")
            conn.commit()

    conn.commit()
    print("All rows loaded successfully.")

    # Optional: re-enable FK checks
    # cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print("MySQL Error:", e)
    except Exception as ex:
        print("General Error:", ex)
