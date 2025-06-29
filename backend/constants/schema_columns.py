# backend/constants/schema_columns.py

STUDENT_COLUMNS = [
    "id", "programme", "awardclassification", "broadsheetyear", "cavg",
    "cohort", "country", "financialaid", "gender", "graduated", "ic", "name",
    "overallcavg", "overallcgpa", "programmecode", "qualifications", "race",
    "sem", "sponsorname", "status", "subjects", "year", "yearoneaverage", "yearonecgpa"
]

SUBJECT_COLUMNS = [
    "id", "programmecode", "subjectcode", "subjectname", "examyear",
    "exammonth", "status", "attendancepercentage", "courseworkpercentage",
    "exampercentage", "grade", "overallpercentage"
]
