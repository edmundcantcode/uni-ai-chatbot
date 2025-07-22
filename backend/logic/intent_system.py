# Advanced Intent System with Complex Query Handling

import json
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import get_session
import difflib

class Intent(Enum):
    """Extended intents for complex academic database queries"""
    # Basic intents
    COUNT_STUDENTS = "count_students"
    GET_STUDENT_INFO = "get_student_info"
    GET_STUDENT_CGPA = "get_student_cgpa"
    GET_STUDENT_GRADES = "get_student_grades"
    GET_SUBJECT_RESULTS = "get_subject_results"
    LIST_STUDENTS = "list_students"
    
    # Complex analysis intents
    COMPARE_PERFORMANCE = "compare_performance"
    ANALYZE_TRENDS = "analyze_trends"
    GET_STATISTICS = "get_statistics"
    RANK_STUDENTS = "rank_students"
    FILTER_COMPLEX = "filter_complex"
    
    # Academic-specific intents
    CHECK_ENROLLMENT = "check_enrollment"
    GET_FINANCIAL_AID = "get_financial_aid"
    COHORT_ANALYSIS = "cohort_analysis"
    PROGRAMME_COMPARISON = "programme_comparison"
    
    # Yes/no and explanatory
    YES_NO_QUESTION = "yes_no_question"
    EXPLAIN_RESULTS = "explain_results"
    
    UNKNOWN = "unknown"

@dataclass
class IntentResult:
    """Enhanced result of intent classification"""
    intent: Intent
    raw_entities: List[str]
    confidence: float
    is_yes_no: bool = False
    complexity: str = "simple"  # simple, moderate, complex
    requires_aggregation: bool = False
    requires_joins: bool = False

@dataclass
class ProcessedSlots:
    """Comprehensive slots for complex queries"""
    # Basic identifiers
    student_id: Optional[str] = None
    student_ids: List[str] = field(default_factory=list)  # Multiple students
    
    # Academic filters
    programme: Optional[str] = None
    programmes: List[str] = field(default_factory=list)  # Multiple programmes
    subject: Optional[str] = None
    subjects: List[str] = field(default_factory=list)  # Multiple subjects
    
    # Demographic filters
    race: Optional[str] = None
    races: List[str] = field(default_factory=list)
    country: Optional[str] = None
    countries: List[str] = field(default_factory=list)
    gender: Optional[str] = None
    genders: List[str] = field(default_factory=list)
    
    # Time-based filters
    cohort: Optional[str] = None
    cohorts: List[str] = field(default_factory=list)
    year: Optional[str] = None
    years: List[str] = field(default_factory=list)
    semester: Optional[str] = None
    
    # Performance filters
    grade: Optional[str] = None
    grades: List[str] = field(default_factory=list)
    cgpa_min: Optional[float] = None
    cgpa_max: Optional[float] = None
    percentage_min: Optional[float] = None
    percentage_max: Optional[float] = None
    
    # Financial and status
    sponsor: Optional[str] = None
    sponsors: List[str] = field(default_factory=list)
    enrollment_status: Optional[str] = None
    graduation_status: Optional[str] = None
    
    # Complex query parameters
    comparison_type: Optional[str] = None  # "greater_than", "less_than", "between", "average"
    aggregation_type: Optional[str] = None  # "count", "average", "sum", "max", "min"
    grouping_fields: List[str] = field(default_factory=list)  # Fields to group by
    sorting_field: Optional[str] = None
    sorting_order: Optional[str] = None  # "asc", "desc"
    limit: Optional[int] = None
    
    # Temporal analysis
    time_period: Optional[str] = None  # "last_year", "current_semester", etc.
    trend_analysis: bool = False

class AdvancedLLMClassifier:
    """Enhanced LLM classifier for complex queries"""
    
    def __init__(self, llm: LlamaLLM):
        self.llm = llm

    async def classify_intent(self, query: str, userid: str, role: str) -> IntentResult:
        """Enhanced intent classification with complexity detection"""
        
        prompt = self._create_advanced_prompt(query, userid, role)
        
        try:
            llm_response = await self.llm.generate_response(prompt, f"{userid}_intent")
            result = json.loads(llm_response)
            
            intent_str = result.get('intent', 'unknown')
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.UNKNOWN
            
            return IntentResult(
                intent=intent,
                raw_entities=result.get('raw_entities', []),
                confidence=result.get('confidence', 0.5),
                is_yes_no=result.get('is_yes_no', False),
                complexity=result.get('complexity', 'simple'),
                requires_aggregation=result.get('requires_aggregation', False),
                requires_joins=result.get('requires_joins', False)
            )
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"LLM Classification Error: {e}")
            return IntentResult(
                intent=Intent.UNKNOWN,
                raw_entities=[],
                confidence=0.1
            )

    def _create_advanced_prompt(self, query: str, userid: str, role: str) -> str:
        """Advanced prompt for complex query classification"""
        
        prompt = f"""You are an advanced intent classifier for academic database queries. Analyze the complexity and requirements.

USER QUERY: "{query}"
USER ROLE: {role}

AVAILABLE INTENTS:
BASIC:
1. count_students - Simple counting
2. get_student_cgpa - Get CGPA for specific student(s)
3. get_student_grades - Get grades for student(s)
4. get_subject_results - Get results for specific subject(s)
5. get_student_info - Get student information
6. list_students - List students with filters

COMPLEX ANALYSIS:
7. compare_performance - Compare performance between groups/students
8. analyze_trends - Trend analysis over time
9. get_statistics - Statistical analysis (average, median, etc.)
10. rank_students - Ranking/top performers
11. filter_complex - Complex multi-criteria filtering

ACADEMIC:
12. check_enrollment - Enrollment status queries
13. get_financial_aid - Financial aid/scholarship queries
14. cohort_analysis - Cohort-specific analysis
15. programme_comparison - Compare programmes

INTERACTIVE:
16. yes_no_question - Yes/no questions
17. explain_results - Explanatory queries

EXTRACT ALL ENTITIES thoroughly:
- Demographics: male, female, chinese, malay, indian, malaysia, indonesia, iran
- Academic: computer science, IT, programming, operating system, subjects, programmes
- Time: months (january-december), years (2020-2024), cohorts (202201, 202203, etc.)
- Performance: grades (A, B, C, D, F), CGPA ranges, percentages
- Status: enrolled, graduated, active, scholarship recipients
- Numbers: student IDs, limits, ranges
- Comparisons: higher than, lower than, average, best, worst, top, bottom
- Aggregations: count, average, total, maximum, minimum

COMPLEXITY ASSESSMENT:
- Simple: Single condition, basic filtering
- Moderate: Multiple conditions, basic comparisons
- Complex: Aggregations, rankings, trends, multi-table joins

Respond with JSON:
{{
    "intent": "intent_name",
    "confidence": 0.0-1.0,
    "raw_entities": ["extract", "every", "relevant", "term"],
    "is_yes_no": true/false,
    "complexity": "simple/moderate/complex",
    "requires_aggregation": true/false,
    "requires_joins": true/false
}}

EXAMPLES:

Query: "How many female students are there in cohort march 2022?"
Response: {{"intent": "count_students", "confidence": 0.9, "raw_entities": ["female", "students", "cohort", "march", "2022"], "is_yes_no": false, "complexity": "simple", "requires_aggregation": true, "requires_joins": false}}

Query: "Compare average CGPA between Computer Science and IT students"
Response: {{"intent": "compare_performance", "confidence": 0.9, "raw_entities": ["compare", "average", "cgpa", "computer", "science", "it", "students"], "is_yes_no": false, "complexity": "complex", "requires_aggregation": true, "requires_joins": false}}

Query: "Who are the top 10 students with highest CGPA in 2023?"
Response: {{"intent": "rank_students", "confidence": 0.9, "raw_entities": ["top", "10", "students", "highest", "cgpa", "2023"], "is_yes_no": false, "complexity": "complex", "requires_aggregation": true, "requires_joins": false}}

Query: "Show me Chinese students from Malaysia with scholarships"
Response: {{"intent": "filter_complex", "confidence": 0.9, "raw_entities": ["chinese", "students", "malaysia", "scholarships"], "is_yes_no": false, "complexity": "moderate", "requires_aggregation": false, "requires_joins": false}}

Query: "What's the trend of enrollment in Computer Science over the last 3 years?"
Response: {{"intent": "analyze_trends", "confidence": 0.9, "raw_entities": ["trend", "enrollment", "computer", "science", "last", "3", "years"], "is_yes_no": false, "complexity": "complex", "requires_aggregation": true, "requires_joins": false}}

Classify now:"""
        
        return prompt

class AdvancedSlotProcessor:
    """Enhanced slot processor for complex queries"""
    
    def __init__(self, unique_values: Dict[str, List[str]]):
        self.unique_values = unique_values
        
        # Enhanced mappings
        self.programme_aliases = {
            'computer science': 'BSc (Hons) in Computer Science',
            'cs': 'BSc (Hons) in Computer Science',
            'information technology': 'BSc (Hons) Information Technology',
            'it': 'BSc (Hons) Information Technology',
            'software engineering': 'BSc (Hons) Software Engineering',
            'data science': 'BSc (Hons) Data Science',
        }
        
        self.subject_aliases = {
            'programming': ['PrinciplesofEntrepreneurship', 'PrinciplesandPracticeofManagement'],
            'operating': ['OperatingSystemFundamentals'],
            'os': ['OperatingSystemFundamentals'],
            'computer vision': ['ComputerVision'],
            'ai': ['ArtificialIntelligence'],
            'artificial intelligence': ['ArtificialIntelligence'],
            'english': ['EnglishforComputerTechnologyStudies'],
            'communication': ['CommunicationSkills'],
            'networking': ['NetworkingPrinciples'],
            'data': ['DataCommunications'],
            'mathematics': ['ComputerMathematics'],
            'math': ['ComputerMathematics'],
            'database': ['DatabaseSystems'],
            'web': ['WebDevelopment'],
        }
        
        self.country_aliases = {
            'malaysia': 'MALAYSIA',
            'iran': 'IRAN',
            'indonesia': 'INDONESIA',
            'sri lanka': 'SRI LANKA',
            'singapore': 'SINGAPORE',
            'thailand': 'THAILAND',
        }
        
        self.month_mapping = {
            'january': '01', 'jan': '01',
            'february': '02', 'feb': '02',
            'march': '03', 'mar': '03',
            'april': '04', 'apr': '04',
            'may': '05',
            'june': '06', 'jun': '06',
            'july': '07', 'jul': '07',
            'august': '08', 'aug': '08',
            'september': '09', 'sep': '09', 'sept': '09',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12'
        }
        
        self.grade_mapping = {
            'a+': 'A+', 'a': 'A', 'a-': 'A-',
            'b+': 'B+', 'b': 'B', 'b-': 'B-',
            'c+': 'C+', 'c': 'C', 'c-': 'C-',
            'd+': 'D+', 'd': 'D', 'd-': 'D-',
            'f': 'F'
        }

    def process_entities(self, raw_entities: List[str], userid: str, role: str, complexity: str = "simple") -> ProcessedSlots:
        """Enhanced entity processing for complex queries"""
        
        slots = ProcessedSlots()
        entity_text = ' '.join(raw_entities).lower()
        
        print(f"DEBUG: Processing entities: {raw_entities}")
        print(f"DEBUG: Query complexity: {complexity}")
        
        # Basic identity processing
        if role == 'student':
            slots.student_id = userid
        
        # Extract multiple student IDs for complex queries
        slots.student_ids = self._extract_student_ids(raw_entities, role)
        
        # Enhanced demographic extraction
        slots.race = self._extract_race(raw_entities)
        slots.races = self._extract_multiple_races(raw_entities)
        
        slots.country = self._extract_country(raw_entities)
        slots.countries = self._extract_multiple_countries(raw_entities)
        
        slots.gender = self._extract_gender(raw_entities)
        slots.genders = self._extract_multiple_genders(raw_entities)
        
        # Enhanced academic extraction
        slots.programme = self._fuzzy_match_programme(raw_entities)
        slots.programmes = self._extract_multiple_programmes(raw_entities)
        
        slots.subject = self._fuzzy_match_subject(raw_entities)
        slots.subjects = self._extract_multiple_subjects(raw_entities)
        
        # Enhanced temporal extraction
        slots.cohort = self._extract_cohort_enhanced(raw_entities)
        slots.cohorts = self._extract_multiple_cohorts(raw_entities)
        
        slots.year = self._extract_year(raw_entities)
        slots.years = self._extract_multiple_years(raw_entities)
        
        # Performance metrics
        slots.grade = self._extract_grade(raw_entities)
        slots.grades = self._extract_multiple_grades(raw_entities)
        
        slots.cgpa_min, slots.cgpa_max = self._extract_cgpa_range(raw_entities)
        slots.percentage_min, slots.percentage_max = self._extract_percentage_range(raw_entities)
        
        # Financial and status
        slots.sponsor = self._extract_sponsor(raw_entities)
        slots.sponsors = self._extract_multiple_sponsors(raw_entities)
        
        slots.enrollment_status = self._extract_enrollment_status(raw_entities)
        slots.graduation_status = self._extract_graduation_status(raw_entities)
        
        # Complex query parameters
        if complexity in ['moderate', 'complex']:
            slots.comparison_type = self._extract_comparison_type(raw_entities)
            slots.aggregation_type = self._extract_aggregation_type(raw_entities)
            slots.grouping_fields = self._extract_grouping_fields(raw_entities)
            slots.sorting_field, slots.sorting_order = self._extract_sorting(raw_entities)
            slots.limit = self._extract_limit(raw_entities)
            slots.time_period = self._extract_time_period(raw_entities)
            slots.trend_analysis = self._detect_trend_analysis(raw_entities)
        
        print(f"DEBUG: Processed slots summary:")
        print(f"  - Cohort: {slots.cohort}, Cohorts: {slots.cohorts}")
        print(f"  - Gender: {slots.gender}, Genders: {slots.genders}")
        print(f"  - Programme: {slots.programme}, Programmes: {slots.programmes}")
        print(f"  - Aggregation: {slots.aggregation_type}")
        print(f"  - Comparison: {slots.comparison_type}")
        print(f"  - Limit: {slots.limit}")
        
        return slots

    def _extract_student_ids(self, entities: List[str], role: str) -> List[str]:
        """Extract multiple student IDs"""
        ids = []
        for entity in entities:
            if re.match(r'^[0-9]{7}$', entity) and role == 'admin':
                ids.append(entity)
        return ids

    def _extract_multiple_races(self, entities: List[str]) -> List[str]:
        """Extract multiple races"""
        race_map = {'chinese': 'CHINESE', 'malay': 'MALAY', 'indian': 'INDIAN', 'others': 'OTHERS'}
        races = []
        for entity in entities:
            if entity.lower() in race_map:
                races.append(race_map[entity.lower()])
        return races

    def _extract_multiple_countries(self, entities: List[str]) -> List[str]:
        """Extract multiple countries"""
        countries = []
        for entity in entities:
            if entity.lower() in self.country_aliases:
                countries.append(self.country_aliases[entity.lower()])
        return countries

    def _extract_multiple_genders(self, entities: List[str]) -> List[str]:
        """Extract multiple genders"""
        entity_text = ' '.join(entities).lower()
        genders = []
        
        if any(word in entity_text for word in ['female', 'women', 'woman', 'girl', 'girls']):
            genders.append('Female')
        if any(word in entity_text for word in ['male', 'men', 'man', 'boy', 'boys']):
            genders.append('Male')
        
        return genders

    def _extract_multiple_programmes(self, entities: List[str]) -> List[str]:
        """Extract multiple programmes"""
        programmes = []
        entity_text = ' '.join(entities).lower()
        
        for alias, programme in self.programme_aliases.items():
            if alias in entity_text:
                programmes.append(programme)
        
        return programmes

    def _extract_multiple_subjects(self, entities: List[str]) -> List[str]:
        """Extract multiple subjects"""
        subjects = []
        entity_text = ' '.join(entities).lower()
        
        for alias, subject_list in self.subject_aliases.items():
            if alias in entity_text:
                subjects.extend(subject_list)
        
        return subjects

    def _extract_cohort_enhanced(self, entities: List[str]) -> Optional[str]:
        """Enhanced cohort extraction"""
        
        # Method 1: Direct YYYYMM format
        for entity in entities:
            if re.match(r'^\d{6}$', entity):
                return entity
        
        # Method 2: Month + Year combination
        found_month = None
        found_year = None
        
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.month_mapping:
                found_month = self.month_mapping[entity_lower]
                break
        
        for entity in entities:
            if re.match(r'^20\d{2}$', entity):
                found_year = entity
                break
        
        if found_month and found_year:
            cohort = f"{found_year}{found_month}"
            print(f"DEBUG: Extracted cohort: {cohort} from month={found_month}, year={found_year}")
            return cohort
        
        # Method 3: Pattern matching
        entity_text = ' '.join(entities).lower()
        pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s*(20\d{2})'
        match = re.search(pattern, entity_text)
        if match:
            month_name = match.group(1).lower()
            year = match.group(2)
            if month_name in self.month_mapping:
                cohort = f"{year}{self.month_mapping[month_name]}"
                print(f"DEBUG: Pattern extracted cohort: {cohort}")
                return cohort
        
        return None

    def _extract_multiple_cohorts(self, entities: List[str]) -> List[str]:
        """Extract multiple cohorts"""
        cohorts = []
        
        # Extract all YYYYMM patterns
        for entity in entities:
            if re.match(r'^\d{6}$', entity):
                cohorts.append(entity)
        
        return cohorts

    def _extract_multiple_years(self, entities: List[str]) -> List[str]:
        """Extract multiple years"""
        years = []
        for entity in entities:
            if re.match(r'^20\d{2}$', entity):
                years.append(entity)
        return years

    def _extract_grade(self, entities: List[str]) -> Optional[str]:
        """Extract single grade"""
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.grade_mapping:
                return self.grade_mapping[entity_lower]
        return None

    def _extract_multiple_grades(self, entities: List[str]) -> List[str]:
        """Extract multiple grades"""
        grades = []
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.grade_mapping:
                grades.append(self.grade_mapping[entity_lower])
        return grades

    def _extract_cgpa_range(self, entities: List[str]) -> Tuple[Optional[float], Optional[float]]:
        """Extract CGPA range from entities"""
        cgpa_min = None
        cgpa_max = None
        
        entity_text = ' '.join(entities).lower()
        
        # Look for patterns like "cgpa above 3.5", "cgpa between 3.0 and 3.8"
        above_match = re.search(r'(?:cgpa|gpa)\s*(?:above|greater than|>)\s*(\d+\.?\d*)', entity_text)
        if above_match:
            cgpa_min = float(above_match.group(1))
        
        below_match = re.search(r'(?:cgpa|gpa)\s*(?:below|less than|<)\s*(\d+\.?\d*)', entity_text)
        if below_match:
            cgpa_max = float(below_match.group(1))
        
        between_match = re.search(r'(?:cgpa|gpa)\s*between\s*(\d+\.?\d*)\s*and\s*(\d+\.?\d*)', entity_text)
        if between_match:
            cgpa_min = float(between_match.group(1))
            cgpa_max = float(between_match.group(2))
        
        return cgpa_min, cgpa_max

    def _extract_percentage_range(self, entities: List[str]) -> Tuple[Optional[float], Optional[float]]:
        """Extract percentage range"""
        percentage_min = None
        percentage_max = None
        
        entity_text = ' '.join(entities).lower()
        
        above_match = re.search(r'(?:percentage|%)\s*(?:above|greater than|>)\s*(\d+)', entity_text)
        if above_match:
            percentage_min = float(above_match.group(1))
        
        below_match = re.search(r'(?:percentage|%)\s*(?:below|less than|<)\s*(\d+)', entity_text)
        if below_match:
            percentage_max = float(below_match.group(1))
        
        return percentage_min, percentage_max

    def _extract_comparison_type(self, entities: List[str]) -> Optional[str]:
        """Extract comparison type"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['greater than', 'above', 'higher than', '>']):
            return 'greater_than'
        elif any(word in entity_text for word in ['less than', 'below', 'lower than', '<']):
            return 'less_than'
        elif any(word in entity_text for word in ['between', 'from', 'to']):
            return 'between'
        elif any(word in entity_text for word in ['equal', 'equals', '=']):
            return 'equal'
        
        return None

    def _extract_aggregation_type(self, entities: List[str]) -> Optional[str]:
        """Extract aggregation type"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['count', 'how many', 'number of']):
            return 'count'
        elif any(word in entity_text for word in ['average', 'avg', 'mean']):
            return 'average'
        elif any(word in entity_text for word in ['sum', 'total']):
            return 'sum'
        elif any(word in entity_text for word in ['maximum', 'max', 'highest']):
            return 'max'
        elif any(word in entity_text for word in ['minimum', 'min', 'lowest']):
            return 'min'
        elif any(word in entity_text for word in ['median']):
            return 'median'
        
        return None

    def _extract_grouping_fields(self, entities: List[str]) -> List[str]:
        """Extract fields to group by"""
        entity_text = ' '.join(entities).lower()
        grouping_fields = []
        
        if any(word in entity_text for word in ['by programme', 'per programme', 'programme wise']):
            grouping_fields.append('programme')
        if any(word in entity_text for word in ['by gender', 'per gender', 'gender wise']):
            grouping_fields.append('gender')
        if any(word in entity_text for word in ['by cohort', 'per cohort', 'cohort wise']):
            grouping_fields.append('cohort')
        if any(word in entity_text for word in ['by country', 'per country', 'country wise']):
            grouping_fields.append('country')
        if any(word in entity_text for word in ['by race', 'per race', 'race wise']):
            grouping_fields.append('race')
        
        return grouping_fields

    def _extract_sorting(self, entities: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Extract sorting field and order"""
        entity_text = ' '.join(entities).lower()
        sorting_field = None
        sorting_order = None
        
        if any(word in entity_text for word in ['top', 'best', 'highest']):
            sorting_order = 'desc'
        elif any(word in entity_text for word in ['bottom', 'worst', 'lowest']):
            sorting_order = 'asc'
        
        if any(word in entity_text for word in ['cgpa', 'gpa']):
            sorting_field = 'overallcgpa'
        elif any(word in entity_text for word in ['percentage', 'marks']):
            sorting_field = 'overallpercentage'
        elif any(word in entity_text for word in ['name', 'alphabetical']):
            sorting_field = 'name'
        
        return sorting_field, sorting_order

    def _extract_limit(self, entities: List[str]) -> Optional[int]:
        """Extract limit/top N"""
        entity_text = ' '.join(entities).lower()
        
        # Look for patterns like "top 10", "first 5", "limit 20"
        patterns = [
            r'top\s*(\d+)',
            r'first\s*(\d+)',
            r'limit\s*(\d+)',
            r'(\d+)\s*students'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, entity_text)
            if match:
                return int(match.group(1))
        
        return None

    def _extract_time_period(self, entities: List[str]) -> Optional[str]:
        """Extract time period for trend analysis"""
        entity_text = ' '.join(entities).lower()
        
        if any(phrase in entity_text for phrase in ['last year', 'past year']):
            return 'last_year'
        elif any(phrase in entity_text for phrase in ['last 3 years', 'past 3 years']):
            return 'last_3_years'
        elif any(phrase in entity_text for phrase in ['current semester', 'this semester']):
            return 'current_semester'
        elif any(phrase in entity_text for phrase in ['current year', 'this year']):
            return 'current_year'
        
        return None

    def _detect_trend_analysis(self, entities: List[str]) -> bool:
        """Detect if trend analysis is needed"""
        entity_text = ' '.join(entities).lower()
        
        trend_keywords = ['trend', 'over time', 'growth', 'decline', 'increase', 'decrease', 'change']
        return any(keyword in entity_text for keyword in trend_keywords)

    # Include all the existing basic extraction methods
    def _extract_race(self, entities: List[str]) -> Optional[str]:
        """Extract race from entities"""
        race_map = {'chinese': 'CHINESE', 'malay': 'MALAY', 'indian': 'INDIAN', 'others': 'OTHERS'}
        
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in race_map:
                return race_map[entity_lower]
        return None

    def _extract_country(self, entities: List[str]) -> Optional[str]:
        """Extract country from entities"""
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.country_aliases:
                return self.country_aliases[entity_lower]
        return None

    def _extract_gender(self, entities: List[str]) -> Optional[str]:
        """Extract gender from entities"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['female', 'women', 'woman', 'girl', 'girls']):
            return 'Female'
        elif any(word in entity_text for word in ['male', 'men', 'man', 'boy', 'boys']):
            return 'Male'
        
        return None

    def _extract_year(self, entities: List[str]) -> Optional[str]:
        """Extract year"""
        for entity in entities:
            if re.match(r'^20\d{2}, entity):
                return f"{entity}%"
        return None

    def _fuzzy_match_subject(self, entities: List[str]) -> Optional[str]:
        """Fuzzy match subject names"""
        entity_text = ' '.join(entities).lower()
        
        for alias, subjects in self.subject_aliases.items():
            if alias in entity_text:
                if len(subjects) == 1:
                    return subjects[0]
                else:
                    return f"AMBIGUOUS:{','.join(subjects)}"
        
        all_subjects = self.unique_values.get('subjectname', [])
        best_matches = []
        
        for subject in all_subjects:
            subject_lower = subject.lower()
            for entity in entities:
                entity_lower = entity.lower()
                if entity_lower in subject_lower or subject_lower in entity_lower:
                    similarity = difflib.SequenceMatcher(None, entity_lower, subject_lower).ratio()
                    if similarity > 0.6:
                        best_matches.append((subject, similarity))
        
        if best_matches:
            best_matches.sort(key=lambda x: x[1], reverse=True)
            return best_matches[0][0]
        
        return None

    def _fuzzy_match_programme(self, entities: List[str]) -> Optional[str]:
        """Fuzzy match programme names"""
        entity_text = ' '.join(entities).lower()
        
        for alias, programme in self.programme_aliases.items():
            if alias in entity_text:
                return programme
        
        all_programmes = self.unique_values.get('programme', [])
        for programme in all_programmes:
            programme_words = programme.lower().split()
            matches = sum(1 for word in programme_words 
                         if any(word in entity.lower() for entity in entities))
            if matches >= 2:
                return programme
        
        return None

    def _extract_sponsor(self, entities: List[str]) -> Optional[str]:
        """Extract sponsor information"""
        entity_text = ' '.join(entities).lower()
        
        if 'jeffrey cheah' in entity_text:
            return 'JEFFREY CHEAH%'
        elif 'sunway' in entity_text:
            return 'SUNWAY%'
        elif 'scholarship' in entity_text:
            return '%Scholarship%'
        
        return None

    def _extract_multiple_sponsors(self, entities: List[str]) -> List[str]:
        """Extract multiple sponsors"""
        sponsors = []
        entity_text = ' '.join(entities).lower()
        
        if 'jeffrey cheah' in entity_text:
            sponsors.append('JEFFREY CHEAH%')
        if 'sunway' in entity_text:
            sponsors.append('SUNWAY%')
        if 'scholarship' in entity_text:
            sponsors.append('%Scholarship%')
        
        return sponsors

    def _extract_enrollment_status(self, entities: List[str]) -> Optional[str]:
        """Extract enrollment status"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['enrolled', 'active', 'current', 'currently']):
            return 'enrolled'
        elif any(word in entity_text for word in ['graduated', 'graduate', 'alumni']):
            return 'graduated'
        
        return None

    def _extract_graduation_status(self, entities: List[str]) -> Optional[str]:
        """Extract graduation status"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['graduated', 'graduate', 'alumni']):
            return 'graduated'
        elif any(word in entity_text for word in ['not graduated', 'current', 'enrolled']):
            return 'not_graduated'
        
        return None


class AdvancedQueryBuilder:
    """Advanced query builder for complex CQL generation"""
    
    def __init__(self):
        self.base_templates = {
            Intent.COUNT_STUDENTS: "SELECT COUNT(*) FROM students WHERE {conditions}",
            Intent.GET_STUDENT_CGPA: "SELECT id, name, overallcgpa FROM students WHERE {conditions}",
            Intent.GET_STUDENT_GRADES: "SELECT id, subjectname, grade, overallpercentage, exampercentage, courseworkpercentage FROM subjects WHERE {conditions}",
            Intent.GET_SUBJECT_RESULTS: "SELECT id, subjectname, grade, overallpercentage, exampercentage, courseworkpercentage FROM subjects WHERE {conditions}",
            Intent.YES_NO_QUESTION: "SELECT id, subjectname, grade, overallpercentage, exampercentage, courseworkpercentage FROM subjects WHERE {conditions}",
            Intent.GET_STUDENT_INFO: "SELECT id, name, programme, overallcgpa, status, cohort, country, sponsorname, gender FROM students WHERE {conditions}",
            Intent.LIST_STUDENTS: "SELECT id, name, programme, cohort, gender, country FROM students WHERE {conditions}",
            Intent.GET_FINANCIAL_AID: "SELECT id, name, sponsorname, programme, cohort FROM students WHERE {conditions}",
        }
        
        # Complex query templates
        self.complex_templates = {
            Intent.COMPARE_PERFORMANCE: "SELECT {aggregation_field}, {grouping_fields} FROM {table} WHERE {conditions} GROUP BY {grouping_fields}",
            Intent.GET_STATISTICS: "SELECT {aggregation_function}({field}) as result, {grouping_fields} FROM {table} WHERE {conditions} GROUP BY {grouping_fields}",
            Intent.RANK_STUDENTS: "SELECT id, name, {ranking_field} FROM students WHERE {conditions} ORDER BY {ranking_field} {order}",
            Intent.COHORT_ANALYSIS: "SELECT cohort, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY cohort",
            Intent.PROGRAMME_COMPARISON: "SELECT programme, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY programme"
        }

    def generate_query(self, intent: Intent, slots: ProcessedSlots, userid: str, role: str, complexity: str = "simple") -> Optional[str]:
        """Generate appropriate query based on intent and complexity"""
        
        print(f"DEBUG: Generating query for intent: {intent}, complexity: {complexity}")
        
        # Handle ambiguous subjects
        if slots.subject and slots.subject.startswith('AMBIGUOUS:'):
            return None
        
        if complexity == "simple" and intent in self.base_templates:
            return self._generate_simple_query(intent, slots, userid, role)
        elif complexity in ["moderate", "complex"]:
            return self._generate_complex_query(intent, slots, userid, role, complexity)
        else:
            return self._generate_simple_query(intent, slots, userid, role)

    def _generate_simple_query(self, intent: Intent, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Generate simple queries"""
        
        conditions = self._build_basic_conditions(slots, intent, userid, role)
        query = self.base_templates[intent].format(conditions=conditions)
        
        # Add ordering and limits
        if slots.sorting_field and slots.sorting_order:
            query += f" ORDER BY {slots.sorting_field} {slots.sorting_order.upper()}"
        
        if slots.limit:
            query += f" LIMIT {slots.limit}"
        elif 'COUNT' not in query:
            query += " LIMIT 1000"
        
        query += " ALLOW FILTERING"
        return query

    def _generate_complex_query(self, intent: Intent, slots: ProcessedSlots, userid: str, role: str, complexity: str) -> str:
        """Generate complex queries with aggregations and grouping"""
        
        if intent == Intent.COMPARE_PERFORMANCE:
            return self._build_comparison_query(slots, userid, role)
        elif intent == Intent.GET_STATISTICS:
            return self._build_statistics_query(slots, userid, role)
        elif intent == Intent.RANK_STUDENTS:
            return self._build_ranking_query(slots, userid, role)
        elif intent == Intent.COHORT_ANALYSIS:
            return self._build_cohort_analysis_query(slots, userid, role)
        elif intent == Intent.PROGRAMME_COMPARISON:
            return self._build_programme_comparison_query(slots, userid, role)
        else:
            # Fall back to enhanced simple query
            return self._generate_enhanced_simple_query(intent, slots, userid, role)

    def _build_comparison_query(self, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Build comparison queries"""
        
        conditions = self._build_basic_conditions(slots, Intent.COUNT_STUDENTS, userid, role)
        
        if slots.grouping_fields:
            grouping = ", ".join(slots.grouping_fields)
            if slots.aggregation_type == 'average':
                query = f"SELECT {grouping}, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY {grouping}"
            else:
                query = f"SELECT {grouping}, COUNT(*) as count FROM students WHERE {conditions} GROUP BY {grouping}"
        else:
            query = f"SELECT programme, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY programme"
        
        query += " ALLOW FILTERING"
        return query

    def _build_statistics_query(self, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Build statistical queries"""
        
        conditions = self._build_basic_conditions(slots, Intent.COUNT_STUDENTS, userid, role)
        
        if slots.aggregation_type == 'average':
            query = f"SELECT AVG(overallcgpa) as average_cgpa FROM students WHERE {conditions}"
        elif slots.aggregation_type == 'count':
            query = f"SELECT COUNT(*) as total_count FROM students WHERE {conditions}"
        elif slots.aggregation_type == 'max':
            query = f"SELECT MAX(overallcgpa) as max_cgpa FROM students WHERE {conditions}"
        elif slots.aggregation_type == 'min':
            query = f"SELECT MIN(overallcgpa) as min_cgpa FROM students WHERE {conditions}"
        else:
            query = f"SELECT COUNT(*) as count FROM students WHERE {conditions}"
        
        query += " ALLOW FILTERING"
        return query

    def _build_ranking_query(self, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Build ranking queries"""
        
        conditions = self._build_basic_conditions(slots, Intent.LIST_STUDENTS, userid, role)
        
        ranking_field = slots.sorting_field or 'overallcgpa'
        order = slots.sorting_order or 'desc'
        limit = slots.limit or 10
        
        query = f"SELECT id, name, {ranking_field}, programme FROM students WHERE {conditions} ORDER BY {ranking_field} {order.upper()} LIMIT {limit}"
        query += " ALLOW FILTERING"
        return query

    def _build_cohort_analysis_query(self, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Build cohort analysis queries"""
        
        conditions = self._build_basic_conditions(slots, Intent.COUNT_STUDENTS, userid, role)
        query = f"SELECT cohort, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY cohort"
        query += " ALLOW FILTERING"
        return query

    def _build_programme_comparison_query(self, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Build programme comparison queries"""
        
        conditions = self._build_basic_conditions(slots, Intent.COUNT_STUDENTS, userid, role)
        query = f"SELECT programme, COUNT(*) as student_count, AVG(overallcgpa) as avg_cgpa FROM students WHERE {conditions} GROUP BY programme"
        query += " ALLOW FILTERING"
        return query

    def _generate_enhanced_simple_query(self, intent: Intent, slots: ProcessedSlots, userid: str, role: str) -> str:
        """Generate enhanced simple queries with multiple filters"""
        
        conditions = self._build_enhanced_conditions(slots, intent, userid, role)
        query = self.base_templates[intent].format(conditions=conditions)
        
        # Add ordering and limits
        if slots.sorting_field and slots.sorting_order:
            query += f" ORDER BY {slots.sorting_field} {slots.sorting_order.upper()}"
        
        if slots.limit:
            query += f" LIMIT {slots.limit}"
        elif 'COUNT' not in query:
            query += " LIMIT 1000"
        
        query += " ALLOW FILTERING"
        return query

    def _build_basic_conditions(self, slots: ProcessedSlots, intent: Intent, userid: str, role: str) -> str:
        """Build basic WHERE conditions"""
        
        conditions = []
        
        # Access control
        if role == 'student':
            conditions.append(f"id = '{userid}'")
        elif slots.student_id:
            conditions.append(f"id = '{slots.student_id}'")
        elif slots.student_ids:
            ids_str = "', '".join(slots.student_ids)
            conditions.append(f"id IN ('{ids_str}')")
        
        # Basic filters
        if slots.programme:
            conditions.append(f"programme = '{slots.programme}'")
        
        if slots.subject:
            conditions.append(f"subjectname = '{slots.subject}'")
        
        if slots.race:
            conditions.append(f"race = '{slots.race}'")
        
        if slots.country:
            conditions.append(f"country = '{slots.country}'")
        
        if slots.gender:
            conditions.append(f"gender = '{slots.gender}'")
            print(f"DEBUG: Added gender condition: gender = '{slots.gender}'")
        
        if slots.cohort:
            conditions.append(f"cohort = '{slots.cohort}'")
            print(f"DEBUG: Added cohort condition: cohort = '{slots.cohort}'")
        
        # Performance filters
        if slots.cgpa_min:
            conditions.append(f"overallcgpa >= {slots.cgpa_min}")
        
        if slots.cgpa_max:
            conditions.append(f"overallcgpa <= {slots.cgpa_max}")
        
        # Status filters
        if slots.enrollment_status == 'enrolled':
            conditions.append("graduated = false")
        elif slots.enrollment_status == 'graduated':
            conditions.append("graduated = true")
        
        # Financial aid
        if slots.sponsor:
            if '%' in slots.sponsor:
                sponsor_clean = slots.sponsor.replace('%', '')
                conditions.append(f"sponsorname = '{sponsor_clean}'")
            else:
                conditions.append(f"sponsorname = '{slots.sponsor}'")
        
        # Return proper condition
        if conditions:
            result = " AND ".join(conditions)
        else:
            if role == 'student':
                result = f"id = '{userid}'"
            else:
                result = "id != ''"
        
        print(f"DEBUG: Generated basic conditions: '{result}'")
        return result

    def _build_enhanced_conditions(self, slots: ProcessedSlots, intent: Intent, userid: str, role: str) -> str:
        """Build enhanced conditions with multiple values"""
        
        conditions = []
        
        # Access control
        if role == 'student':
            conditions.append(f"id = '{userid}'")
        elif slots.student_ids:
            ids_str = "', '".join(slots.student_ids)
            conditions.append(f"id IN ('{ids_str}')")
        elif slots.student_id:
            conditions.append(f"id = '{slots.student_id}'")
        
        # Multiple programmes
        if slots.programmes:
            programmes_str = "', '".join(slots.programmes)
            conditions.append(f"programme IN ('{programmes_str}')")
        elif slots.programme:
            conditions.append(f"programme = '{slots.programme}'")
        
        # Multiple subjects
        if slots.subjects:
            subjects_str = "', '".join(slots.subjects)
            conditions.append(f"subjectname IN ('{subjects_str}')")
        elif slots.subject:
            conditions.append(f"subjectname = '{slots.subject}'")
        
        # Multiple races
        if slots.races:
            races_str = "', '".join(slots.races)
            conditions.append(f"race IN ('{races_str}')")
        elif slots.race:
            conditions.append(f"race = '{slots.race}'")
        
        # Multiple countries
        if slots.countries:
            countries_str = "', '".join(slots.countries)
            conditions.append(f"country IN ('{countries_str}')")
        elif slots.country:
            conditions.append(f"country = '{slots.country}'")
        
        # Multiple genders
        if slots.genders:
            genders_str = "', '".join(slots.genders)
            conditions.append(f"gender IN ('{genders_str}')")
        elif slots.gender:
            conditions.append(f"gender = '{slots.gender}'")
        
        # Multiple cohorts
        if slots.cohorts:
            cohorts_str = "', '".join(slots.cohorts)
            conditions.append(f"cohort IN ('{cohorts_str}')")
        elif slots.cohort:
            conditions.append(f"cohort = '{slots.cohort}'")
        
        # Multiple years (as cohort patterns)
        if slots.years:
            year_conditions = []
            for year in slots.years:
                year_conditions.append(f"cohort >= '{year}' AND cohort < '{str(int(year) + 1)}'")
            conditions.append(f"({' OR '.join(year_conditions)})")
        elif slots.year:
            year_clean = slots.year.replace('%', '')
            conditions.append(f"cohort >= '{year_clean}' AND cohort < '{str(int(year_clean) + 1)}'")
        
        # Performance filters
        if slots.cgpa_min:
            conditions.append(f"overallcgpa >= {slots.cgpa_min}")
        
        if slots.cgpa_max:
            conditions.append(f"overallcgpa <= {slots.cgpa_max}")
        
        if slots.percentage_min:
            conditions.append(f"overallpercentage >= {slots.percentage_min}")
        
        if slots.percentage_max:
            conditions.append(f"overallpercentage <= {slots.percentage_max}")
        
        # Multiple grades
        if slots.grades:
            grades_str = "', '".join(slots.grades)
            conditions.append(f"grade IN ('{grades_str}')")
        elif slots.grade:
            conditions.append(f"grade = '{slots.grade}'")
        
        # Status filters
        if slots.enrollment_status == 'enrolled':
            conditions.append("graduated = false")
        elif slots.enrollment_status == 'graduated':
            conditions.append("graduated = true")
        
        # Multiple sponsors
        if slots.sponsors:
            sponsor_conditions = []
            for sponsor in slots.sponsors:
                sponsor_clean = sponsor.replace('%', '')
                sponsor_conditions.append(f"sponsorname = '{sponsor_clean}'")
            conditions.append(f"({' OR '.join(sponsor_conditions)})")
        elif slots.sponsor:
            sponsor_clean = slots.sponsor.replace('%', '')
            conditions.append(f"sponsorname = '{sponsor_clean}'")
        
        # Return proper condition
        if conditions:
            result = " AND ".join(conditions)
        else:
            if role == 'student':
                result = f"id = '{userid}'"
            else:
                result = "id != ''"
        
        print(f"DEBUG: Generated enhanced conditions: '{result}'")
        return result


class AdvancedIntentProcessor:
    """Main processor for advanced intent handling"""
    
    def __init__(self, llm: LlamaLLM, unique_values: Dict[str, List[str]]):
        self.llm_classifier = AdvancedLLMClassifier(llm)
        self.slot_processor = AdvancedSlotProcessor(unique_values)
        self.query_builder = AdvancedQueryBuilder()
        self.llm = llm

    async def process_query(self, query: str, userid: str, role: str) -> Dict[str, Any]:
        """
        Advanced processing pipeline for complex queries
        """
        
        try:
            print(f"DEBUG: Processing query: '{query}'")
            
            # Step 1: Enhanced intent classification
            intent_result = await self.llm_classifier.classify_intent(query, userid, role)
            
            print(f"DEBUG: Intent: {intent_result.intent}, Complexity: {intent_result.complexity}")
            print(f"DEBUG: Raw entities: {intent_result.raw_entities}")
            
            if intent_result.intent == Intent.UNKNOWN:
                return {
                    "message": "I'm not sure what you're looking for. Could you try rephrasing your question?",
                    "error": True,
                    "query": query
                }
            
            # Step 2: Enhanced entity processing
            processed_slots = self.slot_processor.process_entities(
                intent_result.raw_entities, userid, role, intent_result.complexity
            )
            
            # Step 3: Check for ambiguous subjects
            if processed_slots.subject and processed_slots.subject.startswith('AMBIGUOUS:'):
                subjects = processed_slots.subject.replace('AMBIGUOUS:', '').split(',')
                return {
                    "message": f"Multiple subjects found. Which one did you mean: {', '.join(subjects)}?",
                    "clarification": True,
                    "choices": subjects,
                    "query": query
                }
            
            # Step 4: Generate appropriate query
            cql_query = self.query_builder.generate_query(
                intent_result.intent, processed_slots, userid, role, intent_result.complexity
            )
            
            if not cql_query:
                return {
                    "message": "Could not generate a query for this request. Please try rephrasing.",
                    "error": True,
                    "query": query
                }
            
            print(f"DEBUG: Generated CQL: {cql_query}")
            
            # Step 5: Execute query with enhanced error handling
            try:
                session = get_session()
                result = session.execute(cql_query)
                
                results_data = []
                for row in result:
                    row_dict = {}
                    for column in row._fields:
                        value = getattr(row, column)
                        row_dict[column] = str(value) if value is not None else ""
                    results_data.append(row_dict)
                
                print(f"DEBUG: Query returned {len(results_data)} results")
                
            except Exception as db_error:
                error_msg = str(db_error)
                print(f"DEBUG: Database error: {error_msg}")
                
                if "LIKE restriction" in error_msg:
                    return {
                        "message": "This search requires database indexing. Please try a more specific query.",
                        "error": True,
                        "query": query,
                        "debug": f"Database error: {error_msg}"
                    }
                elif "Undefined column" in error_msg:
                    return {
                        "message": "Database schema issue. Please contact support.",
                        "error": True,
                        "query": query,
                        "debug": f"Schema error: {error_msg}"
                    }
                else:
                    return {
                        "message": f"Database error: {error_msg}",
                        "error": True,
                        "query": query
                    }
            
            # Step 6: Format response based on intent and complexity
            if intent_result.is_yes_no:
                explanation = await self._generate_yes_no_explanation(query, results_data)
                return {
                    "message": explanation,
                    "result": results_data,
                    "query": query,
                    "intent": intent_result.intent.value,
                    "is_yes_no": True,
                    "cql": cql_query
                }
            
            # Step 7: Enhanced response formatting
            return self._format_advanced_response(intent_result, results_data, query, cql_query, processed_slots)
            
        except Exception as e:
            print(f"DEBUG: Processing error: {str(e)}")
            return {
                "message": f"Error processing query: {str(e)}",
                "error": True,
                "query": query,
                "debug": f"Processing error: {str(e)}"
            }

    async def _generate_yes_no_explanation(self, original_query: str, results_data: List[Dict]) -> str:
        """Enhanced yes/no explanations"""
        
        prompt = f"""The user asked: "{original_query}"

Database results: {json.dumps(results_data[:1])}  

Based on the results, provide a clear yes/no answer with explanation.

Rules:
- If grade is not 'F' and not empty → "Yes, you passed!"
- If grade is 'F' → "No, you did not pass"
- If no results → "No information found"
- Include the grade and percentage in your explanation
- Be encouraging and helpful

Example: "Yes, you passed Programming Principles! You got a B grade with 65% overall. Well done! 👍"

Generate response:"""
        
        try:
            response = await self.llm.generate_response(prompt, temperature=0.3)
            return response.strip()
        except:
            if results_data and results_data[0].get('grade', 'F') != 'F':
                return "Yes, you passed!"
            else:
                return "No information found or you did not pass."

    def _format_advanced_response(self, intent_result: IntentResult, results_data: List[Dict], 
                                 query: str, cql: str, slots: ProcessedSlots) -> Dict[str, Any]:
        """Enhanced response formatting for complex queries"""
        
        response = {
            "query": query,
            "intent": intent_result.intent.value,
            "complexity": intent_result.complexity,
            "cql": cql,
            "result": results_data
        }
        
        # Format message based on intent type
        if intent_result.intent == Intent.COUNT_STUDENTS:
            count = int(results_data[0]['count']) if results_data else 0
            response["message"] = f"There are {count} students matching your criteria."
            response["result"] = [{"count": count}]
            
        elif intent_result.intent == Intent.RANK_STUDENTS:
            count = len(results_data)
            limit = slots.limit or 10
            response["message"] = f"Here are the top {min(count, limit)} students based on your criteria."
            
        elif intent_result.intent == Intent.COMPARE_PERFORMANCE:
            response["message"] = f"Performance comparison results with {len(results_data)} groups."
            
        elif intent_result.intent == Intent.GET_STATISTICS:
            if results_data:
                stats = results_data[0]
                if 'avg_cgpa' in str(stats):
                    response["message"] = "Statistical analysis completed."
                else:
                    response["message"] = f"Found {len(results_data)} statistical results."
            else:
                response["message"] = "No statistical data found for your criteria."
                
        elif intent_result.intent == Intent.COHORT_ANALYSIS:
            response["message"] = f"Cohort analysis completed for {len(results_data)} cohorts."
            
        elif intent_result.intent == Intent.PROGRAMME_COMPARISON:
            response["message"] = f"Programme comparison completed for {len(results_data)} programmes."
            
        elif intent_result.intent == Intent.GET_FINANCIAL_AID:
            response["message"] = f"Found {len(results_data)} students with financial aid matching your criteria."
            
        else:
            response["message"] = f"Found {len(results_data)} matching records."
        
        return response


# Example usage and testing
async def test_advanced_system():
    """Test the advanced system with complex queries"""
    
    unique_values = {
        'programme': ['BSc (Hons) in Computer Science', 'BSc (Hons) Information Technology'],
        'subjectname': ['OperatingSystemFundamentals', 'ComputerVision', 'PrinciplesofEntrepreneurship'],
        'country': ['MALAYSIA', 'INDONESIA', 'IRAN']
    }
    
    llm = LlamaLLM()
    processor = AdvancedIntentProcessor(llm, unique_values)
    
    test_queries = [
        # Simple queries
        ("How many female students are there in cohort march 2022?", "admin", "admin"),
        ("Count students in Computer Science that are active", "admin", "admin"),
        
        # Complex queries
        ("Compare average CGPA between Computer Science and IT students", "admin", "admin"),
        ("Who are the top 10 students with highest CGPA in 2023?", "admin", "admin"),
        ("Show me Chinese students from Malaysia with scholarships", "admin", "admin"),
        ("What's the trend of enrollment in Computer Science over the last 3 years?", "admin", "admin"),
        ("How many students graduated in 2023 by programme?", "admin", "admin"),
        ("Students with CGPA above 3.5 in Computer Science", "admin", "admin"),
        
        # Student queries
        ("What is my CGPA?", "6983255", "student"),
        ("Did I pass Programming Principles?", "6983255", "student"),
    ]
    
    for query, userid, role in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing: '{query}'")
        print(f"User: {userid} ({role})")
        print(f"{'='*60}")
        
        result = await processor.process_query(query, userid, role)
        
        print(f"Response: {result.get('message')}")
        print(f"Intent: {result.get('intent', 'unknown')}")
        print(f"Complexity: {result.get('complexity', 'unknown')}")
        
        if result.get('error'):
            print(f"Error: {result.get('debug', 'No debug info')}")
        else:
            print(f"Results: {len(result.get('result', []))} records")
        
        if result.get('cql'):
            print(f"CQL: {result['cql']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_advanced_system())