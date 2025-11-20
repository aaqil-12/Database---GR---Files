SELECT
    r.Firstname,
    r.Lastname,
    r.LEVL_CODE,
    t.*,
    k.*,
    u.MinStart_Date,
    u.MaxEnd_Date,
    i.Graduation_Application_Y_N,
    i.OVERALL_LGPA_GPA_FIX,
    i.Total_Enrolled_hours,
    i.EnrolledCourse_1,
    i.EnrolledCourse_2,
    i.EnrolledCourse_3,
    i.EnrolledCourse_4,
    i.EnrolledCourse_5,
    i.EnrolledCourse_6
FROM
    (
        (
            (
                (
                    student AS r
                    INNER JOIN Employment AS t ON r.SPRIDEN_ID = t.SPRIDEN_ID
                )
                INNER JOIN Employment_Period AS u ON t.Employment_ID = u.Employment_ID
            )
            INNER JOIN Tuition_Remission_Fact AS o ON u.Employment_Period_ID = o.Employment_Period_ID
        )
        INNER JOIN Academic_Enrollment AS i ON o.Enrollment_ID = i.Enrollment_ID
    )
    INNER JOIN Academic_Program AS k ON o.MAJR_CODE = k.MAJR_CODE
WHERE
    (
        i.OVERALL_LGPA_GPA_FIX >= 3
        OR i.OVERALL_LGPA_GPA_FIX = 0
    )
    AND t.JobCode IN ('10062', '10064', '10074', '10091')
    AND Val (t.Percent_Time_Attribute) <= 50
    AND u.MinStart_Date = #2025 -09 -01 #
    AND u.MaxEnd_Date >= #2026 -01 -15 #
    AND (
        i.Total_Enrolled_hours = 9
        OR (
            i.Total_Enrolled_hours = 3
            AND (
                i.EnrolledCourse_1 LIKE "*6398*"
                OR i.EnrolledCourse_1 LIKE "*6399*"
                OR i.EnrolledCourse_2 LIKE "*6398*"
                OR i.EnrolledCourse_2 LIKE "*6399*"
                OR i.EnrolledCourse_3 LIKE "*6398*"
                OR i.EnrolledCourse_3 LIKE "*6399*"
                OR i.EnrolledCourse_4 LIKE "*6398*"
                OR i.EnrolledCourse_4 LIKE "*6399*"
                OR i.EnrolledCourse_5 LIKE "*6398*"
                OR i.EnrolledCourse_5 LIKE "*6399*"
                OR i.EnrolledCourse_6 LIKE "*6398*"
                OR i.EnrolledCourse_6 LIKE "*6399*"
            )
        )
    );
