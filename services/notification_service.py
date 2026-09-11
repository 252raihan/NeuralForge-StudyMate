# Small server-side notification creation helpers for Step 14."
from database.db import create_notification

def notify_material_approved(user_id, material_id, topic):
    return create_notification(
        user_id, "material_approved", "Study material approved",
        f'Your study material "{topic}" has been approved.',
        f"/study-library/material/{int(material_id)}/pdf",
    )


def notify_material_rejected(user_id, material_id, topic):
    return create_notification(
        user_id, "material_rejected", "Study material rejected",
        f'Your study material "{topic}" was rejected.',
        "/my-study-materials",
    )


def notify_quiz_completed(user_id, quiz_id, attempt_id, title, score, total):
    return create_notification(
        user_id, "quiz_completed", "Quiz completed",
        f'Your quiz "{title}" was completed. Score: {score}/{total}.',
        f"/quiz/{int(quiz_id)}/result/{int(attempt_id)}",
    )
