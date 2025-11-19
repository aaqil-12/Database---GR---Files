-- =========================================================
-- Schema: Tuition Remission / Grad School Normalized Model
-- =========================================================


-- Drop in FK-safe order (if you need to re-run)
DROP TABLE IF EXISTS Tuition_Remission_Fact;
DROP TABLE IF EXISTS Academic_Enrollment;
DROP TABLE IF EXISTS Employment_Period;
DROP TABLE IF EXISTS Employment;
DROP TABLE IF EXISTS Academic_Program;
DROP TABLE IF EXISTS Student;


create database tuition_remission;
-- ============================
-- Core reference tables
-- ============================

CREATE TABLE Student (
    SPRIDEN_ID  VARCHAR(20)  NOT NULL PRIMARY KEY,   -- student identifier
    Firstname   VARCHAR(100) NOT NULL,
    Lastname    VARCHAR(100) NOT NULL,
    RESD_CODE   VARCHAR(20),                         -- residency code
    LEVL_CODE   VARCHAR(20)                          -- level code (UG/GR/etc.)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Academic_Program (
    MAJR_CODE   VARCHAR(20)  NOT NULL PRIMARY KEY,   -- major code
    MAJR_DESC   VARCHAR(255),
    COLL_DESC   VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================
-- Employment normalized
-- ============================

CREATE TABLE Employment (
    Employment_ID          INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    SPRIDEN_ID             VARCHAR(20) NOT NULL,     -- FK -> Student
    EmplID                 VARCHAR(20),              -- HR / personnel id
    JobCode                VARCHAR(50),
    Title                  VARCHAR(255),
    Percent_Time_Attribute VARCHAR(20),              -- e.g., '50%', '0.50'
    CostCenter_Project     VARCHAR(100),
    BREAK_IN_APPT          VARCHAR(20),

    CONSTRAINT fk_employment_student
        FOREIGN KEY (SPRIDEN_ID)
        REFERENCES Student(SPRIDEN_ID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

drop table Employment_Period;

drop table Academic_Enrollment;

SET FOREIGN_KEY_CHECKS = 1;


CREATE TABLE Employment_Period (
    Employment_Period_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Employment_ID        INT NOT NULL,               -- FK -> Employment
    MinStart_Date        DATE,
    MaxEnd_Date          DATE,

    CONSTRAINT fk_employment_period_employment
        FOREIGN KEY (Employment_ID)
        REFERENCES Employment(Employment_ID)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================
-- Academic enrollment snapshot
-- ============================alter

drop table Academic_Enrollment;

drop table Employment_Period;


CREATE TABLE Academic_Enrollment (
    Enrollment_ID              INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ENROLLED_IND               CHAR(10),              -- Y/N
    Total_Enrolled_hours       INT,
    OVERALL_LGPA_GPA_FIX       DECIMAL(5,3),         -- GPA, e.g., 3.750
    Graduation_Application_Y_N CHAR(10),              -- Y/N
    EnrolledCourse_1             VARCHAR(255),
    EnrolledCourse_2             VARCHAR(255),
    EnrolledCourse_3             VARCHAR(255),
    EnrolledCourse_4             VARCHAR(255),
    EnrolledCourse_5            VARCHAR(255),
    EnrolledCourse_6             VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================
-- Append-only fact table
-- ============================

CREATE TABLE Tuition_Remission_Fact (
    Record_ID            INT NOT NULL AUTO_INCREMENT PRIMARY KEY,  -- history id
    SPRIDEN_ID           VARCHAR(20) NOT NULL,                     -- FK -> Student
    MAJR_CODE            VARCHAR(20) NOT NULL,                     -- FK -> Academic_Program
    Employment_Period_ID INT,                                      -- FK -> Employment_Period
    Enrollment_ID        INT,                                      -- FK -> Academic_Enrollment
    Load_Timestamp       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_trf_student
        FOREIGN KEY (SPRIDEN_ID)
        REFERENCES Student(SPRIDEN_ID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_trf_program
        FOREIGN KEY (MAJR_CODE)
        REFERENCES Academic_Program(MAJR_CODE)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_trf_employment_period
        FOREIGN KEY (Employment_Period_ID)
        REFERENCES Employment_Period(Employment_Period_ID)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    CONSTRAINT fk_trf_enrollment
        FOREIGN KEY (Enrollment_ID)
        REFERENCES Academic_Enrollment(Enrollment_ID)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


select * from Academic_Enrollment; #all good 

select * from Academic_Program; #all good

select * from Employment; #all good 

select * from Employment_Period; #all good

select * from Student; #all good

select * from Tuition_Remission_Fact; #all good

SET FOREIGN_KEY_CHECKS = 0;


truncate table Academic_Enrollment;

truncate table Academic_Program;

truncate table Employment;

truncate table Employment_Period;

truncate table Student;

truncate table Tuition_Remission_Fact;



############################

-- basic script 

###########################

-- Eligible for Tuition Remission

select r.Firstname, r.Lastname, r.LEVL_CODE, t.*, k.* ,u.MinStart_Date,u.MaxEnd_Date, i.Graduation_Application_Y_N,
i.OVERALL_LGPA_GPA_FIX,i.Total_Enrolled_hours,i.EnrolledCourse_1,i.EnrolledCourse_2,i.EnrolledCourse_3,i.EnrolledCourse_4,
i.EnrolledCourse_5, i.EnrolledCourse_6
from student r
join Employment t on t.SPRIDEN_ID = r.SPRIDEN_ID
join Employment_Period u on u.Employment_ID = t.Employment_ID
join Tuition_Remission_Fact o on o.Employment_Period_ID = u.Employment_ID
join Academic_Enrollment i on i.Enrollment_ID = o.Enrollment_ID
join Academic_Program k on k.MAJR_CODE = o.MAJR_CODE
where (i.OVERALL_LGPA_GPA_FIX >= 3.0 or i.OVERALL_LGPA_GPA_FIX = 0) 
and t.JobCode in ('10062','10064','10074','10091')
and (t.Percent_Time_Attribute = 50 or t.Percent_Time_Attribute < 50) 
and u.MinStart_Date = '2025-09-01' and u.MaxEnd_Date >= '2026-01-15'
and (i.Total_Enrolled_hours = 9 or ( i.Total_Enrolled_hours = 3 and (
i.EnrolledCourse_1 like '%6398%' or i.EnrolledCourse_1 like '%6399%'
or i.EnrolledCourse_2 like '%6398%' or i.EnrolledCourse_2 LIKE '%6399%'
or i.EnrolledCourse_3 like '%6398%' or i.EnrolledCourse_3 LIKE '%6399%'
or i.EnrolledCourse_4 like '%6398%' or i.EnrolledCourse_4 LIKE '%6399%'
or i.EnrolledCourse_5 like '%6398%' or i.EnrolledCourse_5 LIKE '%6399%'
or i.EnrolledCourse_6 like '%6398%' or i.EnrolledCourse_6 LIKE '%6399%')));


-- Not Eligible for Tuition Remission (With reason)


select r.firstname, r.lastname, r.levl_code, t.*, k.*, u.minstart_date, u.maxend_date, i.graduation_application_y_n,i.overall_lgpa_gpa_fix, 
i.total_enrolled_hours,i.enrolledcourse_1,i.enrolledcourse_2,i.enrolledcourse_3,i.enrolledcourse_4,i.enrolledcourse_5,i.enrolledcourse_6,
concat_ws(', ',
        case 
            when not (i.overall_lgpa_gpa_fix >= 3.0 or i.overall_lgpa_gpa_fix = 0)
            then 'GPA Not eligible' 
        end,
        case 
            when not (t.jobcode in ('10062', '10064', '10074', '10091'))
            then 'jobcode not eligible' 
        end,
        case 
            when not (t.percent_time_attribute = 50 or t.percent_time_attribute < 50)
            then 'percent time > 50 or null' 
        end,
        case 
            when not (u.minstart_date = '2025-09-01')
            then 'min start date not 2025-09-01' 
        end,
        case 
            when not (u.maxend_date >= '2026-01-15')
            then 'max end date before 2026-01-15' 
        end,
        case 
            when not (
                i.total_enrolled_hours = 9
                or (
                    i.total_enrolled_hours = 3
                    and (
                        i.enrolledcourse_1 like '%6398%' or i.enrolledcourse_1 like '%6399%'
                        or i.enrolledcourse_2 like '%6398%' or i.enrolledcourse_2 like '%6399%'
                        or i.enrolledcourse_3 like '%6398%' or i.enrolledcourse_3 like '%6399%'
                        or i.enrolledcourse_4 like '%6398%' or i.enrolledcourse_4 like '%6399%'
                        or i.enrolledcourse_5 like '%6398%' or i.enrolledcourse_5 like '%6399%'
                        or i.enrolledcourse_6 like '%6398%' or i.enrolledcourse_6 like '%6399%')))
            then 'hours/course pattern not satisfied' 
        end,

        case when i.overall_lgpa_gpa_fix is null then 'gpa is null' end,
        case when t.jobcode is null then 'jobcode is null' end,
        case when t.percent_time_attribute is null then 'percent_time_attribute is null' end,
        case when u.minstart_date is null then 'minstart_date is null' end,
        case when u.maxend_date is null then 'maxend_date is null' end,
        case when i.total_enrolled_hours is null then 'total_enrolled_hours is null' end,
        case 
            when (
                i.total_enrolled_hours = 3 and 
                (i.enrolledcourse_1 is null and i.enrolledcourse_2 is null 
                 and i.enrolledcourse_3 is null and i.enrolledcourse_4 is null 
                 and i.enrolledcourse_5 is null and i.enrolledcourse_6 is null)
            )
            then 'no enrolled course values present'
        end
    ) as not_eligible_reason
from student r
join employment t on t.spriden_id = r.spriden_id
join employment_period u on u.employment_id = t.employment_id
join tuition_remission_fact o on o.employment_period_id = u.employment_id
join academic_enrollment i on i.enrollment_id = o.enrollment_id
join academic_program k on k.majr_code = o.majr_code
where 
    not (
        (i.overall_lgpa_gpa_fix >= 3.0 or i.overall_lgpa_gpa_fix = 0) 
        and t.jobcode in ('10062', '10064', '10074', '10091')
        and (t.percent_time_attribute = 50 or t.percent_time_attribute < 50) 
        and u.minstart_date = '2025-09-01' 
        and u.maxend_date >= '2026-01-15'
        and (
            i.total_enrolled_hours = 9 
            or (
                i.total_enrolled_hours = 3 
                and (
                    i.enrolledcourse_1 like '%6398%' or i.enrolledcourse_1 like '%6399%'
                    or i.enrolledcourse_2 like '%6398%' or i.enrolledcourse_2 like '%6399%'
                    or i.enrolledcourse_3 like '%6398%' or i.enrolledcourse_3 like '%6399%'
                    or i.enrolledcourse_4 like '%6398%' or i.enrolledcourse_4 like '%6399%'
                    or i.enrolledcourse_5 like '%6398%' or i.enrolledcourse_5 like '%6399%'
                    or i.enrolledcourse_6 like '%6398%' or i.enrolledcourse_6 like '%6399%'))))
    or (
        (i.overall_lgpa_gpa_fix >= 3.0 or i.overall_lgpa_gpa_fix = 0) 
        and t.jobcode in ('10062', '10064', '10074', '10091')
        and (t.percent_time_attribute = 50 or t.percent_time_attribute < 50) 
        and u.minstart_date = '2025-09-01' 
        and u.maxend_date >= '2026-01-15'
        and (
            i.total_enrolled_hours = 9 
            or (
                i.total_enrolled_hours = 3 
                and (
                    i.enrolledcourse_1 like '%6398%' or i.enrolledcourse_1 like '%6399%'
                    or i.enrolledcourse_2 like '%6398%' or i.enrolledcourse_2 like '%6399%'
                    or i.enrolledcourse_3 like '%6398%' or i.enrolledcourse_3 like '%6399%'
                    or i.enrolledcourse_4 like '%6398%' or i.enrolledcourse_4 like '%6399%'
                    or i.enrolledcourse_5 like '%6398%' or i.enrolledcourse_5 like '%6399%'
                    or i.enrolledcourse_6 like '%6398%' or i.enrolledcourse_6 like '%6399%')))) is null;
                    
                    select * from Employment_Period;
                    
                    select * from Employment;
                    
select r.Firstname, r.Lastname, r.LEVL_CODE, t.*, k.* ,u.MinStart_Date,u.MaxEnd_Date, i.Graduation_Application_Y_N,
i.OVERALL_LGPA_GPA_FIX,i.Total_Enrolled_hours,i.EnrolledCourse_1,i.EnrolledCourse_2,i.EnrolledCourse_3,i.EnrolledCourse_4,
i.EnrolledCourse_5, i.EnrolledCourse_6
from student r 
join Employment t on t.SPRIDEN_ID = r.SPRIDEN_ID
join Employment_Period u on u.Employment_ID = t.Employment_ID
join Tuition_Remission_Fact o on o.Employment_Period_ID = u.Employment_ID
join Academic_Enrollment i on i.Enrollment_ID = o.Enrollment_ID
join Academic_Program k on k.MAJR_CODE = o.MAJR_CODE
where r.SPRIDEN_ID = '80837772';              


