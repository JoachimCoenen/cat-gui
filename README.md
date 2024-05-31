
# Cat GUI
![GitHub](https://img.shields.io/github/license/JoachimCoenen/cat-gui)
![GitHub repo size](https://img.shields.io/github/repo-size/JoachimCoenen/cat-gui?color=0072FF)
![Lines of code](https://img.shields.io/tokei/lines/github/JoachimCoenen/cat-gui?color=0072FF)
[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FJoachimCoenen%2Fcat-gui&count_bg=%230072FF&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)

An [imgui](https://github.com/ocornut/imgui) style Graphical User Interface library for python using PyQt5 as its backend.

Mainly used by [Datapack Editor][DatapackEditor_LINK].

## Examples

### Hello World
A simple Hello World implementation. Full source code is [here][HelloWorldExample_LINK]

```python
class MainWindow(PythonGUIMainWindow):
    def OnGUI(self, gui: PythonGUI):
        with gui.hLayout(), gui.hCentered(), gui.vLayout():
            name = gui.textField(None, label="name:")
            if gui.button(f"Greet '{name}'"):
                gui.showInformationDialog(f"Hello {name}!", "How are you?")
```

![HelloWorldExample_IMG]

### Calculator
A simple Calculator app with memory and a history view which can be enabled or disabled. Full source code is [here][CalculatorExample_LINK]

![CalculatorExample_IMG]

### Datapack Editor
An advanced creator & editor for Minecraft Datapacks. Full source code is here: [Datapack-Editor][DatapackEditor_LINK]

![DatapackEditorDialog_IMG]



[HelloWorldExample_IMG]:         examples/media/helloWorld.png               "Hello World Application"
[CalculatorExample_IMG]:         examples/media/calculator.png               "Calculator Application"
[DatapackEditorDialog_IMG]:      https://github.com/JoachimCoenen/Datapack-Editor/blob/develop/screenshots/mainWindow.png?raw=true  "Datapack Editor main window"

[NewIssue_LINK]:                 https://github.com/JoachimCoenen/cat-gui/issues/new  "New issue"
[HelloWorldExample_LINK]:        examples/helloWorld/main.py  "Hello World Example"
[CalculatorExample_LINK]:        examples/calculator/main.py  "Calculator Example"
[DatapackEditor_LINK]:           https://github.com/JoachimCoenen/Datapack-Editor  "Datapack-Editor"
