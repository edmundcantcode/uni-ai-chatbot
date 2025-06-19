from database.connect_cassandra import session

def query_students(filters: dict):
    if not session:
        return {"error": "❌ Cassandra session is not active."}

    base_query = "SELECT * FROM students"
    where_clauses = []
    values = []
    fetch_all = False  # for post-filtering scholarship

    # 🔍 Basic filters
    if "id" in filters:
        where_clauses.append("id = %s")
        values.append(int(filters["id"]))

    if "name" in filters:
        where_clauses.append("name = %s")
        values.append(filters["name"])

    if "gender" in filters:
        where_clauses.append("gender = %s")
        if "gender" in filters:
            gender = filters["gender"].strip().lower()
            if gender == "male":
                values.append("Male")
            elif gender == "female":
                values.append("Female")

    if "race" in filters:
        where_clauses.append("race = %s")
        values.append(filters["race"])

    if "country" in filters:
        where_clauses.append("country = %s")
        values.append(filters["country"])

    if "programme" in filters:
        where_clauses.append("programme = %s")
        values.append(filters["programme"])

    if "programmecode" in filters:
        where_clauses.append("programmecode = %s")
        values.append(filters["programmecode"])

    if "awardclassification" in filters:
        where_clauses.append("awardclassification = %s")
        values.append(filters["awardclassification"])

    if "status" in filters:
        where_clauses.append("status = %s")
        values.append(filters["status"])

    if "broadsheetyear" in filters:
        where_clauses.append("broadsheetyear = %s")
        values.append(filters["broadsheetyear"])

    if "cohort" in filters:
        where_clauses.append("cohort = %s")
        values.append(filters["cohort"])

    if "year" in filters:
        where_clauses.append("year = %s")
        values.append(int(filters["year"]))

    if "sem" in filters:
        where_clauses.append("sem = %s")
        values.append(int(filters["sem"]))

    # ✅ Trigger in-memory scholarship filtering
    if "scholarship" in filters:
        fetch_all = True  # ignore filtering by financialaid in query

    # 🔍 Comparison filters
    if "cgpa_condition" in filters:
        where_clauses.append(f"overallcgpa {filters['cgpa_condition']}")

    if "fail_rate_condition" in filters:
        where_clauses.append(f"fail_rate {filters['fail_rate_condition']}")

    if "avg_grade_score_condition" in filters:
        where_clauses.append(f"avg_grade_score {filters['avg_grade_score_condition']}")

    if "num_failed_condition" in filters:
        where_clauses.append(f"num_failed {filters['num_failed_condition']}")

    # 🧠 Compose query
    if where_clauses:
        query = f"{base_query} WHERE " + " AND ".join(where_clauses)
    else:
        query = f"{base_query} LIMIT 100"

    if "id" not in filters:
        query += " ALLOW FILTERING"

    try:
        print("⚙️ Executing query:", query)
        rows = session.execute(query, tuple(values) if values else None)
        result = [dict(row._asdict()) for row in rows]

        # ✅ Post-filter for scholarship
        if fetch_all and "scholarship" in filters:
            keyword = filters["scholarship"].lower()
            result = [
                r for r in result
                if r.get("financialaid") and keyword in r["financialaid"].lower()
            ]

        print("✅ Query executed.")
        return result

    except Exception as e:
        return {
            "error": "❌ Error during query execution.",
            "code": 2200,
            "message": str(e),
            "query": query
        }
