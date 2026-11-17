
from unittest.mock import Mock

from app.services.performance_service import (
    _close_benchmark_resources
)


def test_resource_cleanup():

    cursor = Mock()
    connection = Mock()

    # Simulate MySQL's unread-result cleanup error.
    cursor.close.side_effect = Exception("Unread result found")

    _close_benchmark_resources(cursor, connection)

    cursor.close.assert_called_once()
    connection.close.assert_called_once()

    print("PASS: Cursor cleanup attempted.")
    print("PASS: Connection closed despite cursor cleanup failure.")
    print("PASS: Cleanup error did not escape the helper.")


if __name__ == "__main__":
    test_resource_cleanup()
