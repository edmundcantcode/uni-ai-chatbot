# backend/constants/schema_columns.py

# Student table columns - ID IS INT
STUDENT_COLUMNS = [
    "id", "programme", "awardclassification", "broadsheetyear", "cavg",
    "cohort", "country", "financialaid", "gender", "graduated", "ic", "name",
    "overallcavg", "overallcgpa", "programmecode", "qualifications", "race",
    "sem", "sponsorname", "status", "subjects", "year", "yearoneaverage", "yearonecgpa"
]

# Subject table columns - ID IS INT
SUBJECT_COLUMNS = [
    "id", "programmecode", "subjectcode", "subjectname", "examyear",
    "exammonth", "status", "attendancepercentage", "courseworkpercentage",
    "exampercentage", "grade", "overallpercentage"
]

# Column descriptions for better LLM understanding
COLUMN_DESCRIPTIONS = {
    # Student columns
    "id": "Student ID (integer primary key)",
    "name": "Student full name",
    "programme": "Academic programme/degree name",
    "overallcgpa": "Overall Cumulative Grade Point Average",
    "overallcavg": "Overall cumulative average percentage",
    "broadsheetyear": "year they are expected to graduate",
    "cohort": "Student cohort/intake year",
    "status": "Student status (active, graduated, etc.)",
    "country": "Student's country of origin",
    "gender": "Student gender",
    "race": "Student ethnicity/race",
    "awardclassification": "Degree classification (Class I, II, III)",
    
    # Subject columns
    "subjectname": "Name of the academic subject/course",
    "grade": "Letter grade achieved (A, B, C, D, F)",
    "overallpercentage": "Overall percentage score for the subject",
    "courseworkpercentage": "Coursework component percentage",
    "exampercentage": "Examination component percentage",
    "attendancepercentage": "Attendance percentage",
    "examyear": "Year when exam was taken",
    "exammonth": "Month when exam was taken"
}

# Data types for validation - ID IS INT
COLUMN_TYPES = {
    # Student columns - ID IS INT
    "id": int,
    "programme": str,
    "awardclassification": str,
    "broadsheetyear": int,
    "cavg": float,
    "cohort": str,
    "country": str,
    "financialaid": str,
    "gender": str,
    "graduated": bool,
    "ic": int,
    "name": str,
    "overallcavg": float,
    "overallcgpa": float,
    "programmecode": str,
    "qualifications": str,
    "race": str,
    "sem": int,
    "sponsorname": str,
    "status": str,
    "subjects": str,
    "year": int,
    "yearoneaverage": float,
    "yearonecgpa": float,
    
    # Subject columns - ID IS INT
    "subjectcode": str,
    "subjectname": str,
    "examyear": int,
    "exammonth": int,
    "attendancepercentage": float,
    "courseworkpercentage": float,
    "exampercentage": float,
    "grade": str,
    "overallpercentage": float
}