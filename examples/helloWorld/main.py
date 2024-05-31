import sys

from PyQt5 import QtWidgets

from cat.GUI.pythonGUI import PythonGUIMainWindow, PythonGUI
from cat.utils.utils import runLaterSafe


class ExampleMainWindow(PythonGUIMainWindow):
	def OnGUI(self, gui: PythonGUI):
		with gui.hLayout(), gui.hCentered(), gui.vLayout():
			name = gui.textField(None, label="name:")
			if gui.button(f"Greet '{name}'"):
				gui.showInformationDialog(f"Hello {name}!", "How are you?")


def start(argv):
	app = QtWidgets.QApplication(argv)
	QtWidgets.QApplication.setStyle("Fusion")
	app.setApplicationName("Hello World")
	window = ExampleMainWindow()
	window.show()
	runLaterSafe(0, lambda: window.resize(0, 0)) # reduce window size
	app.exec_()


if __name__ == '__main__':
	start(argv=sys.argv)
