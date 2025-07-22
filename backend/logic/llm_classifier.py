# llm_classifier.py - LLM-based intent classification

import json
from typing import Dict, List
from backend.llm.llama_integration import LlamaLLM
from intent_enums import Intent, IntentResult, QueryComplexity, QueryContext

class AdvancedLLMClassifier:
    """Enhanced LLM classifier for comprehensive intent detection"""
    
    def __init__(self, llm: LlamaLLM):
        self.llm = llm
        
        # Intent mapping for better classification
        self.intent_patterns = {
            # Counting patterns
            'count': [Intent.COUNT_STUDENTS, Intent.COUNT_COHORT_STUDENTS, Intent.COUNT_PROGRAMME_STUDENTS, Intent.COUNT_SCHOLARSHIP_RECIPIENTS],
            'how_many': [Intent.COUNT_STUDENTS, Intent.COUNT_BY_GENDER, Intent.COUNT_BY_RACE, Intent.COUNT_BY_COUNTRY],
            'number_of': [Intent.COUNT_STUDENTS, Intent.DEMOGRAPHIC_ANALYSIS],
            
            # Listing patterns
            'list': [Intent.LIST_STUDENTS, Intent.LIST_PROGRAMME_STUDENTS, Intent.LIST_FINANCIAL_AID],
            'show': [Intent.SHOW_STUDENTS, Intent.SHOW_GRADES, Intent.GET_STUDENT_INFO],
            'display': [Intent.LIST_STUDENTS, Intent.GET_STUDENT_INFO],
            
            # Student-specific patterns
            'my': [Intent.GET_STUDENT_CGPA, Intent.GET_STUDENT_GRADES, Intent.GET_STUDENT_INFO],
            'cgpa': [Intent.GET_STUDENT_CGPA, Intent.PERFORMANCE_ANALYSIS],
            'grades': [Intent.GET_STUDENT_GRADES, Intent.SHOW_GRADES],
            'results': [Intent.GET_SUBJECT_RESULTS, Intent.GET_STUDENT_GRADES],
            
            # Status patterns
            'enrolled': [Intent.CHECK_ENROLLMENT, Intent.GET_CURRENT_STUDENTS],
            'graduated': [Intent.CHECK_GRADUATION, Intent.GET_GRADUATED_STUDENTS],
            'active': [Intent.GET_CURRENT_STUDENTS, Intent.CHECK_ENROLLMENT],
            
            # Financial patterns
            'scholarship': [Intent.GET_SCHOLARSHIP_STUDENTS, Intent.HAS_SCHOLARSHIP, Intent.COUNT_SCHOLARSHIP_RECIPIENTS],
            'financial_aid': [Intent.GET_FINANCIAL_AID, Intent.LIST_FINANCIAL_AID],
            'sponsor': [Intent.GET_FINANCIAL_AID, Intent.GET_SCHOLARSHIP_STUDENTS],
            
            # Performance patterns
            'top': [Intent.GET_TOP_STUDENTS, Intent.RANK_STUDENTS],
            'best': [Intent.GET_TOP_STUDENTS, Intent.PERFORMANCE_ANALYSIS],
            'highest': [Intent.GET_TOP_STUDENTS, Intent.RANK_STUDENTS],
            'lowest': [Intent.GET_BOTTOM_STUDENTS, Intent.RANK_STUDENTS],
            'worst': [Intent.GET_BOTTOM_STUDENTS, Intent.PERFORMANCE_ANALYSIS],
            
            # Comparison patterns
            'compare': [Intent.COMPARE_PROGRAMMES, Intent.PERFORMANCE_ANALYSIS],
            'between': [Intent.COMPARE_PROGRAMMES, Intent.FILTER_COMPLEX],
            'versus': [Intent.COMPARE_PROGRAMMES, Intent.PERFORMANCE_ANALYSIS],
            
            # Yes/No patterns
            'did': [Intent.DID_PASS, Intent.YES_NO_QUESTION],
            'is': [Intent.IS_ENROLLED, Intent.YES_NO_QUESTION],
            'has': [Intent.HAS_SCHOLARSHIP, Intent.YES_NO_QUESTION],
            'passed': [Intent.DID_PASS, Intent.CHECK_GRADE],
            'failed': [Intent.DID_PASS, Intent.CHECK_GRADE],
            
            # Analysis patterns
            'trend': [Intent.TEMPORAL_ANALYSIS, Intent.COHORT_ANALYSIS],
            'analysis': [Intent.DEMOGRAPHIC_ANALYSIS, Intent.PERFORMANCE_ANALYSIS, Intent.COHORT_ANALYSIS],
            'statistics': [Intent.GET_STATISTICS, Intent.DEMOGRAPHIC_ANALYSIS],
            'average': [Intent.GET_STATISTICS, Intent.PERFORMANCE_ANALYSIS],
        }

    async def classify_intent(self, query: str, context: QueryContext) -> IntentResult:
        """Enhanced intent classification with context awareness"""
        
        # Quick pattern matching for common queries
        quick_intent = self._quick_pattern_match(query)
        if quick_intent:
            return await self._build_intent_result(quick_intent, query, context)
        
        # Full LLM classification for complex queries
        prompt = self._create_comprehensive_prompt(query, context)
        
        try:
            llm_response = await self.llm.generate_response(prompt, f"{context.user_id}_intent")
            result = json.loads(llm_response)
            
            intent_str = result.get('intent', 'unknown')
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.UNKNOWN
            
            complexity_str = result.get('complexity', 'simple')
            try:
                complexity = QueryComplexity(complexity_str)
            except ValueError:
                complexity = QueryComplexity.SIMPLE
            
            return IntentResult(
                intent=intent,
                raw_entities=result.get('raw_entities', []),
                confidence=result.get('confidence', 0.5),
                is_yes_no=result.get('is_yes_no', False),
                complexity=complexity,
                requires_aggregation=result.get('requires_aggregation', False),
                requires_joins=result.get('requires_joins', False),
                requires_temporal_analysis=result.get('requires_temporal_analysis', False)
            )
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"LLM Classification Error: {e}")
            return IntentResult(
                intent=Intent.UNKNOWN,
                raw_entities=[],
                confidence=0.1
            )

    def _quick_pattern_match(self, query: str) -> Optional[Intent]:
        """Quick pattern matching for common queries"""
        query_lower = query.lower()
        
        # Direct intent matches
        if any(phrase in query_lower for phrase in ['how many students are currently enrolled']):
            return Intent.GET_CURRENT_STUDENTS
        elif any(phrase in query_lower for phrase in ['count students in computer science that are active']):
            return Intent.COUNT_PROGRAMME_STUDENTS
        elif any(phrase in query_lower for phrase in ['how many female students are there']):
            return Intent.COUNT_BY_GENDER
        elif any(phrase in query_lower for phrase in ['how many students are in cohort']):
            return Intent.COUNT_COHORT_STUDENTS
        elif any(phrase in query_lower for phrase in ['count students from malaysia']):
            return Intent.COUNT_BY_COUNTRY
        elif any(phrase in query_lower for phrase in ['how many chinese students are there']):
            return Intent.COUNT_BY_RACE
        elif any(phrase in query_lower for phrase in ['show students from malaysia']):
            return Intent.FILTER_COMPLEX
        elif any(phrase in query_lower for phrase in ['students who are female']):
            return Intent.LIST_STUDENTS
        elif any(phrase in query_lower for phrase in ['list students in computer science']):
            return Intent.LIST_PROGRAMME_STUDENTS
        elif any(phrase in query_lower for phrase in ['students who started in 2023']):
            return Intent.GET_COHORT_STUDENTS
        elif any(phrase in query_lower for phrase in ['chinese students from cohort 2023']):
            return Intent.MULTI_CRITERIA_SEARCH
        elif any(phrase in query_lower for phrase in ['students who graduated in 2023']):
            return Intent.GET_GRADUATED_STUDENTS
        elif any(phrase in query_lower for phrase in ['show grades for student']):
            return Intent.SHOW_GRADES
        elif any(phrase in query_lower for phrase in ['get cgpa for student']):
            return Intent.GET_STUDENT_CGPA
        elif any(phrase in query_lower for phrase in ['show all subjects for student']):
            return Intent.GET_STUDENT_SUBJECTS
        elif any(phrase in query_lower for phrase in ['what programme is student']):
            return Intent.GET_PROGRAMME_INFO
        elif any(phrase in query_lower for phrase in ['students with scholarships']):
            return Intent.GET_SCHOLARSHIP_STUDENTS
        elif any(phrase in query_lower for phrase in ['students who received jeffrey cheah scholarship']):
            return Intent.GET_SCHOLARSHIP_STUDENTS
        elif any(phrase in query_lower for phrase in ['list all financial aid recipients']):
            return Intent.LIST_FINANCIAL_AID
        elif any(phrase in query_lower for phrase in ['count students with scholarships']):
            return Intent.COUNT_SCHOLARSHIP_RECIPIENTS
        
        return None

    async def _build_intent_result(self, intent: Intent, query: str, context: QueryContext) -> IntentResult:
        """Build intent result for quick matches"""
        entities = self._extract_basic_entities(query)
        complexity = self._determine_complexity(query, intent)
        
        return IntentResult(
            intent=intent,
            raw_entities=entities,
            confidence=0.9,
            is_yes_no=self._is_yes_no_question(query),
            complexity=complexity,
            requires_aggregation=self._requires_aggregation(intent),
            requires_joins=self._requires_joins(intent),
            requires_temporal_analysis=self._requires_temporal_analysis(query)
        )

    def _extract_basic_entities(self, query: str) -> List[str]:
        """Extract basic entities from query"""
        # Simple entity extraction - can be enhanced
        words = query.lower().split()
        entities = []
        
        # Academic terms
        academic_terms = ['computer', 'science', 'information', 'technology', 'it', 'cs']
        demographic_terms = ['male', 'female', 'chinese', 'malay', 'indian', 'malaysia', 'indonesia', 'iran']
        temporal_terms = ['2023', '2022', '2021', '2020', 'march', 'january', 'cohort']
        performance_terms = ['cgpa', 'grade', 'scholarship', 'jeffrey', 'cheah']
        
        all_terms = academic_terms + demographic_terms + temporal_terms + performance_terms
        
        for word in words:
            if word in all_terms:
                entities.append(word)
        
        return entities

    def _determine_complexity(self, query: str, intent: Intent) -> QueryComplexity:
        """Determine query complexity"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['compare', 'trend', 'analysis', 'between', 'versus']):
            return QueryComplexity.ANALYTICAL
        elif any(word in query_lower for word in ['top', 'rank', 'best', 'worst', 'average', 'statistics']):
            return QueryComplexity.COMPLEX
        elif len(query_lower.split()) > 8:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE

    def _is_yes_no_question(self, query: str) -> bool:
        """Check if query is a yes/no question"""
        return any(word in query.lower() for word in ['did', 'is', 'has', 'does', 'can', 'will'])

    def _requires_aggregation(self, intent: Intent) -> bool:
        """Check if intent requires aggregation"""
        aggregation_intents = [
            Intent.COUNT_STUDENTS, Intent.COUNT_BY_GENDER, Intent.COUNT_BY_RACE,
            Intent.COUNT_BY_COUNTRY, Intent.GET_STATISTICS, Intent.PERFORMANCE_ANALYSIS
        ]
        return intent in aggregation_intents

    def _requires_joins(self, intent: Intent) -> bool:
        """Check if intent requires table joins"""
        join_intents = [
            Intent.GET_STUDENT_GRADES, Intent.GET_SUBJECT_RESULTS, 
            Intent.PERFORMANCE_ANALYSIS, Intent.SHOW_GRADES
        ]
        return intent in join_intents

    def _requires_temporal_analysis(self, query: str) -> bool:
        """Check if query requires temporal analysis"""
        temporal_keywords = ['trend', 'over time', 'growth', 'decline', 'increase', 'decrease', 'change', 'last', 'past']
        return any(keyword in query.lower() for keyword in temporal_keywords)

    def _create_comprehensive_prompt(self, query: str, context: QueryContext) -> str:
        """Create comprehensive prompt for complex queries"""
        
        prompt = f"""You are an advanced intent classifier for academic database queries. 

USER QUERY: "{query}"
USER ROLE: {context.user_role}
CONTEXT: Previous queries: {context.previous_queries[-3:] if context.previous_queries else 'None'}

AVAILABLE INTENTS - Choose the MOST SPECIFIC one:

BASIC OPERATIONS:
- count_students: General student counting
- list_students: List students with basic filters
- show_students: Display student information
- get_student_info: Get specific student details
- get_student_cgpa: Get CGPA for specific student
- get_student_grades: Get all grades for student
- get_student_subjects: Get all subjects for student

SPECIALIZED COUNTING:
- count_cohort_students: Count students in specific cohort
- count_programme_students: Count students in programme
- count_by_gender: Count by gender categories
- count_by_race: Count by racial categories  
- count_by_country: Count by country
- count_scholarship_recipients: Count scholarship students

ENROLLMENT & STATUS:
- check_enrollment: Check enrollment status
- get_current_students: Get currently enrolled students
- check_graduation: Check graduation status
- get_graduated_students: Get graduated students

FINANCIAL AID:
- get_financial_aid: Get financial aid information
- get_scholarship_students: Get students with scholarships
- list_financial_aid: List all financial aid recipients
- has_scholarship: Check if student has scholarship

PERFORMANCE & RANKING:
- get_top_students: Get highest performing students
- get_bottom_students: Get lowest performing students
- rank_students: Rank students by criteria
- performance_analysis: Analyze academic performance
- get_statistics: Get statistical data

PROGRAMME & ACADEMIC:
- get_programme_info: Programme information
- list_programme_students: Students in specific programme
- compare_programmes: Compare different programmes
- get_subject_results: Results for specific subject

COMPLEX ANALYSIS:
- cohort_analysis: Analyze cohort data
- demographic_analysis: Analyze demographics
- temporal_analysis: Time-based analysis
- filter_complex: Complex multi-criteria filtering
- multi_criteria_search: Multiple search criteria

YES/NO QUESTIONS:
- did_pass: Did student pass?
- is_enrolled: Is student enrolled?
- yes_no_question: General yes/no questions

EXTRACT ALL ENTITIES:
- Student info: names, IDs, specific students
- Demographics: male, female, chinese, malay, indian, countries
- Academic: programmes, subjects, grades, CGPA values
- Temporal: years, months, cohorts, semesters
- Financial: scholarships, sponsors, aid types
- Performance: grades, rankings, top/bottom counts
- Status: enrolled, graduated, active, inactive

COMPLEXITY LEVELS:
- simple: Basic single-condition queries
- moderate: Multiple conditions, basic filtering
- complex: Rankings, performance analysis, aggregations
- analytical: Trends, comparisons, statistical analysis

Respond with JSON:
{{
    "intent": "most_specific_intent_name",
    "confidence": 0.0-1.0,
    "raw_entities": ["extract", "every", "relevant", "term"],
    "is_yes_no": true/false,
    "complexity": "simple/moderate/complex/analytical",
    "requires_aggregation": true/false,
    "requires_joins": true/false,
    "requires_temporal_analysis": true/false
}}

EXAMPLES:

Query: "How many students are currently enrolled?"
Response: {{"intent": "get_current_students", "confidence": 0.95, "raw_entities": ["students", "currently", "enrolled"], "is_yes_no": false, "complexity": "simple", "requires_aggregation": true, "requires_joins": false, "requires_temporal_analysis": false}}

Query: "Count students in Computer Science that are active"  
Response: {{"intent": "count_programme_students", "confidence": 0.9, "raw_entities": ["count", "students", "computer", "science", "active"], "is_yes_no": false, "complexity": "moderate", "requires_aggregation": true, "requires_joins": false, "requires_temporal_analysis": false}}

Query: "Show me Chinese students from Malaysia with scholarships"
Response: {{"intent": "multi_criteria_search", "confidence": 0.9, "raw_entities": ["chinese", "students", "malaysia", "scholarships"], "is_yes_no": false, "complexity": "complex", "requires_aggregation": false, "requires_joins": false, "requires_temporal_analysis": false}}

Classify now:"""
        
        return prompt