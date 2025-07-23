#!/usr/bin/env python3
"""
Automated Test Runner for University AI Chatbot
Tests all predefined questions using real database values and generates a comprehensive report
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class TestResult(Enum):
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    ERROR = "🔥 ERROR"
    BLOCKED = "🚫 BLOCKED"
    TIMEOUT = "⏰ TIMEOUT"
    CLARIFICATION = "❓ NEEDS CLARIFICATION"

@dataclass
class TestCase:
    question: str
    expected_behavior: str
    category: str
    priority: str = "HIGH"
    should_work: bool = True
    should_be_blocked: bool = False
    should_need_clarification: bool = False
    timeout_seconds: int = 30

@dataclass
class TestResultData:
    test_case: TestCase
    result: TestResult
    response_data: Dict[str, Any]
    response_time_ms: int
    error_message: str = ""
    notes: str = ""

class ChatbotTestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.results: List[TestResultData] = []
        
        # Define all test cases with real database values
        self.admin_tests = self._define_admin_tests()
        self.student_tests = self._define_student_tests()
        self.edge_case_tests = self._define_edge_case_tests()
    
    def _define_admin_tests(self) -> List[TestCase]:
        """Define admin test cases using real database values"""
        return [
            # === BASIC COUNTING QUERIES ===
            TestCase("How many students are there?", "Should return total student count", "Basic Count"),
            TestCase("Count students in Computer Science", "Should count CS students", "Programme Count"),
            TestCase("Count students in BSc (Hons) in Computer Science", "Should count specific programme", "Programme Count"),
            TestCase("How many female students are there?", "Should count by gender", "Gender Count"),
            TestCase("How many male students are there?", "Should count male students", "Gender Count"),
            TestCase("How many students are in cohort 202301?", "Should count by specific cohort", "Cohort Count"),
            TestCase("Count students from Malaysia", "Should count Malaysian students", "Country Count"),
            TestCase("How many students are from Singapore?", "Should count Singaporean students", "Country Count"),
            TestCase("How many Chinese students are there?", "Should count by race", "Race Count"),
            TestCase("Count Indian students", "Should count Indian students", "Race Count"),
            TestCase("How many Malay students are there?", "Should count Malay students", "Race Count"),
            
            # === PROGRAMME-SPECIFIC QUERIES ===
            TestCase("Students in Bachelor of Software Engineering (Hons)", "Should list software engineering students", "Programme List"),
            TestCase("Count students in Information Systems", "Should count IS students", "Programme Count"),
            TestCase("How many students are in Bachelor of Information Systems (Honours) (Data Analytics)?", "Should count data analytics students", "Programme Count"),
            TestCase("List students in BSc (Hons) Information Technology", "Should list IT students", "Programme List"),
            
            # === STUDENT LISTING QUERIES ===
            TestCase("Show students from Malaysia", "Should list Malaysian students", "Student List"),
            TestCase("Students who are female", "Should list female students", "Gender List"),
            TestCase("Show students from China", "Should list Chinese nationality students", "Country List"),
            TestCase("Students from cohort 202301", "Should list specific cohort students", "Cohort List"),
            TestCase("Chinese students from cohort 202301", "Should filter by race and cohort", "Complex Filter"),
            TestCase("Female students from Malaysia", "Should filter by gender and country", "Complex Filter"),
            
            # === SPECIFIC STUDENT QUERIES ===
            TestCase("Show grades for student 5818844", "Should show student's all grades", "Student Grades"),
            TestCase("Get CGPA for student 5818844", "Should show student's CGPA", "Student CGPA"),
            TestCase("Show all subjects for student 5818844", "Should show all student's subjects", "Student Subjects"),
            TestCase("What programme is student 5818844 in?", "Should show student's programme", "Student Programme"),
            TestCase("Show student 6253786 information", "Should show student profile", "Student Info"),
            TestCase("Is student 5818844 active?", "Should show student status", "Student Status"),
            
            # === SCHOLARSHIP/FINANCIAL AID QUERIES ===
            TestCase("Students with scholarships", "Should list scholarship recipients", "Financial Aid"),
            TestCase("Students who received Jeffrey Cheah scholarship", "Should filter by specific scholarship", "Specific Scholarship"),
            TestCase("List students with Jeffrey Cheah Foundation Scholarship", "Should list specific scholarship recipients", "Scholarship List"),
            TestCase("Count students with scholarships", "Should count scholarship students", "Scholarship Count"),
            TestCase("Students with Sunway scholarships", "Should filter Sunway scholarships", "Scholarship Filter"),
            TestCase("Show all financial aid recipients", "Should list all aid recipients", "Financial Aid List"),
            
            # === PERFORMANCE QUERIES ===
            TestCase("Students with CGPA above 3.5", "Should filter by high CGPA", "Performance Filter"),
            TestCase("Students who failed any subjects", "Should find students with F grades", "Failure Analysis"),
            TestCase("Students with Class I classification", "Should filter by award classification", "Classification Filter"),
            TestCase("Show students with Class II (1) awards", "Should filter by specific classification", "Award Filter"),
            
            # === SUBJECT-SPECIFIC QUERIES ===
            TestCase("Students who took Programming Principles", "Should find students in specific subject", "Subject Analysis"),
            TestCase("Show grades for Programming Principles", "Should show all grades for subject", "Subject Grades"),
            TestCase("Students who failed Programming Principles", "Should find failures in specific subject", "Subject Failure"),
            TestCase("How many students took Database Fundamentals?", "Should count subject enrollment", "Subject Count"),
            
            # === COHORT QUERIES ===
            TestCase("Show students by cohort 202301", "Should filter by specific cohort", "Cohort Filter"),
            TestCase("Students from March 2023 intake", "Should understand cohort format", "Cohort Understanding"),
            TestCase("How many students started in 2023?", "Should count by year", "Year Analysis"),
            
            # === GRADUATION QUERIES ===
            TestCase("Students who graduated", "Should list graduated students", "Graduation Status"),
            TestCase("How many students have graduated?", "Should count graduates", "Graduate Count"),
            TestCase("Students who have not graduated", "Should list current students", "Current Students"),
            
            # === YES/NO QUESTIONS ===
            TestCase("Are there any students from Thailand?", "Should return yes/no answer", "Yes/No Query", "MEDIUM"),
            TestCase("Do we have students in Data Science programme?", "Should check programme existence", "Programme Check", "MEDIUM"),
            TestCase("Are there students from Canada?", "Should check country existence", "Country Check", "MEDIUM"),
            TestCase("Do we have any Jeffrey Cheah scholarship recipients?", "Should check scholarship existence", "Scholarship Check", "MEDIUM"),
            
            # === SHOULD BE BLOCKED FOR ADMIN ===
            TestCase("My grades", "Should be blocked/inappropriate for admin", "Access Control", should_be_blocked=True),
            TestCase("What is my CGPA?", "Should be blocked/inappropriate for admin", "Access Control", should_be_blocked=True),
            TestCase("Show my subjects", "Should be blocked for admin", "Access Control", should_be_blocked=True),
            
            # === COMPLEX ANALYTICAL QUERIES ===
            TestCase("Show students with CGPA between 3.0 and 3.5", "Should filter by CGPA range", "Complex Filter", "MEDIUM"),
            TestCase("Average CGPA by programme", "Should calculate programme averages", "Analytics", "LOW"),
            TestCase("Students from Malaysia in Computer Science", "Should combine country and programme filters", "Complex Filter", "MEDIUM"),
            
            # === ERROR HANDLING CASES ===
            TestCase("Show grades for student 9999999", "Should handle non-existent student gracefully", "Error Handling", "HIGH", should_work=False),
            TestCase("Students in Fake Programme Name", "Should handle non-existent programme", "Error Handling", "MEDIUM", should_work=False),
            TestCase("Count students in Medicine", "Should handle non-existent programme", "Error Handling", "MEDIUM", should_work=False),
            
            # === AMBIGUOUS QUERIES (SHOULD NEED CLARIFICATION) ===
            TestCase("Show me John's grades", "Should ask which John (multiple matches)", "Clarification", "MEDIUM", should_need_clarification=True),
            TestCase("Students named Ahmad", "Should show multiple Ahmad choices", "Multiple Matches", "MEDIUM", should_need_clarification=True),
            TestCase("Show Programming results", "Should clarify which Programming subject", "Subject Clarification", "MEDIUM", should_need_clarification=True),
        ]
    
    def _define_student_tests(self) -> List[TestCase]:
        """Define student test cases for userid 6253786"""
        return [
            # === BASIC STUDENT QUERIES ===
            TestCase("What subjects do I take?", "Should show student's enrolled subjects", "Student Subjects"),
            TestCase("My grades", "Should show all student's grades", "Student Grades"),
            TestCase("What are my grades?", "Should show student's grades", "Student Grades"),
            TestCase("Show my grades", "Should display student's academic results", "Student Grades"),
            TestCase("My current semester grades", "Should show recent grades", "Current Grades"),
            TestCase("Show all my subjects", "Should list all enrolled subjects", "All Subjects"),
            
            # === CGPA/GPA QUERIES ===
            TestCase("What is my CGPA?", "Should show student's overall CGPA", "Student CGPA"),
            TestCase("What is my GPA?", "Should show student's GPA", "Student GPA"),
            TestCase("My academic performance", "Should show performance summary", "Academic Performance"),
            TestCase("How am I doing academically?", "Should show academic status", "Performance Summary"),
            TestCase("My overall average", "Should show cumulative average", "Academic Average"),
            
            # === PROGRAMME AND STATUS INFORMATION ===
            TestCase("What programme am I in?", "Should show student's programme", "Programme Info"),
            TestCase("What course am I studying?", "Should show student's course", "Course Info"),
            TestCase("What is my programme?", "Should display programme name", "Programme Info"),
            TestCase("Am I active?", "Should show enrollment status", "Status Check"),
            TestCase("My enrollment status", "Should show current status", "Status Check"),
            TestCase("Have I graduated?", "Should show graduation status", "Graduation Status"),
            TestCase("What is my student status?", "Should show academic status", "Academic Status"),
            
            # === COHORT AND INTAKE INFORMATION ===
            TestCase("What is my cohort?", "Should show student's cohort", "Cohort Info"),
            TestCase("When did I start?", "Should show start date/cohort", "Start Date"),
            TestCase("My year", "Should show current academic year", "Year Info"),
            TestCase("My intake", "Should show intake information", "Intake Info"),
            TestCase("What cohort am I from?", "Should show cohort details", "Cohort Details"),
            
            # === FINANCIAL AID QUERIES ===
            TestCase("Do I have any scholarships?", "Should show scholarship status", "Scholarship Status"),
            TestCase("My financial aid", "Should show financial aid information", "Financial Aid"),
            TestCase("My scholarship", "Should show scholarship details if any", "Scholarship Details"),
            TestCase("What financial aid do I receive?", "Should list financial assistance", "Aid Details"),
            
            # === DIFFERENT PHRASINGS FOR SAME INTENT ===
            TestCase("Tell me about my academic record", "Should show comprehensive academic info", "Academic Record", "MEDIUM"),
            TestCase("Can you show my results?", "Should display academic results", "Results Display", "MEDIUM"),
            TestCase("What grades did I get?", "Should show grade history", "Grade History", "MEDIUM"),
            TestCase("How did I perform?", "Should show performance summary", "Performance Review", "MEDIUM"),
            TestCase("Show my academic history", "Should display academic timeline", "Academic History", "MEDIUM"),
            
            # === SPECIFIC SUBJECT QUERIES ===
            TestCase("My Programming Principles grade", "Should show specific subject grade", "Subject Grade", "MEDIUM"),
            TestCase("How did I do in Database Fundamentals?", "Should show subject performance", "Subject Performance", "MEDIUM"),
            TestCase("Show my Computer Networks result", "Should display specific subject result", "Subject Result", "MEDIUM"),
            TestCase("What grade did I get in Web Programming?", "Should show subject grade", "Subject Grade Query", "MEDIUM"),
            
            # === TIME-BASED QUERIES ===
            TestCase("My grades from 2023", "Should filter by examination year", "Year Filter", "MEDIUM"),
            TestCase("Show my recent results", "Should show latest grades", "Recent Results", "MEDIUM"),
            TestCase("My first year grades", "Should show early academic results", "Year-based Query", "MEDIUM"),
            
            # === SHOULD BE BLOCKED FOR STUDENTS ===
            TestCase("Show grades for student 5818844", "Should be blocked - other student's data", "Access Control", should_be_blocked=True),
            TestCase("How many students are in my programme?", "Should be blocked - aggregate data", "Access Control", should_be_blocked=True),
            TestCase("List all students from Malaysia", "Should be blocked - admin-only query", "Access Control", should_be_blocked=True),
            TestCase("Show Ahmad's grades", "Should be blocked - other student's data", "Access Control", should_be_blocked=True),
            TestCase("Count female students", "Should be blocked - administrative query", "Access Control", should_be_blocked=True),
            TestCase("Students with scholarships", "Should be blocked - administrative data", "Access Control", should_be_blocked=True),
            
            # === COMPARATIVE QUERIES (MIGHT BE BLOCKED OR LIMITED) ===
            TestCase("How do I compare to other students?", "Should be handled appropriately", "Comparison Query", "LOW"),
            TestCase("Am I performing better than average?", "Should handle comparison request", "Performance Comparison", "LOW"),
        ]
    
    def _define_edge_case_tests(self) -> List[TestCase]:
        """Define edge case and error handling tests"""
        return [
            # === CASE SENSITIVITY TESTS ===
            TestCase("what is my cgpa?", "Should handle lowercase", "Case Sensitivity", "LOW"),
            TestCase("SHOW MY GRADES", "Should handle uppercase", "Case Sensitivity", "LOW"),
            TestCase("My Programming principles grade", "Should handle mixed case", "Case Sensitivity", "LOW"),
            TestCase("students from MALAYSIA", "Should handle country name case", "Case Sensitivity", "LOW"),
            
            # === TYPOS AND MISSPELLINGS ===
            TestCase("Show my greads", "Should handle typo or show helpful error", "Typo Handling", "LOW", should_work=False),
            TestCase("What is my GPA?", "Should handle common alternative term", "Alternative Terms", "MEDIUM"),
            TestCase("My acadmic record", "Should handle typo", "Typo Handling", "LOW", should_work=False),
            TestCase("Programing Principles grade", "Should handle missing letter", "Typo Handling", "LOW"),
            
            # === EMPTY AND INVALID QUERIES ===
            TestCase("", "Should handle empty query gracefully", "Error Handling", "HIGH", should_work=False),
            TestCase("   ", "Should handle whitespace-only query", "Error Handling", "HIGH", should_work=False),
            TestCase("What is the weather today?", "Should handle completely unrelated query", "Unrelated Query", "MEDIUM", should_work=False),
            TestCase("Tell me a joke", "Should handle non-academic request", "Unrelated Query", "LOW", should_work=False),
            
            # === SPECIAL CHARACTERS AND FORMATTING ===
            TestCase("@#$%^&*()", "Should handle special characters", "Special Characters", "LOW", should_work=False),
            TestCase("Student ID: 5,818,844", "Should handle formatted ID with commas", "ID Formatting", "MEDIUM"),
            TestCase("Show student 5818844's grades", "Should handle possessive forms", "Grammar Variations", "MEDIUM"),
            TestCase("What's my CGPA?", "Should handle contractions", "Grammar Variations", "MEDIUM"),
            
            # === VERY LONG QUERIES ===
            TestCase("Can you please show me all of my academic grades and results for all subjects that I have taken during my entire academic career at this university including CGPA and programme information?", "Should handle very long queries", "Long Query", "LOW"),
            
            # === AMBIGUOUS REFERENCES ===
            TestCase("Show Programming grade", "Should ask which Programming subject", "Subject Ambiguity", "MEDIUM", should_need_clarification=True),
            TestCase("My Engineering results", "Should clarify which Engineering subject", "Subject Clarification", "MEDIUM", should_need_clarification=True),
            TestCase("Students in IT", "Should clarify which IT programme", "Programme Ambiguity", "MEDIUM", should_need_clarification=True),
            
            # === NUMERICAL EDGE CASES ===
            TestCase("Student 000123", "Should handle leading zeros", "ID Format", "LOW"),
            TestCase("Show grades for student ID 5818844", "Should handle explicit ID reference", "ID Reference", "MEDIUM"),
            TestCase("Students with CGPA > 4.0", "Should handle mathematical operators", "Math Operators", "LOW"),
            
            # === UNICODE AND ENCODING ===
            TestCase("Students in BSc (Hons) Information Technology", "Should handle special characters in programme names", "Unicode Handling", "MEDIUM"),
            TestCase("Show Malaysia's students", "Should handle special characters", "Unicode Characters", "LOW"),
            
            # === CONTEXT-DEPENDENT QUERIES ===
            TestCase("my", "Should handle single word query", "Minimal Query", "LOW", should_work=False),
            TestCase("grades", "Should handle context-less query", "Context Missing", "LOW"),
            TestCase("show", "Should handle incomplete query", "Incomplete Query", "LOW", should_work=False),
        ]
    
    async def setup_session(self):
        """Setup HTTP session"""
        self.session = aiohttp.ClientSession()
    
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
    
    async def login(self, userid: str, password: str) -> bool:
        """Login and return success status"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/login",
                json={"userid": userid, "password": password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return True
                else:
                    print(f"❌ Login failed for {userid}: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Login error for {userid}: {str(e)}")
            return False
    
    async def send_query(self, query: str, userid: str, role: str) -> Dict[str, Any]:
        """Send query to chatbot and return response"""
        try:
            start_time = time.time()
            
            async with self.session.post(
                f"{self.base_url}/api/chatbot",
                json={"query": query, "userid": userid, "role": role},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "data": data,
                        "response_time_ms": response_time_ms,
                        "status_code": response.status
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}",
                        "response_time_ms": response_time_ms,
                        "status_code": response.status
                    }
                    
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timeout",
                "response_time_ms": 30000,
                "status_code": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time_ms": 0,
                "status_code": 0
            }
    
    def evaluate_response(self, test_case: TestCase, response: Dict[str, Any]) -> TestResult:
        """Evaluate if the response meets expectations"""
        if not response["success"]:
            if "timeout" in response["error"].lower():
                return TestResult.TIMEOUT
            elif test_case.should_work:
                return TestResult.ERROR
            else:
                return TestResult.PASS  # Expected to fail
        
        data = response["data"]
        
        # Check for clarification requests
        if test_case.should_need_clarification:
            if data.get("clarification") or "clarification" in data.get("message", "").lower():
                return TestResult.CLARIFICATION
            else:
                return TestResult.FAIL  # Should have needed clarification
        
        # Check if query should be blocked
        if test_case.should_be_blocked:
            if (data.get("error") or 
                "blocked" in data.get("message", "").lower() or
                "access denied" in data.get("message", "").lower() or
                "unauthorized" in data.get("message", "").lower()):
                return TestResult.BLOCKED
            else:
                return TestResult.FAIL  # Should have been blocked
        
        # Check for errors when expecting success
        if test_case.should_work:
            if data.get("error"):
                return TestResult.FAIL
            elif (data.get("result") is not None or 
                  data.get("message") or 
                  data.get("clarification") or 
                  data.get("confirmation")):
                return TestResult.PASS
            else:
                return TestResult.FAIL
        else:
            # Expected to fail/error
            if data.get("error") or not data.get("result"):
                return TestResult.PASS
            else:
                return TestResult.FAIL
    
    async def run_test_case(self, test_case: TestCase, userid: str, role: str) -> TestResultData:
        """Run a single test case"""
        print(f"  Testing: {test_case.question[:60]}...")
        
        response = await self.send_query(test_case.question, userid, role)
        result = self.evaluate_response(test_case, response)
        
        notes = ""
        if response["success"] and response["data"]:
            data = response["data"]
            if data.get("clarification"):
                notes = "Requires clarification"
            elif data.get("confirmation"):
                notes = "Requires confirmation"
            elif data.get("auto_executed"):
                notes = "Auto-executed"
            elif data.get("result") and len(data["result"]) > 0:
                notes = f"Returned {len(data['result'])} records"
        
        return TestResultData(
            test_case=test_case,
            result=result,
            response_data=response,
            response_time_ms=response.get("response_time_ms", 0),
            error_message=response.get("error", ""),
            notes=notes
        )
    
    async def run_test_suite(self, tests: List[TestCase], userid: str, role: str, suite_name: str):
        """Run a complete test suite"""
        print(f"\n🧪 Running {suite_name} Tests (userid: {userid}, role: {role})")
        print("=" * 70)
        
        # Login first
        login_success = await self.login(userid, userid)  # Using userid as password
        if not login_success:
            print(f"❌ Failed to login as {userid}. Skipping test suite.")
            return
        
        print(f"✅ Logged in successfully as {userid}")
        
        # Run tests
        suite_start_time = time.time()
        for i, test_case in enumerate(tests, 1):
            result = await self.run_test_case(test_case, userid, role)
            self.results.append(result)
            
            # Progress indicator
            progress = f"[{i:2d}/{len(tests):2d}]"
            time_str = f"({result.response_time_ms:4d}ms)"
            print(f"    {progress} {result.result.value} {test_case.question[:45]:<45} {time_str}")
            
            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.1)
        
        suite_time = time.time() - suite_start_time
        print(f"\n📊 {suite_name} suite completed in {suite_time:.1f}s")
    
    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        total_tests = len(self.results)
        if total_tests == 0:
            return "No tests were run."
        
        passed = len([r for r in self.results if r.result == TestResult.PASS])
        failed = len([r for r in self.results if r.result == TestResult.FAIL])
        errors = len([r for r in self.results if r.result == TestResult.ERROR])
        blocked = len([r for r in self.results if r.result == TestResult.BLOCKED])
        timeouts = len([r for r in self.results if r.result == TestResult.TIMEOUT])
        clarifications = len([r for r in self.results if r.result == TestResult.CLARIFICATION])
        
        avg_response_time = sum(r.response_time_ms for r in self.results) / total_tests
        
        # Calculate success rate (passed + blocked + clarifications are considered successful)
        successful = passed + blocked + clarifications
        success_rate = (successful / total_tests) * 100
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            CHATBOT TEST REPORT                               ║
║                          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}      ║                     
╚══════════════════════════════════════════════════════════════════════════════╝

📊 OVERALL SUMMARY:
  Total Tests: {total_tests}
  Success Rate: {success_rate:.1f}% ({successful}/{total_tests})
  
  ✅ Passed: {passed} ({passed/total_tests*100:.1f}%)
  ❌ Failed: {failed} ({failed/total_tests*100:.1f}%)
  🔥 Errors: {errors} ({errors/total_tests*100:.1f}%)
  🚫 Blocked: {blocked} ({blocked/total_tests*100:.1f}%)
  ❓ Clarification: {clarifications} ({clarifications/total_tests*100:.1f}%)
  ⏰ Timeouts: {timeouts} ({timeouts/total_tests*100:.1f}%)
  
⚡ PERFORMANCE METRICS:
  Average Response Time: {avg_response_time:.0f}ms
  Fastest Response: {min(r.response_time_ms for r in self.results)}ms
  Slowest Response: {max(r.response_time_ms for r in self.results)}ms
  Total Test Duration: {sum(r.response_time_ms for r in self.results)/1000:.1f}s

"""
        
        # Group results by category
        categories = {}
        for result in self.results:
            category = result.test_case.category
            if category not in categories:
                categories[category] = []
            categories[category].append(result)
        
        # Sort categories by success rate
        category_stats = []
        for category, results in categories.items():
            category_successful = len([r for r in results if r.result in [TestResult.PASS, TestResult.BLOCKED, TestResult.CLARIFICATION]])
            category_total = len(results)
            success_rate = (category_successful / category_total) * 100
            category_stats.append((category, results, category_successful, category_total, success_rate))
        
        category_stats.sort(key=lambda x: x[4], reverse=True)  # Sort by success rate
        
        for category, results, category_successful, category_total, success_rate in category_stats:
            report += f"\n📁 {category.upper()} ({category_successful}/{category_total} successful - {success_rate:.0f}%):\n"
            report += "-" * 70 + "\n"
            
            for result in results:
                status_icon = result.result.value.split()[0]
                time_str = f"({result.response_time_ms}ms)"
                notes_str = f" - {result.notes}" if result.notes else ""
                
                report += f"  {status_icon} {result.test_case.question[:40]:<40} {time_str:>8}{notes_str}\n"
                
                if result.result in [TestResult.FAIL, TestResult.ERROR] and result.error_message:
                    report += f"      💥 Error: {result.error_message[:80]}\n"
        
        # Priority analysis
        priority_stats = {}
        for result in self.results:
            priority = result.test_case.priority
            if priority not in priority_stats:
                priority_stats[priority] = {'total': 0, 'passed': 0}
            priority_stats[priority]['total'] += 1
            if result.result in [TestResult.PASS, TestResult.BLOCKED, TestResult.CLARIFICATION]:
                priority_stats[priority]['passed'] += 1
        
        report += f"\n\n🎯 PRIORITY ANALYSIS:\n"
        report += "=" * 50 + "\n"
        for priority in ['HIGH', 'MEDIUM', 'LOW']:
            if priority in priority_stats:
                stats = priority_stats[priority]
                rate = (stats['passed'] / stats['total']) * 100
                report += f"  {priority}: {stats['passed']}/{stats['total']} ({rate:.1f}%)\n"
        
        # Failed tests details
        failed_tests = [r for r in self.results if r.result in [TestResult.FAIL, TestResult.ERROR]]
        if failed_tests:
            report += f"\n\n🚨 FAILED TESTS DETAILS:\n"
            report += "=" * 70 + "\n"
            
            for i, result in enumerate(failed_tests[:10], 1):  # Limit to first 10 failures
                report += f"\n{i}. ❌ {result.test_case.question}\n"
                report += f"   Category: {result.test_case.category} | Priority: {result.test_case.priority}\n"
                report += f"   Expected: {result.test_case.expected_behavior}\n"
                report += f"   Error: {result.error_message}\n"
                if result.response_data.get("data"):
                    response_preview = str(result.response_data['data'])[:150]
                    report += f"   Response: {response_preview}...\n"
        
        # Recommendations
        report += f"\n\n💡 RECOMMENDATIONS:\n"
        report += "=" * 50 + "\n"
        
        if failed_tests:
            high_priority_fails = [r for r in failed_tests if r.test_case.priority == 'HIGH']
            if high_priority_fails:
                report += f"🔴 CRITICAL: Fix {len(high_priority_fails)} high-priority failures immediately\n"
        
        if errors:
            report += f"⚠️  Fix {errors} technical errors causing system crashes\n"
        
        if timeouts:
            report += f"🐌 Optimize {timeouts} queries that are timing out\n"
        
        slow_queries = [r for r in self.results if r.response_time_ms > 5000]
        if slow_queries:
            report += f"🚀 Optimize {len(slow_queries)} slow queries (>5s response time)\n"
        
        blocked_rate = (blocked / total_tests) * 100
        if blocked_rate < 5:
            report += f"🔒 Review access control - only {blocked_rate:.1f}% of queries properly blocked\n"
        
        if success_rate >= 90:
            report += f"🎉 Excellent! System performing well with {success_rate:.1f}% success rate\n"
        elif success_rate >= 75:
            report += f"✅ Good performance at {success_rate:.1f}% - minor improvements needed\n"
        elif success_rate >= 50:
            report += f"⚠️  Moderate performance at {success_rate:.1f}% - significant improvements needed\n"
        else:
            report += f"🚨 Poor performance at {success_rate:.1f}% - major fixes required\n"
        
        return report
    
    async def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Automated Chatbot Testing")
        print(f"🎯 Target: {self.base_url}")
        print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await self.setup_session()
        
        try:
            # Test admin functionality
            await self.run_test_suite(self.admin_tests, "admin", "admin", "ADMIN")
            
            # Test student functionality  
            await self.run_test_suite(self.student_tests, "6253786", "student", "STUDENT")
            
            # Test edge cases with admin account
            await self.run_test_suite(self.edge_case_tests, "admin", "admin", "EDGE CASES")
            
        finally:
            await self.cleanup_session()
        
        # Generate and save report
        report = self.generate_report()
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chatbot_test_report_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(report)
        print(f"\n📄 Full report saved to: {filename}")
        
        # Quick summary
        total_tests = len(self.results)
        if total_tests > 0:
            passed = len([r for r in self.results if r.result == TestResult.PASS])
            blocked = len([r for r in self.results if r.result == TestResult.BLOCKED])
            clarifications = len([r for r in self.results if r.result == TestResult.CLARIFICATION])
            successful = passed + blocked + clarifications
            success_rate = (successful / total_tests) * 100
            
            print(f"\n🎯 QUICK SUMMARY:")
            print(f"   Tests Run: {total_tests}")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Status: {'🎉 EXCELLENT' if success_rate >= 90 else '✅ GOOD' if success_rate >= 75 else '⚠️ NEEDS WORK' if success_rate >= 50 else '🚨 CRITICAL'}")

async def main():
    """Main function to run all tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run automated chatbot tests')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL of the chatbot API')
    parser.add_argument('--admin-only', action='store_true', help='Run only admin tests')
    parser.add_argument('--student-only', action='store_true', help='Run only student tests')
    parser.add_argument('--quick', action='store_true', help='Run only high priority tests')
    
    args = parser.parse_args()
    
    runner = ChatbotTestRunner(args.url)
    
    # Filter tests if requested
    if args.quick:
        runner.admin_tests = [t for t in runner.admin_tests if t.priority == 'HIGH']
        runner.student_tests = [t for t in runner.student_tests if t.priority == 'HIGH']
        runner.edge_case_tests = [t for t in runner.edge_case_tests if t.priority == 'HIGH']
    
    if args.admin_only:
        runner.student_tests = []
        runner.edge_case_tests = []
    elif args.student_only:
        runner.admin_tests = []
        runner.edge_case_tests = []
    
    await runner.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())