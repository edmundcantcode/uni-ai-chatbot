# backend/logic/query_processor.py
import logging
import re
from typing import Dict, Any, Tuple, Iterable, List

from backend.database.connect_cassandra import (
    get_session as get_cassandra_session,
    initialize_database,
)
from backend.constants.intent_config import (
    QUERY_TYPES,
    BASE_INTENTS,
    build_query,
)
from backend.llm.intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)

# Intents that should default to the logged-in student's id
MY_INTENTS = {
    "get_my_details",
    "get_my_cgpa",
    "get_my_programme",
    "get_my_subjects",
    "get_my_grade_in_subject",
    "did_i_fail_subject",
    "get_my_failed_subjects",
}


class QueryProcessor:
    def __init__(self):
        self.cassandra_session = None

    async def _get_db_session(self):
        if self.cassandra_session is None:
            await initialize_database()
            self.cassandra_session = get_cassandra_session()
        return self.cassandra_session

    async def _classify_query_type(self, user_query: str) -> str:
        classifier = IntentClassifier()
        result = await classifier.classify_query_type(user_query)
        return result if result in QUERY_TYPES else "list"

    async def _classify_intent_and_entities(self, user_query: str) -> Tuple[str, Dict[str, Any]]:
        classifier = IntentClassifier()
        intent_result = await classifier.classify_intent(user_query)

        intent = intent_result.get("intent")
        if not intent or intent not in BASE_INTENTS:
            raise ValueError(f"Unknown or invalid intent: {intent}")

        entities = intent_result.get("entities", {}) or {}

        # Best-effort numeric coercion
        float_keys = {"cgpa_value", "cgpa_min", "cgpa_max", "cavg_value", "attendance_value", "threshold"}
        int_keys = {"student_id", "year", "semester", "limit", "exam_year", "exam_month", "broadsheet_year"}
        for k, v in list(entities.items()):
            try:
                if k in float_keys and v is not None:
                    entities[k] = float(v)
                elif k in int_keys and v is not None:
                    entities[k] = int(v)
            except Exception:
                pass

        return intent, entities

    async def _execute_active_cohort_failed_subject(self, query_type: str, entities: dict) -> dict:
        session = await self._get_db_session()

        # build the subjects query
        id_cql = build_query("get_active_students_by_cohort_failed_subject", "list", dict(entities))
        # IMPORTANT: Cassandra can't do DISTINCT here; drop it and de-dupe in code
        id_cql_nodist = id_cql.replace("SELECT DISTINCT id", "SELECT id", 1)
        logger.info(f"ID query (no DISTINCT): {id_cql_nodist}")

        # run and de-dupe ids
        id_rows = session.execute(id_cql_nodist)
        ids = sorted({getattr(r, "id", None) for r in id_rows if getattr(r, "id", None) is not None})
        logger.info(f"Found {len(ids)} student IDs who failed the subject")

        if not ids:
            return {
                "type": "count" if query_type == "count" else "list",
                "count": 0,
                "data": [] if query_type == "list" else None,
                "query": id_cql_nodist,
            }

        # continue with step 2 as you already do…
        from backend.utils.normalizers import normalize_cohort
        cohort = normalize_cohort(str(entities["cohort"])) or entities["cohort"]

        def chunk(seq, size=200):
            for i in range(0, len(seq), size):
                yield seq[i:i+size]

        data = []
        for c in chunk(ids):
            in_list = ", ".join(str(i) for i in c)
            cql = (
                "SELECT * FROM students "
                f"WHERE status = 'Active' AND cohort = '{cohort}' "
                f"AND id IN ({in_list}) ALLOW FILTERING"
            )
            logger.info(f"Students query chunk: {cql}")
            for row in session.execute(cql):
                data.append({k: v for k, v in row._asdict().items() if v is not None})

        if query_type == "count":
            return {"type": "count", "count": len(data), "query": f"{id_cql_nodist} -- then chunked student fetch"}
        return {"type": "list", "count": len(data), "data": data, "query": f"{id_cql_nodist} -- then chunked student fetch"}

    def _apply_row_level_security(self, cql: str, role: str, userid: str) -> str:
        """
        For role=student, force `id=<userid>` in any query touching students/subjects.
        This clamps overly broad queries to the logged-in student.
        """
        if role != "student":
            return cql

        try:
            sid = int(str(userid).strip())
        except Exception:
            return cql

        q = cql.strip()

        # strip trailing ALLOW FILTERING and LIMIT so we can re-append cleanly
        had_allow = bool(re.search(r"\sALLOW\s+FILTERING\s*;?\s*$", q, flags=re.I))
        q = re.sub(r"\sALLOW\s+FILTERING\s*;?\s*$", "", q, flags=re.I)

        m_limit = re.search(r"\sLIMIT\s+(\d+)\s*;?\s*$", q, flags=re.I)
        limit_clause = ""
        if m_limit:
            limit_clause = m_limit.group(0)
            q = q[: m_limit.start()].rstrip()

        def force_id(sql: str, table: str) -> str:
            m_tbl = re.search(rf"(FROM\s+{table}\s+)", sql, flags=re.I)
            if not m_tbl:
                return sql

            m_where = re.search(rf"(FROM\s+{table}\s+)WHERE\s+", sql, flags=re.I)
            if not m_where:
                # no WHERE -> add WHERE id = sid
                return re.sub(rf"(FROM\s+{table}\s+)", rf"\1WHERE id = {sid} ", sql, count=1, flags=re.I)

            head = sql[: m_where.end()]
            tail = sql[m_where.end() :]

            # end of WHERE (before LIMIT/ALLOW)
            m_end = re.search(r"\s(LIMIT\s+\d+|ALLOW\s+FILTERING)\b", tail, flags=re.I)
            where_body = tail if not m_end else tail[: m_end.start()]
            rest = "" if not m_end else tail[m_end.start() :]

            # replace any id conditions with our sid
            where_body = re.sub(r"\bid\s*=\s*\d+", f"id = {sid}", where_body, flags=re.I)
            where_body = re.sub(r"\bid\s+IN\s*\([^)]+\)", f"id = {sid}", where_body, flags=re.I)

            if not re.search(rf"\bid\s*=\s*{sid}\b", where_body, flags=re.I):
                where_body = f"id = {sid} AND " + where_body.lstrip()

            return head + where_body + rest

        q = force_id(q, "students")
        q = force_id(q, "subjects")

        if limit_clause:
            q += limit_clause
        if had_allow:
            q += " ALLOW FILTERING"
        return q

    async def execute(self, user_query: str, userid: str = "", role: str = "guest") -> Dict[str, Any]:
        """
        Main entry:
        - Classify query type and intent
        - Inject student_id for "my" intents
        - Enforce 403 if a student asks for another student's id
        - Apply RLS for students
        """
        session = await self._get_db_session()

        qtype = await self._classify_query_type(user_query)
        intent, entities = await self._classify_intent_and_entities(user_query)

        # Parse logged-in sid (only matters for students)
        sid = None
        if role == "student":
            try:
                sid = int(str(userid).strip())
            except Exception:
                sid = None

        # Auto-inject student_id for "my" intents
        if role == "student" and intent in MY_INTENTS:
            if "student_id" not in entities or not entities["student_id"]:
                if sid is None:
                    raise ValueError("Missing required entity: student_id")
                entities["student_id"] = sid

        # HARD ERROR if a student asks for someone else's id explicitly
        if role == "student":
            if "student_id" in entities and entities["student_id"] is not None:
                try:
                    asked_id = int(entities["student_id"])
                except Exception:
                    asked_id = None
                if sid is not None and asked_id is not None and asked_id != sid:
                    # handled as 403 by the router
                    raise PermissionError("FORBIDDEN_STUDENT_SCOPE")

        # Special 2-step intent
        if intent == "get_active_students_by_cohort_failed_subject":
            result = await self._execute_active_cohort_failed_subject(qtype, entities)
            if role == "student" and sid is not None:
                if result.get("data") is not None:
                    result["data"] = [r for r in result["data"] if r.get("id") == sid]
                    result["count"] = len(result["data"])
                else:
                    result["count"] = 0 if result.get("count", 0) == 0 else 1
            return result

        # Normal path with RLS (RLS only for students)
        cql = build_query(intent, qtype, entities)
        cql = self._apply_row_level_security(cql, role, userid)
        logger.info(f"CQL: {cql}")

        rows = session.execute(cql)

        if qtype == "count":
            count = 0
            for row in rows:
                count = list(row)[0]
                break
            return {"type": "count", "count": count, "query": cql, "intent": intent, "entities": entities}

        data = []
        for row in rows:
            data.append({k: v for k, v in row._asdict().items() if v is not None})
        return {"type": "list", "count": len(data), "data": data, "query": cql, "intent": intent, "entities": entities}


# Thin wrapper used by the router
async def process_query(query: str, userid: str = "", role: str = "", page: int = 1, page_size: int = 100):
    processor = QueryProcessor()
    return await processor.execute(query, userid=userid, role=role)
