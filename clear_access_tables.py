import pyodbc

ACCESS_PATH = r"C:\Users\sswarna\Downloads\UTEP_Database_Projects\tuition_remission.accdb"

conn_str = (
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    fr"DBQ={ACCESS_PATH};"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Delete in correct dependency order

tables_in_delete_order = [
    "Tuition_Remission_Fact",   # depends on others → delete first
    "Academic_Enrollment",
    "Employment_Period",
    "Employment",
    "Academic_Program",
    "Student"
]

for t in tables_in_delete_order:
    try:
        cursor.execute(f"DELETE FROM {t};")
        print(f"Cleared: {t}")
    except Exception as e:
        print(f"Error clearing {t}: {e}")

conn.commit()
cursor.close()
conn.close()

print("All tables cleared successfully!")
