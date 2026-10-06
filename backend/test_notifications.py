import os
import unittest
from unittest.mock import patch

from notification_templates import render


class NotificationTests(unittest.TestCase):
    def test_templates_render_without_exposing_credentials(self):
        subject, body = render("GREENPOINTS_EARNED", {"greenPoints": 25})
        self.assertEqual(subject, "GreenPoints earned")
        self.assertIn("25", body)
        self.assertNotIn("AWS_ACCESS_KEY", body)

    def test_unknown_template_is_safe(self):
        subject, body = render("NEW_CHANNEL_EVENT", {})
        self.assertEqual(subject, "KasaMukti notification")
        self.assertIn("requires your attention", body)

    @patch("notification_events.sns")
    def test_demo_notifications_do_not_publish(self, sns):
        with patch.dict(os.environ, {"NOTIFICATIONS_ENABLED": "false"}, clear=False):
            from notification_events import publish_notification
            publish_notification("WASTE_SUBMISSION", user_id="user-1", data={"scanId": "scan-1"})
        sns.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
