import subprocess
import sys

TESTS = [
    "test_database_step5.py",
    "test_auth_step6.py",
    "test_study_material_step7.py",
    "test_admin_step8.py",
    "test_public_library_step9.py",
    "test_ask_studymate_step10.py",
    "test_rag_step11.py",
    "test_quiz_step10.py",
    "test_quiz_generation_step12.py",
    "test_quiz_attempt_step13.py",
    "test_quiz_performance_step14.py",
    "test_bookmarks_step12.py",
    "test_notifications_step14.py",
    "test_dashboard_step13.py",
    "test_smart_search_step11.py",
    "test_course_metadata.py",
    "test_ai_service.py",
    "test_security_step15.py",
    "test_hardening_step145.py",
]

passed = 0
failed = 0
for test in TESTS:
    proc = subprocess.run([sys.executable, test], capture_output=True, text=True)
    if proc.returncode == 0:
        print("PASS :: " + test)
        passed += 1
    else:
        print("FAIL :: " + test + " (exit %d)" % proc.returncode)
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        for line in tail:
            print("    " + line)
        failed += 1

print("======================")
print("PASSED: %d  FAILED: %d" % (passed, failed))
sys.exit(1 if failed else 0)
