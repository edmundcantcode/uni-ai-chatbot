# main_processor.py - Main intent processing orchestrator

import json
import time
from typing import Dict, List, Any
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import get_session

from intent_enums import Intent, QueryContext, QueryResult, ProcessedSlots
from llm_classifier import AdvancedLLMClassifier
from entity_processor import AdvancedEntityProcessor
from query_builder import AdvancedQueryBuilder

class ComprehensiveIntentProcessor:
    """Main processor that orchestrates the complete intent handling pipeline"""
    
    def __init__(self, llm: LlamaLLM, unique_values: Dict[str, List[str]]):
        self.llm = llm
        self.classifier = AdvancedLLMClassifier(llm)
        self.entity_processor = AdvancedEntityProcessor(unique_values)
        self.query_builder = AdvancedQueryBuilder()
        
        # Cache for session management
        self.session_cache = {}

    async def process_query(self, query: str, user_id: str, user_role: str, session_id: str = None) -> QueryResult:
        """
        Main processing pipeline - handles all types of queries comprehensively
        """
        
        start_time = time.time()
        
        try:
            # Step 1: Create query context
            context = self._create_context(query, user_id, user_role, session_id)
            
            print(f"DEBUG: Processing query: '{query}' for user {user_id} ({user_role})")
            
            # Step 2: Intent classification
            intent_result = await self.classifier.classify_intent(query, context)
            
            print(f"DEBUG: Classified intent: {intent_result.intent} (confidence: {intent_result.confidence})")
            print(f"DEBUG: Complexity: {intent_result.complexity}")
            print(f"DEBUG: Raw entities: {intent_result.raw_entities}")
            
            # Step 3: Handle unknown intents
            if intent_result.intent == Intent.UNKNOWN or intent_result.confidence < 0.3:
                return self._handle_unknown_intent(query, context, start_time)
            
            # Step 4: Entity processing
            processed_slots = self.entity_processor.process_entities(
                intent_result.raw_entities, 
                context, 
                intent_result.complexity.value
            )
            
            # Step 5: Handle ambiguous entities
            if processed_slots.subject and processed_slots.subject.startswith('AMBIGUOUS:'):
                return self._handle_ambiguous_subject(processed_slots.subject, query, start_time)
            
            # Step 6: Generate CQL query
            cql_query = self.query_builder.generate_query(intent_result.intent, processed_slots, context)
            
            if not cql_query:
                return QueryResult(
                    success=False,
                    message="Could not generate a database query for this request. Please try rephrasing.",
                    error_details="Query generation failed",
                    execution_time=time.time() - start_time
                )
            
            # Step 7: Execute query
            execution_result = await self._execute_query(cql_query, start_time)
            if not execution_result.success:
                return execution_result
            
            # Step 8: Format response based on intent type
            if intent_result.is_yes_no:
                return await self._handle_yes_no_response(
                    query, execution_result.data, intent_result.intent, cql_query, start_time
                )
            else:
                return self._format_standard_response(
                    intent_result.intent, execution_result.data, query, 
                    cql_query, processed_slots, start_time
                )
            
        except Exception as e:
            print(f"ERROR: Processing failed: {str(e)}")
            return QueryResult(
                success=False,
                message=f"An error occurred while processing your query: {str(e)}",
                error_details=str(e),
                execution_time=time.time() - start_time
            )

    def _create_context(self, query: str, user_id: str, user_role: str, session_id: str = None) -> QueryContext:
        """Create query context with session history"""
        
        # Get session history
        previous_queries = []
        if session_id and session_id in self.session_cache:
            previous_queries = self.session_cache[session_id][-5:]  # Last 5 queries
        
        context = QueryContext(
            user_id=user_id,
            user_role=user_role,
            original_query=query,
            session_id=session_id,
            previous_queries=previous_queries
        )
        
        # Update session cache
        if session_id:
            if session_id not in self.session_cache:
                self.session_cache[session_id] = []
            self.session_cache[session_id].append(query)
            
            # Limit session history
            if len(self.session_cache[session_id]) > 20:
                self.session_cache[session_id] = self.session_cache[session_id][-20:]
        
        return context

    async def _execute_query(self, cql_query: str, start_time: float) -> QueryResult:
        """Execute CQL query with comprehensive error handling"""
        
        try:
            print(f"DEBUG: Executing CQL: {cql_query}")
            
            session = get_session()
            result = session.execute(cql_query)
            
            # Convert results to list of dictionaries
            results_data = []
            for row in result:
                row_dict = {}
                for column in row._fields:
                    value = getattr(row, column)
                    row_dict[column] = str(value) if value is not None else ""
                results_data.append(row_dict)
            
            print(f"DEBUG: Query returned {len(results_data)} results")
            
            return QueryResult(
                success=True,
                message="Query executed successfully",
                data=results_data,
                count=len(results_data),
                cql_query=cql_query,
                execution_time=time.time() - start_time
            )
            
        except Exception as db_error:
            error_msg = str(db_error)
            print(f"DEBUG: Database error: {error_msg}")
            
            # Handle specific database errors
            if "LIKE restriction" in error_msg:
                return QueryResult(
                    success=False,
                    message="This search requires proper database indexing. Please try a more specific query.",
                    error_details=f"Database indexing issue: {error_msg}",
                    suggestions=["Try using exact values instead of partial matches"],
                    execution_time=time.time() - start_time
                )
            elif "Undefined column" in error_msg:
                return QueryResult(
                    success=False,
                    message="Database schema issue. Please contact support.",
                    error_details=f"Schema error: {error_msg}",
                    execution_time=time.time() - start_time
                )
            elif "Invalid query" in error_msg:
                return QueryResult(
                    success=False,
                    message="The query format is invalid. Please try rephrasing your request.",
                    error_details=f"Query syntax error: {error_msg}",
                    suggestions=["Try using simpler language", "Be more specific about what you're looking for"],
                    execution_time=time.time() - start_time
                )
            else:
                return QueryResult(
                    success=False,
                    message="Database error occurred. Please try again or contact support.",
                    error_details=f"Database error: {error_msg}",
                    execution_time=time.time() - start_time
                )

    def _handle_unknown_intent(self, query: str, context: QueryContext, start_time: float) -> QueryResult:
        """Handle unknown intents with helpful suggestions"""
        
        suggestions = [
            "Try asking about student counts (e.g., 'How many students are enrolled?')",
            "Ask for specific student information (e.g., 'What is my CGPA?')",
            "Query about programmes (e.g., 'Students in Computer Science')",
            "Ask about scholarships (e.g., 'Students with scholarships')",
            "Try demographic queries (e.g., 'How many female students?')"
        ]
        
        return QueryResult(
            success=False,
            message="I'm not sure what you're looking for. Could you try rephrasing your question?",
            error_details="Intent classification failed",
            suggestions=suggestions,
            execution_time=time.time() - start_time
        )

    def _handle_ambiguous_subject(self, ambiguous_subject: str, query: str, start_time: float) -> QueryResult:
        """Handle ambiguous subject references"""
        
        subjects = ambiguous_subject.replace('AMBIGUOUS:', '').split(',')
        
        return QueryResult(
            success=False,
            message=f"Multiple subjects found. Which one did you mean: {', '.join(subjects)}?",
            error_details="Ambiguous subject reference",
            suggestions=[f"Try '{subject}'" for subject in subjects],
            metadata={"clarification_type": "subject", "choices": subjects},
            execution_time=time.time() - start_time
        )

    async def _handle_yes_no_response(self, query: str, data: List[Dict], intent: Intent, cql: str, start_time: float) -> QueryResult:
        """Handle yes/no questions with LLM explanations"""
        
        explanation = await self._generate_yes_no_explanation(query, data)
        
        return QueryResult(
            success=True,
            message=explanation,
            data=data,
            count=len(data),
            metadata={"is_yes_no": True, "intent": intent.value},
            cql_query=cql,
            execution_time=time.time() - start_time
        )

    async def _generate_yes_no_explanation(self, query: str, data: List[Dict]) -> str:
        """Generate explanatory responses for yes/no questions"""
        
        prompt = f"""The user asked: "{query}"

Database results: {json.dumps(data[:1])}

Based on the results, provide a clear yes/no answer with explanation.

Rules:
- If grade is not 'F' and not empty → "Yes, you passed!"
- If grade is 'F' → "No, you did not pass"
- If no results → "No information found"
- For enrollment: If graduated=false → "Yes, enrolled", if graduated=true → "No, graduated"
- For scholarships: If sponsorname exists → "Yes, has scholarship", else → "No scholarship"
- Include relevant details (grade, percentage, sponsor name, etc.)
- Be encouraging and helpful

Examples:
- "Yes, you passed Programming Principles! You got a B grade with 75% overall. Well done! 👍"
- "Yes, you are currently enrolled in the BSc Computer Science programme."
- "Yes, you have a Jeffrey Cheah Foundation scholarship."

Generate response:"""
        
        try:
            response = await self.llm.generate_response(prompt, temperature=0.3)
            return response.strip()
        except Exception as e:
            print(f"DEBUG: LLM explanation failed: {e}")
            # Fallback logic
            if data:
                if 'grade' in data[0] and data[0]['grade'] not in ['F', '']:
                    return "Yes, based on the records found."
                elif 'graduated' in data[0] and data[0]['graduated'] == 'false':
                    return "Yes, you are currently enrolled."
                elif 'sponsorname' in data[0] and data[0]['sponsorname']:
                    return "Yes, you have financial aid/scholarship."
                else:
                    return "Based on the records, the answer appears to be no."
            else:
                return "No information found in the database."

    def _format_standard_response(self, intent: Intent, data: List[Dict], query: str, 
                                 cql: str, slots: ProcessedSlots, start_time: float) -> QueryResult:
        """Format standard responses based on intent type"""
        
        response = QueryResult(
            success=True,
            data=data,
            count=len(data),
            metadata={"intent": intent.value},
            cql_query=cql,
            execution_time=time.time() - start_time
        )
        
        # Intent-specific message formatting
        if intent in [Intent.COUNT_STUDENTS, Intent.COUNT_PROGRAMME_STUDENTS, 
                     Intent.COUNT_COHORT_STUDENTS, Intent.COUNT_SCHOLARSHIP_RECIPIENTS,
                     Intent.COUNT_BY_GENDER, Intent.COUNT_BY_RACE, Intent.COUNT_BY_COUNTRY]:
            
            if data and 'count' in data[0]:
                count = int(data[0]['count'])
                response.message = f"There are {count} students matching your criteria."
                response.count = count
            else:
                response.message = "No students found matching your criteria."
                
        elif intent in [Intent.GET_TOP_STUDENTS, Intent.GET_BOTTOM_STUDENTS, Intent.RANK_STUDENTS]:
            limit = slots.limit or 10
            response.message = f"Here are the top {min(len(data), limit)} students based on your criteria."
            
        elif intent == Intent.COMPARE_PROGRAMMES:
            response.message = f"Programme comparison completed for {len(data)} programmes."
            
        elif intent == Intent.COHORT_ANALYSIS:
            response.message = f"Cohort analysis completed for {len(data)} cohorts."
            
        elif intent == Intent.DEMOGRAPHIC_ANALYSIS:
            response.message = f"Demographic analysis completed with {len(data)} groups."
            
        elif intent in [Intent.GET_SCHOLARSHIP_STUDENTS, Intent.GET_FINANCIAL_AID, Intent.LIST_FINANCIAL_AID]:
            response.message = f"Found {len(data)} students with financial aid matching your criteria."
            
        elif intent in [Intent.GET_CURRENT_STUDENTS, Intent.GET_GRADUATED_STUDENTS]:
            status = "currently enrolled" if intent == Intent.GET_CURRENT_STUDENTS else "graduated"
            response.message = f"Found {len(data)} students who are {status}."
            
        elif intent == Intent.PERFORMANCE_ANALYSIS:
            response.message = f"Performance analysis completed with statistical data."
            
        elif intent == Intent.GET_STATISTICS:
            if data:
                response.message = "Statistical analysis completed."
            else:
                response.message = "No statistical data found for your criteria."
                
        else:
            # Default message for other intents
            response.message = f"Found {len(data)} matching records."
        
        return response

    # Utility methods for advanced features
    async def handle_follow_up_query(self, query: str, context: QueryContext, previous_result: QueryResult) -> QueryResult:
        """Handle follow-up queries that reference previous results"""
        
        # Add context from previous query
        context.previous_queries.append(f"Previous: {previous_result.metadata.get('intent', 'unknown')}")
        
        return await self.process_query(query, context.user_id, context.user_role, context.session_id)

    def get_query_suggestions(self, partial_query: str, context: QueryContext) -> List[str]:
        """Get query suggestions based on partial input"""
        
        suggestions = []
        partial_lower = partial_query.lower()
        
        if 'how many' in partial_lower:
            suggestions.extend([
                "How many students are enrolled?",
                "How many female students are there?",
                "How many students are in Computer Science?",
                "How many students have scholarships?"
            ])
        elif 'show' in partial_lower or 'list' in partial_lower:
            suggestions.extend([
                "Show students from Malaysia",
                "List students in Computer Science",
                "Show top 10 students",
                "List students with scholarships"
            ])
        elif 'my' in partial_lower and context.user_role == 'student':
            suggestions.extend([
                "What is my CGPA?",
                "Show my grades",
                "What programme am I in?",
                "Do I have a scholarship?"
            ])
        
        return suggestions[:5]  # Limit to 5 suggestions

    def clear_session_cache(self, session_id: str = None):
        """Clear session cache"""
        if session_id:
            self.session_cache.pop(session_id, None)
        else:
            self.session_cache.clear()


# Example usage and testing
async def test_comprehensive_system():
    """Test the comprehensive system with all query types"""
    
    unique_values = {
        'programme': ['BSc (Hons) in Computer Science', 'BSc (Hons) Information Technology'],
        'subjectname': ['OperatingSystemFundamentals', 'ComputerVision', 'PrinciplesofEntrepreneurship'],
        'country': ['MALAYSIA', 'INDONESIA', 'IRAN']
    }
    
    llm = LlamaLLM()
    processor = ComprehensiveIntentProcessor(llm, unique_values)
    
    # Test queries covering all the examples from your image
    test_queries = [
        # Basic enrollment and status queries
        ("How many students are currently enrolled?", "admin", "admin"),
        ("Count students in Computer Science that are active", "admin", "admin"),
        ("How many female students are there?", "admin", "admin"),
        ("How many students are in cohort March 2022?", "admin", "admin"),
        ("Count students from Malaysia", "admin", "admin"),
        ("How many Chinese students are there?", "admin", "admin"),
        
        # Listing and display queries
        ("Show students from Malaysia", "admin", "admin"),
        ("Students who are female", "admin", "admin"),
        ("List students in Computer Science", "admin", "admin"),
        ("Students who started in 2023", "admin", "admin"),
        ("Chinese students from cohort 2023", "admin", "admin"),
        ("Students who graduated in 2023", "admin", "admin"),
        
        # Student-specific queries
        ("Show grades for student 5818844", "admin", "admin"),
        ("Get CGPA for student 5818844", "admin", "admin"),
        ("Show all subjects for student 5818844", "admin", "admin"),
        ("What programme is student 5818844 in?", "admin", "admin"),
        
        # Financial aid and scholarship queries
        ("Students with scholarships", "admin", "admin"),
        ("Students who received Jeffrey Cheah scholarship", "admin", "admin"),
        ("List all financial aid recipients", "admin", "admin"),
        ("Count students with scholarships", "admin", "admin"),
        
        # Student role queries
        ("What is my CGPA?", "6983255", "student"),
        ("Show my grades", "6983255", "student"),
        ("Did I pass Programming Principles?", "6983255", "student"),
        ("Do I have a scholarship?", "6983255", "student"),
        
        # Complex analytical queries
        ("Compare average CGPA between Computer Science and IT students", "admin", "admin"),
        ("Top 10 students with highest CGPA", "admin", "admin"),
        ("Students with CGPA above 3.5", "admin", "admin"),
        ("Demographic analysis by gender and programme", "admin", "admin"),
        ("Cohort analysis for 2022 and 2023", "admin", "admin"),
    ]
    
    print("🚀 Testing Comprehensive Intent System")
    print("=" * 80)
    
    for i, (query, user_id, role) in enumerate(test_queries, 1):
        print(f"\n[Test {i}/    queries")
        print(f"Query: '{query}'")
        print(f"User: {user_id} ({role})")
        print("-" * 60)
        
        try:
            result = await processor.process_query(query, user_id, role, f"session_{role}")
            
            if result.success:
                print(f"✅ SUCCESS: {result.message}")
                print(f"📊 Results: {result.count} records")
                if result.metadata.get('is_yes_no'):
                    print(f"❓ Yes/No Question Response")
                print(f"🎯 Intent: {result.metadata.get('intent', 'unknown')}")
                print(f"⏱️  Execution Time: {result.execution_time:.3f}s")
                
                # Show sample data for non-count queries
                if result.data and len(result.data) > 0 and result.count != 1:
                    print(f"📄 Sample Data: {result.data[0]}")
                    
            else:
                print(f"❌ FAILED: {result.message}")
                if result.error_details:
                    print(f"🐛 Error: {result.error_details}")
                if result.suggestions:
                    print(f"💡 Suggestions: {', '.join(result.suggestions[:3])}")
            
            if result.cql_query:
                print(f"🔍 CQL: {result.cql_query}")
                
        except Exception as e:
            print(f"💥 EXCEPTION: {str(e)}")
    
    print("\n" + "=" * 80)
    print("🏁 Testing Complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_comprehensive_system())