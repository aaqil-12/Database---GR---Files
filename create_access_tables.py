import pyodbc

access_path = r"C:\Users\sswarna\Downloads\UTEP_Database_Projects\tuition_remission.accdb"

conn_str = (
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    fr"DBQ={access_path};"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Drop tables if they exist (Access-compatible)
tables = [
    "Tuition_Remission_Fact",
    "Academic_Enrollment",
    "Employment_Period",
    "Employment",
    "Academic_Program",
    "Student"
]

for t in tables:
    try:
        cursor.execute(f"DROP TABLE {t};")
    except:
        pass   # Table didn't exist, ignore

# ============================
# Create Student table
# ============================
cursor.execute("""
CREATE TABLE Student (
    SPRIDEN_ID TEXT PRIMARY KEY,
    Firstname TEXT,
    Lastname TEXT,
    RESD_CODE TEXT,
    LEVL_CODE TEXT
);
""")

# ============================
# Academic Program table
# ============================
cursor.execute("""
CREATE TABLE Academic_Program (
    MAJR_CODE TEXT PRIMARY KEY,
    MAJR_DESC TEXT,
    COLL_DESC TEXT
);
""")

# ============================
# Employment table
# ============================
cursor.execute("""
CREATE TABLE Employment (
    Employment_ID AUTOINCREMENT PRIMARY KEY,
    SPRIDEN_ID TEXT,
    EmplID TEXT,
    JobCode TEXT,
    Title TEXT,
    Percent_Time_Attribute TEXT,
    CostCenter_Project TEXT,
    BREAK_IN_APPT TEXT
);
""")

# ============================
# Employment_Period
# ============================
cursor.execute("""
CREATE TABLE Employment_Period (
    Employment_Period_ID AUTOINCREMENT PRIMARY KEY,
    Employment_ID LONG,
    MinStart_Date DATE,
    MaxEnd_Date DATE
);
""")

# ============================
# Academic Enrollment
# ============================
cursor.execute("""
CREATE TABLE Academic_Enrollment (
    Enrollment_ID AUTOINCREMENT PRIMARY KEY,
    ENROLLED_IND TEXT,
    Total_Enrolled_hours LONG,
    OVERALL_LGPA_GPA_FIX DOUBLE,
    Graduation_Application_Y_N TEXT,
    EnrolledCourse_1 TEXT,
    EnrolledCourse_2 TEXT,
    EnrolledCourse_3 TEXT,
    EnrolledCourse_4 TEXT,
    EnrolledCourse_5 TEXT,
    EnrolledCourse_6 TEXT
);
""")

# ============================
# Tuition Remission Fact
# ============================
cursor.execute("""
CREATE TABLE Tuition_Remission_Fact (
    Record_ID AUTOINCREMENT PRIMARY KEY,
    SPRIDEN_ID TEXT,
    MAJR_CODE TEXT,
    Employment_Period_ID LONG,
    Enrollment_ID LONG
);
""")

conn.commit()
cursor.close()
conn.close()

print("All Access tables created successfully!")
