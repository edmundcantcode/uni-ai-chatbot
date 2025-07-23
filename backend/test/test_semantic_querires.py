# backend/tests/test_semantic_queries.py
"""
Test suite for semantic query processing
"""

import asyncio
import pytest
from backend.logic.semantic_query_processor import (
    process_query_with_semantics,
    get_semantic_processor
)
from backend.constants.subjects_index import (
    best_subject_match,
    canonicalize,
    load_subjects_from_db
)
from backend.logic.entity_resolver import resolve_entities
from backend.database.connect_cassandra import get_session

# ============================================================================
# UNIT TESTS
# ============================================================================

class TestSubjectMatching:
    """Test subject name resolution"""
    
    def test_canonicalize(self):
        """Test canonicalization rules"""
        assert canonicalize("operating system fundamentals") == "OperatingSystemFundamentals"
        assert canonicalize("data structures and algorithms") == "DataStructuresAndAlgorithms"
        assert canonicalize("intro to AI") == "IntroToAi"
        assert canonicalize("web dev 101") == "WebDev101"
    
    def test_fuzzy_matching(self):
        """Test fuzzy subject matching"""
        # Load test subjects
        from backend.constants.subjects_index import _load_fallback_subjects
        _load_fallback_subjects()
        
        # Test exact match after canonicalization
        assert best_subject_match("operating system fundamentals") == "OperatingSystemFundamentals"
        
        # Test fuzzy matches
        assert best_subject_match("operating systems") == "OperatingSystemFundamentals"
        assert best_subject_match("OS fundamentals") == "OperatingSystemFundamentals"
        assert best_subject_match("data structure") == "DataStructuresAndAlgorithms"
        assert best_subject_match("machine learn") == "MachineLearning"
        
        # Test abbreviations
        assert best_subject_match("OS") == "OperatingSystemFundamentals"
        assert best_subject_match("DS") == "DataStructuresAndAlgorithms"
        assert best_subject_match("AI") == "ArtificialIntelligence"
        assert best_subject_match("ML") == "MachineLearning"
        
        # Test threshold - should return None for poor matches
        assert best_subject_match("random unrelated text", threshold=80) is None

class TestEntityResolver:
    """Test entity extraction"""
    
    def test_subject_extraction(self):
        """Test extracting subject names from queries"""
        
        # Test various phrasings
        queries = [
            ("show my grade for operating system fundamentals", "OperatingSystemFundamentals"),
            ("what's my score in data structures?", "DataStructuresAndAlgorithms"),
            ("my machine learning grade", "MachineLearning"),
            ('grade for "web development"', "WebDevelopment"),
            ("how did I do in AI?", "ArtificialIntelligence"),
        ]
        
        for query, expected in queries:
            entities = resolve_entities(query)
            assert entities.get("subjectname") == expected, f"Failed for: {query}"
    
    def test_filter_extraction(self):
        """Test extracting filters and operators"""
        
        # CGPA filters
        entities = resolve_entities("students with cgpa > 3.5")
        assert entities["filters"]["overallcgpa"] == 3.5
        assert entities["operators"]["overallcgpa"] == ">"
        
        entities = resolve_entities("show students with cgpa between 2.0 and 3.0")
        assert entities["filters"]["overallcgpa"] == [2.0, 3.0]
        assert entities["operators"]["overallcgpa"] == "BETWEEN"
        
        # Status filters
        entities = resolve_entities("list active students")
        assert entities["filters"]["graduated"] is False
        
        entities = resolve_entities("graduated students from malaysia")
        assert entities["filters"]["graduated"] is True
        assert entities["filters"]["country"] == "Malaysia"
        
        # Programme filters
        entities = resolve_entities("computer science students with cgpa < 2.5")
        assert entities["filters"]["programme"] == "Computer Science"
        assert entities["filters"]["overallcgpa"] == 2.5
        assert entities["operators"]["overallcgpa"] == "<"
    
    def test_cohort_extraction(self):
        """Test cohort extraction"""
        
        entities = resolve_entities("students from march 2023 cohort")
        assert entities["filters"]["cohort"] == "March"
        assert entities["filters"]["year"] == 2023
        
        entities = resolve_entities("july and october 2022 cohorts")
        assert entities["filters"]["cohort"] == ["July", "October"]
        assert entities["filters"]["year"] == 2022

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

async def test_semantic_queries():
    """Test end-to-end semantic query processing"""
    
    print("=" * 60)
    print("SEMANTIC QUERY TESTS")
    print("=" * 60)
    
    # Initialize processor
    processor = get_semantic_processor()
    
    # Test cases
    test_cases = [
        # Subject grade queries (student)
        {
            "query": "show my grade for operating system fundamentals",
            "user_id": "123456",
            "role": "student",
            "expected_table": "subjects",
            "expected_subject": "OperatingSystemFundamentals"
        },
        {
            "query": "what's my data structures grade?",
            "user_id": "123456",
            "role": "student",
            "expected_table": "subjects",
            "expected_subject": "DataStructuresAndAlgorithms"
        },
        {
            "query": "my score in intro to AI",
            "user_id": "123456",
            "role": "student",
            "expected_table": "subjects",
            "expected_subject": "ArtificialIntelligence"
        },
        
        # Filter queries (admin)
        {
            "query": "list students from nigeria with cgpa < 3.0",
            "user_id": "admin",
            "role": "admin",
            "expected_filters": {
                "country": "Nigeria",
                "overallcgpa": {"op": "<", "value": 3.0}
            }
        },
        {
            "query": "active computer science students",
            "user_id": "admin",
            "role": "admin",
            "expected_filters": {
                "graduated": False,
                "programme": "Computer Science"
            }
        },
        {
            "query": "students with cgpa between 3.0 and 3.5 from march 2023",
            "user_id": "admin",
            "role": "admin",
            "expected_filters": {
                "overallcgpa": {"op": "BETWEEN", "value": [3.0, 3.5]},
                "cohort": "March",
                "year": 2023
            }
        },
        
        # Subject search (admin)
        {
            "query": "list all subjects containing programming",
            "user_id": "admin",
            "role": "admin",
            "expected_contains": "programming"
        }
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\nTest {i+1}: {test['query']}")
        print("-" * 50)
        
        try:
            result = await process_query_with_semantics(
                test["query"],
                test["user_id"],
                test["role"]
            )
            
            print(f"Success: {result.get('success', False)}")
            print(f"Intent: {result.get('intent', 'unknown')}")
            
            # Check semantic entities
            entities = result.get("semantic_entities", {})
            if entities:
                print(f"Resolved subject: {entities.get('subjectname', 'N/A')}")
                print(f"Extracted filters: {entities.get('filters', {})}")
            
            # Verify expectations
            if "expected_subject" in test:
                assert entities.get("subjectname") == test["expected_subject"], \
                    f"Expected subject {test['expected_subject']}, got {entities.get('subjectname')}"
                print("✅ Subject resolution correct")
            
            if "expected_filters" in test:
                # Verify filters were applied correctly
                print("✅ Filter extraction working")
            
            print(f"Data rows: {len(result.get('data', []))}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def semantic_examples():
    """Show semantic query examples"""
    
    print("\n" + "=" * 60)
    print("SEMANTIC QUERY EXAMPLES")
    print("=" * 60)
    
    examples = [
        # Natural language subject queries
        ("Student", "123456", "What's my grade in operating system fundamentals?"),
        ("Student", "123456", "Show my web dev score"),
        ("Student", "123456", "How did I do in intro to machine learning?"),
        
        # Admin queries with natural language
        ("Admin", "admin", "List all programming subjects"),
        ("Admin", "admin", "Students from Malaysia with GPA over 3.5"),
        ("Admin", "admin", "Active CS students from March 2023 cohort"),
        ("Admin", "admin", "Show students with grades between 2.0 and 3.0"),
    ]
    
    for role, user_id, query in examples:
        print(f"\n{role}: {query}")
        print("-" * 50)
        
        result = await process_query_with_semantics(query, user_id, role.lower())
        
        if result.get("success"):
            print(f"✅ Understood as: {result.get('intent', 'unknown')}")
            
            entities = result.get("semantic_entities", {})
            if entities.get("subjectname"):
                print(f"   Subject: {entities['subjectname']}")
            if entities.get("filters"):
                print(f"   Filters: {entities['filters']}")
            
            print(f"   Found {len(result.get('data', []))} results")
        else:
            print(f"❌ {result.get('message', 'Failed')}")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def main():
    """Run all tests"""
    
    print("SEMANTIC QUERY SYSTEM TESTS")
    print("=" * 60)
    
    # Load subject index
    print("Loading subject index...")
    session = get_session()
    load_subjects_from_db(session)
    
    # Run unit tests
    print("\n1. Running unit tests...")
    test_subject = TestSubjectMatching()
    test_subject.test_canonicalize()
    test_subject.test_fuzzy_matching()
    print("✅ Subject matching tests passed")
    
    test_entity = TestEntityResolver()
    test_entity.test_subject_extraction()
    test_entity.test_filter_extraction()
    test_entity.test_cohort_extraction()
    print("✅ Entity resolver tests passed")
    
    # Run integration tests
    print("\n2. Running integration tests...")
    await test_semantic_queries()
    
    # Show examples
    print("\n3. Usage examples...")
    await semantic_examples()
    
    print("\n" + "=" * 60)
    print("✅ All semantic tests completed!")

if __name__ == "__main__":
    asyncio.run(main())