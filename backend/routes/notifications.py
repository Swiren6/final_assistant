
from flask import Blueprint, jsonify
from config.database import get_db
import json
from datetime import datetime
import traceback

notifications_bp = Blueprint('notifications_bp', __name__)

@notifications_bp.route('/check_notifications', methods=['GET'])
def check_exam_notifications():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        # --- 1. Sélection des examens à venir
        cursor.execute("""
            SELECT * FROM repartitionexamen
            WHERE date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """)
        examens = cursor.fetchall()

        for examen in examens:
            date_exam = examen['date']
            days_before = (date_exam - datetime.today().date()).days
            idClasse = examen['idClasse']
            idMatiere = examen['idMatiere']
            date_exam_iso = date_exam.strftime("%Y-%m-%d")

            if days_before not in [7, 2, 1]:
                continue

            messages_map = {
                7: f"📆 L’examen approche ! Prévu dans 7 jours (le {date_exam.strftime('%d/%m/%Y')}).",
                2: f"📌 Rappel : Examen dans 2 jours (le {date_exam.strftime('%d/%m/%Y')}) pour la classe ID {idClasse} en matière ID {idMatiere}.",
                1: f"⚠️ Attention ! Examen demain (le {date_exam.strftime('%d/%m/%Y')}) pour la classe ID {idClasse} en matière ID {idMatiere}."
            }
            message = messages_map[days_before]

            cursor.execute("""
                SELECT COUNT(*) AS count FROM notification_queue
                WHERE type = 'examen'
                AND CAST(JSON_EXTRACT(payload, '$.idClasse') AS UNSIGNED) = %s
                AND CAST(JSON_EXTRACT(payload, '$.idMatiere') AS UNSIGNED) = %s
                AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.date_exam')) = %s
            """, (idClasse, idMatiere, date_exam_iso))
            result = cursor.fetchone()

            if result["count"] == 0:
                payload = {
                    "idClasse": idClasse,
                    "idMatiere": idMatiere,
                    "date_exam": date_exam_iso
                }
                cursor.execute("""
                    INSERT INTO notification_queue (type, payload, seen, created_at, message)
                    VALUES (%s, %s, %s, NOW(), %s)
                """, ("examen", json.dumps(payload), 0, message))

        conn.commit()

        # --- 2. Récupérer toutes les notifications non vues
        cursor.execute("SELECT * FROM notification_queue WHERE seen = 0")
        notifications_non_vues = cursor.fetchall()

        messages = [{"message": notif["message"]} for notif in notifications_non_vues]

        # --- 3. Marquer comme vues
        if notifications_non_vues:
            ids = [str(notif['id']) for notif in notifications_non_vues]
            cursor.execute(
                f"UPDATE notification_queue SET seen = 1 WHERE id IN ({','.join(['%s']*len(ids))})",
                ids
            )
            conn.commit()

        return jsonify(messages)

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

    finally:
        cursor.close()
        conn.close()
