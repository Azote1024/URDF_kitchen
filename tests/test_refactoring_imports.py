
import sys
import os
import unittest
from PySide6.QtWidgets import QApplication

# Add the root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestRefactoringImports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a QApplication instance if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_parts_editor_import_and_init(self):
        print("Testing PartsEditor import and init...")
        try:
            from urdf_kitchen_PartsEditor import MainWindow
            window = MainWindow()
            self.assertIsNotNone(window)
            window.close()
            print("PartsEditor initialized successfully.")
        except Exception as e:
            self.fail(f"Failed to initialize PartsEditor: {e}")

    def test_stl_sourcer_import_and_init(self):
        print("Testing StlSourcer import and init...")
        try:
            from urdf_kitchen_StlSourcer import MainWindow
            window = MainWindow()
            self.assertIsNotNone(window)
            window.close()
            print("StlSourcer initialized successfully.")
        except Exception as e:
            self.fail(f"Failed to initialize StlSourcer: {e}")

if __name__ == '__main__':
    unittest.main()
