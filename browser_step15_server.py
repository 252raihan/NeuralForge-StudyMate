# Deterministic Step 15 browser server using an existing local fixture account.
from database.db import get_user_by_email, get_department_by_code, create_user, create_notification
from werkzeug.security import generate_password_hash
from app import app
email = "browser_step15@example.com"
user = get_user_by_email(email)
if not user:
    dept = get_department_by_code("CSE")
    user_id = create_user("Browser Step 15", email, generate_password_hash("Pass12345"), dept["id"], "student")
else:
    user_id = user["id"]
create_notification(user_id, "new_material", "Security QA update", "A safe notification for browser QA.", "/dashboard")
# Browser QA fixture: disable CSRF so the script can drive POST-only flows.
app.config["CSRF_PROTECTION"] = False
app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
