# entity_processor.py - Advanced entity extraction and processing

import re
import difflib
from typing import Dict, List, Optional, Tuple
from intent_enums import ProcessedSlots, QueryContext, AggregationType, SortOrder

class AdvancedEntityProcessor:
    """Comprehensive entity processor for all query types"""
    
    def __init__(self, unique_values: Dict[str, List[str]]):
        self.unique_values = unique_values
        self._init_mappings()

    def _init_mappings(self):
        """Initialize all entity mappings"""
        
        # Programme mappings
        self.programme_aliases = {
            'computer science': 'BSc (Hons) in Computer Science',
            'cs': 'BSc (Hons) in Computer Science',
            'information technology': 'BSc (Hons) Information Technology', 
            'it': 'BSc (Hons) Information Technology',
            'software engineering': 'BSc (Hons) Software Engineering',
            'data science': 'BSc (Hons) Data Science',
            'cybersecurity': 'BSc (Hons) Cybersecurity',
            'business information systems': 'BSc (Hons) Business Information Systems',
            'bis': 'BSc (Hons) Business Information Systems'
        }
        
        # Subject mappings
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
            'software': ['SoftwareEngineering'],
            'algorithm': ['AlgorithmsandDataStructures'],
            'security': ['CybersecurityFundamentals']
        }
        
        # Country mappings
        self.country_aliases = {
            'malaysia': 'MALAYSIA',
            'iran': 'IRAN', 
            'indonesia': 'INDONESIA',
            'sri lanka': 'SRI LANKA',
            'singapore': 'SINGAPORE',
            'thailand': 'THAILAND',
            'china': 'CHINA',
            'india': 'INDIA',
            'pakistan': 'PAKISTAN',
            'bangladesh': 'BANGLADESH'
        }
        
        # Month mappings
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
        
        # Grade mappings
        self.grade_mapping = {
            'a+': 'A+', 'a': 'A', 'a-': 'A-',
            'b+': 'B+', 'b': 'B', 'b-': 'B-',
            'c+': 'C+', 'c': 'C', 'c-': 'C-',
            'd+': 'D+', 'd': 'D', 'd-': 'D-',
            'f': 'F'
        }
        
        # Status mappings
        self.status_mapping = {
            'enrolled': 'enrolled',
            'active': 'enrolled',
            'current': 'enrolled',
            'currently': 'enrolled',
            'graduated': 'graduated',
            'graduate': 'graduated',
            'alumni': 'graduated',
            'inactive': 'inactive',
            'suspended': 'suspended'
        }
        
        # Sponsor mappings
        self.sponsor_aliases = {
            'jeffrey cheah': 'JEFFREY CHEAH FOUNDATION',
            'sunway': 'SUNWAY GROUP',
            'government': 'GOVERNMENT SCHOLARSHIP',
            'merit': 'MERIT SCHOLARSHIP',
            'need': 'NEED-BASED SCHOLARSHIP'
        }

    def process_entities(self, raw_entities: List[str], context: QueryContext, complexity: str = "simple") -> ProcessedSlots:
        """Main entity processing method"""
        
        slots = ProcessedSlots()
        entity_text = ' '.join(raw_entities).lower()
        
        print(f"DEBUG: Processing {len(raw_entities)} entities for {complexity} query")
        print(f"DEBUG: Raw entities: {raw_entities}")
        
        # Basic identification
        self._process_student_identification(slots, raw_entities, context)
        
        # Academic processing
        self._process_academic_entities(slots, raw_entities)
        
        # Demographic processing
        self._process_demographic_entities(slots, raw_entities)
        
        # Temporal processing
        self._process_temporal_entities(slots, raw_entities)
        
        # Performance processing
        self._process_performance_entities(slots, raw_entities)
        
        # Status and enrollment processing
        self._process_status_entities(slots, raw_entities)
        
        # Financial processing
        self._process_financial_entities(slots, raw_entities)
        
        # Query modifiers (for complex queries)
        if complexity in ['moderate', 'complex', 'analytical']:
            self._process_query_modifiers(slots, raw_entities, entity_text)
        
        self._log_processed_slots(slots)
        return slots

    def _process_student_identification(self, slots: ProcessedSlots, entities: List[str], context: QueryContext):
        """Process student identification"""
        
        # Auto-set for student role
        if context.user_role == 'student':
            slots.student_id = context.user_id
        
        # Extract student IDs
        for entity in entities:
            if re.match(r'^[0-9]{7}, entity):
                if context.user_role in ['admin', 'faculty']:
                    if slots.student_id is None:
                        slots.student_id = entity
                    else:
                        slots.student_ids.append(entity)
        
        # Extract student names (basic pattern)
        for entity in entities:
            if len(entity) > 2 and entity.isalpha() and entity not in ['male', 'female', 'chinese', 'malay', 'indian']:
                # Could be a student name - would need better NER for full implementation
                pass

    def _process_academic_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process academic-related entities"""
        
        entity_text = ' '.join(entities).lower()
        
        # Programme processing
        slots.programme = self._extract_programme(entities)
        slots.programmes = self._extract_multiple_programmes(entities)
        
        # Subject processing
        slots.subject = self._extract_subject(entities)
        slots.subjects = self._extract_multiple_subjects(entities)

    def _process_demographic_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process demographic entities"""
        
        # Gender
        slots.gender = self._extract_gender(entities)
        slots.genders = self._extract_multiple_genders(entities)
        
        # Race
        slots.race = self._extract_race(entities)
        slots.races = self._extract_multiple_races(entities)
        
        # Country
        slots.country = self._extract_country(entities)
        slots.countries = self._extract_multiple_countries(entities)

    def _process_temporal_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process temporal entities"""
        
        # Cohort processing (enhanced)
        slots.cohort = self._extract_cohort_enhanced(entities)
        slots.cohorts = self._extract_multiple_cohorts(entities)
        
        # Year processing
        slots.year = self._extract_year(entities)
        slots.years = self._extract_multiple_years(entities)
        
        # Academic year and semester
        slots.academic_year = self._extract_academic_year(entities)
        slots.semester = self._extract_semester(entities)
        
        # Time periods
        slots.time_period = self._extract_time_period(entities)

    def _process_performance_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process performance-related entities"""
        
        # Grades
        slots.grade = self._extract_grade(entities)
        slots.grades = self._extract_multiple_grades(entities)
        
        # CGPA ranges
        slots.cgpa_min, slots.cgpa_max = self._extract_cgpa_range(entities)
        slots.cgpa_exact = self._extract_exact_cgpa(entities)
        
        # Percentage ranges
        slots.percentage_min, slots.percentage_max = self._extract_percentage_range(entities)

    def _process_status_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process status and enrollment entities"""
        
        entity_text = ' '.join(entities).lower()
        
        # Enrollment status
        for status_word, status_value in self.status_mapping.items():
            if status_word in entity_text:
                if status_value in ['enrolled', 'inactive', 'suspended']:
                    slots.enrollment_status = status_value
                elif status_value == 'graduated':
                    slots.graduation_status = 'graduated'
                    slots.enrollment_status = 'graduated'
        
        # Special flags
        if any(word in entity_text for word in ['current', 'active', 'currently']):
            slots.only_current = True
        
        if any(word in entity_text for word in ['include inactive', 'all students']):
            slots.include_inactive = True

    def _process_financial_entities(self, slots: ProcessedSlots, entities: List[str]):
        """Process financial aid and scholarship entities"""
        
        entity_text = ' '.join(entities).lower()
        
        # Scholarship detection
        if any(word in entity_text for word in ['scholarship', 'scholarships']):
            slots.has_scholarship = True
        
        # Sponsor processing
        slots.sponsor = self._extract_sponsor(entities)
        slots.sponsors = self._extract_multiple_sponsors(entities)
        
        # Scholarship types
        if 'jeffrey cheah' in entity_text:
            slots.scholarship_type = 'JEFFREY CHEAH'
        elif 'merit' in entity_text:
            slots.scholarship_type = 'MERIT'
        elif 'need' in entity_text:
            slots.scholarship_type = 'NEED-BASED'

    def _process_query_modifiers(self, slots: ProcessedSlots, entities: List[str], entity_text: str):
        """Process query modifiers for complex queries"""
        
        # Aggregation types
        slots.aggregation_type = self._extract_aggregation_type(entities)
        
        # Comparison types
        slots.comparison_type = self._extract_comparison_type(entities)
        
        # Grouping fields
        slots.grouping_fields = self._extract_grouping_fields(entities)
        
        # Sorting
        slots.sorting_field, slots.sorting_order = self._extract_sorting(entities)
        
        # Limits and offsets
        slots.limit = self._extract_limit(entities)
        slots.offset = self._extract_offset(entities)
        
        # Trend analysis
        slots.trend_analysis = self._detect_trend_analysis(entities)

    # Individual extraction methods
    def _extract_programme(self, entities: List[str]) -> Optional[str]:
        """Extract single programme"""
        entity_text = ' '.join(entities).lower()
        
        for alias, programme in self.programme_aliases.items():
            if alias in entity_text:
                return programme
        
        # Fuzzy matching against actual programmes
        all_programmes = self.unique_values.get('programme', [])
        for programme in all_programmes:
            programme_words = programme.lower().split()
            matches = sum(1 for word in programme_words 
                         if any(word in entity.lower() for entity in entities))
            if matches >= 2:
                return programme
        
        return None

    def _extract_multiple_programmes(self, entities: List[str]) -> List[str]:
        """Extract multiple programmes"""
        programmes = []
        entity_text = ' '.join(entities).lower()
        
        for alias, programme in self.programme_aliases.items():
            if alias in entity_text and programme not in programmes:
                programmes.append(programme)
        
        return programmes

    def _extract_subject(self, entities: List[str]) -> Optional[str]:
        """Extract single subject"""
        entity_text = ' '.join(entities).lower()
        
        for alias, subjects in self.subject_aliases.items():
            if alias in entity_text:
                if len(subjects) == 1:
                    return subjects[0]
                else:
                    return f"AMBIGUOUS:{','.join(subjects)}"
        
        # Fuzzy matching
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

    def _extract_multiple_subjects(self, entities: List[str]) -> List[str]:
        """Extract multiple subjects"""
        subjects = []
        entity_text = ' '.join(entities).lower()
        
        for alias, subject_list in self.subject_aliases.items():
            if alias in entity_text:
                subjects.extend(subject_list)
        
        return subjects

    def _extract_gender(self, entities: List[str]) -> Optional[str]:
        """Extract gender"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['female', 'women', 'woman', 'girl', 'girls']):
            return 'Female'
        elif any(word in entity_text for word in ['male', 'men', 'man', 'boy', 'boys']):
            return 'Male'
        
        return None

    def _extract_multiple_genders(self, entities: List[str]) -> List[str]:
        """Extract multiple genders"""
        entity_text = ' '.join(entities).lower()
        genders = []
        
        if any(word in entity_text for word in ['female', 'women', 'woman', 'girl', 'girls']):
            genders.append('Female')
        if any(word in entity_text for word in ['male', 'men', 'man', 'boy', 'boys']):
            genders.append('Male')
        
        return genders

    def _extract_race(self, entities: List[str]) -> Optional[str]:
        """Extract race"""
        race_map = {
            'chinese': 'CHINESE', 'malay': 'MALAY', 'indian': 'INDIAN', 
            'others': 'OTHERS', 'other': 'OTHERS'
        }
        
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in race_map:
                return race_map[entity_lower]
        
        return None

    def _extract_multiple_races(self, entities: List[str]) -> List[str]:
        """Extract multiple races"""
        race_map = {
            'chinese': 'CHINESE', 'malay': 'MALAY', 'indian': 'INDIAN', 
            'others': 'OTHERS', 'other': 'OTHERS'
        }
        races = []
        
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in race_map and race_map[entity_lower] not in races:
                races.append(race_map[entity_lower])
        
        return races

    def _extract_country(self, entities: List[str]) -> Optional[str]:
        """Extract country"""
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.country_aliases:
                return self.country_aliases[entity_lower]
        
        return None

    def _extract_multiple_countries(self, entities: List[str]) -> List[str]:
        """Extract multiple countries"""
        countries = []
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.country_aliases:
                country = self.country_aliases[entity_lower]
                if country not in countries:
                    countries.append(country)
        
        return countries

    def _extract_cohort_enhanced(self, entities: List[str]) -> Optional[str]:
        """Enhanced cohort extraction"""
        
        # Method 1: Direct YYYYMM format
        for entity in entities:
            if re.match(r'^\d{6}, entity):
                return entity
        
        # Method 2: Month + Year combination
        found_month = None
        found_year = None
        
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in self.month_mapping:
                found_month = self.month_mapping[entity_lower]
        
        for entity in entities:
            if re.match(r'^20\d{2}, entity):
                found_year = entity
        
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
        for entity in entities:
            if re.match(r'^\d{6}, entity):
                cohorts.append(entity)
        return cohorts

    def _extract_year(self, entities: List[str]) -> Optional[str]:
        """Extract year"""
        for entity in entities:
            if re.match(r'^20\d{2}, entity):
                return entity
        return None

    def _extract_multiple_years(self, entities: List[str]) -> List[str]:
        """Extract multiple years"""
        years = []
        for entity in entities:
            if re.match(r'^20\d{2}, entity):
                years.append(entity)
        return years

    def _extract_academic_year(self, entities: List[str]) -> Optional[str]:
        """Extract academic year"""
        entity_text = ' '.join(entities).lower()
        
        # Look for patterns like "2023/2024", "2023-2024"
        pattern = r'(20\d{2})[-/](20\d{2})'
        match = re.search(pattern, entity_text)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        
        return None

    def _extract_semester(self, entities: List[str]) -> Optional[str]:
        """Extract semester"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['semester 1', 'sem 1', 'first semester']):
            return 'semester_1'
        elif any(word in entity_text for word in ['semester 2', 'sem 2', 'second semester']):
            return 'semester_2'
        elif any(word in entity_text for word in ['semester 3', 'sem 3', 'third semester']):
            return 'semester_3'
        
        return None

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
                grade = self.grade_mapping[entity_lower]
                if grade not in grades:
                    grades.append(grade)
        return grades

    def _extract_cgpa_range(self, entities: List[str]) -> Tuple[Optional[float], Optional[float]]:
        """Extract CGPA range"""
        cgpa_min = None
        cgpa_max = None
        entity_text = ' '.join(entities).lower()
        
        # Look for patterns
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

    def _extract_exact_cgpa(self, entities: List[str]) -> Optional[float]:
        """Extract exact CGPA value"""
        entity_text = ' '.join(entities).lower()
        
        # Look for exact CGPA patterns
        exact_match = re.search(r'(?:cgpa|gpa)\s*(?:is|=|equals?)\s*(\d+\.?\d*)', entity_text)
        if exact_match:
            return float(exact_match.group(1))
        
        # Look for standalone CGPA values
        for entity in entities:
            if re.match(r'^\d\.\d{1,2}, entity):
                return float(entity)
        
        return None

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

    def _extract_sponsor(self, entities: List[str]) -> Optional[str]:
        """Extract sponsor"""
        entity_text = ' '.join(entities).lower()
        
        for alias, sponsor in self.sponsor_aliases.items():
            if alias in entity_text:
                return sponsor
        
        return None

    def _extract_multiple_sponsors(self, entities: List[str]) -> List[str]:
        """Extract multiple sponsors"""
        sponsors = []
        entity_text = ' '.join(entities).lower()
        
        for alias, sponsor in self.sponsor_aliases.items():
            if alias in entity_text and sponsor not in sponsors:
                sponsors.append(sponsor)
        
        return sponsors

    def _extract_aggregation_type(self, entities: List[str]) -> Optional[AggregationType]:
        """Extract aggregation type"""
        entity_text = ' '.join(entities).lower()
        
        if any(word in entity_text for word in ['count', 'how many', 'number of']):
            return AggregationType.COUNT
        elif any(word in entity_text for word in ['average', 'avg', 'mean']):
            return AggregationType.AVERAGE
        elif any(word in entity_text for word in ['sum', 'total']):
            return AggregationType.SUM
        elif any(word in entity_text for word in ['maximum', 'max', 'highest']):
            return AggregationType.MAX
        elif any(word in entity_text for word in ['minimum', 'min', 'lowest']):
            return AggregationType.MIN
        elif any(word in entity_text for word in ['median']):
            return AggregationType.MEDIAN
        
        return None

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

    def _extract_grouping_fields(self, entities: List[str]) -> List[str]:
        """Extract grouping fields"""
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

    def _extract_sorting(self, entities: List[str]) -> Tuple[Optional[str], Optional[SortOrder]]:
        """Extract sorting field and order"""
        entity_text = ' '.join(entities).lower()
        sorting_field = None
        sorting_order = None
        
        if any(word in entity_text for word in ['top', 'best', 'highest']):
            sorting_order = SortOrder.DESC
        elif any(word in entity_text for word in ['bottom', 'worst', 'lowest']):
            sorting_order = SortOrder.ASC
        
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

    def _extract_offset(self, entities: List[str]) -> Optional[int]:
        """Extract offset for pagination"""
        entity_text = ' '.join(entities).lower()
        
        offset_match = re.search(r'offset\s*(\d+)', entity_text)
        if offset_match:
            return int(offset_match.group(1))
        
        return None

    def _extract_time_period(self, entities: List[str]) -> Optional[str]:
        """Extract time period"""
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
        """Detect trend analysis"""
        entity_text = ' '.join(entities).lower()
        trend_keywords = ['trend', 'over time', 'growth', 'decline', 'increase', 'decrease', 'change']
        return any(keyword in entity_text for keyword in trend_keywords)

    def _log_processed_slots(self, slots: ProcessedSlots):
        """Log processed slots for debugging"""
        print(f"DEBUG: Processed slots summary:")
        print(f"  - Student: {slots.student_id}")
        print(f"  - Programme: {slots.programme}, Multiple: {slots.programmes}")
        print(f"  - Subject: {slots.subject}, Multiple: {slots.subjects}")
        print(f"  - Gender: {slots.gender}, Multiple: {slots.genders}")
        print(f"  - Race: {slots.race}, Multiple: {slots.races}")
        print(f"  - Country: {slots.country}, Multiple: {slots.countries}")
        print(f"  - Cohort: {slots.cohort}, Multiple: {slots.cohorts}")
        print(f"  - Year: {slots.year}, Multiple: {slots.years}")
        print(f"  - CGPA range: {slots.cgpa_min} - {slots.cgpa_max}")
        print(f"  - Sponsor: {slots.sponsor}, Multiple: {slots.sponsors}")
        print(f"  - Has scholarship: {slots.has_scholarship}")
        print(f"  - Aggregation: {slots.aggregation_type}")
        print(f"  - Sorting: {slots.sorting_field} {slots.sorting_order}")
        print(f"  - Limit: {slots.limit}")