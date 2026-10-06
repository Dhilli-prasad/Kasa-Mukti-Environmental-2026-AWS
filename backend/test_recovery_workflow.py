import unittest
from decimal import Decimal

from recovery_workflow import completion_metrics, validate_transition


class RecoveryWorkflowTests(unittest.TestCase):
    def test_valid_transition(self):
        validate_transition("READY_FOR_RECOVERY", "RESERVED")

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_transition("COLLECTING", "RECOVERED")

    def test_completion_tracks_process_loss(self):
        result = completion_metrics(Decimal("100"), Decimal("82"), Decimal("8"))
        self.assertEqual(result["processLossKg"], Decimal("10"))

    def test_completion_cannot_exceed_input(self):
        with self.assertRaises(ValueError):
            completion_metrics(Decimal("10"), Decimal("9"), Decimal("2"))


if __name__ == "__main__":
    unittest.main()
