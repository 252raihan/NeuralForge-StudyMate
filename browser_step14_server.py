# Deterministic Step 14 browser fixture server; production code is unchanged."
import uuid
import app as app_module
from werkzeug.security import generate_password_hash
from database.db import get_user_by_email, get_department_by_code, create_user, create_notification
from werkzeug.security import generate_password_hash
app = app_module.app
email = "browser_step14@example.com"
user = get_user_by_email(email)
if not user:
    dept = get_department_by_code("CSE")
    user_id = create_user("Browser Step 14", email, generate_password_hash("Pass12345"), dept["id"], "student")
else:
    user_id = user["id"]
student_b_email = "browser_step14_b@example.com"
student_b = get_user_by_email(student_b_email)
if not student_b:
    dept = get_department_by_code("CSE")
    create_user("Browser Step 14 B", student_b_email, generate_password_hash("Pass12345"), dept["id"], "student")
create_notification(user_id, "material_approved", "Study material approved", "Your Database Notes material has been approved.", "/dashboard")
create_notification(user_id, "quiz_completed", "Quiz completed", "Your Database Quiz was completed. Score: 8/10.", "/dashboard")
app.config["STEP14_BROWSER_EMAIL"] = email
# Browser QA fixture: disable CSRF so the script can drive POST-only flows.
app.config["CSRF_PROTECTION"] = False
app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
