# query_builder.py - Advanced CQL query builder

import re
from typing import Optional, Dict, List
from intent_enums import Intent, ProcessedSlots, QueryContext, QueryResult, AggregationType, SortOrder

class AdvancedQueryBuilder:
    """Comprehensive query builder for all intent types"""
    
    def __init__(self):
        self._init_templates()

    def _init_templates(self):
        """Initialize query templates"""
        
        # Basic query templates
        self.basic_templates = {
            # Student information queries
            Intent.GET_STUDENT_INFO: "SELECT id, name, programme, overallcgpa, status, cohort, country, sponsorname, gender, race FROM students WHERE {conditions}",
            Intent.GET_STUDENT_CGPA: "SELECT id, name, overallcgpa FROM students WHERE {conditions}",
            Intent.GET_STUDENT_GRADES: "SELECT s.id, s.name, sub.subjectname, sub.grade, sub.overallpercentage, sub.exampercentage, sub.courseworkpercentage FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            Intent.GET_STUDENT_SUBJECTS: "SELECT s.id, s.name, sub.subjectname FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            
            # Basic counting and listing
            Intent.COUNT_STUDENTS: "SELECT COUNT(*) FROM students WHERE {conditions}",
            Intent.LIST_STUDENTS: "SELECT id, name, programme, cohort, gender, country FROM students WHERE {conditions}",
            Intent.SHOW_STUDENTS: "SELECT id, name, programme, cohort, gender, country, overallcgpa FROM students WHERE {conditions}",
            
            # Subject and grade queries
            Intent.GET_SUBJECT_RESULTS: "SELECT s.id, s.name, sub.subjectname, sub.grade, sub.overallpercentage FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            Intent.SHOW_GRADES: "SELECT s.id, s.name, sub.subjectname, sub.grade, sub.overallpercentage FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            Intent.CHECK_GRADE: "SELECT s.id, s.name, sub.subjectname, sub.grade FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            
            # Enrollment and status
            Intent.CHECK_ENROLLMENT: "SELECT id, name, status, graduated FROM students WHERE {conditions}",
            Intent.GET_CURRENT_STUDENTS: "SELECT id, name, programme, cohort FROM students WHERE graduated = false AND {conditions}",
            Intent.CHECK_GRADUATION: "SELECT id, name, graduated, graduation_date FROM students WHERE {conditions}",
            Intent.GET_GRADUATED_STUDENTS: "SELECT id, name, programme, cohort, graduation_date FROM students WHERE graduated = true AND {conditions}",
            
            # Financial aid queries
            Intent.GET_FINANCIAL_AID: "SELECT id, name, sponsorname, programme FROM students WHERE sponsorname IS NOT NULL AND sponsorname != '' AND {conditions}",
            Intent.GET_SCHOLARSHIP_STUDENTS: "SELECT id, name, sponsorname, programme, overallcgpa FROM students WHERE sponsorname IS NOT NULL AND sponsorname != '' AND {conditions}",
            Intent.LIST_FINANCIAL_AID: "SELECT id, name, sponsorname FROM students WHERE sponsorname IS NOT NULL AND sponsorname != '' AND {conditions}",
            Intent.COUNT_SCHOLARSHIP_RECIPIENTS: "SELECT COUNT(*) FROM students WHERE sponsorname IS NOT NULL AND sponsorname != '' AND {conditions}",
            
            # Programme queries
            Intent.GET_PROGRAMME_INFO: "SELECT id, name, programme FROM students WHERE {conditions}",
            Intent.LIST_PROGRAMME_STUDENTS: "SELECT id, name, programme, cohort FROM students WHERE {conditions}",
            Intent.COUNT_PROGRAMME_STUDENTS: "SELECT COUNT(*) FROM students WHERE {conditions}",
            
            # Demographic queries
            Intent.COUNT_BY_GENDER: "SELECT gender, COUNT(*) as count FROM students WHERE {conditions} GROUP BY gender",
            Intent.COUNT_BY_RACE: "SELECT race, COUNT(*) as count FROM students WHERE {conditions} GROUP BY race",
            Intent.COUNT_BY_COUNTRY: "SELECT country, COUNT(*) as count FROM students WHERE {conditions} GROUP BY country",
            
            # Cohort queries
            Intent.GET_COHORT_STUDENTS: "SELECT id, name, programme, cohort FROM students WHERE {conditions}",
            Intent.COUNT_COHORT_STUDENTS: "SELECT COUNT(*) FROM students WHERE {conditions}",
            
            # Performance queries
            Intent.GET_TOP_STUDENTS: "SELECT id, name, overallcgpa, programme FROM students WHERE {conditions} ORDER BY overallcgpa DESC",
            Intent.GET_BOTTOM_STUDENTS: "SELECT id, name, overallcgpa, programme FROM students WHERE {conditions} ORDER BY overallcgpa ASC",
            Intent.RANK_STUDENTS: "SELECT id, name, overallcgpa, programme FROM students WHERE {conditions} ORDER BY overallcgpa DESC",
            
            # Yes/No queries
            Intent.DID_PASS: "SELECT s.id, s.name, sub.subjectname, sub.grade FROM students s, subjects sub WHERE s.id = sub.id AND {conditions}",
            Intent.IS_ENROLLED: "SELECT id, name, status, graduated FROM students WHERE {conditions}",
            Intent.HAS_SCHOLARSHIP: "SELECT id, name, sponsorname FROM students WHERE {conditions}",
            Intent.YES_NO_QUESTION: "SELECT * FROM students WHERE {conditions}",
        }
        
        # Complex analysis templates
        self.complex_templates = {
            Intent.COMPARE_PROGRAMMES: "SELECT programme, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY programme",
            Intent.COHORT_ANALYSIS: "SELECT cohort, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY cohort",
            Intent.DEMOGRAPHIC_ANALYSIS: "SELECT {group_field}, COUNT(*) as count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY {group_field}",
            Intent.PERFORMANCE_ANALYSIS: "SELECT programme, AVG(overallcgpa) as avg_cgpa, MAX(overallcgpa) as max_cgpa, MIN(overallcgpa) as min_cgpa FROM students WHERE {conditions} GROUP BY programme",
            Intent.GET_STATISTICS: "SELECT {aggregation_function}({field}) as result FROM students WHERE {conditions}",
            Intent.TEMPORAL_ANALYSIS: "SELECT cohort, COUNT(*) as count FROM students WHERE {conditions} GROUP BY cohort ORDER BY cohort",
            Intent.FILTER_COMPLEX: "SELECT id, name, programme, cohort, gender, country, race, overallcgpa FROM students WHERE {conditions}",
            Intent.MULTI_CRITERIA_SEARCH: "SELECT id, name, programme, cohort, gender, country, race, sponsorname FROM students WHERE {conditions}",
        }

    def generate_query(self, intent: Intent, slots: ProcessedSlots, context: QueryContext) -> Optional[str]:
        """Generate CQL query based on intent and processed slots"""
        
        print(f"DEBUG: Generating query for intent: {intent}")
        
        # Handle ambiguous subjects
        if slots.subject and slots.subject.startswith('AMBIGUOUS:'):
            return None
        
        # Build conditions
        conditions = self._build_conditions(slots, intent, context)
        
        # Get appropriate template
        if intent in self.basic_templates:
            query = self._build_basic_query(intent, slots, conditions)
        elif intent in self.complex_templates:
            query = self._build_complex_query(intent, slots, conditions)
        else:
            print(f"DEBUG: No template found for intent: {intent}")
            return None
        
        # Add modifiers
        query = self._add_query_modifiers(query, slots, intent)
        
        print(f"DEBUG: Generated query: {query}")
        return query

    def _build_basic_query(self, intent: Intent, slots: ProcessedSlots, conditions: str) -> str:
        """Build basic queries"""
        
        template = self.basic_templates[intent]
        query = template.format(conditions=conditions)
        
        return query

    def _build_complex_query(self, intent: Intent, slots: ProcessedSlots, conditions: str) -> str:
        """Build complex analytical queries"""
        
        template = self.complex_templates[intent]
        
        if intent == Intent.DEMOGRAPHIC_ANALYSIS:
            group_field = slots.grouping_fields[0] if slots.grouping_fields else 'gender'
            query = template.format(conditions=conditions, group_field=group_field)
        elif intent == Intent.GET_STATISTICS:
            agg_func = self._get_aggregation_function(slots.aggregation_type)
            field = self._get_aggregation_field(slots)
            query = template.format(
                aggregation_function=agg_func,
                field=field,
                conditions=conditions
            )
        else:
            query = template.format(conditions=conditions)
        
        return query

    def _build_conditions(self, slots: ProcessedSlots, intent: Intent, context: QueryContext) -> str:
        """Build comprehensive WHERE conditions"""
        
        conditions = []
        
        # Access control
        if context.user_role == 'student':
            conditions.append(f"id = '{context.user_id}'")
        elif slots.student_id:
            conditions.append(f"id = '{slots.student_id}'")
        elif slots.student_ids:
            ids_str = "', '".join(slots.student_ids)
            conditions.append(f"id IN ('{ids_str}')")
        
        # Programme conditions
        if slots.programmes:
            programmes_str = "', '".join(slots.programmes)
            conditions.append(f"programme IN ('{programmes_str}')")
        elif slots.programme:
            conditions.append(f"programme = '{slots.programme}'")
        
        # Subject conditions (for joined queries)
        if slots.subjects and self._requires_subject_join(intent):
            subjects_str = "', '".join(slots.subjects)
            conditions.append(f"sub.subjectname IN ('{subjects_str}')")
        elif slots.subject and self._requires_subject_join(intent):
            conditions.append(f"sub.subjectname = '{slots.subject}'")
        
        # Demographic conditions
        if slots.genders:
            genders_str = "', '".join(slots.genders)
            conditions.append(f"gender IN ('{genders_str}')")
        elif slots.gender:
            conditions.append(f"gender = '{slots.gender}'")
        
        if slots.races:
            races_str = "', '".join(slots.races)
            conditions.append(f"race IN ('{races_str}')")
        elif slots.race:
            conditions.append(f"race = '{slots.race}'")
        
        if slots.countries:
            countries_str = "', '".join(slots.countries)
            conditions.append(f"country IN ('{countries_str}')")
        elif slots.country:
            conditions.append(f"country = '{slots.country}'")
        
        # Temporal conditions
        if slots.cohorts:
            cohorts_str = "', '".join(slots.cohorts)
            conditions.append(f"cohort IN ('{cohorts_str}')")
        elif slots.cohort:
            conditions.append(f"cohort = '{slots.cohort}'")
        
        if slots.years:
            year_conditions = []
            for year in slots.years:
                year_conditions.append(f"cohort LIKE '{year}%'")
            conditions.append(f"({' OR '.join(year_conditions)})")
        elif slots.year:
            conditions.append(f"cohort LIKE '{slots.year}%'")
        
        # Performance conditions
        if slots.cgpa_min:
            conditions.append(f"overallcgpa >= {slots.cgpa_min}")
        
        if slots.cgpa_max:
            conditions.append(f"overallcgpa <= {slots.cgpa_max}")
        
        if slots.cgpa_exact:
            conditions.append(f"overallcgpa = {slots.cgpa_exact}")
        
        if slots.percentage_min:
            conditions.append(f"overallpercentage >= {slots.percentage_min}")
        
        if slots.percentage_max:
            conditions.append(f"overallpercentage <= {slots.percentage_max}")
        
        # Grade conditions (for subject queries)
        if slots.grades and self._requires_subject_join(intent):
            grades_str = "', '".join(slots.grades)
            conditions.append(f"sub.grade IN ('{grades_str}')")
        elif slots.grade and self._requires_subject_join(intent):
            conditions.append(f"sub.grade = '{slots.grade}'")
        
        # Status conditions
        if slots.enrollment_status == 'enrolled':
            conditions.append("graduated = false")
        elif slots.enrollment_status == 'graduated':
            conditions.append("graduated = true")
        elif slots.enrollment_status == 'inactive':
            conditions.append("status = 'inactive'")
        
        if slots.only_current:
            conditions.append("graduated = false")
        
        # Financial conditions
        if slots.has_scholarship is True:
            conditions.append("sponsorname IS NOT NULL AND sponsorname != ''")
        elif slots.has_scholarship is False:
            conditions.append("(sponsorname IS NULL OR sponsorname = '')")
        
        if slots.sponsors:
            sponsor_conditions = []
            for sponsor in slots.sponsors:
                sponsor_conditions.append(f"sponsorname LIKE '%{sponsor}%'")
            conditions.append(f"({' OR '.join(sponsor_conditions)})")
        elif slots.sponsor:
            conditions.append(f"sponsorname LIKE '%{slots.sponsor}%'")
        
        # Return final conditions
        if conditions:
            result = " AND ".join(conditions)
        else:
            if context.user_role == 'student':
                result = f"id = '{context.user_id}'"
            else:
                result = "id IS NOT NULL"  # Valid condition that's always true
        
        print(f"DEBUG: Generated conditions: '{result}'")
        return result

    def _add_query_modifiers(self, query: str, slots: ProcessedSlots, intent: Intent) -> str:
        """Add ORDER BY, LIMIT, and other modifiers"""
        
        # Add ORDER BY
        if slots.sorting_field and slots.sorting_order and 'ORDER BY' not in query:
            order_str = 'DESC' if slots.sorting_order == SortOrder.DESC else 'ASC'
            query += f" ORDER BY {slots.sorting_field} {order_str}"
        
        # Add LIMIT
        if slots.limit and 'LIMIT' not in query:
            query += f" LIMIT {slots.limit}"
        elif 'COUNT' not in query and 'LIMIT' not in query:
            # Default limit for non-count queries
            query += " LIMIT 1000"
        
        # Add OFFSET
        if slots.offset:
            query += f" OFFSET {slots.offset}"
        
        # Add ALLOW FILTERING
        query += " ALLOW FILTERING"
        
        return query

    def _requires_subject_join(self, intent: Intent) -> bool:
        """Check if intent requires joining with subjects table"""
        
        subject_intents = [
            Intent.GET_STUDENT_GRADES, Intent.GET_STUDENT_SUBJECTS,
            Intent.GET_SUBJECT_RESULTS, Intent.SHOW_GRADES,
            Intent.CHECK_GRADE, Intent.DID_PASS
        ]
        return intent in subject_intents

    def _get_aggregation_function(self, agg_type: Optional[AggregationType]) -> str:
        """Get SQL aggregation function name"""
        
        if agg_type == AggregationType.COUNT:
            return "COUNT"
        elif agg_type == AggregationType.AVERAGE:
            return "AVG"
        elif agg_type == AggregationType.SUM:
            return "SUM"
        elif agg_type == AggregationType.MAX:
            return "MAX"
        elif agg_type == AggregationType.MIN:
            return "MIN"
        else:
            return "COUNT"

    def _get_aggregation_field(self, slots: ProcessedSlots) -> str:
        """Get field for aggregation"""
        
        if slots.aggregation_type in [AggregationType.AVERAGE, AggregationType.MAX, AggregationType.MIN]:
            return "overallcgpa"
        else:
            return "*"

    def build_search_query(self, search_term: str, context: QueryContext) -> str:
        """Build search query for student search"""
        
        conditions = []
        
        # If it looks like a student ID
        if re.match(r'^[0-9]{7}, search_term):
            conditions.append(f"id = '{search_term}'")
        else:
            # Search by name (basic implementation)
            conditions.append(f"name LIKE '%{search_term}%'")
        
        # Access control
        if context.user_role == 'student':
            conditions.append(f"id = '{context.user_id}'")
        
        condition_str = " AND ".join(conditions)
        query = f"SELECT id, name, programme, cohort FROM students WHERE {condition_str} LIMIT 50 ALLOW FILTERING"
        
        return query

    def build_count_query(self, table: str, conditions: str) -> str:
        """Build simple count query"""
        
        return f"SELECT COUNT(*) FROM {table} WHERE {conditions} ALLOW FILTERING"

    def build_existence_query(self, table: str, conditions: str) -> str:
        """Build query to check if records exist"""
        
        return f"SELECT id FROM {table} WHERE {conditions} LIMIT 1 ALLOW FILTERING"