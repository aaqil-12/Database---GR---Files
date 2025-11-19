import pandas as pd
import pyodbc
import datetime

# ===============================================================
# CONFIG
# ===============================================================

ACCESS_PATH = r"C:\Users\sswarna\Downloads\UTEP_Database_Projects\tuition_remission.accdb"
INPUT_FILE = r"C:\Users\sswarna\Downloads\UTEP_Database_Projects\8_9.xlsx"

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
    "CostCenter_Project": "CostCenter/Project",
}

# ===============================================================
# HELPERS
# ===============================================================

def clean(val):
    """Normalize pandas values so Access accepts them."""
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    return val

def to_text(val):
    """Access requires TEXT fields to receive strings."""
    if val is None:
        return None
    return str(val)

def program_exists(cursor, code):
    cursor.execute(
        "SELECT MAJR_CODE FROM Academic_Program WHERE MAJR_CODE = ?",
        (code,)
    )
    return cursor.fetchone() is not None

def student_exists(cursor, sid):
    cursor.execute(
        "SELECT SPRIDEN_ID FROM Student WHERE SPRIDEN_ID = ?",
        (sid,)
    )
    return cursor.fetchone() is not None

def employment_exists(cursor, spriden, emplid, jobcode, title, pct, cost, brk):
    cursor.execute("""
        SELECT Employment_ID FROM Employment
        WHERE SPRIDEN_ID=? AND EmplID=? AND JobCode=? AND Title=?
          AND Percent_Time_Attribute=? AND CostCenter_Project=? AND BREAK_IN_APPT=?
    """, (spriden, emplid, jobcode, title, pct, cost, brk))
    row = cursor.fetchone()
    return row[0] if row else None

def employment_period_exists(cursor, emp_id, min_start, max_end):
    cursor.execute("""
        SELECT Employment_Period_ID FROM Employment_Period
        WHERE Employment_ID=? AND MinStart_Date=? AND MaxEnd_Date=?
    """, (emp_id, min_start, max_end))
    row = cursor.fetchone()
    return row[0] if row else None

def enrollment_exists(cursor, ind, hrs, gpa, grad, c1, c2, c3, c4, c5, c6):
    cursor.execute("""
        SELECT Enrollment_ID FROM Academic_Enrollment
        WHERE ENROLLED_IND=? AND Total_Enrolled_hours=? AND OVERALL_LGPA_GPA_FIX=?
          AND Graduation_Application_Y_N=? AND EnrolledCourse_1=? AND EnrolledCourse_2=?
          AND EnrolledCourse_3=? AND EnrolledCourse_4=? AND EnrolledCourse_5=? AND EnrolledCourse_6=?
    """, (ind, hrs, gpa, grad, c1, c2, c3, c4, c5, c6))
    row = cursor.fetchone()
    return row[0] if row else None

# ===============================================================
# CONNECT TO ACCESS
# ===============================================================

conn_str = (
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    fr"DBQ={ACCESS_PATH};"
)
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("Connected to Access database.")

# ===============================================================
# READ EXCEL
# ===============================================================

df = pd.read_excel(INPUT_FILE)
print("Loaded Excel rows:", len(df))

# ===============================================================
# PREPARE SQL STATEMENTS
# ===============================================================

insert_student_sql = """
INSERT INTO Student (SPRIDEN_ID, Firstname, Lastname, RESD_CODE, LEVL_CODE)
VALUES (?, ?, ?, ?, ?)
"""

insert_program_sql = """
INSERT INTO Academic_Program (MAJR_CODE, MAJR_DESC, COLL_DESC)
VALUES (?, ?, ?)
"""

insert_employment_sql = """
INSERT INTO Employment (
    SPRIDEN_ID, EmplID, JobCode, Title,
    Percent_Time_Attribute, CostCenter_Project, BREAK_IN_APPT
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

insert_employment_period_sql = """
INSERT INTO Employment_Period (Employment_ID, MinStart_Date, MaxEnd_Date)
VALUES (?, ?, ?)
"""

insert_enrollment_sql = """
INSERT INTO Academic_Enrollment (
    ENROLLED_IND, Total_Enrolled_hours, OVERALL_LGPA_GPA_FIX,
    Graduation_Application_Y_N,
    EnrolledCourse_1, EnrolledCourse_2, EnrolledCourse_3,
    EnrolledCourse_4, EnrolledCourse_5, EnrolledCourse_6
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

insert_fact_sql = """
INSERT INTO Tuition_Remission_Fact (
    SPRIDEN_ID, MAJR_CODE, Employment_Period_ID, Enrollment_ID
) VALUES (?, ?, ?, ?)
"""

# ===============================================================
# CACHES TO AVOID DUPLICATES WITHIN THIS RUN
# ===============================================================

employment_cache = {}
employment_period_cache = {}
enrollment_cache = {}

# ===============================================================
# MAIN ETL LOOP
# ===============================================================

for idx, row in df.iterrows():

    spriden_id  = clean(row.get(COLUMN_MAP["SPRIDEN_ID"]))
    emplid      = clean(row.get(COLUMN_MAP["EmplID"]))
    lastname    = clean(row.get(COLUMN_MAP["Lastname"]))
    firstname   = clean(row.get(COLUMN_MAP["Firstname"]))
    major_code  = clean(row.get(COLUMN_MAP["MAJR_CODE"]))
    major_desc  = clean(row.get(COLUMN_MAP["MAJR_DESC"]))
    coll_desc   = clean(row.get(COLUMN_MAP["COLL_DESC"]))
    resd_code   = clean(row.get(COLUMN_MAP["RESD_CODE"]))
    levl_code   = clean(row.get(COLUMN_MAP["LEVL_CODE"]))

    enrolled_ind = clean(row.get(COLUMN_MAP["ENROLLED_IND"]))
    total_hrs = clean(row.get(COLUMN_MAP["Total_Enrolled_hours"]))
    gpa = clean(row.get(COLUMN_MAP["OVERALL_LGPA_GPA_FIX"]))
    grad_app = clean(row.get(COLUMN_MAP["Graduation_Application_Y_N"]))

    enrolled_course_1 = clean(row.get(COLUMN_MAP["EnrolledCourse_1"]))
    enrolled_course_2 = clean(row.get(COLUMN_MAP["EnrolledCourse_2"]))
    enrolled_course_3 = clean(row.get(COLUMN_MAP["EnrolledCourse_3"]))
    enrolled_course_4 = clean(row.get(COLUMN_MAP["EnrolledCourse_4"]))
    enrolled_course_5 = clean(row.get(COLUMN_MAP["EnrolledCourse_5"]))
    enrolled_course_6 = clean(row.get(COLUMN_MAP["EnrolledCourse_6"]))

    jobcode = clean(row.get(COLUMN_MAP["JobCode"]))
    title = clean(row.get(COLUMN_MAP["Title"]))
    pct_time = clean(row.get(COLUMN_MAP["Percent_Time_Attribute"]))
    min_start = clean(row.get(COLUMN_MAP["MinStart_Date_For_EMPLID"]))
    max_end = clean(row.get(COLUMN_MAP["Max_END_Date_For_EMPLID"]))
    break_in = clean(row.get(COLUMN_MAP["BREAK_IN_APPT"]))
    cost_center = clean(row.get(COLUMN_MAP["CostCenter_Project"]))

    # -------------------------
    # STUDENT (avoid duplicate SPRIDEN_ID)
    # -------------------------
    sid_text = to_text(spriden_id) if spriden_id else None
    if sid_text and not student_exists(cursor, sid_text):
        cursor.execute(
            insert_student_sql,
            (sid_text,
             to_text(firstname),
             to_text(lastname),
             to_text(resd_code),
             to_text(levl_code))
        )

    # -------------------------
    # PROGRAM (avoid duplicate MAJR_CODE)
    # -------------------------
    major_text = to_text(major_code) if major_code else None
    if major_text and not program_exists(cursor, major_text):
        cursor.execute(
            insert_program_sql,
            (major_text,
             to_text(major_desc),
             to_text(coll_desc))
        )

    # -------------------------
    # EMPLOYMENT (cache + DB check)
    # -------------------------
    emp_key = (sid_text, to_text(emplid), to_text(jobcode), to_text(title),
               to_text(pct_time), to_text(cost_center), to_text(break_in))
    employment_id = employment_cache.get(emp_key)

    if employment_id is None:
        employment_id = employment_exists(
            cursor,
            emp_key[0], emp_key[1], emp_key[2], emp_key[3],
            emp_key[4], emp_key[5], emp_key[6]
        )

        if employment_id is None:
            cursor.execute(
                insert_employment_sql,
                emp_key  # all already to_text()
            )
            employment_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]

        employment_cache[emp_key] = employment_id

    # -------------------------
    # EMPLOYMENT PERIOD (cache + DB check)
    # -------------------------
    ep_key = (employment_id, min_start, max_end)
    employment_period_id = employment_period_cache.get(ep_key)

    if employment_period_id is None:
        employment_period_id = employment_period_exists(
            cursor,
            employment_id,
            min_start,
            max_end
        )

        if employment_period_id is None:
            cursor.execute(
                insert_employment_period_sql,
                (employment_id,
                 min_start if min_start else None,
                 max_end if max_end else None)
            )
            employment_period_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]

        employment_period_cache[ep_key] = employment_period_id

    # -------------------------
    # ENROLLMENT (cache + DB check)
    # -------------------------
    enroll_key = (
        to_text(enrolled_ind),
        total_hrs,
        gpa,
        to_text(grad_app),
        to_text(enrolled_course_1),
        to_text(enrolled_course_2),
        to_text(enrolled_course_3),
        to_text(enrolled_course_4),
        to_text(enrolled_course_5),
        to_text(enrolled_course_6),
    )

    enrollment_id = enrollment_cache.get(enroll_key)

    if enrollment_id is None:
        enrollment_id = enrollment_exists(
            cursor,
            enroll_key[0], enroll_key[1], enroll_key[2], enroll_key[3],
            enroll_key[4], enroll_key[5], enroll_key[6],
            enroll_key[7], enroll_key[8], enroll_key[9]
        )

        if enrollment_id is None:
            cursor.execute(
                insert_enrollment_sql,
                enroll_key
            )
            enrollment_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]

        enrollment_cache[enroll_key] = enrollment_id

    # -------------------------
    # FACT TABLE (no duplicate check — mode B)
    # -------------------------
    cursor.execute(
        insert_fact_sql,
        (sid_text,
         major_text,
         employment_period_id,
         enrollment_id)
    )

    if (idx + 1) % 500 == 0:
        print(f"Loaded {idx+1} rows...")
        conn.commit()

# final commit
conn.commit()
cursor.close()
conn.close()

print("ALL DATA LOADED INTO ACCESS SUCCESSFULLY!")
