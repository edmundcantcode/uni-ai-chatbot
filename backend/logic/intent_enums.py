# intent_enums.py - Core enums and data structures

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

class Intent(Enum):
    """Comprehensive intents covering all query types"""
    # Basic counting and listing
    COUNT_STUDENTS = "count_students"
    LIST_STUDENTS = "list_students"
    SHOW_STUDENTS = "show_students"
    
    # Student-specific information
    GET_STUDENT_INFO = "get_student_info"
    GET_STUDENT_CGPA = "get_student_cgpa"
    GET_STUDENT_GRADES = "get_student_grades"
    GET_STUDENT_SUBJECTS = "get_student_subjects"
    
    # Subject and grade queries
    GET_SUBJECT_RESULTS = "get_subject_results"
    SHOW_GRADES = "show_grades"
    CHECK_GRADE = "check_grade"
    
    # Enrollment and status
    CHECK_ENROLLMENT = "check_enrollment"
    CHECK_GRADUATION = "check_graduation"
    GET_CURRENT_STUDENTS = "get_current_students"
    GET_GRADUATED_STUDENTS = "get_graduated_students"
    
    # Financial aid and scholarships
    GET_FINANCIAL_AID = "get_financial_aid"
    GET_SCHOLARSHIP_STUDENTS = "get_scholarship_students"
    LIST_FINANCIAL_AID = "list_financial_aid"
    COUNT_SCHOLARSHIP_RECIPIENTS = "count_scholarship_recipients"
    
    # Programme-related queries
    GET_PROGRAMME_INFO = "get_programme_info"
    LIST_PROGRAMME_STUDENTS = "list_programme_students"
    COUNT_PROGRAMME_STUDENTS = "count_programme_students"
    COMPARE_PROGRAMMES = "compare_programmes"
    
    # Cohort and temporal analysis
    COHORT_ANALYSIS = "cohort_analysis"
    GET_COHORT_STUDENTS = "get_cohort_students"
    COUNT_COHORT_STUDENTS = "count_cohort_students"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    
    # Demographic analysis
    DEMOGRAPHIC_ANALYSIS = "demographic_analysis"
    COUNT_BY_GENDER = "count_by_gender"
    COUNT_BY_RACE = "count_by_race"
    COUNT_BY_COUNTRY = "count_by_country"
    
    # Performance analysis
    PERFORMANCE_ANALYSIS = "performance_analysis"
    GET_TOP_STUDENTS = "get_top_students"
    GET_BOTTOM_STUDENTS = "get_bottom_students"
    RANK_STUDENTS = "rank_students"
    GET_STATISTICS = "get_statistics"
    
    # Complex filtering
    FILTER_COMPLEX = "filter_complex"
    MULTI_CRITERIA_SEARCH = "multi_criteria_search"
    
    # Yes/no questions
    YES_NO_QUESTION = "yes_no_question"
    DID_PASS = "did_pass"
    IS_ENROLLED = "is_enrolled"
    HAS_SCHOLARSHIP = "has_scholarship"
    
    # Special queries
    SEARCH_SPECIFIC_STUDENT = "search_specific_student"
    GET_RECENT_ACTIVITIES = "get_recent_activities"
    
    UNKNOWN = "unknown"

class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"  
    COMPLEX = "complex"
    ANALYTICAL = "analytical"

class AggregationType(Enum):
    """Types of aggregations"""
    COUNT = "count"
    AVERAGE = "average"
    SUM = "sum"
    MAX = "max"
    MIN = "min"
    MEDIAN = "median"
    STDEV = "stdev"

class SortOrder(Enum):
    """Sorting orders"""
    ASC = "asc"
    DESC = "desc"

@dataclass
class IntentResult:
    """Result of intent classification"""
    intent: Intent
    raw_entities: List[str]
    confidence: float
    is_yes_no: bool = False
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    requires_aggregation: bool = False
    requires_joins: bool = False
    requires_temporal_analysis: bool = False

@dataclass
class ProcessedSlots:
    """Comprehensive slots for all query types"""
    # Basic identifiers
    student_id: Optional[str] = None
    student_ids: List[str] = field(default_factory=list)
    student_name: Optional[str] = None
    
    # Academic filters
    programme: Optional[str] = None
    programmes: List[str] = field(default_factory=list)
    subject: Optional[str] = None
    subjects: List[str] = field(default_factory=list)
    
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
    academic_year: Optional[str] = None
    
    # Performance filters
    grade: Optional[str] = None
    grades: List[str] = field(default_factory=list)
    cgpa_min: Optional[float] = None
    cgpa_max: Optional[float] = None
    cgpa_exact: Optional[float] = None
    percentage_min: Optional[float] = None
    percentage_max: Optional[float] = None
    
    # Status and enrollment
    enrollment_status: Optional[str] = None  # enrolled, graduated, inactive
    graduation_status: Optional[str] = None  # graduated, not_graduated
    student_status: Optional[str] = None     # active, inactive, suspended
    
    # Financial and sponsorship
    sponsor: Optional[str] = None
    sponsors: List[str] = field(default_factory=list)
    has_scholarship: Optional[bool] = None
    scholarship_type: Optional[str] = None
    
    # Query modifiers
    comparison_type: Optional[str] = None    # greater_than, less_than, between, equal
    aggregation_type: Optional[AggregationType] = None
    grouping_fields: List[str] = field(default_factory=list)
    sorting_field: Optional[str] = None
    sorting_order: Optional[SortOrder] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    
    # Temporal analysis
    time_period: Optional[str] = None        # last_year, current_semester, etc.
    trend_analysis: bool = False
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    
    # Special flags
    include_inactive: bool = False
    include_graduated: bool = False
    exclude_failed: bool = False
    only_current: bool = False

@dataclass
class QueryContext:
    """Context information for query processing"""
    user_id: str
    user_role: str  # student, admin, faculty
    original_query: str
    session_id: Optional[str] = None
    previous_queries: List[str] = field(default_factory=list)
    user_preferences: Dict = field(default_factory=dict)

@dataclass
class QueryResult:
    """Standardized query result"""
    success: bool
    message: str
    data: List[Dict] = field(default_factory=list)
    count: Optional[int] = None
    metadata: Dict = field(default_factory=dict)
    error_details: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    cql_query: Optional[str] = None
    execution_time: Optional[float] = None